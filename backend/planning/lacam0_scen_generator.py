# planning/lacam0_scen_generator.py
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple


def generate_scen(
    active_cars: dict,
    map_path: str,
    grid_width: int,
    grid_height: int,
    world_to_planner: Optional[Callable[[int, int], Tuple[int, int]]] = None,
) -> Tuple[str, Dict[int, int]]:
    """
    Generate a MAPF benchmark .scen file string from active cars.

    Agents are ordered by car_id (ascending) for a stable agent-index mapping.
    Only cars that have both a current_position and a goal are included.

    Args:
        active_cars:      Dict[car_id -> Car] of cars to plan for.
        map_path:         Path to the .map file (basename used in scen body).
        grid_width:       Map width in cells (pass expanded_W when using ghost boxes).
        grid_height:      Map height in cells (pass expanded_H when using ghost boxes).
        world_to_planner: Optional coordinate translation function
                          (world_x, world_y) -> (planner_x, planner_y).
                          When None, coordinates are written as-is.

    Returns:
        scen_string:           The .scen file content (tab-separated).
        agent_index_to_car_id: Dict mapping agent index (0-based) to car_id,
                               in the same order as the scen lines.
    """
    if world_to_planner is None:
        world_to_planner = lambda x, y: (x, y)

    map_basename = Path(map_path).name
    sorted_cars = sorted(active_cars.values(), key=lambda c: c.car_id)

    lines = ["version 1"]
    agent_index_to_car_id: Dict[int, int] = {}

    for agent_idx, car in enumerate(sorted_cars):
        sx, sy = world_to_planner(*car.current_position)
        gx, gy = world_to_planner(*car.goal)
        lines.append(
            f"0\t{map_basename}\t{grid_width}\t{grid_height}"
            f"\t{sx}\t{sy}\t{gx}\t{gy}\t0.0"
        )
        agent_index_to_car_id[agent_idx] = car.car_id

    return "\n".join(lines), agent_index_to_car_id
