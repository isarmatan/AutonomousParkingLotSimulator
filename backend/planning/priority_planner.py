'''
PriorityPlanner is not an algorithm in the heavy sense.
It is a policy layer.

Its responsibilities are:

1) Decide priority order

2) Call the single-agent planner

3) Reserve the resulting path

4) Attach the path to the car
'''

from planning.single_agent_planner import *

class PriorityPlanner:
    def __init__(self, grid, reservation_table, planning_horizon):
        self.grid = grid
        self.reservation_table = reservation_table
        self.planning_horizon = planning_horizon

    def plan_for_car(self, car, current_time, obstacles=None, obstacle_persistence=20):
        path = single_agent_a_star(
            start=car.current_position,
            start_time=current_time,
            goal=car.goal,
            grid=self.grid,
            reservation_table=self.reservation_table,
            max_time=current_time + self.planning_horizon,
            additional_obstacles=obstacles,
            obstacle_persistence=obstacle_persistence
        )

        if path is None:
            return False

        car.set_path(path)
        self.reservation_table.reserve_path(path)

        return True

    def cancel_plan(self, car):
        """
        Cancel the current plan for a car, freeing its reservations.
        """
        if not car.has_path():
            return

        self.reservation_table.unreserve_path(car.path)
        car.clear_path()

