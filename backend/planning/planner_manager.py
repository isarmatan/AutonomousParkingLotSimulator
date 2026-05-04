from planning.base_planner import BasePlanner
from planning.priority_planner_adapter import PriorityPlannerAdapter
from planning.lacam0_planner_adapter import LaCAM0PlannerAdapter


def create_planner(
    algorithm: str,
    grid,
    reservation_table,
    planning_horizon: int,
) -> BasePlanner:
    """
    Factory: returns the appropriate BasePlanner implementation.

    Supported algorithms
    --------------------
    "priority"  – decoupled priority-based A* (default, always available)
    "lacam0"    – LaCAM0 MAPF solver (Windows native, requires LACAM0_DIR env var)
    """
    if algorithm == "priority":
        return PriorityPlannerAdapter(
            grid=grid,
            reservation_table=reservation_table,
            planning_horizon=planning_horizon,
        )

    if algorithm == "lacam0":
        return LaCAM0PlannerAdapter(
            grid=grid,
            reservation_table=reservation_table,
            planning_horizon=planning_horizon,
        )

    raise ValueError(
        f"Unknown planning algorithm: '{algorithm}'. "
        f"Supported values: 'priority', 'lacam0'"
    )
