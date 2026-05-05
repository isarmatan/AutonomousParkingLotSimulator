import argparse
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.append(str(ROOT))

from core.simulation_core import SimulationCore, SimulationConfig
from core.parking_manager import ParkingManager
from planning.priority_planner import PriorityPlanner
from planning.reservation_table import ReservationTable
from generator.cell import CellType
from generator.parking_lot_generator import ParkingLotGenerator, GeneratorRules


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


def run_once(args):
    random.seed(args.seed)

    rules = GeneratorRules(
        num_entries=args.num_entries,
        num_exits=args.num_exits,
        num_parking_spots=args.num_parking_spots,
    )
    grid = ParkingLotGenerator(width=args.width, height=args.height, rules=rules).generate()
    parking_cells, exit_cells, entry_cells = extract_cells(grid)

    pm = ParkingManager(
        grid=grid,
        parking_cells=parking_cells,
        exit_cells=exit_cells,
        entry_cells=entry_cells,
    )

    rt = ReservationTable()
    planner = PriorityPlanner(grid=grid, reservation_table=rt, planning_horizon=args.planning_horizon)

    timing = {
        "init": 0.0,
        "advance": 0.0,
        "arrival": 0.0,
        "total": 0.0,
        "plan_calls": 0,
        "plan_time": 0.0,
        "plan_ok": 0,
        "plan_fail": 0,
    }

    original_plan_for_car = planner.plan_for_car

    def wrapped_plan_for_car(car, current_time, obstacles=None, obstacle_persistence=20):
        t0 = time.perf_counter()
        ok = original_plan_for_car(
            car,
            current_time,
            obstacles=obstacles,
            obstacle_persistence=obstacle_persistence,
        )
        t1 = time.perf_counter()
        timing["plan_calls"] += 1
        timing["plan_time"] += (t1 - t0)
        if ok:
            timing["plan_ok"] += 1
        else:
            timing["plan_fail"] += 1
        return ok

    planner.plan_for_car = wrapped_plan_for_car

    config = SimulationConfig(
        planning_horizon=args.planning_horizon,
        goal_reserve_horizon=args.goal_reserve_horizon,
        arrival_lambda=args.arrival_lambda,
        max_arriving_cars=args.max_arriving_cars,
        initial_parked_cars=args.initial_parked_cars,
        initial_active_cars=args.initial_active_cars,
    )

    start_wall = time.perf_counter()
    t_init0 = time.perf_counter()
    sim = SimulationCore(grid=grid, parking_manager=pm, priority_planner=planner, config=config)
    t_init1 = time.perf_counter()
    timing["init"] = (t_init1 - t_init0)

    last_snapshot = sim.get_positions_snapshot().copy()
    no_change_steps = 0

    while True:
        if sim.time >= args.max_steps:
            break

        t_step0 = time.perf_counter()

        t0 = time.perf_counter()
        sim._advance_cars()
        t1 = time.perf_counter()
        timing["advance"] += (t1 - t0)

        t0 = time.perf_counter()
        sim._maybe_poisson_arrival()
        t1 = time.perf_counter()
        timing["arrival"] += (t1 - t0)

        sim.time += 1

        t_step1 = time.perf_counter()
        timing["total"] += (t_step1 - t_step0)

        snapshot = sim.get_positions_snapshot()
        if snapshot == last_snapshot:
            no_change_steps += 1
        else:
            no_change_steps = 0
            last_snapshot = snapshot.copy()

        if args.progress_every and sim.time % args.progress_every == 0:
            print(
                f"[PROGRESS] t={sim.time} active={len(sim.active_cars)} parked={sim.total_parked} "
                f"created={sim.arriving_cars_created}/{config.max_arriving_cars} "
                f"plan_calls={timing['plan_calls']}"
            )

        if args.stall_steps and no_change_steps >= args.stall_steps and len(sim.active_cars) > 0:
            print(f"\n[STALL] No position changes for {no_change_steps} steps at t={sim.time}")
            print(
                f"active={len(sim.active_cars)} parked={sim.total_parked} "
                f"free_spots={len(sim.parking_manager.free_spots)} assigned={len(sim.parking_manager.assigned_spots)} "
                f"vertex_res={len(sim.priority_planner.reservation_table.vertex_reservations)} "
                f"edge_res={len(sim.priority_planner.reservation_table.edge_reservations)}"
            )
            shown = 0
            for cid, car in sim.active_cars.items():
                if shown >= 30:
                    print("... (more cars hidden)")
                    break
                plan_info = "no_path" if not car.has_path() else f"path_len={len(car.path)} step={car.current_step}"
                print(
                    f"car {cid} pos={car.current_position} intent={car.intent} goal={car.goal} "
                    f"fails={getattr(car, 'plan_fail_count', '?')} {plan_info}"
                )
                shown += 1
            if args.break_on_stall:
                break

        if not sim.active_cars and sim.arriving_cars_created >= config.max_arriving_cars:
            break

        if not sim.active_cars and not sim.parking_manager.free_spots and sim.arriving_cars_created < config.max_arriving_cars:
            break

    end_wall = time.perf_counter()

    print("\n=== SUMMARY ===")
    print(
        {
            "final_time": sim.time,
            "active": len(sim.active_cars),
            "parked": sim.total_parked,
            "arrivals_created": sim.arriving_cars_created,
            "total_arrived": sim.total_arrived,
            "total_planned": sim.total_planned,
            "total_failed_plans": sim.total_failed_plans,
        }
    )

    wall = end_wall - start_wall
    print(
        {
            "wall_s": round(wall, 3),
            "init_s": round(timing["init"], 3),
            "step_total_s": round(timing["total"], 3),
            "advance_s": round(timing["advance"], 3),
            "arrival_s": round(timing["arrival"], 3),
            "plan_calls": timing["plan_calls"],
            "plan_time_s": round(timing["plan_time"], 3),
            "plan_ok": timing["plan_ok"],
            "plan_fail": timing["plan_fail"],
        }
    )


def parse_args():
    p = argparse.ArgumentParser()

    p.add_argument("--seed", type=int, default=123)

    p.add_argument("--width", type=int, default=35)
    p.add_argument("--height", type=int, default=25)

    p.add_argument("--num-entries", type=int, default=3)
    p.add_argument("--num-exits", type=int, default=3)
    p.add_argument("--num-parking-spots", type=int, default=150)

    p.add_argument("--planning-horizon", type=int, default=150)
    p.add_argument("--goal-reserve-horizon", type=int, default=300)

    p.add_argument("--arrival-lambda", type=float, default=0.6)
    p.add_argument("--max-arriving-cars", type=int, default=70)

    p.add_argument("--initial-parked-cars", type=int, default=40)
    p.add_argument("--initial-active-cars", type=int, default=10)

    p.add_argument("--max-steps", type=int, default=6000)
    p.add_argument("--progress-every", type=int, default=100)

    p.add_argument("--stall-steps", type=int, default=400)
    p.add_argument("--break-on-stall", action="store_true")

    return p.parse_args()


def main():
    args = parse_args()
    run_once(args)


if __name__ == "__main__":
    main()
