import os
from generator.cell import CellType


class LaCAM0FileGenerator:
    """
    Generates LaCAM0-compatible .map and .scen files from the current
    parking lot simulation state.
    """

    def generate_map(self, grid, parked_positions: set, output_path: str) -> None:
        """
        Write a MovingAI octile .map file.

        Encoding:
          WALL                                    -> '@'
          ROAD, ENTRY, EXIT                       -> '.'
          PARKING (no parked car there)           -> '.'
          PARKING (cell in parked_positions)      -> '@'  (static obstacle)

        Active/moving cars are NOT treated as obstacles here — LaCAM0
        plans them as agents and handles their collisions internally.

        parked_positions: set of (x, y) tuples for spots occupied by
                          parked (idle) cars.
        """
        lines = [
            "type octile",
            f"height {grid.height}",
            f"width {grid.width}",
            "map",
        ]
        for y in range(grid.height):
            row = []
            for x in range(grid.width):
                cell = grid.get_cell(x, y)
                if cell.type == CellType.WALL:
                    row.append("@")
                elif cell.type == CellType.PARKING and (x, y) in parked_positions:
                    row.append("@")
                else:
                    row.append(".")
            lines.append("".join(row))

        with open(output_path, "w") as f:
            f.write("\n".join(lines))

    def generate_scen(
        self,
        plannable_cars: list,
        map_filename: str,
        grid_width: int,
        grid_height: int,
        output_path: str,
        goal_overrides: dict = None,
    ) -> None:
        """
        Write a MovingAI scenario (.scen) file.

        plannable_cars: ordered list of Car objects that have a goal.
                        The index of each car here matches the agent index
                        in LaCAM0's result output.
        goal_overrides: optional dict mapping car_id -> (gx, gy).  When
                        present, overrides car.goal for the scen entry so
                        that duplicate goals can be replaced with nearby
                        unique alternatives without mutating the car object.

        Each line format:
          bucket  map_filename  W  H  start_x  start_y  goal_x  goal_y  0.0
        """
        lines = ["version 1"]
        for car in plannable_cars:
            sx, sy = car.current_position
            if goal_overrides and car.car_id in goal_overrides:
                gx, gy = goal_overrides[car.car_id]
            else:
                gx, gy = car.goal
            lines.append(
                f"0\t{map_filename}\t{grid_width}\t{grid_height}"
                f"\t{sx}\t{sy}\t{gx}\t{gy}\t0.0"
            )

        with open(output_path, "w") as f:
            f.write("\n".join(lines))
