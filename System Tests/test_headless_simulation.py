import sys, os
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_project_root, "backend"))

import pytest
from fastapi.testclient import TestClient
from api_app import app

client = TestClient(app)

# ─── Shared base payload ───────────────────────────────────────────────────────

_BASE = {
    "source": "generate",
    "width": 20,
    "height": 20,
    "rules": {"num_entries": 1, "num_exits": 1, "num_parking_spots": 20},
    "algorithm": "priority",
    "max_steps": 100,
    "initial_cars": 5,
    "arrival_lambda": 0.3,
    "exit_rate": 0.02,
    "planning_horizon": 50,
    "goal_reserve_horizon": 200,
    "max_arriving_cars": 0,
}


def _post(overrides: dict | None = None) -> dict:
    payload = {**_BASE, **(overrides or {})}
    resp = client.post("/simulation/headless", json=payload)
    return resp


# ─── UT-01: generate + priority ───────────────────────────────────────────────

def test_headless_generate_priority_returns_200():
    """UT-01: generate source with priority planner → HTTP 200 + key fields."""
    resp = _post()
    assert resp.status_code == 200
    data = resp.json()
    assert data["algorithm"] == "priority"
    assert data["grid_width"] == 20
    assert data["grid_height"] == 20
    assert "completed_steps" in data
    assert "stopped_reason" in data
    assert "total_exited" in data


# ─── UT-07: lacam0 ────────────────────────────────────────────────────────────

def test_headless_lacam0_returns_correct_algorithm():
    """UT-07: algorithm='lacam0' → result.algorithm == 'lacam0'."""
    resp = _post({"algorithm": "lacam0"})
    assert resp.status_code == 200
    assert resp.json()["algorithm"] == "lacam0"


# ─── UT-08: lns2 ──────────────────────────────────────────────────────────────

def test_headless_lns2_returns_correct_algorithm():
    """UT-08: algorithm='lns2' → result.algorithm == 'lns2'."""
    resp = _post({"algorithm": "lns2"})
    assert resp.status_code == 200
    assert resp.json()["algorithm"] == "lns2"


# ─── UT-09: unknown algorithm ─────────────────────────────────────────────────

def test_headless_unknown_algorithm_is_rejected():
    """UT-09: unknown algorithm string → non-2xx (server rejects it)."""
    safe_client = TestClient(app, raise_server_exceptions=False)
    payload = {**_BASE, "algorithm": "bogus_algo"}
    resp = safe_client.post("/simulation/headless", json=payload)
    assert resp.status_code >= 400


# ─── UT-03: missing required field ────────────────────────────────────────────

def test_headless_empty_body_returns_422():
    """UT-03: empty body → HTTP 422 (Pydantic validation)."""
    resp = client.post("/simulation/headless", json={})
    assert resp.status_code == 422


def test_headless_missing_max_steps_returns_422():
    """max_steps is required; omitting it → HTTP 422."""
    payload = {k: v for k, v in _BASE.items() if k != "max_steps"}
    resp = client.post("/simulation/headless", json=payload)
    assert resp.status_code == 422


# ─── UT-04: max_steps = 1 edge case ──────────────────────────────────────────

def test_headless_max_steps_1_completes_one_step():
    """UT-04: max_steps=1 → completed_steps == 1."""
    resp = _post({"max_steps": 1})
    assert resp.status_code == 200
    assert resp.json()["completed_steps"] == 1


# ─── UT-05: stops at max_steps ────────────────────────────────────────────────

def test_headless_never_exceeds_max_steps():
    """UT-05: completed_steps is always ≤ max_steps regardless of config."""
    max_steps = 30
    resp = _post({"max_steps": max_steps, "arrival_lambda": 1.0, "initial_cars": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert data["completed_steps"] <= max_steps
    assert data["stopped_reason"] in ("max_steps_reached", "all_cars_completed")


# ─── UT-10: stats are non-negative ────────────────────────────────────────────

def test_headless_result_stats_are_non_negative():
    """UT-10: numeric stat fields must never be negative."""
    resp = _post()
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_exited"] >= 0
    assert data["total_failed_plans"] >= 0
    assert data["completed_steps"] >= 0
    assert data["arriving_cars_spawned"] >= 0
    assert data["arriving_cars_parked"] >= 0
    if data.get("avg_planner_ms") is not None:
        assert data["avg_planner_ms"] >= 0


# ─── Grid dimensions match request ────────────────────────────────────────────

def test_headless_grid_dimensions_match_request():
    """Result grid dimensions must equal the requested width/height."""
    resp = _post({"width": 15, "height": 12})
    assert resp.status_code == 200
    data = resp.json()
    assert data["grid_width"] == 15
    assert data["grid_height"] == 12


# ─── All three algorithms produce valid results ────────────────────────────────

@pytest.mark.parametrize("algo", ["priority", "lacam0", "lns2"])
def test_all_algorithms_return_valid_result(algo):
    """UT-06/07/08 parametrized: each algorithm returns a valid result."""
    resp = _post({"algorithm": algo, "max_steps": 50})
    assert resp.status_code == 200
    data = resp.json()
    assert data["algorithm"] == algo
    assert data["completed_steps"] <= 50
