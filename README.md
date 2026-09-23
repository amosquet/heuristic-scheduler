# Heuristic Print Queue Scheduler (`heuristic-scheduler`)

[![Python Version](https://img.shields.io/badge/python-3.13%2B-blue.svg)](pyproject.toml)
[![Package Manager](https://img.shields.io/badge/managed%20by-uv-purple.svg)](https://github.com/astral-sh/uv)
[![Test Suite](https://img.shields.io/badge/pytest-25%20passed-brightgreen.svg)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-99%25-success.svg)](tests/)
[![Course](https://img.shields.io/badge/ECE%2049595-Senior%20Design%20I-orange.svg)](https://purdue.edu)

An autonomous, starvation-resistant dynamic priority queue and discrete-event simulation engine for additive manufacturing fleets. Built as the scheduling prototype for **PrintHive** in **ECE 49595 (Senior Design I - Software Track)** at Purdue University.

---

## Problem Overview

Campus makerspaces and shared 3D printing labs (e.g., Purdue Bechtel Innovation Design Center, Purdue Hive) frequently suffer from severe queue bottlenecks when managed via standard First-Come, First-Served (FCFS) dispatching:

- **Queue Starvation:** High-priority submissions (e.g., academic capstones, staff maintenance jobs) can indefinitely delay lower-priority student prints if priorities are static.
- **Physical Handover Latency:** FCFS schedulers fail to account for post-print operations, such as print bed cooldown and manual part removal. Prints finish unmonitored and sit idle on heated build plates.
- **Dynamic Arrival Complexity:** Jobs arrive continuously at arbitrary timestamps with disparate build durations and priority tiers.

`heuristic-scheduler` addresses these challenges by implementing a **discrete-event timeline simulation** with a **mathematically optimized dynamic priority queue** utilizing linear time-dependent aging and physical bed-clearance buffer windows.

---

## Mathematical Formulation & Algorithmic Design

### Dynamic Priority with Linear Aging

To prevent starvation, each waiting job's effective priority score $P_i(t)$ increases dynamically as a function of the time it has spent waiting in the queue:

$$P_i(t) = W_{\text{base}, i} + \alpha \cdot (t - t_{\text{submit}, i})$$

Where:

- $W_{\text{base}, i}$: The base priority weight assigned to the job (e.g., standard student print vs. urgent staff job).
- $\alpha$: The aging rate coefficient ($\text{priority points} / \text{second}$).
- $t$: The current simulation timestamp (seconds).
- $t_{\text{submit}, i}$: The arrival/submission timestamp of job $i$ (seconds).

### The Static-Score Heap Invariant ($O(1)$ Re-Ranking)

In a naive dynamic queue, all waiting jobs must be re-evaluated and sorted every time a machine becomes available, leading to an expensive $O(N \log N)$ operation at every scheduling event.

However, when all waiting jobs share a uniform linear aging rate $\alpha$, the priority equation can be rewritten as:

$$P_i(t) = \underbrace{(W_{\text{base}, i} - \alpha \cdot t_{\text{submit}, i})}_{\text{Static Score } S_i} + \alpha \cdot t$$

Notice that for any two waiting jobs $A$ and $B$ evaluated at identical simulation time $t$:

$$P_A(t) > P_B(t) \iff S_A > S_B$$

Because the $\alpha \cdot t$ term increases at the exact same rate for every queued job, the relative priority ordering among waiting jobs is strictly **time-invariant**.

**Algorithmic Benefit:** We compute the static score $S_i = W_{\text{base}, i} - \alpha \cdot t_{\text{submit}, i}$ once upon arrival and push the job into a binary max-heap (`heapq` with negated keys). Dispatches achieve optimal $O(\log N)$ push/pop complexity without periodic queue rebuilds.

### Deterministic Tie-Breaking

When multiple jobs possess identical static priority scores, ties are resolved deterministically using a multi-key tuple:

1. **Static Priority Score** (highest score first via negation)
2. **Submission Time** (earliest arrival first, enforcing FCFS fairness)
3. **Job ID** (lowest numerical ID first for deterministic ordering)

### Soft Cancellation (Tombstoning)

Jobs cancelled mid-queue have their `cancelled` flag toggled to `True`. The dispatch engine discards cancelled jobs lazily upon popping ($O(\log N)$) rather than performing an expensive in-heap search and rebalance ($O(N)$).

---

## Project Architecture

```
heuristic-scheduler/
├── pyproject.toml              # Project configuration, dependencies, and pytest metadata
├── uv.lock                     # Deterministic dependency lockfile
├── jobs.json                   # Default benchmark dataset (5 print jobs)
├── jobs1.json                  # Multi-tier arrival test dataset
├── jobs3.json                  # Scaled workload dataset
├── conftest.py                 # Pytest root configuration
├── data.py                     # Data models (PrintJob dataclass) and JSON parsers
├── manager.py                  # Priority scoring engine and heapq queue manager
├── simulate.py                 # Discrete-event simulation loop and execution reporter
├── main.py                     # CLI entrypoint with configurable parameters
├── src/
│   └── heuristic_scheduler/    # Package entrypoint for CLI execution
└── tests/                      # Automated unit and integration test suite (99% coverage)
    ├── test_data.py            # Validation of data parsing and weight calculations
    ├── test_manager.py         # Static scoring, tie-breaking, and heap push/pop tests
    ├── test_scheduler.py       # Cancellation handling and priority inversion verification
    ├── test_simulation.py      # Timeline stepping, buffer times, and idle gap tests
    └── test_integration.py     # End-to-end simulation runs on realistic datasets
```

---

## Getting Started

### Prerequisites

- Python `>= 3.13`
- [`uv`](https://docs.astral.sh/uv/) (recommended high-speed Python package manager)

### Installation

Clone the repository and install dependencies using `uv`:

```bash
git clone https://github.com/AlmondMan/heuristic-scheduler.git
cd heuristic-scheduler
uv sync
```

Alternatively, if using standard `pip` and virtual environments:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install pytest pytest-cov
```

---

## CLI Usage

Run the discrete-event simulation using `uv run python main.py` or through the CLI executable:

### Basic Execution (Default Dataset)

```bash
uv run python main.py
```

### Custom Dataset with Tuned Parameters

```bash
uv run python main.py jobs1.json --alpha 0.08 --buffer-time 300
```

### CLI Arguments & Options

| Option          | Short |  Type   |   Default   | Description                                                           |
| :-------------- | :---: | :-----: | :---------: | :-------------------------------------------------------------------- |
| `filepath`      |  N/A  |  `str`  | `jobs.json` | Path to the JSON dataset containing print jobs.                       |
| `--alpha`       | `-a`  | `float` |   `0.05`    | Dynamic aging coefficient ($\text{priority points} / \text{second}$). |
| `--buffer-time` | `-b`  |  `int`  |    `600`    | Physical transition buffer in seconds (bed cooldown + part removal).  |

### Example Terminal Output

```
=========================================================================================================
                                  HEURISTIC PRINT SCHEDULER SIMULATION
                    Alpha (Aging Rate): 0.05 | Bed Clear Buffer: 600s | Total Jobs: 5
=========================================================================================================
Seq  | Job ID  | Submit (s) | Start (s)  | Wait (s)  | Duration (s) | Finish (s) | Next Ready (s) | Priority
---------------------------------------------------------------------------------------------------------
1    | 101     | 0          | 0          | 0         | 1800         | 1800       | 2400           | 50.00
2    | 102     | 300        | 2400       | 2100      | 3600         | 6000       | 6600           | 195.00
3    | 103     | 600        | 6600       | 6000      | 1200         | 7800       | 8400           | 330.00
4    | 104     | 2400       | 8400       | 6000      | 2400         | 10800      | 11400          | 370.00
5    | 105     | 3000       | 11400      | 8400      | 900          | 12300      | 12900          | 430.00
=========================================================================================================
                                           SIMULATION SUMMARY
---------------------------------------------------------------------------------------------------------
  • Total Jobs Processed : 5
  • Execution Order      : Job #101 -> Job #102 -> Job #103 -> Job #104 -> Job #105
  • Final Job Completion : 12300 s
  • Total Print Duration : 9900 s
  • Average Wait Time    : 4500.00 s
  • Total Simulation End : 12900 s (including final buffer)
=========================================================================================================
```

---

## Dataset Format

Job datasets are formatted in JSON as either a flat array of job objects or a dictionary containing a `"jobs"` key:

```json
[
  {
    "job_id": 101,
    "base_weight": 50,
    "submit_time": 0,
    "print_duration": 1800,
    "cancelled": false
  },
  {
    "job_id": 102,
    "base_weight": 80,
    "submit_time": 300,
    "print_duration": 3600,
    "cancelled": false
  }
]
```

### Schema Fields

- `job_id` (`int`): Unique identifier for the print submission.
- `base_weight` (`int`): Base priority score (higher values indicate higher priority).
- `submit_time` (`int`): Submission timestamp in epoch seconds from start of simulation ($T \ge 0$).
- `print_duration` (`int`): Estimated execution duration on the 3D printer in seconds.
- `cancelled` (`bool`, optional): Soft cancellation state (defaults to `false`).

---

## Testing & Verification

The project includes an automated test suite covering unit functions, queue state mutations, mathematical edge cases, and end-to-end integration runs.

Run the test suite with line coverage reporting:

```bash
uv run pytest --cov
```

### Test Coverage Summary

```
Name                        Stmts   Miss  Cover
-----------------------------------------------
conftest.py                     0      0   100%
data.py                        17      0   100%
manager.py                     26      0   100%
simulate.py                    60      0   100%
tests/test_data.py             44      0   100%
tests/test_integration.py      19      1    95%
tests/test_manager.py          57      0   100%
tests/test_scheduler.py        35      0   100%
tests/test_simulation.py       59      0   100%
-----------------------------------------------
TOTAL                         317      1    99%
```

### Key Behaviors Validated

- **Priority Inversion over Time (`test_scheduler.py`):** Proves that an earlier low-priority job ($W=10, T=0$) mathematically overtakes a later higher-priority job ($W=50, T=1000$) through dynamic aging, confirming starvation resistance.
- **Mid-Queue Cancellation (`test_scheduler.py`):** Confirms that cancelled jobs are safely skipped without corrupting remaining queue order.
- **Arrival Gaps & Timeline Advancement (`test_simulation.py`):** Ensures that when the machine is idle and no jobs are queued, the simulation clock jumps directly to the arrival of the next future job.
- **Multi-Key Tie Breaking (`test_manager.py`):** Verifies deterministic dispatching when multiple jobs have identical static scores.
