from generator.cell import Cell, CellType

class Grid:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.cells = [
            [Cell(x, y, CellType.WALL) for y in range(height)]
            for x in range(width)
        ]

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def get_cell(self, x: int, y: int) -> Cell:
        return self.cells[x][y]

    def set_cell(self, x: int, y: int, cell_type: CellType):
        self.cells[x][y].type = cell_type

    def is_boundary_non_corner(self, x: int, y: int) -> bool:
        """
        Returns True if (x, y) is on the boundary of the grid
        but not on a corner cell.
        """
        if not self.in_bounds(x, y):
            return False

        on_boundary = (
            x == 0 or
            x == self.width - 1 or
            y == 0 or
            y == self.height - 1
        )

        if not on_boundary:
            return False

        is_corner = (
            (x == 0 and y == 0) or
            (x == 0 and y == self.height - 1) or
            (x == self.width - 1 and y == 0) or
            (x == self.width - 1 and y == self.height - 1)
        )

        return not is_corner
