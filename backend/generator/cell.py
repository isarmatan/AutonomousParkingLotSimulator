from enum import Enum
from typing import Any, Dict

class CellType(Enum):
    ROAD = 0
    PARKING = 1
    WALL = 2
    ENTRY = 3
    EXIT = 4


class Cell:
    def __init__(self, x: int, y: int, cell_type: CellType):
        self.x = x
        self.y = y
        self.type = cell_type
        # Editor support: per-cell metadata (e.g., parking_id).
        self.metadata: Dict[str, Any] = {}

    @property
    def cell_type(self) -> CellType:
        # Compatibility alias (some editor code uses `cell.cell_type`).
        return self.type

    @cell_type.setter
    def cell_type(self, value: CellType) -> None:
        self.type = value

    def is_drivable(self) -> bool:
        return self.type in {
            CellType.ROAD,
            CellType.PARKING,
            CellType.ENTRY,
            CellType.EXIT
        }