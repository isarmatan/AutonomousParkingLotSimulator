# planning/single_agent_planner.py
import heapq
from typing import Dict, List, Optional, Tuple
from generator.cell import CellType

Position = Tuple[int, int]
TimedPosition = Tuple[int, int, int]  # (x, y, t)


def manhattan(a: Position, b: Position) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def reconstruct_path(came_from: Dict[TimedPosition, TimedPosition], goal_node: TimedPosition) -> List[TimedPosition]:
    path = [goal_node]
    cur = goal_node
    while cur in came_from:
        cur = came_from[cur]
        path.append(cur)
    path.reverse()
    return path


def _reconstruct_path_packed(came_from: Dict[int, int], goal_key: int, *, area: int, height: int) -> List[TimedPosition]:
    path_keys = [goal_key]
    cur = goal_key
    while cur in came_from:
        cur = came_from[cur]
        path_keys.append(cur)
    path_keys.reverse()
    out: List[TimedPosition] = []
    for k in path_keys:
        t, idx = divmod(k, area)
        x, y = divmod(idx, height)
        out.append((x, y, t))
    return out


def single_agent_a_star(
    start: Position,
    start_time: int,
    goal: Position,
    grid,
    reservation_table,
    max_time: int = 1000,
    additional_obstacles: Optional[set] = None,
    obstacle_persistence: int = 20,
) -> Optional[List[TimedPosition]]:
    """
    Time-expanded A* for one agent.

    Args:
        start: (x, y)
        start_time: global time the agent starts moving
        goal: (gx, gy)
        grid: your Grid instance (must have in_bounds(x,y), get_cell(x,y))
        reservation_table: your ReservationTable (must have is_cell_free, is_edge_free)
        max_time: safety horizon to avoid infinite searches (esp. with 'wait')
        additional_obstacles: set of (x, y) coordinates to treat as static obstacles
        obstacle_persistence: number of timesteps these obstacles are considered valid. 
                              After start_time + persistence, they are ignored.
    """

    sx, sy = start
    gx, gy = goal

    if additional_obstacles is None:
        additional_obstacles = set()

    # Validate start/goal are in bounds and drivable
    if not grid.in_bounds(sx, sy):
        return None
    if not grid.in_bounds(gx, gy):
        return None
    if not grid.get_cell(sx, sy).is_drivable():
        return None
    if not grid.get_cell(gx, gy).is_drivable():
        return None

    # Check start against additional obstacles (immediate collision)
    if (sx, sy) in additional_obstacles:
        # If we are somehow spawning on top of one, fail.
        return None

    width = grid.width
    height = grid.height
    area = width * height
    cells = grid.cells

    vertex_res = reservation_table.vertex_reservations
    edge_res = reservation_table.edge_reservations
    static_cells = reservation_table.static_cells

    persist_until_t = start_time + obstacle_persistence

    # open_set entries: (f, g, (x, y, t))
    open_set: List[Tuple[int, int, int]] = []
    start_idx = sx * height + sy
    start_key = start_time * area + start_idx
    g_score: Dict[int, int] = {start_key: 0}
    came_from: Dict[int, int] = {}

    start_h = abs(sx - gx) + abs(sy - gy)
    heapq.heappush(open_set, (start_h, 0, start_key))

    # 4-dir + wait
    moves = ((0, 1), (0, -1), (1, 0), (-1, 0), (0, 0))

    in_bounds = grid.in_bounds
    heappush = heapq.heappush
    heappop = heapq.heappop

    while open_set:
        _, g, key = heappop(open_set)
        best_g = g_score.get(key)
        if best_g is None or g != best_g:
            continue

        t, idx = divmod(key, area)
        x, y = divmod(idx, height)

        # Goal condition: first time we reach (gx, gy)
        if (x, y) == (gx, gy):
            return _reconstruct_path_packed(came_from, key, area=area, height=height)

        if t >= max_time:
            continue

        for dx, dy in moves:
            nx, ny = x + dx, y + dy
            nt = t + 1

            if not in_bounds(nx, ny):
                continue

            # Static obstacles
            cell_type = cells[nx][ny].type
            if cell_type == CellType.WALL:
                continue
            
            # EXIT cell constraint: Only enter an EXIT cell if it is the goal
            if cell_type == CellType.EXIT and (nx, ny) != (gx, gy):
                continue

            # ENTRY cell constraint: Only enter an ENTRY cell if it is the start cell (spawn)
            # or the goal. This prevents cars from using the entrance as an alternate "exit" route.
            if cell_type == CellType.ENTRY and (nx, ny) != (sx, sy) and (nx, ny) != (gx, gy):
                continue

            # Dynamic/Temporary static obstacles (e.g. unplanned cars)
            # Only consider them obstacles for the first 'obstacle_persistence' steps
            if additional_obstacles and (nx, ny) in additional_obstacles and nt < persist_until_t:
                continue

            # Vertex constraint (next cell at next time)
            if (nx, ny) in static_cells or (nx, ny, nt) in vertex_res:
                continue

            # Edge constraint (moving x,y -> nx,ny during t -> t+1)
            if (x, y, nx, ny, t) in edge_res or (nx, ny, x, y, t) in edge_res:
                continue

            neighbor_key = nt * area + (nx * height + ny)
            tentative_g = g + 1

            # Standard A* relaxation
            prev_g = g_score.get(neighbor_key)
            if prev_g is not None and tentative_g >= prev_g:
                continue

            came_from[neighbor_key] = key
            g_score[neighbor_key] = tentative_g
            f = tentative_g + abs(nx - gx) + abs(ny - gy)
            heappush(open_set, (f, tentative_g, neighbor_key))

    return None
