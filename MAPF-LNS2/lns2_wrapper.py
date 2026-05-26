"""
lns2_wrapper.py
---------------
Python interface to the MAPF-LNS2 solver (lns.exe) via subprocess.

Usage example:
    from lns2_wrapper import LNS2Solver, LNS2Result

    solver = LNS2Solver()
    result = solver.solve(
        map_file="random-32-32-20.map",
        scen_file="random-32-32-20-random-1.scen",
        num_agents=50,
    )
    print(result.solved, result.makespan, result.solution_cost)
    print(result.solution[0])   # list of (x,y) positions at timestep 0

Coordinate convention
---------------------
lns.exe writes paths as  Agent N:(row,col)->(row,col)->...
Our grid uses (x=col, y=row), so the parser swaps each pair:
    x = col = second integer
    y = row = first integer
"""

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple


# ---------------------------------------------------------------------------
# DLL search path — lns.exe depends on MinGW runtime DLLs
# ---------------------------------------------------------------------------
_MINGW_BIN = r"C:\msys64\mingw64\bin"


@dataclass
class LNS2Result:
    solved: bool
    agents: int
    makespan: int
    solution_cost: int
    initial_solution_cost: int
    runtime_sec: float
    iterations: int
    solution: List[List[Tuple[int, int]]]  # solution[t] = [(x,y), ...] per agent


@dataclass
class LNS2Solver:
    """Wrapper around the MAPF-LNS2 lns.exe binary."""

    exe: str = str(Path(__file__).resolve().parent / "build" / "lns.exe")
    time_limit_sec: float = 5.0
    init_algo: str = "PP"
    replan_algo: str = "PP"
    destroy_strategy: str = "Adaptive"
    neighbor_size: int = 8
    seed: int = 0

    def solve(
        self,
        map_file: str,
        scen_file: str,
        num_agents: int,
        verbose: int = 0,
    ) -> LNS2Result:
        """Run lns.exe and return a parsed LNS2Result.

        Args:
            map_file:    Path to the .map file (MovingAI octile format).
            scen_file:   Path to the .scen file (MovingAI benchmark format).
            num_agents:  Number of agents (uses first num_agents rows of scen).
            verbose:     Screen verbosity: 0=silent, 1=summary, 2=detailed.
        """
        exe_path = Path(self.exe).resolve()
        if not exe_path.exists():
            raise RuntimeError(f"lns2 exe not found: {exe_path}")

        tmp_paths = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
        paths_file = tmp_paths.name
        tmp_paths.close()

        cmd = [
            str(exe_path),
            "-m", map_file,
            "-a", scen_file,
            "-k", str(num_agents),
            "-t", str(int(self.time_limit_sec)),
            "-s", str(verbose),
            "--outputPaths", paths_file,
            "--seed", str(self.seed),
            "--initAlgo", self.init_algo,
            "--replanAlgo", self.replan_algo,
            "--destoryStrategy", self.destroy_strategy,
            "--neighborSize", str(self.neighbor_size),
        ]

        lns2_dir = str(exe_path.parent.parent)

        env = os.environ.copy()
        if _MINGW_BIN not in env.get("PATH", ""):
            env["PATH"] = _MINGW_BIN + os.pathsep + env.get("PATH", "")

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=lns2_dir,
                env=env,
            )
            if proc.returncode != 0:
                hint = (
                    " (STATUS_DLL_NOT_FOUND — ensure C:\\msys64\\mingw64\\bin is accessible"
                    " or copy its DLLs into MAPF-LNS2/build/)"
                    if proc.returncode == 3221225781 else ""
                )
                raise RuntimeError(
                    f"lns2 solver failed (exit {proc.returncode}){hint}\n"
                    f"STDOUT: {proc.stdout.strip()}\n"
                    f"STDERR: {proc.stderr.strip()}"
                )
        except FileNotFoundError:
            raise RuntimeError(f"lns2 exe not found at runtime: {exe_path}")

        result = _parse_lns2_result(paths_file, num_agents, proc.stdout)

        try:
            os.unlink(paths_file)
        except OSError:
            pass

        return result


# ---------------------------------------------------------------------------
# Internal parsing helpers
# ---------------------------------------------------------------------------

def _parse_lns2_paths(paths_file: str, num_agents: int) -> List[List[Tuple[int, int]]]:
    """Parse lns.exe --outputPaths file into agent-indexed position lists.

    Input format (one line per agent):
        Agent 0:(row,col)->(row,col)->...
        Agent 1:(row,col)->...

    Returns:
        agent_paths[agent_idx] = [(x0,y0), (x1,y1), ...]
        where x=col, y=row  (coordinate swap applied).
    """
    agent_paths: List[List[Tuple[int, int]]] = [[] for _ in range(num_agents)]

    try:
        with open(paths_file, "r") as f:
            lines = f.readlines()
    except (OSError, IOError):
        return agent_paths

    for line in lines:
        line = line.strip()
        m = re.match(r"^Agent\s+(\d+):(.+)$", line)
        if not m:
            continue
        agent_idx = int(m.group(1))
        if agent_idx >= num_agents:
            continue
        positions: List[Tuple[int, int]] = []
        for pm in re.finditer(r"\((\d+),(\d+)\)", m.group(2)):
            row = int(pm.group(1))
            col = int(pm.group(2))
            positions.append((col, row))  # swap: (x=col, y=row)
        if positions:
            agent_paths[agent_idx] = positions

    return agent_paths


def _transpose_to_timesteps(
    agent_paths: List[List[Tuple[int, int]]]
) -> List[List[Tuple[int, int]]]:
    """Transpose agent-indexed paths to timestep-indexed solution.

    Input:  agent_paths[agent_idx][t] = (x, y)
    Output: solution[t][agent_idx]    = (x, y)

    Agents with shorter paths hold their final position.
    """
    if not agent_paths or all(len(p) == 0 for p in agent_paths):
        return []

    makespan = max((len(p) for p in agent_paths), default=0)
    solution: List[List[Tuple[int, int]]] = []
    for t in range(makespan):
        config: List[Tuple[int, int]] = []
        for agent_path in agent_paths:
            if not agent_path:
                config.append((0, 0))
            elif t < len(agent_path):
                config.append(agent_path[t])
            else:
                config.append(agent_path[-1])
        solution.append(config)
    return solution


def _parse_summary_line(stdout: str) -> Tuple[float, int, int, int]:
    """Extract (runtime_sec, iterations, solution_cost, initial_solution_cost)
    from the last LNS console summary line, if present.

    Format: LNS(...): runtime = X, iterations = Y, solution cost = Z,
                      initial solution cost = W, ...
    """
    runtime = 0.0
    iterations = 0
    solution_cost = 0
    initial_solution_cost = 0

    for line in reversed(stdout.splitlines()):
        m = re.search(r"runtime\s*=\s*([\d.]+)", line)
        if m:
            runtime = float(m.group(1))
        m = re.search(r"iterations\s*=\s*(\d+)", line)
        if m:
            iterations = int(m.group(1))
        m = re.search(r"solution cost\s*=\s*(\d+)", line)
        if m:
            solution_cost = int(m.group(1))
        m = re.search(r"initial solution cost\s*=\s*(\d+)", line)
        if m:
            initial_solution_cost = int(m.group(1))
        if runtime > 0 or iterations > 0:
            break

    return runtime, iterations, solution_cost, initial_solution_cost


def _parse_lns2_result(paths_file: str, num_agents: int, stdout: str) -> LNS2Result:
    agent_paths = _parse_lns2_paths(paths_file, num_agents)
    solved = any(len(p) > 0 for p in agent_paths)
    solution = _transpose_to_timesteps(agent_paths)
    makespan = len(solution)

    runtime, iterations, solution_cost, initial_solution_cost = _parse_summary_line(stdout)

    return LNS2Result(
        solved=solved,
        agents=num_agents,
        makespan=makespan,
        solution_cost=solution_cost,
        initial_solution_cost=initial_solution_cost,
        runtime_sec=runtime,
        iterations=iterations,
        solution=solution,
    )
