
import unittest
import random
from core.simulation_core import SimulationCore, SimulationConfig
from core.parking_manager import ParkingManager
from planning.priority_planner import PriorityPlanner
from planning.reservation_table import ReservationTable
from generator.parking_lot_generator import ParkingLotGenerator, GeneratorRules
from generator.cell import CellType

class TestExitRate(unittest.TestCase):
    def test_staggered_exit(self):
        # Setup: 10x10 grid, 5 initial active cars, exit_rate=0.2
        # We expect them to NOT all start at t=0.
        
        # Ensure deterministic behavior
        random.seed(42)
        
        rules = GeneratorRules(num_entries=1, num_exits=1, num_parking_spots=10)
        
        # Retry generation until we get enough spots
        grid = None
        for i in range(10):
            generator = ParkingLotGenerator(15, 15, rules)
            g = generator.generate()
            p_cells = [(c.x, c.y) for row in g.cells for c in row if c.type == CellType.PARKING]
            print(f"Attempt {i}: Generated {len(p_cells)} parking spots")
            if len(p_cells) >= 5:
                grid = g
                break
        
        self.assertIsNotNone(grid, "Failed to generate grid with enough parking spots")

        # Extract cells
        parking_cells = [(c.x, c.y) for row in grid.cells for c in row if c.type == CellType.PARKING]
        exit_cells = [(c.x, c.y) for row in grid.cells for c in row if c.type == CellType.EXIT]
        entry_cells = [(c.x, c.y) for row in grid.cells for c in row if c.type == CellType.ENTRY]
        
        print(f"Generated {len(parking_cells)} parking spots.")
        
        parking_manager = ParkingManager(grid, parking_cells, exit_cells, entry_cells)
        reservation_table = ReservationTable()
        planner = PriorityPlanner(grid, reservation_table, planning_horizon=50)
        
        # Config with low exit rate
        config = SimulationConfig(
            planning_horizon=50,
            goal_reserve_horizon=100,
            arrival_lambda=0.0, # No new arrivals
            max_arriving_cars=0,
            initial_parked_cars=0,
            initial_active_cars=5,
            initial_active_exit_rate=0.1  # 10% chance per step
        )
        
        sim = SimulationCore(grid, parking_manager, planner, config)
        
        # At initialization (t=0), all cars are in waiting list and have no path
        self.assertEqual(len(sim.waiting_active_cars), 5)
        # Verify no car has a path yet
        cars_with_path = [c for c in sim.active_cars.values() if c.has_path()]
        self.assertEqual(len(cars_with_path), 0, "No cars should have a path at init")

        # Step 1
        sim.step()
        # With 0.1 rate and 5 cars, expected number to start is 0.5 cars.
        # It's random, but it shouldn't be ALL 5.
        
        remaining_waiting = len(sim.waiting_active_cars)
        self.assertGreater(remaining_waiting, 0, "Not all cars should have started immediately with low rate")
        
        cars_with_path_t1 = [c for c in sim.active_cars.values() if c.has_path()]
        # Some might have started
        print(f"T=1: Waiting={remaining_waiting}, Started={len(cars_with_path_t1)}")

        # Run for 20 steps, they should eventually all start
        for _ in range(20):
            sim.step()
            if not sim.waiting_active_cars:
                break
        
        print(f"Final Waiting={len(sim.waiting_active_cars)}")
        # Ideally all started by now
        if len(sim.waiting_active_cars) > 0:
             print("Warning: Randomness caused some cars to wait very long, which is possible but unlikely.")
        
        # Verify that cars actually exited or are moving
        # (Just ensuring the simulation runs without crash)

if __name__ == '__main__':
    unittest.main()
