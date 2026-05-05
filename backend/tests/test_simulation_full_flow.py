import json
import sys
import os

# Add the project root to the python path so imports work
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from api_app import app

def test_simulation_generate_and_run():
    client = TestClient(app)

    payload = {
        "source": "generate",
        "width": 100,
        "height": 10,
        "rules": {
            "num_entries": 1,
            "num_exits": 1,
            "num_parking_spots": 15
        },
        "planning_horizon": 50,
        "arrival_lambda": 0.5,
        "max_arriving_cars": 0,
        "initial_parked_cars": 0,
        "initial_active_cars": 15,
        "max_steps": 100
    }

    print("Sending simulation request...")
    response = client.post("/simulation/run", json=payload)

    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        return

    data = response.json()
    
    print("\n--- Simulation Response (Subset) ---")
    print(f"Meta: {json.dumps(data['meta'], indent=2)}")
    
    print(f"\nNumber of Timesteps: {len(data['timesteps'])}")
    if data['timesteps']:
        print("First Timestep Cars:", data['timesteps'][0]['cars'])
        print("Last Timestep Cars:", data['timesteps'][-1]['cars'])

    # --- Save to File ---
    output_filename = "simulation_test_result.txt"
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write("Simulation Test Results\n")
        f.write("=======================\n\n")
        
        f.write("Meta Information:\n")
        f.write(json.dumps(data['meta'], indent=2))
        f.write("\n\n")

        f.write("Generated Grid:\n")
        f.write("---------------\n")
        grid_data = data['grid']
        width = grid_data['width']
        height = grid_data['height']
        cells = grid_data['cells']
        
        # Build grid char map
        # Flatten list of cells for easy lookup if needed, but they usually come in order or we can just iterate
        # The API returns a list of cells. Let's map (x,y) -> type
        grid_map = {}
        for c in cells:
            grid_map[(c['x'], c['y'])] = c['type']
            
        symbols = {
            "WALL": "#",
            "ROAD": ".",
            "PARKING": "P",
            "ENTRY": "E",
            "EXIT": "X"
        }

        for y in range(height):
            row_str = ""
            for x in range(width):
                ctype = grid_map.get((x, y), "UNKNOWN")
                row_str += symbols.get(ctype, "?") + " "
            f.write(row_str + "\n")
        
        f.write("\n")
        f.write("Full JSON Response:\n")
        f.write("-------------------\n")
        f.write(json.dumps(data, indent=2))
    
    print(f"\nResults saved to {output_filename}")

if __name__ == "__main__":
    test_simulation_generate_and_run()
