# core/parking_manager.py
import random
from agents.car import Car

class ParkingManager:
    def __init__(self, grid, parking_cells, exit_cells, entry_cells):
        self.grid = grid
        self.parking_cells = parking_cells
        self.exit_cells = set(exit_cells)
        self.entry_cells = set(entry_cells)

        self.free_spots = set(parking_cells)
        self.assigned_spots = {}
        self.occupied_spots = set()

        self.next_car_id = 0

    # ---------------- car creation ----------------

    def create_active_car(self, start, intent = "PARK"):
        # start = self._random_entry_cell()
        car = Car(self.next_car_id, start, intent=intent)
        self.next_car_id += 1
        return car

    def create_parked_car(self):
        spot = random.choice(list(self.free_spots))
        car = Car(self.next_car_id, spot, intent=None)
        self.next_car_id += 1
        car.goal = spot
        self.free_spots.remove(spot)
        self.occupied_spots.add(spot)
        return car

    # ---------------- parking logic ----------------
    def assign_goal(self, car, current_time):
        if car.intent == "PARK":
            return self.choose_free_parking_spot(car)

        if car.intent == "EXIT":
            return self.choose_exit_cell(car)
    

    def choose_free_parking_spot(self, car):
        if not self.free_spots:
            return None

        spot = min(
            self.free_spots,
            key=lambda p: abs(p[0] - car.current_position[0]) +
                          abs(p[1] - car.current_position[1])
        )

        self.free_spots.remove(spot)
        self.assigned_spots[car.car_id] = spot
        return spot


    def choose_exit_cell(self, car):
        """
        Choose an exit cell for a car.
        Policy: nearest exit by Manhattan distance.
        """

        if not self.exit_cells:
            return None

        cx, cy = car.current_position

        exit_cell = min(
            self.exit_cells,
            key=lambda p: abs(p[0] - cx) + abs(p[1] - cy)
        )

        return exit_cell

    def mark_assigned(self, car, spot):
        self.assigned_spots[car.car_id] = spot

    def mark_occupied(self, car, spot):
        self.assigned_spots.pop(car.car_id, None)
        self.occupied_spots.add(spot)

    def release_assigned_spot(self, car_id: int):
        spot = self.assigned_spots.pop(car_id, None)
        if spot is None:
            return
        if spot not in self.occupied_spots:
            self.free_spots.add(spot)

    # ---------------- helpers ----------------

    # def _random_entry_cell(self):
    #     entries = [
    #         (cell.x, cell.y)
    #         for cell in self.grid.cells
    #         if cell.is_entry()
    #     ]
    #     return random.choice(entries)

    def _random_entry_cell(self):
        if not self.entry_cells:
            raise RuntimeError("No entry cells available")

        return random.choice(list(self.entry_cells))