# kitchen.py
# Paluto Restaurant — Distributed Kitchen System
#
# Windows requires TWO separate runs (MPI + multiprocessing can't mix):
#
#   STEP 1:  mpiexec -n 5 python kitchen.py
#            (MPI phase — Head Chef sends tickets, cooks receive them)
#
#   STEP 2:  python kitchen.py --cook
#            (Cooking phase — shared memory board + Lock synchronization)

import sys
import io
import os
import json
import time
import argparse
from multiprocessing import Manager, Process, Lock

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ==============================================================
# MENU
# ==============================================================
MENU = [
    {"ticket": 1, "dish": "Beef Sinigang",  "complexity": "hard"},
    {"ticket": 2, "dish": "Kare-Kare",       "complexity": "hard"},
    {"ticket": 3, "dish": "Lechon Kawali",    "complexity": "medium"},
    {"ticket": 4, "dish": "Chicken Adobo",    "complexity": "easy"},
    {"ticket": 5, "dish": "Pinakbet",         "complexity": "easy"},
    {"ticket": 6, "dish": "Crispy Pata",      "complexity": "hard"},
    {"ticket": 7, "dish": "Pancit Canton",    "complexity": "medium"},
    {"ticket": 8, "dish": "Tinolang Manok",   "complexity": "easy"},
]

PREP_TIME = {
    "easy":   1,
    "medium": 2,
    "hard":   3,
}

ASSIGNMENTS_FILE = "cook_assignments.json"


# ==============================================================
# PHASE 1 — MPI: distribute tickets, save assignments to file
# ==============================================================
def run_mpi_phase():
    from mpi4py import MPI

    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()

    # --- HEAD CHEF (rank 0) ---
    if rank == 0:
        num_workers = size - 1

        print("=" * 60)
        print("     PALUTO RESTAURANT  --  DISTRIBUTED KITCHEN")
        print("=" * 60)
        print(f"[Head Chef] Kitchen is open!")
        print(f"[Head Chef] {len(MENU)} orders | {num_workers} cooks on duty\n")

        # STAGE 1: Send tickets to cooks via MPI
        print("--- STAGE 1: Dispatching Tickets via MPI ---")
        for i, order in enumerate(MENU):
            target = (i % num_workers) + 1
            comm.send(order, dest=target, tag=1)
            print(f"[Head Chef] [TICKET] Ticket #{order['ticket']} "
                  f"({order['dish']}) --> Cook {target} [{order['complexity']}]")

        # Send stop signal to all cooks
        for w in range(1, size):
            comm.send(None, dest=w, tag=0)

        print("\n[Head Chef] All tickets dispatched. Collecting confirmations...\n")

        # Collect confirmed assignments from each cook
        all_assignments = {}
        for w in range(1, size):
            orders = comm.recv(source=w, tag=3)
            all_assignments[str(w)] = orders
            dishes = ', '.join(o['dish'] for o in orders)
            print(f"[Head Chef] Cook {w} confirmed: {dishes}")

        # Save assignments so Phase 2 can load them
        with open(ASSIGNMENTS_FILE, "w") as f:
            json.dump(all_assignments, f)

        print(f"\n[Head Chef] MPI phase complete. Assignments saved.")
        print(f"[Head Chef] >>> Now run: python kitchen.py --cook")
        print("=" * 60)

    # --- LINE COOKS (ranks 1-4) ---
    else:
        my_orders = []
        while True:
            order = comm.recv(source=0, tag=MPI.ANY_TAG)
            if order is None:
                break
            my_orders.append(order)
            print(f"  [Cook {rank}] Got Ticket #{order['ticket']}: "
                  f"{order['dish']} ({order['complexity']})")

        # Send assignment list back to Head Chef
        comm.send(my_orders, dest=0, tag=3)


# ==============================================================
# COOK WORKER — runs as subprocess in Phase 2
# ==============================================================
def cook_worker(cook_id, assigned_orders, kitchen_board, lock, use_lock=True):
    """
    Stage 2: Simulates cooking delay per dish complexity.
    Stage 4: Uses Lock() to safely write to the shared board.
    use_lock=False demonstrates the unsafe version for Stage 4 comparison.
    """
    for order in assigned_orders:
        prep_time = PREP_TIME[order["complexity"]]

        print(f"  [Cook {cook_id}] [COOKING] Ticket #{order['ticket']}: "
              f"{order['dish']} -- {prep_time}s prep time...")
        time.sleep(prep_time)

        entry = {
            "ticket":    order["ticket"],
            "dish":      order["dish"],
            "cook":      cook_id,
            "prep_time": prep_time,
            "status":    "SERVED",
        }

        if use_lock:
            # Stage 4 — only one cook writes at a time (SAFE)
            with lock:
                kitchen_board.append(entry)
                print(f"  [Cook {cook_id}] [BOARD] Ticket #{order['ticket']} "
                      f"{order['dish']} posted to board!")
        else:
            # No lock — unsafe concurrent write (intentional for demo)
            print(f"  [Cook {cook_id}] [WARNING] No lock -- writing Ticket "
                  f"#{order['ticket']} {order['dish']} unsafely...")
            kitchen_board.append(entry)
            print(f"  [Cook {cook_id}] [BOARD] Ticket #{order['ticket']} "
                  f"{order['dish']} posted (no lock)!")


# ==============================================================
# PHASE 2 — Cooking: shared memory + Lock (no MPI)
# ==============================================================
def run_cooking_phase(use_lock=True):
    if not os.path.exists(ASSIGNMENTS_FILE):
        print("[ERROR] cook_assignments.json not found!")
        print("        Run MPI phase first:  mpiexec -n 5 python kitchen.py")
        sys.exit(1)

    with open(ASSIGNMENTS_FILE, "r") as f:
        all_assignments = json.load(f)

    print("=" * 60)
    if use_lock:
        print("     PALUTO RESTAURANT  --  COOKING PHASE (WITH LOCK)")
    else:
        print("     PALUTO RESTAURANT  --  COOKING PHASE (NO LOCK)")
    print("=" * 60)
    print("[Head Chef] Assignments loaded from MPI phase:\n")
    for cook_id, orders in all_assignments.items():
        dishes = ', '.join(o['dish'] for o in orders)
        print(f"  Cook {cook_id}: {dishes}")

    print()
    if use_lock:
        print("--- STAGE 2, 3 & 4: Cooking + Shared Board + Lock (SAFE) ---\n")
    else:
        print("--- STAGE 2 & 3: Cooking + Shared Board, NO Lock (UNSAFE) ---\n")
        print("[Head Chef] [WARNING] Running WITHOUT Lock -- inconsistencies may occur!\n")

    manager = Manager()
    kitchen_board = manager.list()
    lock = Lock()

    start_time = time.time()

    processes = []
    for cook_id, orders in all_assignments.items():
        p = Process(
            target=cook_worker,
            args=(int(cook_id), orders, kitchen_board, lock, use_lock)
        )
        processes.append(p)
        p.start()

    for p in processes:
        p.join()

    elapsed = round(time.time() - start_time, 2)

    print("\n" + "=" * 60)
    print(f"[Head Chef] Kitchen done! Total cook time: {elapsed}s")

    if not use_lock:
        print(f"[Head Chef] [WARNING] No lock was used -- check for missing entries!\n")
    else:
        print()

    print("[Head Chef] Final Kitchen Board:\n")
    print(f"  {'Ticket':<8} {'Dish':<20} {'Cook':<8} {'Prep':<6} Status")
    print(f"  {'-'*8} {'-'*20} {'-'*8} {'-'*6} {'-'*10}")

    board = sorted(list(kitchen_board), key=lambda x: x["ticket"])
    for entry in board:
        print(f"  #{entry['ticket']:<7} {entry['dish']:<20} "
              f"Cook {entry['cook']:<4} {entry['prep_time']}s     "
              f"{entry['status']}")

    total = len(board)
    expected = len(MENU)
    print(f"\n[Head Chef] {total}/{expected} dishes on the board.", end=" ")
    if total < expected:
        print(f"<-- MISSING {expected - total} dish(es)! (race condition)")
    elif not use_lock:
        print("<-- All present this time, but not guaranteed without a lock.")
    else:
        print("<-- Complete and consistent!")
    print("=" * 60)

    # Keep the file if running without lock so you can still run --cook after
    if use_lock:
        os.remove(ASSIGNMENTS_FILE)


# ==============================================================
# ENTRY POINT — Windows multiprocessing requires this guard
# ==============================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cook", action="store_true",
                        help="Run the cooking phase (shared memory + Lock)")
    parser.add_argument("--no-lock", action="store_true",
                        help="Run cooking phase WITHOUT lock (shows race condition)")
    args = parser.parse_args()

    if args.no_lock:
        run_cooking_phase(use_lock=False)
    elif args.cook:
        run_cooking_phase(use_lock=True)
    else:
        run_mpi_phase()