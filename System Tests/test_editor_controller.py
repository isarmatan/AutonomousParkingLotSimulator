import sys, os
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_project_root, "backend"))

import pytest
from generator.grid import Grid
from generator.cell import CellType
from editor.editor_controller import EditorController
from editor.editor_errors import InvalidPlacementError, OutOfBoundsError


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_grid(width=10, height=10) -> Grid:
    """Grid initializes all cells as WALL."""
    return Grid(width, height)


def set_road(grid: Grid, x: int, y: int) -> None:
    grid.get_cell(x, y).type = CellType.ROAD


# ─── place_entry ──────────────────────────────────────────────────────────────

def test_place_entry_on_boundary_non_corner_succeeds():
    """UT-21: ENTRY on left-edge non-corner cell is accepted."""
    grid = make_grid()
    ctrl = EditorController(grid)
    ctrl.place_entry(0, 5)
    assert grid.get_cell(0, 5).type == CellType.ENTRY


def test_place_entry_converts_boundary_wall_to_entry():
    """Boundary cell starts as WALL; place_entry should still succeed."""
    grid = make_grid()
    assert grid.get_cell(0, 5).type == CellType.WALL
    EditorController(grid).place_entry(0, 5)
    assert grid.get_cell(0, 5).type == CellType.ENTRY


def test_place_entry_on_interior_raises():
    """UT-22: ENTRY on interior cell raises InvalidPlacementError."""
    grid = make_grid()
    with pytest.raises(InvalidPlacementError):
        EditorController(grid).place_entry(5, 5)


def test_place_entry_on_corner_raises():
    """UT-23: ENTRY on corner (0,0) raises InvalidPlacementError."""
    grid = make_grid()
    with pytest.raises(InvalidPlacementError):
        EditorController(grid).place_entry(0, 0)


def test_place_entry_on_all_four_corners_raises():
    """All four corners must be rejected for ENTRY placement."""
    grid = make_grid(10, 10)
    ctrl = EditorController(grid)
    corners = [(0, 0), (9, 0), (0, 9), (9, 9)]
    for x, y in corners:
        with pytest.raises(InvalidPlacementError):
            ctrl.place_entry(x, y)


# ─── place_exit ───────────────────────────────────────────────────────────────

def test_place_exit_on_boundary_non_corner_succeeds():
    """UT-24: EXIT on right-edge non-corner cell is accepted."""
    grid = make_grid()
    ctrl = EditorController(grid)
    ctrl.place_exit(9, 4)
    assert grid.get_cell(9, 4).type == CellType.EXIT


def test_place_exit_on_corner_raises():
    """UT-25: EXIT on bottom-right corner raises InvalidPlacementError."""
    grid = make_grid()
    with pytest.raises(InvalidPlacementError):
        EditorController(grid).place_exit(9, 9)


def test_place_exit_on_interior_raises():
    """EXIT on interior cell raises InvalidPlacementError."""
    grid = make_grid()
    with pytest.raises(InvalidPlacementError):
        EditorController(grid).place_exit(4, 4)


# ─── place_parking ────────────────────────────────────────────────────────────

def test_place_parking_on_wall_raises():
    """UT-26: PARKING on WALL cell raises InvalidPlacementError."""
    grid = make_grid()  # all cells are WALL by default
    with pytest.raises(InvalidPlacementError, match="Cannot place PARKING on WALL"):
        EditorController(grid).place_parking(3, 3)


def test_place_parking_on_existing_parking_raises():
    """UT-27: PARKING on an already-PARKING cell raises InvalidPlacementError."""
    grid = make_grid()
    set_road(grid, 3, 3)
    ctrl = EditorController(grid)
    ctrl.place_parking(3, 3)
    with pytest.raises(InvalidPlacementError, match="already a PARKING spot"):
        ctrl.place_parking(3, 3)


def test_place_parking_on_road_auto_generates_id():
    """UT-28: PARKING on ROAD with no explicit ID gets auto-generated 'P1'."""
    grid = make_grid()
    set_road(grid, 3, 3)
    EditorController(grid).place_parking(3, 3)
    cell = grid.get_cell(3, 3)
    assert cell.type == CellType.PARKING
    assert cell.metadata.get("parking_id") == "P1"


def test_place_parking_explicit_id_is_used():
    """Providing an explicit parking_id stores it in metadata."""
    grid = make_grid()
    set_road(grid, 3, 3)
    EditorController(grid).place_parking(3, 3, parking_id="SPOT-A")
    assert grid.get_cell(3, 3).metadata.get("parking_id") == "SPOT-A"


def test_place_parking_sequential_ids():
    """Second parking spot gets next sequential ID ('P2')."""
    grid = make_grid()
    set_road(grid, 3, 3)
    set_road(grid, 4, 4)
    ctrl = EditorController(grid)
    ctrl.place_parking(3, 3)
    ctrl.place_parking(4, 4)
    assert grid.get_cell(4, 4).metadata.get("parking_id") == "P2"


# ─── paint_cell ───────────────────────────────────────────────────────────────

def test_paint_wall_to_parking_raises():
    """UT-29: Painting PARKING onto a WALL raises InvalidPlacementError."""
    grid = make_grid()  # (1,1) is WALL
    with pytest.raises(InvalidPlacementError):
        EditorController(grid).paint_cell(1, 1, CellType.PARKING)


def test_paint_road_to_wall_succeeds():
    """UT-30: Painting WALL onto a ROAD succeeds."""
    grid = make_grid()
    set_road(grid, 3, 3)
    EditorController(grid).paint_cell(3, 3, CellType.WALL)
    assert grid.get_cell(3, 3).type == CellType.WALL


def test_paint_clears_existing_metadata():
    """paint_cell resets metadata to empty dict."""
    grid = make_grid()
    set_road(grid, 3, 3)
    grid.get_cell(3, 3).metadata = {"stale": "data"}
    EditorController(grid).paint_cell(3, 3, CellType.ROAD)
    assert grid.get_cell(3, 3).metadata == {}


# ─── clear_cell ───────────────────────────────────────────────────────────────

def test_clear_parking_cell_becomes_road():
    """UT-31: clear_cell on PARKING → ROAD with empty metadata."""
    grid = make_grid()
    set_road(grid, 2, 2)
    ctrl = EditorController(grid)
    ctrl.place_parking(2, 2)
    ctrl.clear_cell(2, 2)
    cell = grid.get_cell(2, 2)
    assert cell.type == CellType.ROAD
    assert cell.metadata == {}


def test_clear_wall_cell_becomes_road():
    """clear_cell on a WALL also resets it to ROAD."""
    grid = make_grid()  # (5,5) is WALL
    EditorController(grid).clear_cell(5, 5)
    assert grid.get_cell(5, 5).type == CellType.ROAD


# ─── out of bounds ────────────────────────────────────────────────────────────

def test_out_of_bounds_place_entry_raises():
    """UT-32: Coordinates beyond grid dimensions → OutOfBoundsError."""
    grid = make_grid(10, 10)
    with pytest.raises(OutOfBoundsError):
        EditorController(grid).place_entry(15, 0)


def test_out_of_bounds_negative_coordinates_raises():
    """Negative coordinates → OutOfBoundsError."""
    grid = make_grid(10, 10)
    with pytest.raises(OutOfBoundsError):
        EditorController(grid).place_parking(-1, 5)


def test_out_of_bounds_clear_raises():
    """clear_cell with out-of-bounds coordinates → OutOfBoundsError."""
    grid = make_grid(10, 10)
    with pytest.raises(OutOfBoundsError):
        EditorController(grid).clear_cell(999, 999)
