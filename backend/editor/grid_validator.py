from typing import List, Optional
from dataclasses import dataclass
from generator.grid import Grid
from generator.cell import CellType
from collections import deque


@dataclass
class ValidationIssue:
    message: str
    x: Optional[int] = None
    y: Optional[int] = None


class GridValidationError(Exception):
    """
    Raised when a grid fails validation.
    Contains a list of structured validation issues.
    """

    def __init__(self, issues: List[ValidationIssue]):
        super().__init__("Grid validation failed")
        self.issues = issues


class GridValidator:
    @staticmethod
    def validate_basic_constraints(grid: Grid) -> List[ValidationIssue]:
        """
        Validates the grid as a whole (counts, boundaries).
        Returns a list of ValidationIssue.
        """
        issues: List[ValidationIssue] = []

        entry_count = 0
        exit_count = 0
        parking_ids = set()
        parking_count = 0

        for x in range(grid.width):
            for y in range(grid.height):
                cell = grid.get_cell(x, y)

                if cell.cell_type == CellType.ENTRY:
                    entry_count += 1
                    if not grid.is_boundary_non_corner(x, y):
                        issues.append(ValidationIssue(
                            message=f"ENTRY at ({x},{y}) is not on a valid boundary cell",
                            x=x, y=y
                        ))

                elif cell.cell_type == CellType.EXIT:
                    exit_count += 1
                    if not grid.is_boundary_non_corner(x, y):
                        issues.append(ValidationIssue(
                            message=f"EXIT at ({x},{y}) is not on a valid boundary cell",
                            x=x, y=y
                        ))

                elif cell.cell_type == CellType.PARKING:
                    parking_count += 1

                    # Optional rule: parking should not be on boundary
                    if (
                        x == 0 or
                        x == grid.width - 1 or
                        y == 0 or
                        y == grid.height - 1
                    ):
                        issues.append(ValidationIssue(
                            message=f"PARKING at ({x},{y}) cannot be on grid boundary",
                            x=x, y=y
                        ))

                    parking_id = cell.metadata.get("parking_id")
                    if parking_id is not None:
                        if parking_id in parking_ids:
                            issues.append(ValidationIssue(
                                message=f"Duplicate PARKING id '{parking_id}'",
                                x=x, y=y
                            ))
                        parking_ids.add(parking_id)

        # Global requirements
        if entry_count == 0:
            issues.append(ValidationIssue(message="Grid must contain at least one ENTRY"))

        if exit_count == 0:
            issues.append(ValidationIssue(message="Grid must contain at least one EXIT"))

        if parking_count == 0:
            issues.append(ValidationIssue(message="Grid must contain at least one PARKING spot"))

        return issues
    
    @staticmethod
    def validate_connectivity(grid: Grid) -> List[ValidationIssue]: 
        """
        Validates that all functional cells (Entries, Exits, Parking) are connected
        and reachable via ROAD cells.
        Returns a list of ValidationIssue.
        """
        issues: List[ValidationIssue] = []
        
        DRIVABLE = {
            CellType.ROAD,
            CellType.ENTRY,
            CellType.EXIT,
            CellType.PARKING,
        }
        
        FUNCTIONAL = {
            CellType.ENTRY,
            CellType.EXIT,
            CellType.PARKING,
        }

        # 1. Find a starting point (preferably an ENTRY)
        start_node = None
        for x in range(grid.width):
            for y in range(grid.height):
                if grid.get_cell(x, y).cell_type == CellType.ENTRY:
                    start_node = (x, y)
                    break
            if start_node:
                break
        
        # Fallback if no ENTRY (though basic constraints should catch that)
        if not start_node:
            for x in range(grid.width):
                for y in range(grid.height):
                    if grid.get_cell(x, y).cell_type in DRIVABLE:
                        start_node = (x, y)
                        break
                if start_node:
                    break

        if not start_node:
            issues.append(ValidationIssue(message="No drivable cells found in grid"))
            return issues

        # 2. BFS from start_node to find all reachable cells
        visited = set()
        queue = deque([start_node])
        visited.add(start_node)

        while queue:
            x, y = queue.popleft()

            for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
                nx, ny = x + dx, y + dy
                if not grid.in_bounds(nx, ny):
                    continue
                if (nx, ny) in visited:
                    continue
                if grid.get_cell(nx, ny).cell_type in DRIVABLE:
                    visited.add((nx, ny))
                    queue.append((nx, ny))

        # 3. Check that ALL functional cells are visited
        for x in range(grid.width):
            for y in range(grid.height):
                cell = grid.get_cell(x, y)
                if cell.cell_type in FUNCTIONAL:
                    if (x, y) not in visited:
                        issues.append(ValidationIssue(
                            message=f"{cell.cell_type.name} at ({x},{y}) is not reachable via roads",
                            x=x, y=y
                        ))
                        
        return issues
