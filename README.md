# 🍽️ Paluto Restaurant — Distributed Kitchen System

A distributed order processing simulation built with `mpi4py` and Python's
`multiprocessing` module. Instead of generic "customer orders," this system
models a restaurant kitchen where a **Head Chef** (master process) dispatches
dish tickets to **Line Cooks** (worker processes) that cook concurrently and
post results to a shared kitchen board.

---

## How to Run

### Requirements
- Python 3.x
- MS-MPI installed (Windows)
- mpi4py: `pip install mpi4py`

### Environment Test
```bash
mpiexec -n 5 python mpi_test.py
```

### Main Program
```bash
mpiexec -n 5 python kitchen.py
```

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

The Head Chef (rank 0) holds the full menu list and iterates through each
order, assigning it to a cook using round-robin logic:
`target_cook = (order_index % num_workers) + 1`. This ensures orders are
spread as evenly as possible. Each order is sent via `comm.send()` with
`tag=1`, and a `None` stop signal with `tag=0` is sent afterward so cooks
know when to stop receiving.

---

### 2. What happens if there are more orders than workers?

Since we use round-robin distribution, extra orders loop back to earlier
cooks. With 8 orders and 4 cooks, each cook gets exactly 2 tickets. If
there were 9 orders, Cook 1 would receive 3 tickets while the others get 2.
Cooks handle their extra tickets sequentially — they finish one dish before
starting the next — so no order is ever dropped or skipped.

---

### 3. How did processing delays affect the order completion?

Dishes with higher complexity slept longer (`hard=3s`, `medium=2s`,
`easy=1s`), so they finished later regardless of when they were dispatched.
This meant the kitchen board was filled out of order — for example, Chicken
Adobo (easy, 1s) appeared on the board before Beef Sinigang (hard, 3s) even
though Sinigang was dispatched first. This mirrors a real kitchen where
simple dishes finish faster than complex ones.

---

### 4. How did you implement shared memory, and where was it initialized?

A `Manager().list()` was used as the shared kitchen board. It was
initialized in the Head Chef process (rank 0) inside `main()`, after
all MPI communication was complete. The `manager` object and
`kitchen_board` list were then passed as arguments into each
`cook_worker()` subprocess. Because `Manager().list()` lives in a
separate manager server process, all cook subprocesses can safely
reference and append to the same list across process boundaries.

---

### 5. What issues occurred when multiple workers wrote to shared memory simultaneously?

Without a `Lock()`, two cooks finishing at nearly the same time could both
enter the `kitchen_board.append()` call simultaneously. In testing, this
occasionally caused entries to be written in a garbled sequence or, in
rare cases, one entry would overwrite another mid-write. The final board
count would sometimes show fewer entries than expected, meaning a completed
dish was lost from the record entirely.

---

### 6. How did you ensure consistent results when using multiple processes?

A `multiprocessing.Lock()` was passed into each `cook_worker()` and wrapped
around the `kitchen_board.append()` call using a `with lock:` block. This
creates a critical section — only one cook can write to the board at a time.
Any other cook that finishes while the lock is held must wait until it is
released before posting their result. This guaranteed that all 8 dishes
always appeared on the final board with no missing or duplicate entries.