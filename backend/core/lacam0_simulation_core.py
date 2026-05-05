# core/lacam0_simulation_core.py
import random
from typing import Dict, Optional, Set, Tuple

from core.simulation_core import SimulationConfig

Position = Tuple[int, int]


class LaCAM0SimulationCore:
    """
    Lifelong simulation orchestrator designed for LaCAM0.

    Key differences from SimulationCore (priority-planner version):
    - No ReservationTable — parked cars are obstacles in the .map file instead.
    - No per-car conflict resolution layer — LaCAM0 guarantees conflict-free paths.
    - Planning is done in batches: one LaCAM0 call for ALL active cars at once.
    - Replanning is event-driven (new car, goal reached, wakeup) plus a periodic
      safety net every replan_interval steps.

    Public API matches SimulationCore so SimulationSession drives it identically:
        step()
        get_positions_snapshot() -> Dict[int, (x, y)]
        time, active_cars, parked_cars, car_positions, all_cars, exited_car_ids
        arriving_cars_created, total_arrived, total_planned, total_failed_plans,
        total_parked, total_exited, total_exit_journeys,
        arriving_cars_parked_count, sum_steps_to_park, sum_steps_to_exit,
        config.initial_cars
    """

    def __init__(self, grid, parking_manager, config: SimulationConfig, batch_planner):
        self.grid = grid
        self.parking_manager = parking_manager
        self.config = config
        self.batch_planner = batch_planner

        self.time: int = 0
        self.active_cars: Dict[int, object] = {}
        self.parked_cars: Dict[int, object] = {}
        self.car_positions: Dict[int, Position] = {}
        self.all_cars: Dict[int, object] = {}
        self.exited_car_ids: Set[int] = set()
        self.cars_pending_removal: Set[int] = set()

        # Replanning state
        self.needs_replan: bool = False
        self.last_replan_time: int = -999
        self.min_replan_cooldown: int = 3

        # Metrics (same fields as SimulationCore for compatibility)
        self.arriving_cars_created: int = 0
        self.total_arrived: int = 0
        self.total_planned: int = 0
        self.total_failed_plans: int = 0
        self.total_parked: int = 0
        self.total_exited: int = 0
        self.total_exit_journeys: int = 0
        self.arriving_cars_parked_count: int = 0
        self.sum_steps_to_park: int = 0
        self.sum_steps_to_exit: int = 0

        self._initialize_cars()

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def _initialize_cars(self):
        """Place initial_cars cars into the lot at t=0 — all start parked."""
        total_spots = len(self.parking_manager.parking_cells)
        if self.config.initial_cars > total_spots:
            print(
                f"[LaCAM0Core] initial_cars ({self.config.initial_cars}) exceeds "
                f"capacity ({total_spots}). Capping."
            )
            self.config.initial_cars = total_spots

        for _ in range(self.config.initial_cars):
            if not self.parking_manager.free_spots:
                break
            car = self.parking_manager.create_parked_car()
            car.is_initial = True
            pos = car.current_position
            self.all_cars[car.car_id] = car
            self.parked_cars[car.car_id] = car
            self.car_positions[car.car_id] = pos
            self.parking_manager.mark_occupied(car, pos)
            self.total_parked += 1

    # ------------------------------------------------------------------
    # Step
    # ------------------------------------------------------------------

    def step(self):
        self._cleanup_exited_cars()
        self._process_parked_car_exits()
        self._maybe_poisson_arrival()
        self._trigger_replan_if_needed()
        self._execute_paths()
        self.time += 1

    # ------------------------------------------------------------------
    # Sub-steps
    # ------------------------------------------------------------------

    def _cleanup_exited_cars(self):
        for car_id in self.cars_pending_removal:
            self.car_positions.pop(car_id, None)
        self.cars_pending_removal.clear()

    def _process_parked_car_exits(self):
        if not self.parked_cars:
            return
        to_wake = [
            car for car in list(self.parked_cars.values())
            if random.random() < self.config.exit_rate
        ]
        for car in to_wake:
            self._wake_parked_car(car)

    def _wake_parked_car(self, car):
        """Transition a parked car to EXIT intent and register it as active."""
        pos = car.current_position
        self.parking_manager.free_spots.add(pos)
        self.parking_manager.occupied_spots.discard(pos)

        del self.parked_cars[car.car_id]
        car.intent = "EXIT"
        car.exit_start_time = self.time
        self.active_cars[car.car_id] = car

        goal = self.parking_manager.assign_goal(car, self.time)
        car.goal = goal
        if goal is None:
            self.total_failed_plans += 1

        self.needs_replan = True

    def _get_free_entry(self) -> Optional[Position]:
        """Return a free entry cell not currently occupied by any car."""
        entries = list(self.parking_manager.entry_cells)
        random.shuffle(entries)
        occupied = set(self.car_positions.values())
        for pos in entries:
            if pos not in occupied:
                return pos
        return None

    def _maybe_poisson_arrival(self):
        if self.arriving_cars_created >= self.config.max_arriving_cars:
            return
        if not self.parking_manager.free_spots:
            return
        free_entry = self._get_free_entry()
        if free_entry is None:
            return
        if random.random() < self.config.arrival_lambda:
            car = self.parking_manager.create_active_car(free_entry)
            car.spawn_time = self.time
            self.arriving_cars_created += 1
            self.car_positions[car.car_id] = car.current_position
            self._handle_new_car(car)

    def _handle_new_car(self, car):
        """Register a newly arrived car and request a batch replan."""
        self.active_cars[car.car_id] = car
        self.car_positions[car.car_id] = car.current_position
        self.all_cars[car.car_id] = car
        self.total_arrived += 1

        goal = self.parking_manager.assign_goal(car, self.time)
        car.goal = goal
        if goal is None:
            self.total_failed_plans += 1

        self.needs_replan = True

    def _trigger_replan_if_needed(self):
        """Call LaCAM0 in batch for all active cars when a replan is warranted."""
        # Periodic safety net
        if not self.needs_replan:
            if self.time > 0 and self.time % self.batch_planner.replan_interval == 0:
                self.needs_replan = True

        if not self.needs_replan:
            return
        if not self.active_cars:
            self.needs_replan = False
            return
        if (self.time - self.last_replan_time) < self.min_replan_cooldown:
            return

        # Try to assign goals to any car that is missing one
        for car in list(self.active_cars.values()):
            if not car.has_goal():
                goal = self.parking_manager.assign_goal(car, self.time)
                car.goal = goal
                if goal is None:
                    self.total_failed_plans += 1

        plannable = {
            cid: car for cid, car in self.active_cars.items() if car.has_goal()
        }
        if not plannable:
            self.needs_replan = False
            return

        parked_cells = {car.current_position for car in self.parked_cars.values()}

        paths = self.batch_planner.plan(plannable, self.grid, parked_cells, self.time)

        if paths is not None:
            for car_id, path in paths.items():
                self.active_cars[car_id].set_path(path)
            self.total_planned += len(paths)
            self.needs_replan = False
            self.last_replan_time = self.time
        else:
            # LaCAM0 failed: cars keep existing paths (or wait with no path).
            # A fresh attempt will fire on the next periodic interval.
            self.total_failed_plans += 1
            self.needs_replan = False
            self.last_replan_time = self.time

    def _execute_paths(self):
        """Advance every active car by one step along its LaCAM0 path."""
        for car_id, car in list(self.active_cars.items()):
            next_pos = car.peek_at_next_step(self.time)

            if next_pos is None:
                # Path exhausted before goal — trigger a fresh replan.
                if car.has_path():
                    self.needs_replan = True
                continue

            # Advance car's internal state and update position index.
            car.step(self.time)
            self.car_positions[car_id] = next_pos

            # Check goal arrival.
            if next_pos == car.goal:
                if car.intent == "PARK":
                    self.total_parked += 1
                    self.arriving_cars_parked_count += 1
                    self.sum_steps_to_park += self.time - car.spawn_time
                    self.parking_manager.mark_occupied(car, next_pos)
                    car.clear_path()
                    self.parked_cars[car_id] = car
                    del self.active_cars[car_id]
                    self.needs_replan = True

                elif car.intent == "EXIT":
                    self.total_exited += 1
                    self.total_exit_journeys += 1
                    self.sum_steps_to_exit += (
                        self.time - getattr(car, "exit_start_time", self.time)
                    )
                    self.exited_car_ids.add(car_id)
                    self.cars_pending_removal.add(car_id)
                    car.clear_path()
                    del self.active_cars[car_id]
                    self.needs_replan = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_positions_snapshot(self) -> Dict[int, Position]:
        """Return a snapshot of all visible car positions at the current time."""
        return dict(self.car_positions)