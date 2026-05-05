# planning/lacam0_map_generator.py
from generator.cell import CellType


def generate_map(grid, parked_cells: set) -> str:
    """
    Generate a MovingAI .map file string from the parking lot grid.

    parked_cells: set of (x, y) positions currently occupied by parked/idle cars.
                  These are encoded as '@' (static obstacles) so LaCAM0 routes
                  active agents around them.

    Map coordinate system: row y, column x  (y is outer loop, x is inner loop).
    LaCAM0 reads (x=column, y=row) which matches this encoding.
    """
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
