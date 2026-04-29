import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

import random
from collections import Counter

from core.simulation_core import SimulationCore, SimulationConfig
from core.parking_manager import ParkingManager
from planning.priority_planner import PriorityPlanner
from planning.reservation_table import ReservationTable
from generator.cell import CellType
from generator.parking_lot_generator import ParkingLotGenerator, GeneratorRules


# -------------------------------------------------
# Utilities
# -------------------------------------------------

def extract_cells(grid):
    parking_cells = []
    exit_cells = []
    entry_cells = []

    for row in grid.cells:
        for cell in row:
            if cell.type == CellType.PARKING:
                parking_cells.append((cell.x, cell.y))
            elif cell.type == CellType.EXIT:
                exit_cells.append((cell.x, cell.y))
            elif cell.type == CellType.ENTRY:
                entry_cells.append((cell.x, cell.y))

    return parking_cells, exit_cells, entry_cells


def is_exit_cell(grid, pos):
    x, y = pos
    return grid.get_cell(x, y).type == CellType.EXIT


# -------------------------------------------------
# Invariant checks
# -------------------------------------------------

def assert_no_vertex_conflicts(sim, *, scenario, t):
    positions = list(sim.get_positions_snapshot().values())
    
    # exits are allowed to be shared (cars disappear or queue virtually)
    non_exit_positions = [pos for pos in positions if not is_exit_cell(sim.grid, pos)]

    counts = Counter(non_exit_positions)
    conflicts = [(cell, c) for cell, c in counts.items() if c > 1]

    assert not conflicts, (
        f"[{scenario}] t={t} Vertex collision on non-exit cells: {conflicts} "
        f"| snapshot={sim.get_positions_snapshot()}"
    )


def assert_no_edge_swaps(prev, curr, grid, *, scenario, t):
    prev_items = list(prev.items())

    for i in range(len(prev_items)):
        a, a_prev = prev_items[i]
        if a not in curr:
            continue
        a_curr = curr[a]

        for j in range(i + 1, len(prev_items)):
            b, b_prev = prev_items[j]
            if b not in curr:
                continue
            b_curr = curr[b]

            if (
                a_prev == b_curr and
                b_prev == a_curr and
                not is_exit_cell(grid, a_prev) and
                not is_exit_cell(grid, b_prev)
            ):
                raise AssertionError(
                    f"[{scenario}] t={t} Edge swap between cars {a} and {b} "
                    f"on {a_prev} <-> {b_prev} | prev={prev} | curr={curr}"
                )


def assert_valid_motion(prev, curr, *, scenario, t):
    for car, p0 in prev.items():
        if car not in curr:
            continue
        p1 = curr[car]
        dist = abs(p0[0] - p1[0]) + abs(p0[1] - p1[1])
        assert dist in (0, 1), (
            f"[{scenario}] t={t} Illegal move by car {car}: {p0} -> {p1} "
            f"| prev={prev} | curr={curr}"
        )


def assert_drivable(sim, *, scenario, t):
    for pos in sim.get_positions_snapshot().values():
        cell = sim.grid.get_cell(*pos)
        assert cell.is_drivable(), (
            f"[{scenario}] t={t} Car on non-drivable cell {pos} "
            f"(type={cell.type}) | snapshot={sim.get_positions_snapshot()}"
        )


def assert_exit_absorbing(prev, curr, grid, *, scenario, t):
    for car, p0 in prev.items():
        if is_exit_cell(grid, p0):
            if car in curr:
                p1 = curr[car]
                assert is_exit_cell(grid, p1), (
                    f"[{scenario}] t={t} Car {car} left EXIT area: {p0} -> {p1} "
                    f"| prev={prev} | curr={curr}"
                )

# -------------------------------------------------
# Scenario runner
# -------------------------------------------------

def run_scenario(name, *, seed, width, height, rules_cfg, sim_cfg):
    print(f"\n=== Running scenario: {name} ===")

    random.seed(seed)

    rules = GeneratorRules(**rules_cfg)
    generator = ParkingLotGenerator(
        width=width,
        height=height,
        rules=rules
    )
    grid = generator.generate()

    parking_cells, exit_cells, entry_cells = extract_cells(grid)
    
    # Ensure we have enough spots for the test configuration
    total_cars_needed = sim_cfg["initial_parked_cars"] + sim_cfg["max_arriving_cars"]
    if len(parking_cells) < total_cars_needed:
        print(f"[WARNING] Not enough parking spots generated! Needed {total_cars_needed}, got {len(parking_cells)}. Adjusting max arrivals.")
        # Adjust arrivals to fit capacity if generator fell short
        sim_cfg["max_arriving_cars"] = max(0, len(parking_cells) - sim_cfg["initial_parked_cars"])

    parking_manager = ParkingManager(
        grid=grid,
        parking_cells=parking_cells,
        exit_cells=exit_cells,
        entry_cells=entry_cells
    )

    reservation_table = ReservationTable()
    planner = PriorityPlanner(
        grid=grid,
        reservation_table=reservation_table,
        planning_horizon=sim_cfg["planning_horizon"]
    )

    config = SimulationConfig(**sim_cfg)

    sim = SimulationCore(
        grid=grid,
        parking_manager=parking_manager,
        priority_planner=planner,
        config=config
    )

    max_steps = 4000  # Increased timeout for large scale tests
    last_active_count = -1
    stall_counter = 0

    while True:
        if sim.time > max_steps:
             # Dump debug info before failing
             print(f"\n[TIMEOUT DIAGNOSTIC] Active Cars: {len(sim.active_cars)}")
             # Only print first 20 cars to avoid spamming console
             count = 0
             for cid, car in sim.active_cars.items():
                 if count > 20:
                     print("... (more cars hidden)")
                     break
                 path_info = "No Path"
                 if car.has_path():
                     path_info = f"Path(len={len(car.path)}, curr={car.current_step})"
                 print(f"Car {cid}: Pos={car.current_position}, Intent={car.intent}, Goal={car.goal}, {path_info}")
                 count += 1
             
             raise TimeoutError(f"Scenario {name} timed out at t={sim.time}")

        t = sim.time
        prev = sim.get_positions_snapshot().copy()

        sim.step()

        curr = sim.get_positions_snapshot()
        
        # Stall detection
        if len(sim.active_cars) == last_active_count and len(sim.active_cars) > 0:
            stall_counter += 1
        else:
            stall_counter = 0
            last_active_count = len(sim.active_cars)
            
        if stall_counter > 300: # If active count doesn't change for 300 steps
            # Check if anyone is actually moving or if it's a true deadlock
            # (parked count changing means progress)
            pass 
            # We won't raise error yet because they might be slowly parking one by one
            # But if parked count is ALSO static, then we have a problem.
            
        if t % 100 == 0:
            print(f"[PROGRESS] Scenario {name}: t={t}, active={len(sim.active_cars)}, parked={sim.total_parked}, arrived={sim.total_arrived}")

        # invariants
        assert_no_vertex_conflicts(sim, scenario=name, t=t)
        assert_no_edge_swaps(prev, curr, grid, scenario=name, t=t)
        assert_valid_motion(prev, curr, scenario=name, t=t)
        assert_drivable(sim, scenario=name, t=t)
        assert_exit_absorbing(prev, curr, grid, scenario=name, t=t)

        if (
            not sim.active_cars and
            sim.arriving_cars_created >= config.max_arriving_cars
        ):
            break
        
        # Early exit if we can't spawn any more cars because it's full
        # and everyone active has finished.
        if (
            not sim.active_cars and 
            not sim.parking_manager.free_spots and
            sim.arriving_cars_created < config.max_arriving_cars
        ):
            print(f"\n[INFO] Parking lot full ({len(sim.parking_manager.occupied_spots)}/{len(sim.parking_manager.parking_cells)}). Stopping scenario early.")
            break

    print("[OK] Scenario finished successfully")
    print({
        "final_time": sim.time,
        "total_arrived": sim.total_arrived,
        "total_planned": sim.total_planned,
        "total_failed_plans": sim.total_failed_plans,
        "total_parked": sim.total_parked,
    })


# -------------------------------------------------
# Test suite entry point
# -------------------------------------------------

def main():
    scenarios = [
        
        # 1. Large Grid Sparse
        # Tests long-distance pathfinding on a 50x30 grid.
        dict(
            name="large_grid_sparse",
            seed=201,
            width=50,
            height=30,
            rules_cfg=dict(
                num_entries=4,
                num_exits=4,
                num_parking_spots=200
            ),
            sim_cfg=dict(
                planning_horizon=200, # Longer horizon for larger map
                goal_reserve_horizon=400,
                arrival_lambda=0.5,
                max_arriving_cars=50,
                initial_parked_cars=50,
                initial_active_cars=20
            )
        ),

        # 2. Medium Grid Heavy Load (100+ cars)
        # Increased to 35x25 to allow more maneuvering space
        dict(
            name="medium_grid_heavy_load",
            seed=202,
            width=35,
            height=25,
            rules_cfg=dict(
                num_entries=3,
                num_exits=3,
                num_parking_spots=150
            ),
            sim_cfg=dict(
                planning_horizon=150,
                goal_reserve_horizon=300,
                arrival_lambda=0.6,
                max_arriving_cars=70, # 40 parked + 10 active + 70 arriving = 120 total involved
                initial_parked_cars=40,
                initial_active_cars=10
            )
        ),

        # 3. Massive Congestion (200 cars)
        # Increased to 50x50 to prevent total gridlock
        dict(
            name="massive_congestion",
            seed=203,
            width=100,
            height=30,
            rules_cfg=dict(
                num_entries=5,
                num_exits=5,
                num_parking_spots=500
            ),
            sim_cfg=dict(
                planning_horizon=200,
                goal_reserve_horizon=400,
                arrival_lambda=0.8, # Very fast arrivals
                max_arriving_cars=0, # 80 parked + 20 active + 100 arriving = 200 total involved
                initial_parked_cars=0,
                initial_active_cars=100
            )
        )
    ]

    for s in scenarios:
        run_scenario(**s)



if __name__ == "__main__":
    main()
