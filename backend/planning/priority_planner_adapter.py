from planning.base_planner import BasePlanner
from planning.priority_planner import PriorityPlanner


class PriorityPlannerAdapter(BasePlanner):
    """
    Thin adapter that makes the existing PriorityPlanner conform to BasePlanner.

    Constructor signature mirrors PriorityPlanner so it can be used as a
    drop-in replacement wherever PriorityPlanner was constructed directly.
    """

    def __init__(self, grid, reservation_table, planning_horizon: int):
        self._planner = PriorityPlanner(
            grid=grid,
            reservation_table=reservation_table,
            planning_horizon=planning_horizon,
        )
        self._reservation_table = reservation_table

    # ------------------------------------------------------------------
    # BasePlanner interface
    # ------------------------------------------------------------------

    def plan_for_car(
        self,
        car,
        current_time: int,
        obstacles=None,
        obstacle_persistence: int = 20,
    ) -> bool:
        return self._planner.plan_for_car(
            car,
            current_time,
            obstacles=obstacles,
            obstacle_persistence=obstacle_persistence,
        )

    def cancel_plan(self, car) -> None:
        self._planner.cancel_plan(car)

    @property
    def reservation_table(self):
        return self._reservation_table
