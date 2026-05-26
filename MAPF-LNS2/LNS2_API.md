# MAPF-LNS2 API Reference

## Before Running

Add MinGW DLLs to PATH every session:
```powershell
$env:PATH = "C:\msys64\mingw64\bin;" + $env:PATH
```

---

## Basic Command

```
.\build\lns.exe -m <map> -a <scenario> -k <agents> -t <seconds> [options]
```

---

## Parameters

### Required
| Flag | Description |
|------|-------------|
| `-m` | Path to `.map` file (MovingAI grid format) |
| `-a` | Path to `.scen` scenario file |

### Common Options
| Flag | Default | Description |
|------|---------|-------------|
| `-k` | `0` (all) | Number of agents (uses first k rows of scenario file) |
| `-t` | `7200` | Time limit in seconds |
| `-s` | `0` | Screen verbosity: `0`=silent, `1`=summary, `2`=detailed, `3`=MAPF detailed |
| `--seed` | `0` | Random seed |

### Output Files
| Option | Description |
|--------|-------------|
| `-o <name>` | Write summary CSV → `<name>-LNS.csv` |
| `--outputPaths <file>` | Write per-agent paths to a text file |
| `--stats <name>` | Write per-iteration stats CSV → `<name>-LNS.csv` |

### Solver
| Option | Default | Choices |
|--------|---------|---------|
| `--solver` | `LNS` | `LNS`, `A-BCBS`, `A-EECBS` |
| `--sipp` | `true` | Use SIPP low-level planner (`true`/`false`) |

### LNS Tuning
| Option | Default | Choices / Notes |
|--------|---------|-----------------|
| `--initAlgo` | `PP` | Initial solver: `PP`, `EECBS`, `CBS`, `PIBT`, `winPIBT`, `PPS` |
| `--replanAlgo` | `PP` | Replan solver: `PP`, `EECBS`, `CBS` |
| `--destoryStrategy` | `Adaptive` | `Random`, `RandomWalk`, `Intersection`, `Adaptive` |
| `--neighborSize` | `8` | Agents replanned per iteration |
| `--maxIterations` | `0` | Max LNS iterations (0 = run until time limit) |
| `--initLNS` | `true` | Use LNS to repair collisions in initial solution |
| `--initDestoryStrategy` | `Adaptive` | `Target`, `Collision`, `Random`, `Adaptive` |
| `--pibtWindow` | `5` | Window size for winPIBT |
| `--winPibtSoftmode` | `true` | Soft mode for winPIBT |

---

## Output Files

### Paths file (`--outputPaths paths.txt`)
One line per agent with `(row,col)` at every timestep:
```
Agent 0:(3,5)->(3,6)->(3,7)->
Agent 1:(10,2)->(10,2)->(10,3)->
```

### Summary CSV (`-o results` → `results-LNS.csv`)
One row appended per run. Columns:
```
runtime, solution cost, initial solution cost, lower bound,
sum of distance, iterations, group size,
runtime of initial solution, restart times, area under curve,
LL expanded nodes, LL generated, LL reopened, LL runs,
preprocessing runtime, solver name, instance name
```

### Iteration stats CSV (`--stats stats` → `stats-LNS.csv`)
One row per LNS iteration. Useful for plotting cost-over-time curves. Columns:
```
num of agents, sum of costs, runtime, cost lowerbound,
sum of distances, MAPF algorithm
```

---

## Example Runs

**Smoke test — print summary to console:**
```powershell
.\build\lns.exe -m random-32-32-20.map -a random-32-32-20-random-1.scen -k 50 -t 10 -s 1
```

**Save paths + summary CSV:**
```powershell
.\build\lns.exe `
  -m random-32-32-20.map `
  -a random-32-32-20-random-1.scen `
  -k 400 -t 300 `
  -o results --outputPaths paths.txt
```

**Full run with all outputs + iteration stats:**
```powershell
.\build\lns.exe `
  -m random-32-32-20.map `
  -a random-32-32-20-random-1.scen `
  -k 400 -t 300 -s 1 `
  -o results --outputPaths paths.txt --stats stats
```

**Use CBS for replanning, Intersection destroy strategy:**
```powershell
.\build\lns.exe `
  -m random-32-32-20.map `
  -a random-32-32-20-random-1.scen `
  -k 200 -t 120 `
  --replanAlgo CBS --destoryStrategy Intersection `
  -o results
```

**Anytime EECBS solver:**
```powershell
.\build\lns.exe `
  -m random-32-32-20.map `
  -a random-32-32-20-random-1.scen `
  -k 200 -t 120 `
  --solver A-EECBS -o results
```

---

## Console Output Format

When `-s 1`, each line printed during the run looks like:
```
LNS(PP;PP): runtime = 1.23, iterations = 45, solution cost = 3210,
            initial solution cost = 3500, failed iterations = 2
```

- **runtime** — seconds elapsed so far
- **iterations** — LNS iterations completed
- **solution cost** — current sum of all agent path lengths (lower is better)
- **initial solution cost** — cost after the initial solve before LNS improvement
- **failed iterations** — iterations where no improvement was found
