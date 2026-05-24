"""
lacam_wrapper.py
----------------
Python interface to the lacam0 solver via subprocess.

Usage example:
    from lacam_wrapper import LaCaM, LaCaMResult

    solver = LaCaM()
    result = solver.solve(
        map_file="assets/random-32-32-10.map",
        scen_file="assets/random-32-32-10-random-1.scen",
        num_agents=50,
    )
    print(result.solved, result.makespan, result.sum_of_costs)
    print(result.solution[0])   # list of (x,y) positions at timestep 0
"""

import subprocess
import tempfile
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class LaCaMResult:
    solved: bool
    agents: int
    makespan: int
    makespan_lb: int
    sum_of_costs: int
    sum_of_costs_lb: int
    sum_of_loss: int
    sum_of_loss_lb: int
    comp_time_ms: float
    seed: int
    starts: list[tuple[int, int]]
    goals: list[tuple[int, int]]
    solution: list[list[tuple[int, int]]]  # solution[t] = [(x,y), ...] for each agent


@dataclass
class LaCaM:
    """Wrapper around the lacam0 main.exe binary."""

    exe: str = str(Path(__file__).resolve().parent / "build" / "main.exe")
    time_limit_sec: float = 3.0
    anytime: bool = False
    no_pibt_swap: bool = False
    no_pibt_hindrance: bool = False
    no_dist_table_init: bool = False

    def solve(
        self,
        map_file: str,
        num_agents: int,
        scen_file: Optional[str] = None,
        seed: int = 0,
        verbose: int = 0,
        output_file: Optional[str] = None,
    ) -> LaCaMResult:
        """Run the lacam0 solver and return a parsed LaCaMResult.

        Args:
            map_file:     Path to the .map file.
            num_agents:   Number of agents.
            scen_file:    Path to the .scen file (optional; random placement used if omitted).
            seed:         Random seed (used when no scen_file is given).
            verbose:      Verbosity level passed to the solver.
            output_file:  Where to write result.txt (uses a temp file if None).
        """
        use_temp = output_file is None
        if use_temp:
            tmp = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
            output_file = tmp.name
            tmp.close()

        cmd = [
            self.exe,
            "-m", map_file,
            "-N", str(num_agents),
            "-s", str(seed),
            "-v", str(verbose),
            "-t", str(self.time_limit_sec),
            "-o", output_file,
        ]
        if scen_file:
            cmd += ["-i", scen_file]
        if self.anytime:
            cmd.append("--anytime")
        if self.no_pibt_swap:
            cmd.append("--no_pibt_swap")
        if self.no_pibt_hindrance:
            cmd.append("--no_pibt_hindrance")
        if self.no_dist_table_init:
            cmd.append("--no_dist_table_init")

        exe_path = Path(self.exe).resolve()
        if not exe_path.exists():
            raise RuntimeError(f"lacam0 exe not found: {exe_path}")

        lacam0_dir = str(exe_path.parent.parent)
        print(f"[LaCAM0 wrapper] exe={exe_path} cwd={lacam0_dir}")
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=lacam0_dir,
            )
            if proc.stdout.strip():
                print(f"[LaCAM0 exe stdout]\n{proc.stdout.rstrip()}")
            if proc.stderr.strip():
                print(f"[LaCAM0 exe stderr]\n{proc.stderr.rstrip()}")
            if proc.returncode != 0:
                hint = (
                    " (STATUS_DLL_NOT_FOUND — copy libstdc++-6.dll, libgcc_s_seh-1.dll,"
                    " libwinpthread-1.dll from MSYS2/MinGW bin into lacam0/build/)"
                    if proc.returncode == 3221225781 else ""
                )
                raise RuntimeError(
                    f"lacam0 solver failed (exit {proc.returncode}){hint}\n"
                    f"STDOUT: {proc.stdout.strip()}\n"
                    f"STDERR: {proc.stderr.strip()}"
                )
        except FileNotFoundError:
            raise RuntimeError(f"lacam0 exe not found at runtime: {exe_path}")

        result = _parse_result(output_file)

        if use_temp:
            os.unlink(output_file)

        return result


# ---------------------------------------------------------------------------
# Internal parsing helpers
# ---------------------------------------------------------------------------

def _parse_coords(raw: str) -> list[tuple[int, int]]:
    """Parse a comma-separated list of (x,y) pairs like '(1,2),(3,4),...'"""
    return [
        (int(m.group(1)), int(m.group(2)))
        for m in re.finditer(r"\((\d+),(\d+)\)", raw)
    ]


def _parse_result(path: str) -> LaCaMResult:
    with open(path, "r") as f:
        text = f.read()

    def get(key: str, default="0") -> str:
        m = re.search(rf"^{key}=(.+)$", text, re.MULTILINE)
        return m.group(1).strip() if m else default

    solution: list[list[tuple[int, int]]] = []
    for line in text.splitlines():
        m = re.match(r"^(\d+):(.+)$", line)
        if m:
            solution.append(_parse_coords(m.group(2)))

    return LaCaMResult(
        solved=get("solved") == "1",
        agents=int(get("agents")),
        makespan=int(get("makespan")),
        makespan_lb=int(get("makespan_lb")),
        sum_of_costs=int(get("soc")),
        sum_of_costs_lb=int(get("soc_lb")),
        sum_of_loss=int(get("sum_of_loss")),
        sum_of_loss_lb=int(get("sum_of_loss_lb")),
        comp_time_ms=float(get("comp_time")),
        seed=int(get("seed")),
        starts=_parse_coords(get("starts", "")),
        goals=_parse_coords(get("goals", "")),
        solution=solution,
    )
