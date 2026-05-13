# planning/lacam0_map_generator.py
from typing import Optional

from generator.cell import CellType


def generate_map(grid, parked_cells: set, ghost_exit_manager=None) -> str:
    """
    Generate a MovingAI .map file string from the parking lot grid.

    parked_cells: set of (x, y) positions currently occupied by parked/idle cars.
                  These are encoded as '@' (static obstacles) so LaCAM0 routes
                  active agents around them.

    ghost_exit_manager: optional GhostExitManager.  When provided the map is
                        expanded to include ghost boxes outside every edge that
                        has EXIT cells, giving exiting cars space for unique
                        planner goals.  All ghost-box cells are marked '.'
                        (passable).  Corner padding between ghost boxes is '@'.

    Map coordinate system: row y, column x  (y is outer loop, x is inner loop).
    LaCAM0 reads (x=column, y=row) which matches this encoding.
    """
    if ghost_exit_manager is None:
        # --- Original behaviour: original grid only ---
        lines = [
            "type octile",
            f"height {grid.height}",
            f"width {grid.width}",
            "map",
        ]
        for y in range(grid.height):
            row = ""
            for x in range(grid.width):
                cell = grid.get_cell(x, y)
                if cell.type == CellType.WALL:
                    row += "@"
                elif (x, y) in parked_cells:
                    row += "@"
                else:
                    row += "."
            lines.append(row)
        return "\n".join(lines)

    # --- Expanded map with ghost boxes ---
    ex_W = ghost_exit_manager.expanded_W
    ex_H = ghost_exit_manager.expanded_H
    W = grid.width
    H = grid.height

    lines = [
        "type octile",
        f"height {ex_H}",
        f"width {ex_W}",
        "map",
    ]
    for py in range(ex_H):
        row = ""
        for px in range(ex_W):
            wx, wy = ghost_exit_manager.planner_to_world(px, py)
            if 0 <= wx < W and 0 <= wy < H:
                # Original grid cell
                cell = grid.get_cell(wx, wy)
                if cell.type == CellType.WALL:
                    row += "@"
                elif (wx, wy) in parked_cells:
                    row += "@"
                else:
                    row += "."
            elif ghost_exit_manager.is_ghost_area(px, py):
                # Inside an active ghost box — always passable
                row += "."
            else:
                # Corner padding between ghost boxes — unreachable wall
                row += "@"
        lines.append(row)
    return "\n".join(lines)
