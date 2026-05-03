# from generator.parking_lot_generator import ParkingLotGenerator
# from generator.rules import GeneratorRules
# from generator.cell import CellType

def print_grid(grid):
     symbols = {
         CellType.WALL: "#",
        CellType.ROAD: "=",
         CellType.PARKING: "@",
         CellType.ENTRY: "E",
         CellType.EXIT: "X"
     }

     for y in range(grid.height):
         for x in range(grid.width):
             print(symbols[grid.get_cell(x, y).type], end="")
         print()

# rules = GeneratorRules(
#     num_entries=2,
#     num_exits=2,
#     num_parking_spots=1444
# )

# generator = ParkingLotGenerator(
#     width=80,
#     height=40,
#     rules=rules
# )

# grid = generator.generate()
# print_grid(grid)

# main.py
import random

from core.simulation_core import SimulationCore, SimulationConfig
from core.parking_manager import ParkingManager
from planning.priority_planner import PriorityPlanner
from planning.reservation_table import ReservationTable
from generator.grid import Grid
from generator.cell import CellType
from generator.parking_lot_generator import ParkingLotGenerator
from generator.parking_lot_generator import GeneratorRules


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


def main():
    # -------------------------------------------------
    # Determinism (important for debugging / demos)
    # -------------------------------------------------
    random.seed(42)

    # -------------------------------------------------
    # Build environment
    # -------------------------------------------------
    
    
    #grid = Grid.from_file("maps/simple_parking_lot.txt")
    rules = GeneratorRules(
        num_entries=2,
        num_exits=2,
        num_parking_spots=55
    )
    generator = ParkingLotGenerator(
        width=20,
         height=10,
        rules=rules
 )
    grid = generator.generate()
    print_grid(grid)

    # print(grid.cells)
    parking_cells, exit_cells, entry_cells = extract_cells(grid)
    print(parking_cells)
    print (exit_cells)
    # -------------------------------------------------
    # Parking manager (domain logic)
    # -------------------------------------------------
    parking_manager = ParkingManager(
        grid=grid,
        parking_cells=parking_cells,
        exit_cells=exit_cells,
        entry_cells=entry_cells
    )

    # -------------------------------------------------
    # Planning infrastructure
    # -------------------------------------------------
    reservation_table = ReservationTable()

    priority_planner = PriorityPlanner(
        grid=grid,
        reservation_table=reservation_table,
        planning_horizon=100
    )
 
    # -------------------------------------------------
    # Simulation configuration
    # -------------------------------------------------
    config = SimulationConfig(
        # max_steps= 40,
        planning_horizon=100,
        goal_reserve_horizon=200,
        arrival_lambda=0.3,
        max_arriving_cars=30,
        initial_parked_cars=2,
        initial_active_cars=0
    )

    # -------------------------------------------------
    # Simulation core
    # -------------------------------------------------
    simulation = SimulationCore(
        grid=grid,
        parking_manager=parking_manager,
        priority_planner=priority_planner,
        config=config
    )

    # -------------------------------------------------
    # Run step-by-step (simulates "Next" button)
    # -------------------------------------------------

    print("Starting simulation...\n")
    while True:
        simulation.step()
        print(f"t = {simulation.time}")
        print("Active car positions:", simulation.get_positions_snapshot())

        

        if (
            not simulation.active_cars and
            simulation.arriving_cars_created >= config.max_arriving_cars
        ):
            break

        print("-" * 40)

    print("\nSimulation finished.")
    print({
        "final_time": simulation.time,
        "total_arrived": simulation.total_arrived,
        "total_planned": simulation.total_planned,
        "total_failed_plans": simulation.total_failed_plans,
        "total_parked": simulation.total_parked,
        "active_cars": len(simulation.active_cars),
    })


if __name__ == "__main__":
    main()
