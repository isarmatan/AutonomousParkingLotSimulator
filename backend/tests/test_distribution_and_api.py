
import unittest
import random
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api_app import app
from db.database import Base
from db.deps import get_db
import db.models  # Register models
from generator.parking_lot_generator import ParkingLotGenerator, GeneratorRules
from generator.cell import CellType

# Setup in-memory DB for testing
# Use StaticPool to share the same in-memory database across all connections
SQLALCHEMY_DATABASE_URL = "sqlite://"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

class TestDistributionAndAPI(unittest.TestCase):
    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.client = TestClient(app)
        random.seed(42)

    def tearDown(self):
        Base.metadata.drop_all(bind=engine)

    def test_generator_distribution(self):
        """Verify that entries/exits are placed on different walls."""
        rules = GeneratorRules(num_entries=4, num_exits=4, num_parking_spots=10)
        # Use a grid large enough to have spots on all sides
        # 15x15
        width, height = 15, 15
        
        # Run multiple generations to ensure we see variety
        counts = {"TOP": 0, "BOTTOM": 0, "LEFT": 0, "RIGHT": 0}
        
        for _ in range(20):
            generator = ParkingLotGenerator(width, height, rules)
            grid = generator.generate()
            
            for y in range(height):
                for x in range(width):
                    c = grid.get_cell(x, y)
                    if c.type in (CellType.ENTRY, CellType.EXIT):
                        if y == 0: counts["TOP"] += 1
                        elif y == height - 1: counts["BOTTOM"] += 1
                        elif x == 0: counts["LEFT"] += 1
                        elif x == width - 1: counts["RIGHT"] += 1
        
        print(f"Distribution over 20 runs (Total 160 items): {counts}")
        
        # We expect significant counts on all sides
        self.assertGreater(counts["TOP"], 0)
        self.assertGreater(counts["LEFT"], 0)
        self.assertGreater(counts["RIGHT"], 0)
        # Bottom might be lower depending on parity, but with 15x15 (odd), it should be fine.
        self.assertGreater(counts["BOTTOM"], 0)

    def test_api_saved_lots_metadata(self):
        """Verify GET /editor/saved returns correct metadata."""
        # 1. Create a draft with known stats
        # We'll use the generator via the API to make it easier, 
        # or just construct a grid manually if we want precise control.
        # Let's use 'generate' endpoint.
        
        gen_payload = {
            "source": "generate",
            "width": 10,
            "height": 10,
            "rules": {
                "num_entries": 2,
                "num_exits": 1,
                "num_parking_spots": 5
            }
        }
        res = self.client.post("/editor/drafts", json=gen_payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        draft_id = data["draftId"]
        grid = data["grid"]
        
        # Count actual stats from the generated grid to be sure
        actual_entries = sum(1 for c in grid["cells"] if c["type"] == "ENTRY")
        actual_exits = sum(1 for c in grid["cells"] if c["type"] == "EXIT")
        actual_spots = sum(1 for c in grid["cells"] if c["type"] == "PARKING")
        
        # 2. Save it
        save_payload = {"name": "Test Lot 1"}
        res = self.client.post(f"/editor/drafts/{draft_id}:save", json=save_payload)
        self.assertEqual(res.status_code, 200)
        
        # 3. List saved lots
        res = self.client.get("/editor/saved")
        self.assertEqual(res.status_code, 200)
        saved_list = res.json()["items"]
        
        self.assertEqual(len(saved_list), 1)
        item = saved_list[0]
        
        self.assertEqual(item["name"], "Test Lot 1")
        self.assertEqual(item["width"], 10)
        self.assertEqual(item["height"], 10)
        self.assertEqual(item["num_entries"], actual_entries)
        self.assertEqual(item["num_exits"], actual_exits)
        self.assertEqual(item["capacity"], actual_spots)

if __name__ == "__main__":
    unittest.main()
