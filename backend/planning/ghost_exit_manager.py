# planning/ghost_exit_manager.py
from collections import deque
from typing import Dict, List, Optional, Set, Tuple

Position = Tuple[int, int]


class GhostExitManager:
    """
    Manages ghost exit areas for the LaCAM0 MAPF planner.

    LaCAM0 requires every agent to have a UNIQUE goal.  For exiting cars this
    is a problem because the parking lot may have only a few physical exit cells
    that multiple cars would share.

    Solution: attach a virtual "ghost box" of empty cells outside every edge
    that has at least one EXIT cell.  Each exiting car is assigned a unique
    ghost cell as its LaCAM0 planner goal.  The car is removed from the
    simulation the instant it steps on a real exit cell — it never actually
    moves into the ghost area.

    Coordinate systems
    ------------------
    World coords  : original parking lot grid (0-indexed).  Ghost cells have
                    negative or out-of-bounds coordinates.
    Planner coords: non-negative integers used inside .map / .scen files.

        planner_x = world_x + offset_x
        planner_y = world_y + offset_y

    Ghost box sizes (world coords, for a W×H original grid):
        Left  edge → x ∈ [-W, -1],   y ∈ [0, H-1]
        Right edge → x ∈ [W,  2W-1], y ∈ [0, H-1]
        Top   edge → x ∈ [0, W-1],   y ∈ [-H, -1]
        Bottom edge→ x ∈ [0, W-1],   y ∈ [H,  2H-1]
    """

    def __init__(
        self,
        grid_width: int,
        grid_height: int,
        exit_cells: List[Position],
    ):
        self.W = grid_width
        self.H = grid_height

        # Classify each exit cell to exactly one edge (elif order: left > right > top > bottom)
        self._edge_exit_cells: Dict[str, List[Position]] = {
            "left": [], "right": [], "top": [], "bottom": [],
        }
        for ex, ey in exit_cells:
            if ex == 0:
                self._edge_exit_cells["left"].append((ex, ey))
            elif ex == grid_width - 1:
                self._edge_exit_cells["right"].append((ex, ey))
            elif ey == 0:
                self._edge_exit_cells["top"].append((ex, ey))
            elif ey == grid_height - 1:
                self._edge_exit_cells["bottom"].append((ex, ey))

        self._active_edges: Set[str] = {
            e for e, cells in self._edge_exit_cells.items() if cells
        }

        # Planner coordinate offsets
        self.offset_x = self.W if "left" in self._active_edges else 0
        self.offset_y = self.H if "top" in self._active_edges else 0

        # Expanded map dimensions (in planner coords)
        self.expanded_W = (
            self.W
            + self.offset_x
            + (self.W if "right" in self._active_edges else 0)
        )
        self.expanded_H = (
            self.H
            + self.offset_y
            + (self.H if "bottom" in self._active_edges else 0)
        )

        # Ghost cell pools: one deque per active edge, sorted closest-first
        self._pools: Dict[str, deque] = {}
        self._build_pools()

        # Active assignments: car_id → (edge, ghost_cell_world, exit_cell_world)
        self._assigned: Dict[int, Tuple[str, Position, Position]] = {}

    # ------------------------------------------------------------------
    # Pool construction
    # ------------------------------------------------------------------

    def _build_pools(self):
        W, H = self.W, self.H
        edge_ghost_cells: Dict[str, List[Position]] = {
            "left":   [(x, y) for x in range(-W, 0)  for y in range(H)],
            "right":  [(x, y) for x in range(W, 2*W) for y in range(H)],
            "top":    [(x, y) for x in range(W)       for y in range(-H, 0)],
            "bottom": [(x, y) for x in range(W)       for y in range(H, 2*H)],
        }

        for edge in self._active_edges:
            exits_on_edge = self._edge_exit_cells[edge]

            def _min_dist(pos, exits=exits_on_edge):
                gx, gy = pos
                return min(abs(gx - ex) + abs(gy - ey) for (ex, ey) in exits)

            ghosts_sorted = sorted(edge_ghost_cells[edge], key=_min_dist)
            self._pools[edge] = deque(ghosts_sorted)

    # ------------------------------------------------------------------
    # Coordinate translation
    # ------------------------------------------------------------------

    def world_to_planner(self, wx: int, wy: int) -> Position:
        return (wx + self.offset_x, wy + self.offset_y)

    def planner_to_world(self, px: int, py: int) -> Position:
        return (px - self.offset_x, py - self.offset_y)

    # ------------------------------------------------------------------
    # Map helpers
    # ------------------------------------------------------------------

    def is_ghost_area(self, planner_x: int, planner_y: int) -> bool:
        """Return True if a planner-coord cell is inside an active ghost box."""
        wx, wy = self.planner_to_world(planner_x, planner_y)
        # Must be outside original grid
        if 0 <= wx < self.W and 0 <= wy < self.H:
            return False
        if "left" in self._active_edges and -self.W <= wx < 0 and 0 <= wy < self.H:
            return True
        if "right" in self._active_edges and self.W <= wx < 2 * self.W and 0 <= wy < self.H:
            return True
        if "top" in self._active_edges and 0 <= wx < self.W and -self.H <= wy < 0:
            return True
        if "bottom" in self._active_edges and 0 <= wx < self.W and self.H <= wy < 2 * self.H:
            return True
        return False

    # ------------------------------------------------------------------
    # Ghost goal management
    # ------------------------------------------------------------------

    def assign_ghost_goal(self, car) -> Optional[Position]:
        """
        Assign a unique ghost cell (world coords) to an exiting car.

        Selects the edge whose nearest exit minimises distance to the car,
        breaking ties by fewest currently assigned ghost goals on that edge
        (load balancing).

        Returns None if no ghost goals are available (car should wait).
        """
        cx, cy = car.current_position

        candidates = []
        for edge, pool in self._pools.items():
            if not pool:
                continue
            exits_on_edge = self._edge_exit_cells[edge]
            nearest_exit = min(
                exits_on_edge,
                key=lambda p: abs(p[0] - cx) + abs(p[1] - cy),
            )
            dist = abs(nearest_exit[0] - cx) + abs(nearest_exit[1] - cy)
            load = sum(1 for v in self._assigned.values() if v[0] == edge)
            # Load dominates; distance breaks ties
            candidates.append((load * 10_000 + dist, edge, nearest_exit))

        if not candidates:
            return None

        candidates.sort()
        _, best_edge, best_exit_cell = candidates[0]
        ghost_cell = self._pools[best_edge].popleft()
        self._assigned[car.car_id] = (best_edge, ghost_cell, best_exit_cell)
        return ghost_cell

    def release_ghost_goal(self, car_id: int) -> None:
        """Return a car's ghost cell to the pool so it can be reused."""
        entry = self._assigned.pop(car_id, None)
        if entry is None:
            return
        edge, ghost_cell, _ = entry
        if edge in self._pools:
            self._pools[edge].appendleft(ghost_cell)

    def get_exit_cell_for_car(self, car_id: int) -> Optional[Position]:
        """Return the original exit cell that was chosen for this car."""
        entry = self._assigned.get(car_id)
        return entry[2] if entry else None

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def pool_sizes(self) -> Dict[str, int]:
        return {e: len(p) for e, p in self._pools.items()}

    def __repr__(self) -> str:
        return (
            f"GhostExitManager(W={self.W}, H={self.H}, "
            f"active_edges={self._active_edges}, "
            f"expanded={self.expanded_W}x{self.expanded_H}, "
            f"offset=({self.offset_x},{self.offset_y}), "
            f"assigned={len(self._assigned)})"
        )
