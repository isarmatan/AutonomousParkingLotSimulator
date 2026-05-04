import os
import subprocess
import threading
from collections import deque
from typing import Optional

from planning.base_planner import BasePlanner
from planning.reservation_table import ReservationTable
from planning.lacam0_file_generator import LaCAM0FileGenerator
from planning.lacam0_result_parser import LaCAM0ResultParser

_lacam0_lock = threading.Lock()


class LaCAM0PlannerAdapter(BasePlanner):
    """
    Integrates the LaCAM0 MAPF solver as a BasePlanner.

    LaCAM0 is a batch MAPF planner: it solves for all active agents
    simultaneously and is very fast even for large numbers of agents.

    Configuration (via environment variables):
      LACAM0_DIR   path to the LaCAM0 repo root (where build/main.exe lives)
                   Default: must be set — a clear error is raised if missing.
      LACAM0_TIMEOUT_SEC  subprocess timeout in seconds (default: 10)

    Windows-native: LaCAM0 is compiled with MinGW on Windows.
    No WSL involved. Result is written to LACAM0_DIR/build/result.txt.
    Input files are written to LACAM0_DIR/tmp/ (ASCII-safe path) so that
    the MinGW executable can open them without Unicode path issues.
    A threading.Lock() serialises calls since result.txt is at a fixed path.
    """

    def __init__(
        self,
        grid,
        reservation_table: ReservationTable,
        planning_horizon: int,
    ):
        self.grid = grid
        self._reservation_table = reservation_table
        self.planning_horizon = planning_horizon

        lacam0_dir = os.environ.get("LACAM0_DIR", "")
        if not lacam0_dir:
            raise EnvironmentError(
                "LACAM0_DIR environment variable is not set. "
                "Set it to the root of your LaCAM0 repository "
                r"(e.g. set LACAM0_DIR=C:\Users\user\lacam)."
            )
        self._lacam0_dir = lacam0_dir
        self._exe = os.path.join(lacam0_dir, "build", "main.exe")
        self._result_path = os.path.join(lacam0_dir, "build", "result.txt")
        self._timeout = int(os.environ.get("LACAM0_TIMEOUT_SEC", "10"))

        # Write input files directly to LACAM0_DIR (= cwd when the exe runs).
        # LaCAM0 opens the map by the filename declared in the scen file,
        # resolved relative to cwd — so the map must live in the same dir.
        # This also avoids any Unicode path issues from the system %TEMP%.
        self._map_path  = os.path.join(lacam0_dir, "parking.map")
        self._scen_path = os.path.join(lacam0_dir, "parking.scen")

        # MinGW runtime DLLs must be on PATH for main.exe to run.
        # Default: C:\msys64\mingw64\bin — override with MINGW_BIN env var.
        self._mingw_bin = os.environ.get("MINGW_BIN", r"C:\msys64\mingw64\bin")

        self._generator = LaCAM0FileGenerator()
        self._parser = LaCAM0ResultParser()

    # ------------------------------------------------------------------
    # BasePlanner interface
    # ------------------------------------------------------------------

    @property
    def uses_batch_planning(self) -> bool:
        return True

    @property
    def reservation_table(self) -> ReservationTable:
        return self._reservation_table

    def plan_for_car(self, car, current_time: int, obstacles=None,
                     obstacle_persistence: int = 20) -> bool:
        """
        Individual planning is a no-op for LaCAM0.
        All planning is handled by replan_all() called from step().
        Return True so SimulationCore does not increment plan_fail_count.
        """
        return True

    def cancel_plan(self, car) -> None:
        """
        Clear the car's path. LaCAM0 never registers paths in the
        reservation table, so no table updates are needed here.
        """
        car.clear_path()

    # ------------------------------------------------------------------
    # Batch planning
    # ------------------------------------------------------------------

    def replan_all(
        self,
        active_cars: list,
        current_time: int,
        parked_positions: set,
    ) -> bool:
        """
        Run LaCAM0 for all active cars with goals.

        Steps:
          1. Filter active_cars to those with a goal (plannable).
          2. Write .map and .scen files to LACAM0_DIR/tmp/ (ASCII-safe).
          3. Run LaCAM0 subprocess with a timeout.
          4. Parse result.txt.
          5. Convert per-agent (x,y) sequences to car paths (x, y, t).
          6. Truncate paths to planning_horizon and attach to cars.

        Returns True if at least one car received a path, False otherwise.
        """
        # Collect all active cars that have a goal.
        # Sort closest-to-goal first so that when two cars share a goal cell
        # the closer one keeps the real goal and the farther one gets a BFS
        # alternative.  This creates a natural queue toward shared destinations
        # (e.g. the single exit cell) without excluding any car from the batch.
        def _dist(c):
            gx, gy = c.goal
            cx, cy = c.current_position
            return abs(cx - gx) + abs(cy - gy)

        candidates = sorted(
            [c for c in active_cars if c.goal is not None],
            key=_dist,
        )

        if not candidates:
            return False

        # Assign a unique effective goal to every candidate.
        # LaCAM0 requires distinct goal cells — two agents at the same goal
        # is an infeasible MAPF instance that causes LaCAM0 to hang / error.
        # Parked-car positions are also forbidden (they are '@' in the map).
        effective_goals: dict = {}          # car_id -> (gx, gy)
        taken_goals: set = set(parked_positions)

        for car in candidates:
            if car.goal not in taken_goals:
                taken_goals.add(car.goal)
                effective_goals[car.car_id] = car.goal
            else:
                alt = self._find_nearby_goal(car.goal, taken_goals)
                if alt is not None:
                    taken_goals.add(alt)
                    effective_goals[car.car_id] = alt
                # If no alt found the car is simply skipped this step.

        plannable = sorted(
            [c for c in candidates if c.car_id in effective_goals],
            key=lambda c: c.car_id,
        )

        if not plannable:
            return False

        print(
            f"[LaCAM0] t={current_time}: planning for {len(plannable)} agents, "
            f"{len(parked_positions)} parked obstacles"
        )

        with _lacam0_lock:
            self._generator.generate_map(self.grid, parked_positions, self._map_path)
            self._generator.generate_scen(
                plannable, "parking.map",
                self.grid.width, self.grid.height, self._scen_path,
                goal_overrides=effective_goals,
            )

            success = self._run_lacam0(self._map_path, self._scen_path, len(plannable))
            if not success:
                print(f"[LaCAM0] t={current_time}: subprocess failed — cars will wait")
                return False

            agent_paths = self._parser.parse(self._result_path)

        if agent_paths is None:
            print(f"[LaCAM0] t={current_time}: result.txt parse failed or solved=0")
            return False

        print(f"[LaCAM0] t={current_time}: solved — assigning paths to {len(agent_paths)} agents")

        any_planned = False
        for i, car in enumerate(plannable):
            raw = agent_paths.get(i)
            if raw is None:
                continue
            car_path = [
                (x, y, current_time + t_offset)
                for t_offset, (x, y) in enumerate(raw)
            ]
            car.set_path(car_path[: self.planning_horizon])
            any_planned = True

        return any_planned

    def _find_nearby_goal(self, center: tuple, forbidden: set):
        """
        BFS from *center* to find the nearest passable cell that is not in
        *forbidden*.  Returns (x, y) or None if the reachable area is exhausted.

        Used to assign unique effective goals to cars that share the same
        real goal cell (e.g. multiple EXIT cars heading to a single exit).
        """
        from generator.cell import CellType

        visited = {center}
        q = deque([(center, 0)])
        while q:
            (x, y), dist = q.popleft()
            if dist > 0 and (x, y) not in forbidden:
                if self.grid.get_cell(x, y).type != CellType.WALL:
                    return (x, y)
            for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.grid.width and 0 <= ny < self.grid.height:
                    npos = (nx, ny)
                    if npos not in visited:
                        visited.add(npos)
                        q.append((npos, dist + 1))
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_lacam0(
        self, map_path: str, scen_path: str, n_agents: int
    ) -> bool:
        """
        Invoke the LaCAM0 executable and return True on success.
        """
        if not os.path.isfile(self._exe):
            print(
                f"[LaCAM0] Executable not found: {self._exe}. "
                "Check LACAM0_DIR."
            )
            return False

        cmd = [
            self._exe,
            "-i", scen_path,
            "-m", map_path,
            "-N", str(n_agents),
            "-v", "0",
        ]

        # Prepend MinGW bin so runtime DLLs (libgcc, libstdc++, etc.) resolve.
        env = os.environ.copy()
        env["PATH"] = self._mingw_bin + os.pathsep + env.get("PATH", "")

        try:
            result = subprocess.run(
                cmd,
                cwd=self._lacam0_dir,
                capture_output=True,
                timeout=self._timeout,
                env=env,
            )
        except subprocess.TimeoutExpired:
            print(
                f"[LaCAM0] Subprocess timed out after {self._timeout}s "
                f"({n_agents} agents)."
            )
            return False
        except Exception as exc:
            print(f"[LaCAM0] Subprocess error: {exc}")
            return False

        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace").strip()
            print(f"[LaCAM0] Non-zero exit ({result.returncode}): {stderr}")
            return False

        return True
