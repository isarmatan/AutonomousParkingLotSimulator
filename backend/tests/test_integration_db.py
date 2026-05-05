import pytest
from fastapi.testclient import TestClient
from api_app import app
from db.database import init_db
import os

client = TestClient(app)

# Ensure DB is initialized
init_db()

def test_full_db_persistence_flow():
    # 1. Create a blank draft
    print("1. Creating draft...")
    create_resp = client.post("/editor/drafts", json={
        "source": "blank",
        "width": 10,
        "height": 10
    })
    if create_resp.status_code != 200:
        print(f"Create failed: {create_resp.status_code} {create_resp.text}")
    assert create_resp.status_code == 200
    draft_id = create_resp.json()["draftId"]
    print(f"Draft ID: {draft_id}")

    # 2. Add required cells (Entry, Exit, Parking) to make it valid
    print("2. Applying actions...")
    actions = [
        # Entry/Exit (Boundaries)
        {"type": "PLACE_ENTRY", "x": 0, "y": 1},
        {"type": "PLACE_EXIT", "x": 0, "y": 2},
        
        # Roads for connectivity
        {"type": "PAINT", "x": 1, "y": 1, "cellType": "ROAD"},
        {"type": "PAINT", "x": 1, "y": 2, "cellType": "ROAD"},
        {"type": "PAINT", "x": 2, "y": 1, "cellType": "ROAD"},
        {"type": "PAINT", "x": 2, "y": 2, "cellType": "ROAD"},
        {"type": "PAINT", "x": 2, "y": 3, "cellType": "ROAD"},
        {"type": "PAINT", "x": 3, "y": 1, "cellType": "ROAD"},
        {"type": "PAINT", "x": 3, "y": 2, "cellType": "ROAD"},
        {"type": "PAINT", "x": 3, "y": 3, "cellType": "ROAD"},
        
        # Multiple Parking Spots (Interior)
        {"type": "PLACE_PARKING", "x": 4, "y": 1},
        {"type": "PLACE_PARKING", "x": 4, "y": 2},
        {"type": "PLACE_PARKING", "x": 4, "y": 3},
        
        # Multiple Walls (Interior)
        {"type": "PAINT", "x": 5, "y": 1, "cellType": "WALL"},
        {"type": "PAINT", "x": 5, "y": 2, "cellType": "WALL"},
        {"type": "PAINT", "x": 5, "y": 3, "cellType": "WALL"}
    ]
    
    for action in actions:
        resp = client.post(f"/editor/drafts/{draft_id}/actions:apply", json={"action": action})
        if resp.status_code != 200:
             print(f"Action failed: {resp.status_code} {resp.text}")
        assert resp.status_code == 200
        data = resp.json()
        if not data["ok"]:
            print(f"Action failed logic: {action} -> {data['error']}")
        assert data["ok"] is True

    # 3. Save the draft
    print("3. Saving draft...")
    lot_name = "Integration Test Lot " + str(os.urandom(4).hex())
    save_resp = client.post(f"/editor/drafts/{draft_id}:save", json={
        "name": lot_name
    })
    
    if save_resp.status_code != 200:
        print(f"Save failed: {save_resp.status_code} {save_resp.text}")
    assert save_resp.status_code == 200
    
    save_data = save_resp.json()
    if not save_data["ok"]:
        print("\nSave logic failed with errors:", save_data["errors"])
        
    assert save_data["ok"] is True
    saved_id = save_data["parkingLotId"]
    assert saved_id is not None
    print(f"Saved ID: {saved_id}")

    # 4. List saved lots and verify it's there
    print("4. Listing saved...")
    list_resp = client.get("/editor/saved")
    if list_resp.status_code != 200:
        print(f"List failed: {list_resp.status_code} {list_resp.text}")
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    
    found = next((item for item in items if item["id"] == saved_id), None)
    assert found is not None
    assert found["name"] == lot_name

    # 5. Load the saved lot back into a NEW draft
    print("5. Loading saved...")
    load_resp = client.post("/editor/drafts", json={
        "source": "load",
        "parkingLotId": saved_id
    })
    if load_resp.status_code != 200:
        print(f"Load failed: {load_resp.status_code} {load_resp.text}")
    assert load_resp.status_code == 200
    new_grid = load_resp.json()["grid"]
    
    # Verify content (spot check)
    cells = new_grid["cells"]
    # Check for the parking spot at (4,1)
    parking_cell = next((c for c in cells if c["x"]==4 and c["y"]==1), None)
    print(f"Checking cell at 4,1: {parking_cell}")
    assert parking_cell is not None
    assert parking_cell["type"] == "PARKING"

    # 6. Run simulation on the saved lot
    print("6. Running simulation...")
    sim_resp = client.post("/simulation/run", json={
        "source": "load",
        "parkingLotId": saved_id,
        "planning_horizon": 10,
        "arrival_lambda": 0.0, # No new cars, just checking load
        "max_steps": 5,
        "initial_parked_cars": 0,
        "initial_active_cars": 0
    })
    if sim_resp.status_code != 200:
         print(f"Sim failed: {sim_resp.status_code} {sim_resp.text}")
    assert sim_resp.status_code == 200
    assert sim_resp.json()["meta"]["total_steps"] >= 0

if __name__ == "__main__":
    # If run directly, clean up DB file first to avoid name collisions if re-run
    if os.path.exists("./parking_lots.db"):
        os.remove("./parking_lots.db")
    init_db()
    test_full_db_persistence_flow()
    print("DB Integration Test Passed!")
