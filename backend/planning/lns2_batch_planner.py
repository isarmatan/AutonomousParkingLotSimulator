# planning/lns2_batch_planner.py
import os
import sys
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from planning.lacam0_map_generator import generate_map
from planning.lacam0_scen_generator import generate_scen

# ---------------------------------------------------------------------------
# Add the MAPF-LNS2 folder to sys.path so lns2_wrapper can be imported.
# Resolves to:  <project_root>/MAPF-LNS2/
# ---------------------------------------------------------------------------
_LNS2_DIR = Path(__file__).resolve().parent.parent.parent / "MAPF-LNS2"
if str(_LNS2_DIR) not in sys.path:
    sys.path.insert(0, str(_LNS2_DIR))

from lns2_wrapper import LNS2Solver  # noqa: E402

TimedPosition = Tuple[int, int, int]  # (x, y, t)


class LNS2BatchPlanner:
    """
    Batch MAPF planner: calls LNS2 for ALL active cars simultaneously.

    One call per replan event rather than per-car — same model as
    LaCAM0BatchPlanner.  Uses LNS2Solver (lns.exe) instead of LaCaM.

    Args:
        time_limit_sec:   Per-call time budget for the LNS2 solver.
        replan_interval:  Periodic safety net: force a replan every N steps
                          even if no event fires.
    """

    def __init__(self, time_limit_sec: float = 3.0, replan_interval: int = 20):
        self.time_limit_sec = time_limit_sec
        self.replan_interval = replan_interval
        self._solver = LNS2Solver(time_limit_sec=time_limit_sec)

    def plan(
        self,
        active_cars: dict,
        grid,
        parked_cells: set,
        current_time: int,
        ghost_exit_manager=None,
    ) -> Optional[Dict[int, List[TimedPosition]]]:
        """
        Run LNS2 for all active cars at once.

        Only cars that have a valid goal are included as MAPF agents.
        Parked-car positions are encoded as '@' walls in the .map file.

        Returns:
            Dict[car_id -> List[(x, y, t)]] mapping each car to its global-time
            path on success.  The path starts at (current_position, current_time)
            and ends at (goal, current_time + makespan).
            Returns None if LNS2 fails or times out.
        """
        plannable = {
            cid: car for cid, car in active_cars.items() if car.has_goal()
        }
        if not plannable:
            return {}

        tmp_dir = tempfile.mkdtemp(prefix="lns2_sim_")
        try:
            map_path = os.path.join(tmp_dir, "parking_lot.map")
            scen_path = os.path.join(tmp_dir, "agents.scen")

            # --- 1. Write .map ---
            map_content = generate_map(grid, parked_cells, ghost_exit_manager)
            with open(map_path, "w", newline="\n") as f:
                f.write(map_content)

            # --- 2. Pre-validate: cross-check each agent against the actual map ---
            map_lines = map_content.split("\n")
            grid_rows = map_lines[4:]   # skip: type octile / height / width / map

            def _cell_char(x, y):
                if y < 0 or y >= len(grid_rows):
                    return "OOB"
                row_str = grid_rows[y]
                if x < 0 or x >= len(row_str):
                    return "OOB"
                return row_str[x]

            valid_plannable = {}
            for cid, car in sorted(plannable.items()):
                sx, sy = car.current_position
                gx, gy = car.goal
                if ghost_exit_manager is not None:
                    psx, psy = ghost_exit_manager.world_to_planner(sx, sy)
                    pgx, pgy = ghost_exit_manager.world_to_planner(gx, gy)
                else:
                    psx, psy = sx, sy
                    pgx, pgy = gx, gy
                sc = _cell_char(psx, psy)
                gc = _cell_char(pgx, pgy)
                ok = (sc == ".") and (gc == ".")
                if ok:
                    valid_plannable[cid] = car

            if not valid_plannable:
                tmp_dir = None
                return None

            # --- 3. Write .scen for valid agents only ---
            if ghost_exit_manager is not None:
                scen_w = ghost_exit_manager.expanded_W
                scen_h = ghost_exit_manager.expanded_H
                w2p = ghost_exit_manager.world_to_planner
            else:
                scen_w = grid.width
                scen_h = grid.height
                w2p = None
            scen_content, idx_to_car_id = generate_scen(
                valid_plannable, map_path, scen_w, scen_h, world_to_planner=w2p
            )
            with open(scen_path, "w", newline="\n") as f:
                f.write(scen_content)

            # --- 4. Solve ---
            result = self._solver.solve(
                map_file=map_path,
                scen_file=scen_path,
                num_agents=len(valid_plannable),
                verbose=0,
            )

            if not result.solved:
                return None

            # --- 5. Convert solution to per-car timed paths (world coords) ---
            paths: Dict[int, List[TimedPosition]] = {}
            for agent_idx, car_id in idx_to_car_id.items():
                car_path: List[TimedPosition] = []
                for t_rel, config in enumerate(result.solution):
                    if agent_idx < len(config):
                        px, py = config[agent_idx]
                        if ghost_exit_manager is not None:
                            x, y = ghost_exit_manager.planner_to_world(px, py)
                        else:
                            x, y = px, py
                        car_path.append((x, y, current_time + t_rel))
                paths[car_id] = car_path

            return paths

        except Exception as e:
            print(f"[LNS2BatchPlanner] Exception at t={current_time}: {e}")
            tmp_dir = None
            return None

        finally:
            if tmp_dir is not None:
                shutil.rmtree(tmp_dir, ignore_errors=True)
