import sys, os
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_project_root, "backend"))

import pytest
from fastapi.testclient import TestClient
from api_app import app

client = TestClient(app)

# ─── Shared helpers ───────────────────────────────────────────────────────────

def _blank_draft(w=10, h=10) -> str:
    resp = client.post("/editor/drafts", json={"source": "blank", "width": w, "height": h})
    assert resp.status_code == 200
    return resp.json()["draftId"]


def _generate_draft(w=15, h=15) -> str:
    resp = client.post("/editor/drafts", json={
        "source": "generate", "width": w, "height": h,
        "rules": {"num_entries": 1, "num_exits": 1, "num_parking_spots": 10},
    })
    assert resp.status_code == 200
    return resp.json()["draftId"]


def _apply(draft_id: str, action: dict, dry_run: bool = False) -> dict:
    resp = client.post(
        f"/editor/drafts/{draft_id}/actions:apply",
        json={"action": action, "dryRun": dry_run},
    )
    assert resp.status_code == 200
    return resp.json()


def _make_valid_draft() -> str:
    """Blank 10×10 draft made valid: ENTRY(0,1), EXIT(0,2), ROAD loop, PARKING(3,1)."""
    draft_id = _blank_draft()
    setup_actions = [
        {"type": "PLACE_ENTRY", "x": 0, "y": 1},
        {"type": "PLACE_EXIT",  "x": 0, "y": 2},
        {"type": "PAINT", "x": 1, "y": 1, "cellType": "ROAD"},
        {"type": "PAINT", "x": 1, "y": 2, "cellType": "ROAD"},
        {"type": "PAINT", "x": 2, "y": 1, "cellType": "ROAD"},
        {"type": "PAINT", "x": 2, "y": 2, "cellType": "ROAD"},
        {"type": "PLACE_PARKING", "x": 3, "y": 1},
    ]
    for action in setup_actions:
        result = _apply(draft_id, action)
        assert result["ok"], f"Setup action failed: {action} → {result.get('error')}"
    return draft_id


# ─── IT-09: Create blank draft ────────────────────────────────────────────────

def test_create_blank_draft_returns_grid():
    """IT-09: POST /editor/drafts blank → draftId + correct dimensions."""
    resp = client.post("/editor/drafts", json={"source": "blank", "width": 15, "height": 15})
    assert resp.status_code == 200
    data = resp.json()
    assert "draftId" in data
    assert data["grid"]["width"] == 15
    assert data["grid"]["height"] == 15


# ─── IT-10: Create generate draft ────────────────────────────────────────────

def test_create_generate_draft_has_functional_cells():
    """IT-10: POST /editor/drafts generate → grid contains ENTRY/EXIT/PARKING."""
    resp = client.post("/editor/drafts", json={
        "source": "generate", "width": 20, "height": 20,
        "rules": {"num_entries": 1, "num_exits": 1, "num_parking_spots": 10},
    })
    assert resp.status_code == 200
    cells = resp.json()["grid"]["cells"]
    types = {c["type"] for c in cells}
    assert "ENTRY" in types
    assert "EXIT" in types
    assert "PARKING" in types


# ─── IT-11: Blank draft missing dimensions ────────────────────────────────────

def test_create_blank_draft_without_dimensions_returns_422():
    """IT-11: blank source with no width/height → HTTP 422 MISSING_DIMENSIONS."""
    resp = client.post("/editor/drafts", json={"source": "blank"})
    assert resp.status_code == 422
    assert "MISSING_DIMENSIONS" in resp.text


# ─── IT-12: Load unknown parking lot ID ──────────────────────────────────────

def test_create_load_draft_unknown_id_returns_404():
    """IT-12: load source with non-existent parkingLotId → HTTP 404."""
    resp = client.post("/editor/drafts", json={"source": "load", "parkingLotId": "does-not-exist"})
    assert resp.status_code == 404
    assert "PARKING_LOT_NOT_FOUND" in resp.text


# ─── IT-13: Place ENTRY on valid boundary ────────────────────────────────────

def test_apply_place_entry_on_boundary_ok():
    """IT-13: PLACE_ENTRY on boundary non-corner → ok:true, cell is ENTRY."""
    draft_id = _blank_draft()
    result = _apply(draft_id, {"type": "PLACE_ENTRY", "x": 0, "y": 4})
    assert result["ok"] is True
    cells = {(c["x"], c["y"]): c["type"] for c in result["grid"]["cells"]}
    assert cells[(0, 4)] == "ENTRY"


# ─── IT-14: Place ENTRY on interior ──────────────────────────────────────────

def test_apply_place_entry_on_interior_returns_not_ok():
    """IT-14: PLACE_ENTRY on interior cell → ok:false."""
    draft_id = _blank_draft()
    result = _apply(draft_id, {"type": "PLACE_ENTRY", "x": 5, "y": 5})
    assert result["ok"] is False
    assert result["error"] is not None


# ─── IT-15: Place ENTRY on corner ────────────────────────────────────────────

def test_apply_place_entry_on_corner_returns_not_ok():
    """IT-15: PLACE_ENTRY on corner (0,0) → ok:false."""
    draft_id = _blank_draft()
    result = _apply(draft_id, {"type": "PLACE_ENTRY", "x": 0, "y": 0})
    assert result["ok"] is False


# ─── IT-16: Place PARKING on WALL ────────────────────────────────────────────

def test_apply_place_parking_on_wall_returns_not_ok():
    """IT-16: PLACE_PARKING on a WALL cell → ok:false."""
    draft_id = _blank_draft()
    result = _apply(draft_id, {"type": "PLACE_PARKING", "x": 0, "y": 3})
    assert result["ok"] is False


# ─── IT-17: Out-of-bounds action ─────────────────────────────────────────────

def test_apply_out_of_bounds_returns_not_ok():
    """IT-17: action with coordinates outside grid → ok:false."""
    draft_id = _blank_draft(10, 10)
    result = _apply(draft_id, {"type": "PLACE_ENTRY", "x": 999, "y": 999})
    assert result["ok"] is False
    assert result["error"] is not None


# ─── IT-18: dryRun does not mutate server ────────────────────────────────────

def test_apply_dry_run_does_not_mutate_server():
    """IT-18: dryRun=true → response shows change but server grid is unchanged."""
    draft_id = _blank_draft()

    # Read the actual initial type of cell (3,3) — may be ROAD or WALL depending on GridFactory
    initial_cells = {(c["x"], c["y"]): c["type"]
                     for c in client.get(f"/editor/drafts/{draft_id}").json()["grid"]["cells"]}
    initial_type = initial_cells[(3, 3)]

    # Paint to the OPPOSITE type so the change is observable
    paint_type = "WALL" if initial_type != "WALL" else "ROAD"
    dry_result = _apply(draft_id, {"type": "PAINT", "x": 3, "y": 3, "cellType": paint_type}, dry_run=True)
    assert dry_result["ok"] is True

    # The returned (speculative) grid reflects the change
    dry_cells = {(c["x"], c["y"]): c["type"] for c in dry_result["grid"]["cells"]}
    assert dry_cells[(3, 3)] == paint_type

    # Fetch actual server state — must still match the ORIGINAL type
    server_cells = {(c["x"], c["y"]): c["type"]
                    for c in client.get(f"/editor/drafts/{draft_id}").json()["grid"]["cells"]}
    assert server_cells[(3, 3)] == initial_type


# ─── IT-19: Validate valid grid ──────────────────────────────────────────────

def test_validate_valid_generated_draft_passes():
    """IT-19: POST :validate on a generated draft → ok:true, errors:[]."""
    draft_id = _generate_draft()
    resp = client.post(f"/editor/drafts/{draft_id}:validate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["errors"] == []


# ─── IT-20: Validate blank grid fails ────────────────────────────────────────

def test_validate_blank_draft_fails_with_errors():
    """IT-20: POST :validate on blank draft → ok:false, errors for missing cells."""
    draft_id = _blank_draft()
    resp = client.post(f"/editor/drafts/{draft_id}:validate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    messages = [e["message"] for e in data["errors"]]
    assert any("ENTRY" in m for m in messages)
    assert any("EXIT" in m for m in messages)
    assert any("PARKING" in m for m in messages)


# ─── IT-21: Save valid draft ──────────────────────────────────────────────────

def test_save_valid_draft_returns_parking_lot_id():
    """IT-21: POST :save on valid draft → ok:true, parkingLotId is non-empty."""
    draft_id = _make_valid_draft()
    resp = client.post(f"/editor/drafts/{draft_id}:save", json={"name": "Test Lot A"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["parkingLotId"] is not None
    assert len(data["parkingLotId"]) > 0


# ─── IT-22: Save invalid draft ───────────────────────────────────────────────

def test_save_invalid_draft_returns_errors():
    """IT-22: POST :save on blank draft (no ENTRY/EXIT/PARKING) → ok:false + errors."""
    draft_id = _blank_draft()
    resp = client.post(f"/editor/drafts/{draft_id}:save", json={"name": "Broken Lot"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert len(data["errors"]) > 0


# ─── IT-23: Duplicate name rejected ──────────────────────────────────────────

def test_save_duplicate_name_returns_name_taken():
    """IT-23: Saving two drafts with the same name → second returns NAME_TAKEN."""
    draft_id_1 = _make_valid_draft()
    resp1 = client.post(f"/editor/drafts/{draft_id_1}:save", json={"name": "My Lot"})
    assert resp1.json()["ok"] is True

    draft_id_2 = _make_valid_draft()
    resp2 = client.post(f"/editor/drafts/{draft_id_2}:save", json={"name": "My Lot"})
    data2 = resp2.json()
    assert data2["ok"] is False
    assert any(e["code"] == "NAME_TAKEN" for e in data2["errors"])


# ─── IT-24: Saved lot appears in list ────────────────────────────────────────

def test_saved_lot_appears_in_get_saved():
    """IT-24: GET /editor/saved includes the newly saved lot with all metadata."""
    draft_id = _make_valid_draft()
    save_resp = client.post(f"/editor/drafts/{draft_id}:save", json={"name": "Listed Lot"})
    saved_id = save_resp.json()["parkingLotId"]

    list_resp = client.get("/editor/saved")
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    found = next((i for i in items if i["id"] == saved_id), None)
    assert found is not None
    assert found["name"] == "Listed Lot"
    assert "capacity" in found
    assert "width" in found
    assert "height" in found
    assert "num_entries" in found
    assert "num_exits" in found


# ─── IT-25: Delete removes lot ───────────────────────────────────────────────

def test_delete_lot_removes_it_from_list():
    """IT-25: DELETE /editor/saved/{id} → 204; lot no longer in GET /editor/saved."""
    draft_id = _make_valid_draft()
    saved_id = client.post(f"/editor/drafts/{draft_id}:save", json={"name": "To Delete"}).json()["parkingLotId"]

    del_resp = client.delete(f"/editor/saved/{saved_id}")
    assert del_resp.status_code == 204

    items = client.get("/editor/saved").json()["items"]
    assert all(i["id"] != saved_id for i in items)


# ─── IT-26: Delete non-existent ID ───────────────────────────────────────────

def test_delete_nonexistent_lot_returns_404():
    """IT-26: DELETE /editor/saved/fake-id → HTTP 404."""
    resp = client.delete("/editor/saved/totally-fake-id-xyz")
    assert resp.status_code == 404
