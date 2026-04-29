
import sys
import json
from pathlib import Path
from fastapi.testclient import TestClient

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

from api_app import app

def main():
    client = TestClient(app)
    
    print("Requesting GET /editor/saved ...")
    response = client.get("/editor/saved")
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        return

    data = response.json()
    
    # Pretty print the JSON
    formatted_json = json.dumps(data, indent=2)
    
    output_file = ROOT / "saved_lots_response.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("Response from GET /editor/saved:\n")
        f.write("================================\n")
        f.write(formatted_json)
        f.write("\n")
    
    print(f"Response saved to {output_file}")
    print(formatted_json)

if __name__ == "__main__":
    main()
