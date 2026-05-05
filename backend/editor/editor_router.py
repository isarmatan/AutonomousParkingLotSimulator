from __future__ import annotations

"""Parking lot editor HTTP API.

This router is consumed by the frontend parking lot editor.

Key concepts:
- Drafts are server-owned: the backend stores the authoritative grid.
- The frontend sends editing actions; the backend validates and applies them.
- Saving persists validated drafts into SQLite as globally shared parking lots.
"""

import copy
import json
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException
from fastapi import Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from generator.cell import CellType
from generator.grid import Grid
from generator.parking_lot_generator import ParkingLotGenerator
from generator.rules import GeneratorRules

from db.deps import get_db
from db.parking_lot_repository import ParkingLotRepository

from .draft_store import DraftStore
from .editor_controller import EditorController
from .editor_errors import EditorError, InvalidPlacementError, OutOfBoundsError
from .grid_factory import GridFactory
from .grid_validator import GridValidationError, GridValidator


router = APIRouter(prefix="/editor", tags=["editor"])
_store = DraftStore()


# ------------------------
# DTOs
# ------------------------

class RulesDTO(BaseModel):
    num_entries: int
    num_exits: int
    num_parking_spots: int


class CreateDraftRequest(BaseModel):
    source: Literal["blank", "generate", "load"]
    width: Optional[int] = None
    height: Optional[int] = None
    rules: Optional[RulesDTO] = None
    parkingLotId: Optional[str] = None


class CellDTO(BaseModel):
    x: int
    y: int
    type: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GridDTO(BaseModel):
    width: int
    height: int
    cells: List[CellDTO]


class CreateDraftResponse(BaseModel):
    draftId: str
    grid: GridDTO


class ErrorDTO(BaseModel):
    code: str
    message: str
    x: Optional[int] = None
    y: Optional[int] = None


class ActionDTO(BaseModel):
    type: Literal["PAINT", "CLEAR", "PLACE_ENTRY", "PLACE_EXIT", "PLACE_PARKING"]
    x: int
    y: int
    cellType: Optional[str] = None
    parkingId: Optional[str] = None


class ApplyActionRequest(BaseModel):
    action: ActionDTO
    dryRun: bool = False


class ApplyActionResponse(BaseModel):
    ok: bool
    grid: Optional[GridDTO] = None
    error: Optional[ErrorDTO] = None


class ValidateResponse(BaseModel):
    ok: bool
    errors: List[ErrorDTO] = Field(default_factory=list)


class SaveResponse(BaseModel):
    ok: bool
    parkingLotId: Optional[str] = None
    errors: List[ErrorDTO] = Field(default_factory=list)


class SavedParkingLotSummaryDTO(BaseModel):
    id: str
    name: str
    width: int
    height: int
    capacity: int
    num_entries: int
    num_exits: int
    preview_matrix: List[str]


class ListSavedParkingLotsResponse(BaseModel):
    items: List[SavedParkingLotSummaryDTO]


class SaveDraftRequest(BaseModel):
    name: str


# ------------------------
# Serialization helpers
# ------------------------

def _cell_type_from_str(value: str) -> CellType:
    try:
        return CellType[value]
    except KeyError:
        raise HTTPException(status_code=422, detail={"code": "INVALID_CELL_TYPE", "message": f"Unknown CellType '{value}'"})


def _grid_to_dto(grid: Grid) -> GridDTO:
    cells: List[CellDTO] = []
    for x in range(grid.width):
        for y in range(grid.height):
            c = grid.get_cell(x, y)
            cells.append(
                CellDTO(
                    x=x,
                    y=y,
                    type=c.type.name,
                    metadata=dict(getattr(c, "metadata", {}) or {}),
                )
            )
    return GridDTO(width=grid.width, height=grid.height, cells=cells)


def _apply_action(controller: EditorController, action: ActionDTO) -> None:
    if action.type == "CLEAR":
        controller.clear_cell(action.x, action.y)
        return

    if action.type == "PLACE_ENTRY":
        controller.place_entry(action.x, action.y)
        return

    if action.type == "PLACE_EXIT":
        controller.place_exit(action.x, action.y)
        return

    if action.type == "PLACE_PARKING":
        controller.place_parking(action.x, action.y, parking_id=action.parkingId)
        return

    if action.type == "PAINT":
        if action.cellType is None:
            raise HTTPException(status_code=422, detail={"code": "MISSING_CELL_TYPE", "message": "cellType is required for PAINT"})
        controller.paint_cell(action.x, action.y, _cell_type_from_str(action.cellType))
        return

    raise HTTPException(status_code=422, detail={"code": "INVALID_ACTION", "message": f"Unknown action type '{action.type}'"})


def _validate_grid(grid: Grid) -> List[ErrorDTO]:
    errors: List[ErrorDTO] = []

    # Basic constraints
    basic_issues = GridValidator.validate_basic_constraints(grid)
    for issue in basic_issues:
        errors.append(ErrorDTO(
            code="BASIC_CONSTRAINT",
            message=issue.message,
            x=issue.x,
            y=issue.y
        ))

    # Connectivity
    conn_issues = GridValidator.validate_connectivity(grid)
    for issue in conn_issues:
        errors.append(ErrorDTO(
            code="CONNECTIVITY",
            message=issue.message,
            x=issue.x,
            y=issue.y
        ))

    return errors


# ------------------------
# Routes
# ------------------------

@router.post("/drafts", response_model=CreateDraftResponse)
def create_draft(req: CreateDraftRequest, db: Session = Depends(get_db)):
    if req.source == "blank":
        if req.width is None or req.height is None:
            raise HTTPException(status_code=422, detail={"code": "MISSING_DIMENSIONS", "message": "width and height are required for blank drafts"})
        grid = GridFactory.create_with_outliers(req.width, req.height)
        draft = _store.create(grid)
        return CreateDraftResponse(draftId=draft.draft_id, grid=_grid_to_dto(draft.grid))

    if req.source == "generate":
        if req.width is None or req.height is None or req.rules is None:
            raise HTTPException(status_code=422, detail={"code": "MISSING_GENERATION_PARAMS", "message": "width, height and rules are required for generate drafts"})
        rules = GeneratorRules(
            num_entries=req.rules.num_entries,
            num_exits=req.rules.num_exits,
            num_parking_spots=req.rules.num_parking_spots,
        )
        grid = ParkingLotGenerator(width=req.width, height=req.height, rules=rules).generate()
        draft = _store.create(grid)
        return CreateDraftResponse(draftId=draft.draft_id, grid=_grid_to_dto(draft.grid))

    if req.source == "load":
        if req.parkingLotId is None:
            raise HTTPException(status_code=422, detail={"code": "MISSING_PARKING_LOT_ID", "message": "parkingLotId is required for load"})
        
        repo = ParkingLotRepository(db)
        grid = repo.load_grid(req.parkingLotId)
        
        if grid is None:
            raise HTTPException(status_code=404, detail={"code": "PARKING_LOT_NOT_FOUND", "message": "Saved parking lot not found"})
        draft = _store.create(grid)
        return CreateDraftResponse(draftId=draft.draft_id, grid=_grid_to_dto(draft.grid))

    raise HTTPException(status_code=422, detail={"code": "INVALID_SOURCE", "message": f"Unknown source '{req.source}'"})


@router.get("/drafts/{draft_id}", response_model=CreateDraftResponse)
def get_draft(draft_id: str):
    grid = _store.get(draft_id)
    if grid is None:
        raise HTTPException(status_code=404, detail={"code": "DRAFT_NOT_FOUND", "message": "Draft not found"})
    return CreateDraftResponse(draftId=draft_id, grid=_grid_to_dto(grid))


@router.post("/drafts/{draft_id}/actions:apply", response_model=ApplyActionResponse)
def apply_action(draft_id: str, req: ApplyActionRequest):
    grid = _store.get(draft_id)
    if grid is None:
        raise HTTPException(status_code=404, detail={"code": "DRAFT_NOT_FOUND", "message": "Draft not found"})

    working_grid = grid if not req.dryRun else copy.deepcopy(grid)
    controller = EditorController(working_grid)

    try:
        _apply_action(controller, req.action)
    except (OutOfBoundsError, InvalidPlacementError) as e:
        return ApplyActionResponse(
            ok=False,
            error=ErrorDTO(
                code=e.__class__.__name__.upper(),
                message=str(e),
                x=req.action.x,
                y=req.action.y,
            ),
        )
    except EditorError as e:
        return ApplyActionResponse(
            ok=False,
            error=ErrorDTO(code="EDITOR_ERROR", message=str(e), x=req.action.x, y=req.action.y),
        )

    if not req.dryRun:
        _store.set(draft_id, controller.get_grid())

    return ApplyActionResponse(ok=True, grid=_grid_to_dto(controller.get_grid()))


@router.post("/drafts/{draft_id}:validate", response_model=ValidateResponse)
def validate_draft(draft_id: str):
    grid = _store.get(draft_id)
    if grid is None:
        raise HTTPException(status_code=404, detail={"code": "DRAFT_NOT_FOUND", "message": "Draft not found"})

    errors = _validate_grid(grid)
    if errors:
        return ValidateResponse(ok=False, errors=errors)
    return ValidateResponse(ok=True, errors=[])


@router.post("/drafts/{draft_id}:save", response_model=SaveResponse)
def save_draft(draft_id: str, req: SaveDraftRequest, db: Session = Depends(get_db)):
    grid = _store.get(draft_id)
    if grid is None:
        raise HTTPException(status_code=404, detail={"code": "DRAFT_NOT_FOUND", "message": "Draft not found"})

    errors = _validate_grid(grid)
    if errors:
        return SaveResponse(ok=False, errors=errors)

    repo = ParkingLotRepository(db)
    try:
        model = repo.create(name=req.name, grid=grid)
    except ValueError:
        return SaveResponse(
            ok=False,
            errors=[ErrorDTO(code="NAME_TAKEN", message="Parking lot name already exists")],
        )

    return SaveResponse(ok=True, parkingLotId=model.id, errors=[])


@router.get("/saved", response_model=ListSavedParkingLotsResponse)
def list_saved_parking_lots(db: Session = Depends(get_db)):
    repo = ParkingLotRepository(db)
    models = repo.list_all()
    items = []
    
    for m in models:
        try:
            data = json.loads(m.grid_json)
            width = int(data.get("width", 0))
            height = int(data.get("height", 0))
            cells = data.get("cells", [])
            
            capacity = 0
            num_entries = 0
            num_exits = 0
            
            # Reconstruct 2D grid for matrix preview
            grid_chars = [["?" for _ in range(height)] for _ in range(width)]
            
            char_map = {
                "WALL": "#",
                "ROAD": ".",
                "PARKING": "P",
                "ENTRY": "E",
                "EXIT": "X"
            }

            for c in cells:
                cx = int(c.get("x", 0))
                cy = int(c.get("y", 0))
                ctype = c.get("type")
                
                if 0 <= cx < width and 0 <= cy < height:
                    grid_chars[cx][cy] = char_map.get(ctype, "?")

                if ctype == "PARKING":
                    capacity += 1
                elif ctype == "ENTRY":
                    num_entries += 1
                elif ctype == "EXIT":
                    num_exits += 1
            
            # Transpose to (y, x) for row-by-row printing and join
            preview_matrix = []
            for y in range(height):
                row_str = "".join(grid_chars[x][y] for x in range(width))
                preview_matrix.append(row_str)
            
            items.append(SavedParkingLotSummaryDTO(
                id=m.id,
                name=m.name,
                width=width,
                height=height,
                capacity=capacity,
                num_entries=num_entries,
                num_exits=num_exits,
                preview_matrix=preview_matrix
            ))
        except Exception:
            # If JSON is corrupted or schema changed, skip or return partial
            # For now, we skip to avoid crashing the list
            continue

    return ListSavedParkingLotsResponse(items=items)


@router.delete("/saved/{parking_lot_id}", status_code=204)
def delete_parking_lot(parking_lot_id: str, db: Session = Depends(get_db)):
    repo = ParkingLotRepository(db)
    success = repo.delete(parking_lot_id)
    if not success:
        raise HTTPException(status_code=404, detail="Parking lot not found")
    return
