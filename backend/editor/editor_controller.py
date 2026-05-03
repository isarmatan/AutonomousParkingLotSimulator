from typing import Optional
from .editor_errors import (
    OutOfBoundsError,
    InvalidPlacementError,
    
)
from generator.cell import CellType
from generator.grid import Grid


class EditorController:
    """
    Applies editor actions to a Grid.
    Owns local editor invariants.
    """

    def __init__(self, grid: Grid):
        self.grid = grid

    # ------------------------
    # Internal helpers
    # ------------------------

    def _validate_bounds(self, x: int, y: int):
        if not self.grid.in_bounds(x, y):
            raise OutOfBoundsError(f"Cell ({x},{y}) is outside grid")

    # we dont need it
    def _find_cell_of_type(self, cell_type: CellType) -> Optional[tuple]:
        for y in range(self.grid.height):
            for x in range(self.grid.width):
                if self.grid.get_cell(x, y).cell_type == cell_type:
                    return (x, y)
        return None

    # ------------------------
    # Basic editing operations
    # ------------------------

    def paint_cell(self, x: int, y: int, cell_type: CellType): #is it just wall? //if not -> more constraints
        self._validate_bounds(x, y)

        cell = self.grid.get_cell(x, y)

        # Prevent illegal overwrites
        if cell.cell_type == CellType.WALL and cell_type == CellType.PARKING:
            raise InvalidPlacementError("Cannot place PARKING on WALL")

        cell.cell_type = cell_type
        cell.metadata = {}

    def clear_cell(self, x: int, y: int): #what if cleared outlier wall? if grid.is_outlier(grid.get_cell(x,y)) == true && cellType = entry/entrance -> place wall else throw error.
        self._validate_bounds(x, y)

        cell = self.grid.get_cell(x, y)
        cell.cell_type = CellType.ROAD
        cell.metadata = {}

    # ------------------------
    # Special placements
    # ------------------------

    def place_entry(self, x: int, y: int):
        self._validate_bounds(x, y)

        if not self.grid.is_boundary_non_corner(x, y):
            raise InvalidPlacementError(
                "ENTRY must be placed on a boundary cell (not a corner)"
            )

        cell = self.grid.get_cell(x, y)

        # If there is a wall, remove it
        if cell.cell_type == CellType.WALL:
            cell.cell_type = CellType.ROAD

        cell.cell_type = CellType.ENTRY
        cell.metadata = {}


    def place_exit(self, x: int, y: int):
        self._validate_bounds(x, y)

        if not self.grid.is_boundary_non_corner(x, y):
            raise InvalidPlacementError(
                "EXIT must be placed on a boundary cell (not a corner)"
            )

        cell = self.grid.get_cell(x, y)

        # If there is a wall, remove it
        if cell.cell_type == CellType.WALL:
            cell.cell_type = CellType.ROAD

        cell.cell_type = CellType.EXIT
        cell.metadata = {}


    def place_parking(self, x: int, y: int, parking_id: Optional[str] = None):
        self._validate_bounds(x, y)

        cell = self.grid.get_cell(x, y)

        if cell.cell_type == CellType.WALL:
            raise InvalidPlacementError("Cannot place PARKING on WALL")

        if cell.cell_type == CellType.PARKING:
            raise InvalidPlacementError("Cell is already a PARKING spot")

        if parking_id is None:
            parking_id = self._generate_parking_id()

        cell.cell_type = CellType.PARKING
        cell.metadata = {"parking_id": parking_id}

    # ------------------------
    # Utilities
    # ------------------------

    def _generate_parking_id(self) -> str:
        max_id = 0
        for y in range(self.grid.height):
            for x in range(self.grid.width):
                cell = self.grid.get_cell(x, y)
                if cell.cell_type == CellType.PARKING:
                    pid = cell.metadata.get("parking_id", "")
                    if pid.startswith("P"):
                        try:
                            num = int(pid[1:])
                            max_id = max(max_id, num)
                        except ValueError:
                            pass
        return f"P{max_id + 1}"


    def get_grid(self) -> Grid:
        """
        Returns the current grid.
        Callers must not mutate it directly.
        """
        return self.grid