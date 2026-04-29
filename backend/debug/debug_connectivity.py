import random
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.append(str(ROOT))

from generator.parking_lot_generator import ParkingLotGenerator, GeneratorRules
from generator.cell import CellType


def extract_cells(grid):
    exits = []
    entries = []
    for row in grid.cells:
        for c in row:
            if c.type == CellType.EXIT:
                exits.append((c.x, c.y))
            elif c.type == CellType.ENTRY:
                entries.append((c.x, c.y))
    return exits, entries


def reachable_exits(grid, start, exits):
    # Match the planner constraints:
    # - cannot traverse ENTRY unless it's the start
    # - cannot traverse EXIT unless it's the goal (we will treat EXIT cells as terminals)

    q = deque([start])
    seen = {start}

    def ok_to_enter(nx, ny):
        cell = grid.get_cell(nx, ny)
        if not cell.is_drivable():
            return False
        if cell.type == CellType.ENTRY and (nx, ny) != start:
            return False
        return True

    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if not grid.in_bounds(nx, ny):
                continue
            if (nx, ny) in seen:
                continue
            if not ok_to_enter(nx, ny):
                continue
            seen.add((nx, ny))
            # We can continue BFS through drivable cells.
            # EXIT cells are drivable; reaching them means reachable.
            q.append((nx, ny))

    return [e for e in exits if e in seen], len(seen)


def main():
    seed = 103
    width = 25
    height = 15
    rules = GeneratorRules(num_entries=3, num_exits=3, num_parking_spots=120)

    random.seed(seed)
    grid = ParkingLotGenerator(width=width, height=height, rules=rules).generate()

    exits, entries = extract_cells(grid)
    print("seed", seed)
    print("exits", exits)
    print("entries", entries)

    # Position from the timeout diagnostic
    start = (14, 7)
    cell_type = grid.get_cell(*start).type
    print("start", start, "type", cell_type)

    re, seen_count = reachable_exits(grid, start, exits)
    print("reachable_exits", re)
    print("reachable_cell_count", seen_count)


if __name__ == "__main__":
    main()
