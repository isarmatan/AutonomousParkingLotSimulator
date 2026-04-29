import json
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from generator.cell import CellType
from generator.grid import Grid

from .models import ParkingLotModel


def grid_to_json_dict(grid: Grid) -> Dict[str, Any]:
    """Serialize an in-memory `Grid` into a JSON-friendly dict."""
    cells: List[Dict[str, Any]] = []
    for x in range(grid.width):
        for y in range(grid.height):
            c = grid.get_cell(x, y)
            cells.append(
                {
                    "x": x,
                    "y": y,
                    "type": c.type.name,
                    "metadata": dict(getattr(c, "metadata", {}) or {}),
                }
            )
    return {"width": grid.width, "height": grid.height, "cells": cells}


def grid_from_json_dict(data: Dict[str, Any]) -> Grid:
    """Deserialize a `Grid` from a JSON-friendly dict."""
    width = int(data["width"])
    height = int(data["height"])
    grid = Grid(width, height)

    # Default to WALL; then fill in.
    for cell in data.get("cells", []):
        x = int(cell["x"])
        y = int(cell["y"])
        t = CellType[str(cell["type"])]
        grid.set_cell(x, y, t)
        grid.get_cell(x, y).metadata = dict(cell.get("metadata", {}) or {})

    return grid


class ParkingLotRepository:
    """Data-access layer for globally saved parking lots.

    Why this exists:
    - Keeps SQLAlchemy/DB code out of the FastAPI router.
    - Central place to evolve storage format and constraints.
    """

    def __init__(self, db: Session):
        self._db = db

    def list_all(self) -> List[ParkingLotModel]:
        return list(self._db.scalars(select(ParkingLotModel).order_by(ParkingLotModel.created_at.desc())))

    def get(self, parking_lot_id: str) -> Optional[ParkingLotModel]:
        return self._db.get(ParkingLotModel, parking_lot_id)

    def get_by_name(self, name: str) -> Optional[ParkingLotModel]:
        stmt = select(ParkingLotModel).where(ParkingLotModel.name == name)
        return self._db.scalars(stmt).first()

    def create(self, *, name: str, grid: Grid) -> ParkingLotModel:
        if self.get_by_name(name) is not None:
            raise ValueError("Parking lot name already exists")

        model = ParkingLotModel(
            id=str(uuid.uuid4()),
            name=name,
            grid_json=json.dumps(grid_to_json_dict(grid)),
        )
        self._db.add(model)
        self._db.commit()
        self._db.refresh(model)
        return model

    def load_grid(self, parking_lot_id: str) -> Optional[Grid]:
        model = self.get(parking_lot_id)
        if model is None:
            return None
        data = json.loads(model.grid_json)
        return grid_from_json_dict(data)

    def delete(self, parking_lot_id: str) -> bool:
        model = self.get(parking_lot_id)
        if model:
            self._db.delete(model)
            self._db.commit()
            return True
        return False
