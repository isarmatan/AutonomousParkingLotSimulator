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

    # exits are allowed to be shared
    non_exit_positions = [pos for pos in positions if not is_exit_cell(sim.grid, pos)]

    counts = Counter(non_exit_positions)
    conflicts = [(cell, c) for cell, c in counts.items() if c > 1]

    assert not conflicts, (
        f"[{scenario}] t={t} Vertex collision on non-exit cells: {conflicts} "
        f"| snapshot={sim.get_positions_snapshot()}"
    )


def assert_no_edge_swaps(prev, curr, grid, *, scenario, t):
    # Edge swap = A: u->v and B: v->u in the same timestep, on non-exit cells.
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
    # If a car is on an exit, it may:
    # 1) stay on an exit (same or another exit cell), or
    # 2) disappear from snapshot (if you remove it on completion)
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

def run_scenario(name, *, seed, rules_cfg, sim_cfg):
    print(f"\n=== Running scenario: {name} ===")

    random.seed(seed)

    rules = GeneratorRules(**rules_cfg)
    generator = ParkingLotGenerator(
        width=20,
        height=10,
        rules=rules
    )
    grid = generator.generate()

    parking_cells, exit_cells, entry_cells = extract_cells(grid)

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

    while True:
        if sim.time > 2000:
             # Dump debug info before failing
             print(f"\n[TIMEOUT DIAGNOSTIC] Active Cars: {len(sim.active_cars)}")
             for cid, car in sim.active_cars.items():
                 path_info = "No Path"
                 if car.has_path():
                     path_info = f"Path(len={len(car.path)}, curr={car.current_step})"
                 print(f"Car {cid}: Pos={car.current_position}, Intent={car.intent}, Goal={car.goal}, {path_info}")
             
             raise TimeoutError(f"Scenario {name} timed out at t={sim.time}")

        t = sim.time
        prev = sim.get_positions_snapshot().copy()

        sim.step()

        curr = sim.get_positions_snapshot()

        if t % 100 == 0:
            print(f"[PROGRESS] Scenario {name}: t={t}, active={len(sim.active_cars)}, parked={sim.total_parked}")

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

        # 1. Pure evacuation
        dict(
            name="pure_evacuate",
            seed=42,
            rules_cfg=dict(
                num_entries=2,
                num_exits=2,
                num_parking_spots=55
            ),
            sim_cfg=dict(
                planning_horizon=100,
                goal_reserve_horizon=200,
                arrival_lambda=0.0,
                max_arriving_cars=0,
                initial_parked_cars=0,
                initial_active_cars=10
            )
        ),

        # 2. Parking only
        dict(
            name="parking_only",
            seed=43,
            rules_cfg=dict(
                num_entries=2,
                num_exits=2,
                num_parking_spots=55
            ),
            sim_cfg=dict(
                planning_horizon=100,
                goal_reserve_horizon=200,
                arrival_lambda=0.3,
                max_arriving_cars=55,
                initial_parked_cars=0,
                initial_active_cars=0
            )
        ),

        # 3. Mixed load
        dict(
            name="mixed_load",
            seed=44,
            rules_cfg=dict(
                num_entries=2,
                num_exits=2,
                num_parking_spots=55
            ),
            sim_cfg=dict(
                planning_horizon=100,
                goal_reserve_horizon=200,
                arrival_lambda=0.2,
                max_arriving_cars=20,
                initial_parked_cars=10,
                initial_active_cars=10
            )
        ),

        # 4. Stress evacuation
        dict(
            name="stress_evacuate",
            seed=45,
            rules_cfg=dict(
                num_entries=2,
                num_exits=2,
                num_parking_spots=55
            ),
            sim_cfg=dict(
                planning_horizon=50,
                goal_reserve_horizon=100,
                arrival_lambda=0.0,
                max_arriving_cars=0,
                initial_parked_cars=0,
                initial_active_cars=15
            )
        ),
    ]

    for s in scenarios:
        run_scenario(**s)


if __name__ == "__main__":
    main()
