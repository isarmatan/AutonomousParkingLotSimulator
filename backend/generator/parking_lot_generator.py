import random
from generator.grid import Grid
from generator.cell import CellType
from generator.rules import GeneratorRules


class GenerationError(Exception):
    pass


class ParkingLotGenerator:
    def __init__(self, width: int, height: int, rules: GeneratorRules):
        if width < 5 or height < 5:
            raise GenerationError("Parking lot must be at least 5x5")

        self.width = width
        self.height = height
        self.rules = rules

    def generate(self) -> Grid:
        grid = Grid(self.width, self.height)

        self._generate_structure(grid)
        self._place_entries_and_exits(grid)
        self._place_parking_spots(grid)

        return grid

    # -------------------------------------------------
    # Structure generation
    # -------------------------------------------------
    def _generate_structure(self, grid: Grid):
        for y in range(self.height):

            # Top / bottom borders
            if y == 0 or y == self.height - 1:
                for x in range(self.width):
                    grid.set_cell(x, y, CellType.WALL)
                continue

            # Interior rows
            if y % 2 == 1:
                self._generate_road_row(grid, y)
            else:
                self._generate_parking_row_skeleton(grid, y)

    def _generate_road_row(self, grid: Grid, y: int):
        for x in range(self.width):
            if x == 0 or x == self.width - 1:
                grid.set_cell(x, y, CellType.WALL)
            else:
                grid.set_cell(x, y, CellType.ROAD)

    def _generate_parking_row_skeleton(self, grid: Grid, y: int):
        for x in range(self.width):
            if x == 0 or x == self.width - 1:
                grid.set_cell(x, y, CellType.WALL)
            elif x == 1 or x == self.width - 2:
                grid.set_cell(x, y, CellType.ROAD)
            else:
                grid.set_cell(x, y, CellType.WALL)  # placeholder

    # -------------------------------------------------
    # Entries and exits
    # -------------------------------------------------
    def _place_entries_and_exits(self, grid: Grid):
        candidates = []

        # Top border (y=0) - check neighbor at (x, 1)
        for x in range(1, self.width - 1):
            if grid.get_cell(x, 1).type == CellType.ROAD:
                candidates.append((x, 0))

        # Bottom border (y=h-1) - check neighbor at (x, h-2)
        for x in range(1, self.width - 1):
            if grid.get_cell(x, self.height - 2).type == CellType.ROAD:
                candidates.append((x, self.height - 1))

        # Left border (x=0) - check neighbor at (1, y)
        for y in range(1, self.height - 1):
            if grid.get_cell(1, y).type == CellType.ROAD:
                candidates.append((0, y))

        # Right border (x=w-1) - check neighbor at (w-2, y)
        for y in range(1, self.height - 1):
            if grid.get_cell(self.width - 2, y).type == CellType.ROAD:
                candidates.append((self.width - 1, y))

        # Remove duplicates if corners are double counted?
        # Corners: (0,0), (w-1,0), (0,h-1), (w-1,h-1).
        # Top loop: x in 1..w-2. Excludes corners.
        # Bottom loop: x in 1..w-2. Excludes corners.
        # Left loop: y in 1..h-2. Excludes corners.
        # Right loop: y in 1..h-2. Excludes corners.
        # So corners are never candidates (which is good, corners are usually tricky).
        # And no overlap.

        total = self.rules.num_entries + self.rules.num_exits
        if total > len(candidates):
            raise GenerationError(
                "Not enough valid border locations for entries/exits"
            )

        chosen = random.sample(candidates, total)

        for i, (x, y) in enumerate(chosen):
            if i < self.rules.num_entries:
                grid.set_cell(x, y, CellType.ENTRY)
            else:
                grid.set_cell(x, y, CellType.EXIT)

    # -------------------------------------------------
    # Parking placement
    # -------------------------------------------------
    def _place_parking_spots(self, grid: Grid):
        candidates = []

        for y in range(1, self.height - 1):
            if y % 2 == 0:  # parking rows only
                for x in range(2, self.width - 2):
                    if grid.get_cell(x, y).type == CellType.WALL:
                        candidates.append((x, y))

        if self.rules.num_parking_spots > len(candidates):
            raise GenerationError(
                f"Requested {self.rules.num_parking_spots} parking spots, "
                f"but only {len(candidates)} are possible in a "
                f"{self.width}x{self.height} parking lot."
            )

        chosen = random.sample(candidates, self.rules.num_parking_spots)

        for x, y in chosen:
            grid.set_cell(x, y, CellType.PARKING)
