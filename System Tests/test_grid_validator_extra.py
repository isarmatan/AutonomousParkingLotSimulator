import sys, os
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_project_root, "backend"))

import pytest
from editor.grid_validator import GridValidator
from generator.grid import Grid
from generator.cell import CellType


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_grid(width=10, height=10, setup_fn=None) -> Grid:
    grid = Grid(width, height)
    if setup_fn:
        setup_fn(grid)
    return grid


def _set(grid: Grid, x: int, y: int, ct: CellType) -> None:
    grid.get_cell(x, y).type = ct


# ─── UT-13: ENTRY / EXIT on corner ────────────────────────────────────────────

def test_entry_on_top_left_corner_is_invalid():
    """UT-13: ENTRY placed on corner (0,0) → boundary non-corner violation."""
    def setup(grid):
        _set(grid, 0, 0, CellType.ENTRY)
        _set(grid, 1, 0, CellType.EXIT)
        _set(grid, 2, 2, CellType.PARKING)

    issues = GridValidator.validate_basic_constraints(make_grid(setup_fn=setup))
    msgs = [i.message for i in issues]
    assert any("ENTRY at (0,0)" in m for m in msgs)


def test_entry_on_top_right_corner_is_invalid():
    """ENTRY placed on corner (9,0) → violation reported."""
    def setup(grid):
        _set(grid, 9, 0, CellType.ENTRY)
        _set(grid, 1, 0, CellType.EXIT)
        _set(grid, 2, 2, CellType.PARKING)

    issues = GridValidator.validate_basic_constraints(make_grid(setup_fn=setup))
    msgs = [i.message for i in issues]
    assert any("ENTRY at (9,0)" in m for m in msgs)


def test_exit_on_corner_is_invalid():
    """EXIT placed on corner (9,9) → violation reported."""
    def setup(grid):
        _set(grid, 1, 0, CellType.ENTRY)
        _set(grid, 9, 9, CellType.EXIT)
        _set(grid, 2, 2, CellType.PARKING)

    issues = GridValidator.validate_basic_constraints(make_grid(setup_fn=setup))
    msgs = [i.message for i in issues]
    assert any("EXIT at (9,9)" in m for m in msgs)


def test_entry_on_non_corner_boundary_has_no_boundary_issue():
    """ENTRY on a valid non-corner boundary generates no boundary issue."""
    def setup(grid):
        _set(grid, 0, 5, CellType.ENTRY)
        _set(grid, 9, 5, CellType.EXIT)
        _set(grid, 3, 3, CellType.PARKING)

    issues = GridValidator.validate_basic_constraints(make_grid(setup_fn=setup))
    boundary_issues = [i for i in issues if "is not on a valid boundary" in i.message]
    assert len(boundary_issues) == 0


# ─── UT-18: Duplicate parking IDs ─────────────────────────────────────────────

def test_duplicate_parking_ids_flagged():
    """UT-18: Two PARKING cells with the same parking_id → duplicate issue."""
    def setup(grid):
        _set(grid, 1, 0, CellType.ENTRY)
        _set(grid, 2, 0, CellType.EXIT)

        c1 = grid.get_cell(2, 2)
        c1.type = CellType.PARKING
        c1.metadata["parking_id"] = "P1"

        c2 = grid.get_cell(3, 3)
        c2.type = CellType.PARKING
        c2.metadata["parking_id"] = "P1"  # duplicate

    issues = GridValidator.validate_basic_constraints(make_grid(setup_fn=setup))
    msgs = [i.message for i in issues]
    assert any("Duplicate PARKING id 'P1'" in m for m in msgs)


def test_three_cells_same_parking_id_flagged():
    """Three PARKING cells sharing an ID → at least two duplicate issues."""
    def setup(grid):
        _set(grid, 1, 0, CellType.ENTRY)
        _set(grid, 2, 0, CellType.EXIT)
        for coord in [(2, 2), (3, 3), (4, 4)]:
            c = grid.get_cell(*coord)
            c.type = CellType.PARKING
            c.metadata["parking_id"] = "P1"

    issues = GridValidator.validate_basic_constraints(make_grid(setup_fn=setup))
    dup_issues = [i for i in issues if "Duplicate" in i.message]
    assert len(dup_issues) >= 2


def test_unique_parking_ids_produce_no_duplicate_issue():
    """Unique IDs across PARKING cells → no duplicate issues."""
    def setup(grid):
        _set(grid, 1, 0, CellType.ENTRY)
        _set(grid, 2, 0, CellType.EXIT)

        for i, coord in enumerate([(2, 2), (3, 3), (4, 4)], start=1):
            c = grid.get_cell(*coord)
            c.type = CellType.PARKING
            c.metadata["parking_id"] = f"P{i}"

    issues = GridValidator.validate_basic_constraints(make_grid(setup_fn=setup))
    msgs = [i.message for i in issues]
    assert not any("Duplicate" in m for m in msgs)


def test_parking_without_id_no_duplicate_check():
    """PARKING cells with no parking_id set should not trigger duplicate check."""
    def setup(grid):
        _set(grid, 1, 0, CellType.ENTRY)
        _set(grid, 2, 0, CellType.EXIT)
        grid.get_cell(2, 2).type = CellType.PARKING
        grid.get_cell(3, 3).type = CellType.PARKING
        # No metadata set — parking_id is None for both

    issues = GridValidator.validate_basic_constraints(make_grid(setup_fn=setup))
    msgs = [i.message for i in issues]
    assert not any("Duplicate" in m for m in msgs)
