# core/simulation_core.py
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import random
from generator.cell import CellType
from planning.base_planner import BasePlanner
Position = Tuple[int, int]


@dataclass
class SimulationConfig:
    planning_horizon: int
    goal_reserve_horizon: int
    arrival_lambda: float       # Poisson arrival rate (prob per timestep)
    exit_rate: float            # Per-car probability per step to start exiting

    initial_cars: int = 0       # Cars present at t=0 — all start parked with no goal
    max_arriving_cars: int = 0  # 0 = unlimited


class SimulationCore:
    """
    Discrete-time simulation orchestrator.

    Responsibilities:
    - Maintain global time
    - Initialize parked and active cars
    - Inject cars over time (Poisson arrivals)
    - Assign goals (via ParkingManager)
    - Trigger planning (via PriorityPlanner)
    - Advance cars along their planned space-time paths
    """

    def __init__(self, grid, parking_manager, config: SimulationConfig,
                 planner: BasePlanner = None, priority_planner: BasePlanner = None):
        self.grid = grid
        self.parking_manager = parking_manager
        # Accept both 'planner' (new) and 'priority_planner' (legacy) keyword args
        # so existing test/debug call-sites keep working without modification.
        self.planner: BasePlanner = planner if planner is not None else priority_planner
        self.config = config

        self.time: int = 0
        self.active_cars: Dict[int, object] = {}      # car_id -> Car (currently moving)
        self.parked_cars: Dict[int, object] = {}      # car_id -> Car (idle, waiting to exit)
        self.car_positions: Dict[int, Position] = {}  # car_id -> (x, y)
        self.all_cars: Dict[int, object] = {}
        self.exited_car_ids = set()
        self.cars_pending_removal = set() # Cars that reached exit but need to persist for one frame

        # Metrics
        self.arriving_cars_created = 0
        self.total_arrived = 0
        self.total_planned = 0
        self.total_failed_plans = 0
        self.total_parked = 0

        self.total_exited = 0           # all cars that left the lot
        self.total_exit_journeys = 0    # denominator for avg_steps_to_exit
        self.arriving_cars_parked_count = 0
        self.sum_steps_to_park = 0
        self.sum_steps_to_exit = 0

        self._initialize_cars()

    # -------------------------------------------------
    # Initialization
    # -------------------------------------------------

    def _initialize_cars(self):
        """Place initial_cars cars into the lot at t=0. All start idle (no goal)."""
        total_spots = len(self.parking_manager.parking_cells)
        if self.config.initial_cars > total_spots:
            print(f"[WARNING] initial_cars ({self.config.initial_cars}) exceeds capacity "
                  f"({total_spots}). Capping.")
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
            self.planner.reservation_table.reserve_goal(
                pos[0], pos[1], start_time=0, horizon=self.config.goal_reserve_horizon
            )
            self.total_parked += 1

    # -------------------------------------------------
    # Runtime helpers
    # -------------------------------------------------

    def _get_unplanned_obstacles(self, exclude_car_id: int) -> set:
        """Get positions of active cars that do not have a path."""
        obs = set()
        for cid, c in self.active_cars.items():
            if cid == exclude_car_id:
                continue
            # If a car is in waiting list, it's covered by static reservation (reserve_goal)
            # BUT: we need to be careful. reserve_goal adds to static_cells.
            # is_cell_free checks static_cells.
            # PriorityPlanner checks is_cell_free.
            # So waiting cars are effectively walls.
            # However, once they wake up, we unreserve the goal.
            
            if not c.has_path():
                obs.add(c.current_position)
        return obs

    def _process_parked_car_exits(self):
        """Each idle parked car has exit_rate probability per step of starting to leave."""
        if not self.parked_cars:
            return
        to_wake = [car for car in list(self.parked_cars.values())
                   if random.random() < self.config.exit_rate]
        for car in to_wake:
            self._wake_parked_car(car)

    def _wake_parked_car(self, car):
        """Move an idle parked car into active state with EXIT intent."""
        cx, cy = car.current_position
        self.planner.reservation_table.unreserve_goal(cx, cy, 0)
        self.parking_manager.free_spots.add((cx, cy))
        self.parking_manager.occupied_spots.discard((cx, cy))

        del self.parked_cars[car.car_id]
        car.intent = "EXIT"
        car.exit_start_time = self.time
        self.active_cars[car.car_id] = car

        goal = self.parking_manager.assign_goal(car, self.time)
        car.goal = goal
        if goal is None:
            self.total_failed_plans += 1
            return

        obstacles = self._get_unplanned_obstacles(exclude_car_id=car.car_id)
        ok = self.planner.plan_for_car(car, self.time, obstacles=obstacles)
        if not ok:
            self.total_failed_plans += 1
            car.plan_fail_count += 1

    def _maybe_poisson_arrival(self):
        if self.arriving_cars_created >= self.config.max_arriving_cars:
            return
        
        # User Feedback: Don't spawn cars if there is no parking space
        if not self.parking_manager.free_spots:
            return

        free_entry = self._get_free_entry()
        if free_entry is None:
            return
        
        """Generate a new car according to Poisson arrival process."""
        if random.random() < self.config.arrival_lambda:
            car = self.parking_manager.create_active_car(free_entry)
            car.spawn_time = self.time # Track spawn time
            self.arriving_cars_created += 1
            self.car_positions[car.car_id] = car.current_position
            # Poisson arrivals start moving at the NEXT timestep
            self._handle_new_car(car, start_time=self.time + 1)

    def _handle_new_car(self, car, start_time: int):
        """Assign goal and plan for a newly arrived car."""
        self.active_cars[car.car_id] = car
        self.car_positions[car.car_id] = car.current_position
        self.all_cars[car.car_id] = car
        self.total_arrived += 1

        # Note: We assign goal based on CURRENT time state, but plan for FUTURE start
        # Ideally assign_goal should also know about future? 
        # For now, assign_goal just picks a spot, which is fine.
        goal = self.parking_manager.assign_goal(car, start_time)
        car.goal = goal

        if goal is None:
            self.total_failed_plans += 1
            return

        obstacles = self._get_unplanned_obstacles(exclude_car_id=car.car_id)
        
        ok = self.planner.plan_for_car(car, start_time, obstacles=obstacles)
        if ok:
             self.total_planned += 1
             car.plan_fail_count = 0
        else:
             self.total_failed_plans += 1
             car.plan_fail_count += 1

             if car.intent == "EXIT" and car.plan_fail_count % 5 == 0:
                 exits = list(self.parking_manager.exit_cells)
                 if exits:
                     car.goal = random.choice(exits)

             if car.intent == "PARK" and car.plan_fail_count >= 3:
                 self.parking_manager.release_assigned_spot(car.car_id)
                 car.goal = None

             if car.intent == "PARK" and car.plan_fail_count >= 12:
                 self.parking_manager.release_assigned_spot(car.car_id)
                 car.intent = "EXIT"
                 car.goal = self.parking_manager.assign_goal(car, start_time)

    def _advance_cars(self):
        """Move active cars along their planned paths with collision resolution."""
        # 1. Plan for cars that need it
        #    Skipped for batch planners (LaCAM0) — replan_all() already ran.
        if self.planner.uses_batch_planning:
            cars_needing_plan = []
        else:
            # Heuristic: Plan for cars closest to their goal FIRST.
            # This helps clear congestion at exits/entries.
            cars_needing_plan = []
            for car in self.active_cars.values():
                if not car.has_path():
                    cars_needing_plan.append(car)
        
        def dist_to_goal(c):
            if not c.goal: return float('inf')
            return abs(c.current_position[0] - c.goal[0]) + abs(c.current_position[1] - c.goal[1])

        cars_needing_plan.sort(key=dist_to_goal)

        for car in cars_needing_plan:
            # Backoff check: if we failed recently, skip
            # if (self.time - car.last_plan_fail_time) < 5:
            #    continue
            
            # Ensure goal (might be missing if new or cleared)
            if not car.has_goal():
                car.goal = self.parking_manager.assign_goal(car, self.time)
            
            if not car.has_goal():
                continue

            obstacles = self._get_unplanned_obstacles(exclude_car_id=car.car_id)
            
            # Randomized persistence to break symmetry in deadlocks
            persistence = random.randint(10, 30)
            
            ok = self.planner.plan_for_car(
                car, 
                self.time, 
                obstacles=obstacles,
                obstacle_persistence=persistence
            )
            
            if not ok:
                car.last_plan_fail_time = self.time
                car.plan_fail_count += 1

                if car.intent == "EXIT" and car.plan_fail_count % 5 == 0:
                    exits = list(self.parking_manager.exit_cells)
                    if exits:
                        car.goal = random.choice(exits)

                if car.intent == "PARK" and car.plan_fail_count % 3 == 0:
                    self.parking_manager.release_assigned_spot(car.car_id)
                    car.goal = None

                if car.intent == "PARK" and car.plan_fail_count >= 12:
                    self.parking_manager.release_assigned_spot(car.car_id)
                    car.intent = "EXIT"
                    car.goal = self.parking_manager.assign_goal(car, self.time)
            else:
                car.plan_fail_count = 0

        # 2. Determine intended next positions
        # current_pos -> active_car_id
        current_positions = self.get_positions_snapshot()
        
        # Build spatial index for fast lookup: pos -> car_id
        pos_to_cid = {pos: cid for cid, pos in current_positions.items()}

        # car_id -> (next_x, next_y)
        intended_moves = {}
        for car_id, car in self.active_cars.items():
            next_pos = car.peek_at_next_step(self.time)
            if next_pos is None:
                # Path finished or no path
                intended_moves[car_id] = car.current_position
            else:
                intended_moves[car_id] = next_pos

        # Add non-active cars (parked) as "staying put"
        for cid, pos in current_positions.items():
            if cid not in self.active_cars:
                intended_moves[cid] = pos

        # 3. Iterative Conflict Resolution
        # We start with everyone doing their intended move.
        # If a conflict arises, we revert the 'aggressor' (or both) to their current position.
        # We repeat until stable.
        
        active_moves = intended_moves.copy()
        
        while True:
            changed = False
            
            # Map target_pos -> list of car_ids
            moves_to_cell = {}
            for cid, pos in active_moves.items():
                if pos not in moves_to_cell:
                    moves_to_cell[pos] = []
                moves_to_cell[pos].append(cid)
            
            # Check Vertex Conflicts
            for pos, cids in moves_to_cell.items():
                if len(cids) > 1:
                    # Conflict!
                    # Rule: If a car is ALREADY at 'pos' (staying put), it wins.
                    # Everyone else moving into 'pos' must revert.
                    
                    winner_id = None
                    for cid in cids:
                        if current_positions[cid] == pos:
                            winner_id = cid
                            break
                    
                    # If nobody is currently there (all moving in), pick arbitrary winner (min ID)
                    if winner_id is None:
                         winner_id = min(cids)
                    
                    # Revert losers
                    for cid in cids:
                        if cid != winner_id:
                            # Revert to current position
                            if active_moves[cid] != current_positions[cid]:
                                active_moves[cid] = current_positions[cid]
                                changed = True

            # Check Edge Swaps
            # Swap occurs if A moves to B's current, and B moves to A's current
            # Only check if not already reverted
            for cid_a, next_a in active_moves.items():
                curr_a = current_positions[cid_a]
                
                # If A is staying put, no swap possible
                if next_a == curr_a:
                    continue
                
                # Check who is currently at next_a using spatial index
                cid_b = pos_to_cid.get(next_a)
                
                if cid_b is not None:
                    # B is at A's target. Where is B going?
                    next_b = active_moves.get(cid_b)
                    curr_b = current_positions[cid_b] # == next_a
                    
                    # Swap condition: B is moving to A's current
                    if next_b == curr_a:
                        # EDGE SWAP DETECTED: A->B, B->A
                        # Revert BOTH to be safe
                        if active_moves[cid_a] != curr_a:
                            active_moves[cid_a] = curr_a
                            changed = True
                        if active_moves[cid_b] != curr_b:
                            active_moves[cid_b] = curr_b
                            changed = True

            if not changed:
                break

        # 4. Apply Moves
        for car_id, car in list(self.active_cars.items()):
            final_pos = active_moves[car_id]
            curr_pos = car.current_position
            
            if final_pos != curr_pos:
                # Car moved successfully
                # Verify it matches plan (it should)
                # Call step to advance internal state
                stepped_pos = car.step(self.time)
                if stepped_pos != final_pos:
                    # This shouldn't happen if logic is correct
                    # print(f"WARNING: Logic mismatch for {car_id}")
                    pass
                self.car_positions[car_id] = final_pos
                car.blocked_count = 0
                
                # Check goal
                if final_pos == car.goal:
                    completed_path = car.path
                    if car.intent == "PARK":
                        self.total_parked += 1
                        self.arriving_cars_parked_count += 1
                        self.sum_steps_to_park += (self.time - car.spawn_time)

                        self.parking_manager.mark_occupied(car, final_pos)
                        if completed_path:
                            self.planner.reservation_table.unreserve_path(completed_path)
                            gx, gy, gt = completed_path[-1]
                            self.planner.reservation_table.reserve_goal(
                                gx, gy, gt, horizon=self.config.goal_reserve_horizon
                            )
                        car.clear_path()
                        self.parked_cars[car_id] = car
                    elif car.intent == "EXIT":
                         self.total_exited += 1
                         self.total_exit_journeys += 1
                         self.sum_steps_to_exit += self.time - getattr(car, 'exit_start_time', self.time)

                         # Remove from tracking so it doesn't block the exit
                         self.exited_car_ids.add(car_id)
                         if completed_path:
                             self.planner.reservation_table.unreserve_path(completed_path)
                         
                         # Defer removal from car_positions so it shows up in this step's snapshot
                         # if car_id in self.car_positions:
                         #    del self.car_positions[car_id]
                         self.cars_pending_removal.add(car_id)
                         
                         car.clear_path()

                    del self.active_cars[car_id]
            
            else:
                # Car stayed put
                # Did it WANT to move?
                if intended_moves[car_id] != curr_pos:
                    # It wanted to move but was blocked/reverted
                    # We MUST cancel its plan because it is now off-path (time desync)
                    self.planner.cancel_plan(car)
                    car.blocked_count += 1

                    if car.intent == "PARK" and car.blocked_count % 3 == 0:
                        self.parking_manager.release_assigned_spot(car.car_id)
                        car.goal = None

                    if car.intent == "PARK" and car.blocked_count >= 12:
                        self.parking_manager.release_assigned_spot(car.car_id)
                        car.intent = "EXIT"
                        car.goal = self.parking_manager.assign_goal(car, self.time)
                    # Do NOT call step()
                else:
                    # It wanted to stay put (or finished path).
                    # If it has a path and we are just waiting (t < next_t), that's fine.
                    # If it finished path and is at goal, handled? 
                    # If finished path but NOT at goal (e.g. partial path), logic?
                    # step() handles "finished path" by returning None, but here we peeked.
                    # We should check if path is done.
                    if car.has_path():
                         stepped_pos = car.step(self.time)
                         if stepped_pos is not None:
                              self.car_positions[car_id] = stepped_pos
                    if car.is_finished() and car.has_path():
                         # Path done, verify goal
                         if curr_pos == car.goal:
                             completed_path = car.path
                             if car.intent == "PARK":
                                 self.total_parked += 1
                                 self.arriving_cars_parked_count += 1
                                 self.sum_steps_to_park += (self.time - car.spawn_time)
                                 self.parking_manager.mark_occupied(car, curr_pos)
                                 if completed_path:
                                     self.planner.reservation_table.unreserve_path(completed_path)
                                     gx, gy, gt = completed_path[-1]
                                     self.planner.reservation_table.reserve_goal(
                                         gx, gy, gt, horizon=self.config.goal_reserve_horizon
                                     )
                                 car.clear_path()
                                 self.parked_cars[car_id] = car
                             elif car.intent == "EXIT":
                                 self.total_exited += 1
                                 self.total_exit_journeys += 1
                                 self.sum_steps_to_exit += self.time - getattr(car, 'exit_start_time', self.time)
                                 self.exited_car_ids.add(car_id)
                                 if completed_path:
                                     self.planner.reservation_table.unreserve_path(completed_path)
                                 
                                 # Defer removal from car_positions so it shows up in this step's snapshot
                                 # if car_id in self.car_positions:
                                 #    del self.car_positions[car_id]
                                 self.cars_pending_removal.add(car_id)

                                 car.clear_path()
                                     
                             del self.active_cars[car_id]
                         else:
                             # Reached end of path but not goal? 
                             # This happens if we planned a partial path? 
                             # Or if we just arrived. 
                             # If we are not at goal, we probably need to re-plan?
                             # For now, clear path to force replan next step
                             car.clear_path()
                    else:
                         # Just waiting or no path
                         pass


    def _get_free_entry(self):
        """Return a free entry cell (x, y) if one exists, else None."""
        entries = list(self.parking_manager.entry_cells)
        random.shuffle(entries)

        for (x, y) in entries:

            # spatial check
            if (x, y) in self.car_positions.values():
                continue

            # spatio-temporal check
            # Check if cell is free now AND for a short future window
            safe = True
            check_horizon = 20 # Check 20 steps ahead
            for t_offset in range(check_horizon):
                if not self.planner.reservation_table.is_cell_free(x, y, self.time + t_offset):
                    safe = False
                    break
            
            if not safe:
                continue

            return (x, y)

        return None

    def _get_free_road_cell(self):
        candidates = []

        for x in range(self.grid.width):
            for y in range(self.grid.height):
                cell = self.grid.get_cell(x, y)

                if cell.type != CellType.ROAD:
                    continue

                # spatial check
                if (x, y) in self.car_positions.values():
                    continue

                # spatio-temporal check
                # Check if cell is free now AND for a short future window
                # This prevents spawning a car on a path that is already reserved by another car arriving soon,
                # which avoids collisions if the new car fails to plan and becomes a static obstacle.
                safe = True
                check_horizon = 20 # Check 20 steps ahead
                for t_offset in range(check_horizon):
                    if not self.planner.reservation_table.is_cell_free(x, y, self.time + t_offset):
                        safe = False
                        break
                
                if not safe:
                    continue

                candidates.append((x, y))

        if not candidates:
            return None

        return random.choice(candidates)
    # -------------------------------------------------
    # Public API
    # -------------------------------------------------

    def _cleanup_exited_cars(self):
        """Remove cars that were marked as exited in the previous step."""
        for car_id in self.cars_pending_removal:
            if car_id in self.car_positions:
                del self.car_positions[car_id]
        self.cars_pending_removal.clear()

    def step(self):
        self._cleanup_exited_cars()
        self._process_parked_car_exits()
        if self.planner.uses_batch_planning:
            parked_pos = {self.car_positions[cid] for cid in self.parked_cars if cid in self.car_positions}
            self.planner.replan_all(list(self.active_cars.values()), self.time, parked_pos)
        self._advance_cars()
        self._maybe_poisson_arrival()
        self.time += 1

    def run(self) -> Dict[str, int]:
        """Run the simulation."""
        while True:
            self.step()

                # early termination condition
    # FIXED CONDITION: 
            # If no one is moving AND we have reached our spawn limit
            # OR if you just want to stop when active_cars is empty:
            if not self.active_cars:
                if self.arriving_cars_created >= self.config.max_arriving_cars:
                    break
                # Optional: Add a check if arrival_lambda is 0
                if self.config.arrival_lambda == 0:
                    break

        return {
            "final_time": self.time,
            "total_arrived": self.total_arrived,
            "total_planned": self.total_planned,
            "total_failed_plans": self.total_failed_plans,
            "total_parked": self.total_parked,
            "active_cars": len(self.active_cars),
        }

    def get_positions_snapshot(self) -> Dict[int, Position]:
        """car_id -> (x, y) at current time"""
        return dict(self.car_positions)
