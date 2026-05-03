
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))

from generator.parking_lot_generator import ParkingLotGenerator, GeneratorRules
from generator.cell import CellType

def main():
    rules_cfg = dict(
        num_entries=2,
        num_exits=2,
        num_parking_spots=55
    )
    rules = GeneratorRules(**rules_cfg)
    # Use the same seed and dimensions as pure_evacuate
    import random
    random.seed(42)
    generator = ParkingLotGenerator(width=20, height=10, rules=rules)
    grid = generator.generate()

    print("Map Layout:")
    for y in range(grid.height):
        row_str = ""
        for x in range(grid.width):
            cell = grid.get_cell(x, y)
            char = "."
            if cell.type == CellType.WALL: char = "#"
            elif cell.type == CellType.PARKING: char = "P"
            elif cell.type == CellType.ENTRY: char = "E"
            elif cell.type == CellType.EXIT: char = "X"
            
            if (x, y) == (8, 0):
                char = "!" # The problematic cell
            elif (x, y) == (8, 1):
                char = "?" # The stuck car

            row_str += char
        print(f"{y:2d} {row_str}")

    cell_8_0 = grid.get_cell(8, 0)
    print(f"\nCell (8, 0) Type: {cell_8_0.type}")
    print(f"Cell (8, 0) Drivable: {cell_8_0.is_drivable()}")

if __name__ == "__main__":
    main()
