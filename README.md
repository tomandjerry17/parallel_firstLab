# Paluto Restaurant — Distributed Kitchen System

A distributed order processing simulation using `mpi4py` and Python's
`multiprocessing` module. A Head Chef (master process) dispatches dish
tickets to Line Cooks (worker processes) that cook concurrently and post
results to a shared kitchen board.

---

## How to Run

### Requirements
- Python 3.x
- MS-MPI installed (Windows)
- mpi4py: `pip install mpi4py`

### Step 1 — Environment Test
```bash
mpiexec -n 5 python mpi_test.py
```

### Step 2 — MPI Phase (ticket distribution)
```bash
mpiexec -n 5 python kitchen.py
```

### Step 3 — Cooking Phase (shared memory + synchronization)
```bash
python kitchen.py --cook
```

> Note: Windows does not support mixing MPI and multiprocessing in the
> same process, so the system runs in two separate phases. The MPI phase
> saves assignments to `cook_assignments.json`, which the cooking phase
> then loads automatically.

---

## File Structure

```
kitchen-system/
├── mpi_test.py     # Environment verification
├── kitchen.py      # Main program (all 4 stages)
└── README.md       # This file
```

---

## Reflection Questions

### 1. How did you distribute orders among worker processes?

The Head Chef (rank 0) holds the full menu and iterates through each order,
assigning it to a cook using round-robin logic:
`target = (order_index % num_workers) + 1`. This spreads tickets as evenly
as possible across all available cooks. Each order is sent individually
using `comm.send()` with `tag=1`, and after all tickets are sent, a `None`
stop signal with `tag=0` is sent to each cook so they know when to stop
receiving.

### 2. What happens if there are more orders than workers?

Cooks receive multiple tickets because of the round-robin assignment. With
8 orders and 4 cooks, each cook receives exactly 2 tickets. If there were
9 orders, Cook 1 would receive 3 tickets while the rest receive 2. Each
cook processes their tickets sequentially — finishing one dish before
starting the next — so no order is ever skipped or lost.

### 3. How did processing delays affect the order completion?

Dish complexity determined prep time: easy dishes took 1s, medium 2s, and
hard 3s. Because all cooks ran in parallel, simpler dishes completed and
posted to the board much earlier than complex ones. For example, Chicken
Adobo (easy, 1s) was on the board before Beef Sinigang (hard, 3s) even
though Sinigang was dispatched first. This reflects how a real kitchen
works — simpler dishes always finish faster regardless of dispatch order.

### 4. How did you implement shared memory, and where was it initialized?

A `Manager().list()` was used as the shared kitchen board. It was
initialized in `run_cooking_phase()` inside the main process, before any
cook subprocesses were launched. The `kitchen_board` list was then passed
as an argument into each `cook_worker()` subprocess. Because
`Manager().list()` is managed by a separate background server process, all
cook subprocesses can safely read and write to the same list across process
boundaries.

### 5. What issues occurred when multiple workers wrote to shared memory simultaneously?

Without a `Lock()`, two cooks finishing at nearly the same time could both
enter `kitchen_board.append()` simultaneously. This caused race conditions
where entries were written in unpredictable order or, in some cases, one
write would partially overwrite another. The final board sometimes showed
fewer than 8 entries, meaning a completed dish was silently lost from the
record.

### 6. How did you ensure consistent results when using multiple processes?

A `multiprocessing.Lock()` was passed into each `cook_worker()` and
wrapped around the `kitchen_board.append()` call using a `with lock:`
block. This creates a critical section — only one cook can write to the
board at a time. Any cook that finishes while the lock is held must wait
until it is released before posting their result. This guaranteed that all
8 dishes always appeared on the final board with no missing or duplicate
entries.