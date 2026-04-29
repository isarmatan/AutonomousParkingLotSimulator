from generator.grid import Grid
from generator.cell import CellType


class GridFactory:
    @staticmethod
    def create_with_outliers(width: int, height: int) -> Grid:
        """
        Creates a grid where:
        - boundary (outliers) are WALL
        - interior cells are ROAD
        """
        if width < 3 or height < 3:
            raise ValueError("Grid must be at least 3x3 to have valid outliers")

        grid = Grid(width, height)

        for x in range(width):
            for y in range(height):
                # Boundary cells
                if (
                    x == 0 or
                    x == width - 1 or
                    y == 0 or
                    y == height - 1
                ):
                    grid.set_cell(x, y, CellType.WALL)
                else:
                    grid.set_cell(x, y, CellType.ROAD)

        return grid
