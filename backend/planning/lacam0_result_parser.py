import os
import re
from typing import Dict, List, Optional, Tuple


class LaCAM0ResultParser:
    """
    Parses a LaCAM0 result.txt file into per-agent (x, y) path lists.

    Result file format (from "understand lacam0/result.txt"):
      solved=1
      ...
      solution=
      0:(11,6),(29,9),(9,0),
      1:(11,7),(29,10),(10,0),
      ...
      T:(x0,y0),(x1,y1),...,(xN,yN),

    Coordinate system: (x=column, y=row), 0-indexed — matches the
    simulation's internal (x, y) convention.
    """

    _POSITION_RE = re.compile(r"\((\d+),(\d+)\)")

    def parse(
        self, result_path: str
    ) -> Optional[Dict[int, List[Tuple[int, int]]]]:
        """
        Parse result.txt and return per-agent (x, y) position sequences.

        Returns:
          { agent_index: [(x, y), (x, y), ...] }   on success
          None                                       if file missing, or solved=0
        """
        if not os.path.exists(result_path):
            return None

        paths: Dict[int, List[Tuple[int, int]]] = {}
        in_solution = False
        solved = False

        with open(result_path, "r") as f:
            for line in f:
                line = line.strip()

                if line.startswith("solved="):
                    solved = line.split("=", 1)[1] == "1"
                    continue

                if line == "solution=":
                    if not solved:
                        return None
                    in_solution = True
                    continue

                if in_solution and line:
                    colon = line.index(":")
                    positions = self._POSITION_RE.findall(line[colon + 1:])
                    for i, (x_str, y_str) in enumerate(positions):
                        paths.setdefault(i, []).append(
                            (int(x_str), int(y_str))
                        )

        return paths if paths else None
