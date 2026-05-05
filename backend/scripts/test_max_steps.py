
import sys
import json
import urllib.request
import urllib.error
import time
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

API_URL = "http://127.0.0.1:8000"

def run_simulation(max_steps, name):
    print(f"\n--- Testing {name} (max_steps={max_steps}) ---")
    payload = {
        "source": "generate",
        "width": 10,
        "height": 10,
        "rules": {
            "num_entries": 1,
            "num_exits": 1,
            "num_parking_spots": 5
        },
        "planning_horizon": 20,
        "arrival_lambda": 0.5,
        "max_arriving_cars": 2,
        "initial_parked_cars": 1,
        "initial_active_cars": 0,
        "max_steps": max_steps
    }
    
    req = urllib.request.Request(
        f"{API_URL}/simulation/run", 
        data=json.dumps(payload).encode("utf-8"), 
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode("utf-8"))
            meta = data["meta"]
            print(f"Status: {meta.get('status')}")
            print(f"Message: {meta.get('message')}")
            print(f"Total Steps: {meta.get('total_steps')}")
            return meta
            
    except urllib.error.URLError as e:
        print(f"Error: {e}")
        return None

def main():
    # 1. Test short run (should fail to complete)
    meta_short = run_simulation(max_steps=5, name="Short Run")
    if meta_short and meta_short.get("status") == "MAX_STEPS_REACHED":
        print("PASS: Short run correctly identified as incomplete.")
    else:
        print("FAIL: Short run should be incomplete.")

    # 2. Test long run (should complete)
    # 2 cars + 1 parked, small grid. Should finish in < 200 steps easily.
    meta_long = run_simulation(max_steps=500, name="Long Run")
    if meta_long and meta_long.get("status") == "COMPLETED":
        print("PASS: Long run correctly identified as completed.")
    else:
        print("FAIL: Long run should be completed.")

if __name__ == "__main__":
    main()
