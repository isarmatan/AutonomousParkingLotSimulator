from planning.base_planner import BasePlanner
from planning.priority_planner_adapter import PriorityPlannerAdapter


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
    "lacam0"    – LaCAM0 MAPF solver via WSL subprocess  (Phase 3)
    """
    if algorithm == "priority":
        return PriorityPlannerAdapter(
            grid=grid,
            reservation_table=reservation_table,
            planning_horizon=planning_horizon,
        )

    # Phase 3 placeholder – prevents unknown-algorithm requests from silently
    # falling back to priority without an explicit error.
    raise ValueError(
        f"Unknown planning algorithm: '{algorithm}'. "
        f"Supported values: 'priority'  (more coming in Phase 3)"
    )
