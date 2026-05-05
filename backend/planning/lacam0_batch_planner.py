# planning/lacam0_batch_planner.py
import os
import sys
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from planning.lacam0_map_generator import generate_map
from planning.lacam0_scen_generator import generate_scen

# ---------------------------------------------------------------------------
# Add the lacam0 folder to sys.path so lacam_wrapper can be imported.
# Resolves to:  <project_root>/lacam0/
# ---------------------------------------------------------------------------
_LACAM0_DIR = Path(__file__).resolve().parent.parent.parent / "lacam0"
if str(_LACAM0_DIR) not in sys.path:
    sys.path.insert(0, str(_LACAM0_DIR))

from lacam_wrapper import LaCaM  # noqa: E402

TimedPosition = Tuple[int, int, int]  # (x, y, t)


class LaCAM0BatchPlanner:
    """
    Batch MAPF planner: calls LaCAM0 for ALL active cars simultaneously.

    One call per replan event rather than per-car — this is the fundamental
    difference from the priority-planner approach.

    Args:
        time_limit_sec:   Per-call time budget for the LaCAM0 solver.
        replan_interval:  Periodic safety net: force a replan every N steps
                          even if no event fires.
    """

    def __init__(self, time_limit_sec: float = 3.0, replan_interval: int = 20):
        self.time_limit_sec = time_limit_sec
        self.replan_interval = replan_interval
        self._solver = LaCaM(time_limit_sec=time_limit_sec)

    def plan(
        self,
        active_cars: dict,
        grid,
        parked_cells: set,
        current_time: int,
    ) -> Optional[Dict[int, List[TimedPosition]]]:
        """
        Run LaCAM0 for all active cars at once.

        Only cars that have a valid goal are included as MAPF agents.
        Parked-car positions are encoded as '@' walls in the .map file.

        Returns:
            Dict[car_id -> List[(x, y, t)]] mapping each car to its global-time
            path on success.  The path starts at (current_position, current_time)
            and ends at (goal, current_time + makespan).
            Returns None if LaCAM0 fails or times out.
        """
        plannable = {
            cid: car for cid, car in active_cars.items() if car.has_goal()
        }
        if not plannable:
            return {}

        tmp_dir = tempfile.mkdtemp(prefix="lacam0_sim_")
        try:
            map_path = os.path.join(tmp_dir, "parking_lot.map")
            scen_path = os.path.join(tmp_dir, "agents.scen")
            out_path = os.path.join(tmp_dir, "result.txt")

            # --- 1. Write .map ---
            map_content = generate_map(grid, parked_cells)
            with open(map_path, "w", newline="\n") as f:
                f.write(map_content)

            # --- 2. Pre-validate: cross-check each agent against the actual map ---
            # grid_rows[y] is the y-th row of the MovingAI map (0 = top).
            # A cell is passable iff its character is '.'.
            map_lines = map_content.split("\n")
            grid_rows = map_lines[4:]   # skip: type octile / height / width / map

            def _cell_char(x, y):
                """Return the map character at (col=x, row=y), or '?' if OOB."""
                if y < 0 or y >= len(grid_rows):
                    return "OOB"
                row_str = grid_rows[y]
                if x < 0 or x >= len(row_str):
                    return "OOB"
                return row_str[x]

            print(
                f"\n[LaCAM0] ===== t={current_time} replan "
                f"| map {grid.width}x{grid.height} "
                f"| parked_cells={len(parked_cells)} "
                f"| candidates={len(plannable)} ====="
            )

            valid_plannable = {}
            for cid, car in sorted(plannable.items()):
                sx, sy = car.current_position
                gx, gy = car.goal
                sc = _cell_char(sx, sy)
                gc = _cell_char(gx, gy)
                s_parked = (sx, sy) in parked_cells
                g_parked = (gx, gy) in parked_cells
                s_type = grid.get_cell(sx, sy).type.name if grid.in_bounds(sx, sy) else "OOB"
                g_type = grid.get_cell(gx, gy).type.name if grid.in_bounds(gx, gy) else "OOB"
                ok = (sc == ".") and (gc == ".")
                tag = "OK     " if ok else "BLOCKED"
                print(
                    f"  [{tag}] car={cid} intent={car.intent:4s} "
                    f"start=({sx:2d},{sy:2d}) map='{sc}' type={s_type:7s} parked={s_parked}  "
                    f"goal=({gx:2d},{gy:2d}) map='{gc}' type={g_type:7s} parked={g_parked}"
                )
                if not ok:
                    # Extra detail: who is blocking?
                    if s_type == "WALL" and sc == "@":
                        print(f"           ^ START is a structural WALL cell!")
                    if g_type == "WALL" and gc == "@":
                        print(f"           ^ GOAL  is a structural WALL cell!")
                    if s_parked:
                        blocker = next((c for c in parked_cells if c == (sx,sy)), None)
                        print(f"           ^ START is occupied by a parked car at {blocker}")
                    if g_parked:
                        print(f"           ^ GOAL  is occupied by a parked car")
                    print(f"           ^ SKIP — agent excluded from this solve")
                else:
                    valid_plannable[cid] = car

            if not valid_plannable:
                print(
                    f"[LaCAM0] t={current_time}: all agents are blocked — "
                    f"skipping solve, keeping temp dir: {tmp_dir}"
                )
                tmp_dir = None
                return None

            if len(valid_plannable) < len(plannable):
                print(
                    f"[LaCAM0] WARNING: {len(plannable) - len(valid_plannable)} agent(s) "
                    f"had blocked start/goal and were excluded from this solve."
                )

            # --- 3. Write .scen for valid agents only ---
            scen_content, idx_to_car_id = generate_scen(
                valid_plannable, map_path, grid.width, grid.height
            )
            with open(scen_path, "w", newline="\n") as f:
                f.write(scen_content)

            print(f"[LaCAM0] Solving for {len(valid_plannable)} valid agent(s)...")

            # --- 4. Solve ---
            result = self._solver.solve(
                map_file=map_path,
                scen_file=scen_path,
                num_agents=len(valid_plannable),
                output_file=out_path,
                verbose=1,
            )

            if not result.solved:
                print(
                    f"[LaCAM0] Not solved at t={current_time} "
                    f"({len(plannable)} agents, {result.comp_time_ms:.0f}ms)"
                )
                return None

            # --- 4. Convert solution to per-car timed paths ---
            paths: Dict[int, List[TimedPosition]] = {}
            for agent_idx, car_id in idx_to_car_id.items():
                car_path: List[TimedPosition] = []
                for t_rel, config in enumerate(result.solution):
                    if agent_idx < len(config):
                        x, y = config[agent_idx]
                        car_path.append((x, y, current_time + t_rel))
                paths[car_id] = car_path

            return paths

        except Exception as e:
            print(f"[LaCAM0BatchPlanner] Exception at t={current_time}: {e}")
            print(f"[LaCAM0BatchPlanner] Temp files kept for inspection: {tmp_dir}")
            tmp_dir = None   # skip cleanup so files stay on disk
            return None

        finally:
            if tmp_dir is not None:
                shutil.rmtree(tmp_dir, ignore_errors=True)
