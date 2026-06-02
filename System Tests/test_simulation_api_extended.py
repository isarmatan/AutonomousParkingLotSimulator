import sys, os
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_project_root, "backend"))

import pytest
from fastapi.testclient import TestClient
from api_app import app

client = TestClient(app)

# ─── Shared helpers ───────────────────────────────────────────────────────────

_HEADLESS_BASE = {
    "source": "generate",
    "width": 15,
    "height": 15,
    "rules": {"num_entries": 1, "num_exits": 1, "num_parking_spots": 10},
    "algorithm": "priority",
    "max_steps": 60,
    "initial_cars": 3,
    "arrival_lambda": 0.3,
    "exit_rate": 0.02,
    "planning_horizon": 50,
    "goal_reserve_horizon": 200,
    "max_arriving_cars": 0,
}


def _run_headless(overrides: dict | None = None) -> dict:
    payload = {**_HEADLESS_BASE, **(overrides or {})}
    resp = client.post("/simulation/headless", json=payload)
    assert resp.status_code == 200, f"Headless failed: {resp.text}"
    return resp.json()


def _save_a_parking_lot(name: str = "Sim Test Lot") -> str:
    """Create a valid editor draft, save it, return its parkingLotId."""
    blank = client.post("/editor/drafts", json={"source": "blank", "width": 10, "height": 10})
    draft_id = blank.json()["draftId"]
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
        r = client.post(f"/editor/drafts/{draft_id}/actions:apply", json={"action": action})
        assert r.json()["ok"], f"Setup failed: {action}"
    save_resp = client.post(f"/editor/drafts/{draft_id}:save", json={"name": name})
    assert save_resp.json()["ok"], f"Could not save draft: {save_resp.text}"
    return save_resp.json()["parkingLotId"]


# ─── IT-05: Headless with load source ────────────────────────────────────────

def test_headless_load_source_uses_saved_lot_dimensions():
    """IT-05: headless with source='load' uses the saved lot's dimensions."""
    lot_id = _save_a_parking_lot("IT05 Lot")

    resp = client.post("/simulation/headless", json={
        "source": "load",
        "parkingLotId": lot_id,
        "algorithm": "priority",
        "max_steps": 30,
        "initial_cars": 1,
        "arrival_lambda": 0.0,
        "exit_rate": 0.02,
        "planning_horizon": 50,
        "goal_reserve_horizon": 200,
        "max_arriving_cars": 0,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["grid_width"] == 10
    assert data["grid_height"] == 10


def test_headless_load_source_unknown_id_returns_error():
    """IT-05 (negative): load source with non-existent ID → non-200 response."""
    safe_client = TestClient(app, raise_server_exceptions=False)
    resp = safe_client.post("/simulation/headless", json={
        "source": "load",
        "parkingLotId": "ghost-lot-id",
        "algorithm": "priority",
        "max_steps": 10,
        "initial_cars": 0,
        "arrival_lambda": 0.0,
        "exit_rate": 0.02,
        "planning_horizon": 50,
        "goal_reserve_horizon": 200,
        "max_arriving_cars": 0,
    })
    assert resp.status_code >= 400


# ─── IT-06: Save headless result ─────────────────────────────────────────────

def test_save_headless_result_persists_to_history():
    """IT-06: POST /simulation/headless/save → saved item appears in GET /simulation/history."""
    result = _run_headless()

    save_resp = client.post("/simulation/headless/save", json={
        "name": "IT06 Run",
        "result": result,
    })
    assert save_resp.status_code == 200
    saved = save_resp.json()
    assert saved["name"] == "IT06 Run"

    history = client.get("/simulation/history").json()
    ids = [h["id"] for h in history]
    assert saved["id"] in ids


def test_save_headless_result_with_config_json():
    """IT-06 variant: saving with config_json stores the config string."""
    result = _run_headless()
    import json
    config_str = json.dumps({"algorithm": "priority", "max_steps": 60})

    save_resp = client.post("/simulation/headless/save", json={
        "name": "IT06 With Config",
        "result": result,
        "config_json": config_str,
    })
    assert save_resp.status_code == 200


def test_save_headless_default_name_when_omitted():
    """IT-06: omitting 'name' field uses the default 'Untitled'."""
    result = _run_headless()
    save_resp = client.post("/simulation/headless/save", json={"result": result})
    assert save_resp.status_code == 200
    assert save_resp.json()["name"] == "Untitled"


# ─── IT-07: Compare two algorithms ───────────────────────────────────────────

def test_compare_two_algorithms_returns_two_results():
    """IT-07: POST /simulation/compare with 2 algorithms → results list of length 2."""
    resp = client.post("/simulation/compare", json={
        "source": "generate",
        "width": 15,
        "height": 15,
        "rules": {"num_entries": 1, "num_exits": 1, "num_parking_spots": 10},
        "max_steps": 50,
        "initial_cars": 3,
        "arrival_lambda": 0.3,
        "exit_rate": 0.02,
        "planning_horizon": 50,
        "goal_reserve_horizon": 200,
        "max_arriving_cars": 0,
        "algorithms": ["priority", "lacam0"],
    })
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 2
    algo_names = {r["algorithm"] for r in results}
    assert "priority" in algo_names
    assert "lacam0" in algo_names


def test_compare_results_share_grid_dimensions():
    """IT-07: both comparison results must report the same grid dimensions."""
    resp = client.post("/simulation/compare", json={
        "source": "generate",
        "width": 12,
        "height": 12,
        "rules": {"num_entries": 1, "num_exits": 1, "num_parking_spots": 8},
        "max_steps": 30,
        "initial_cars": 2,
        "arrival_lambda": 0.2,
        "exit_rate": 0.02,
        "planning_horizon": 50,
        "goal_reserve_horizon": 200,
        "max_arriving_cars": 0,
        "algorithms": ["priority", "lacam0"],
    })
    assert resp.status_code == 200
    results = resp.json()["results"]
    widths  = {r["grid_width"]  for r in results}
    heights = {r["grid_height"] for r in results}
    assert len(widths)  == 1, "Both algorithms should run on the same grid width"
    assert len(heights) == 1, "Both algorithms should run on the same grid height"


def test_compare_missing_algorithms_field_returns_422():
    """IT-07 (negative): omitting 'algorithms' field → HTTP 422."""
    resp = client.post("/simulation/compare", json={
        "source": "generate",
        "width": 12, "height": 12,
        "rules": {"num_entries": 1, "num_exits": 1, "num_parking_spots": 5},
        "max_steps": 10,
        "initial_cars": 1,
        "arrival_lambda": 0.0,
        "exit_rate": 0.02,
        "planning_horizon": 50,
        "goal_reserve_horizon": 200,
        "max_arriving_cars": 0,
    })
    assert resp.status_code == 422
