# kitchen.py
# Paluto Restaurant — Distributed Kitchen System
# Run with: mpiexec -n 5 python kitchen.py
#
# Stage 1: MPI task distribution (Head Chef -> Line Cooks)
# Stage 2: Cooking delays based on dish complexity
# Stage 3: Shared memory kitchen board (Manager().list())
# Stage 4: Lock synchronization for safe concurrent writes

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from mpi4py import MPI
from multiprocessing import Manager, Process, Lock
import time

# ==============================================================
# MENU — Filipino dishes with complexity levels
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

# Prep time in seconds per complexity
PREP_TIME = {
    "easy":   1,
    "medium": 2,
    "hard":   3,
}

# ==============================================================
# STAGE 3 & 4 — Cook worker (runs as a subprocess via Process)
# ==============================================================
def cook_worker(cook_id, assigned_orders, kitchen_board, lock):
    """
    Each cook receives their assigned orders, simulates cooking
    (Stage 2 delay), then safely writes to the shared board (Stage 4).
    """
    for order in assigned_orders:
        prep_time = PREP_TIME[order["complexity"]]

        # Stage 2: Simulate cooking time
        print(f"  [Cook {cook_id}] [COOKING] Preparing Ticket #{order['ticket']}: "
              f"{order['dish']} — est. {prep_time}s prep time...")
        time.sleep(prep_time)

        entry = {
            "ticket":    order["ticket"],
            "dish":      order["dish"],
            "cook":      cook_id,
            "prep_time": prep_time,
            "status":    "SERVED [OK]",
        }

        # Stage 4: Lock ensures only one cook writes at a time
        with lock:
            kitchen_board.append(entry)
            print(f"  [Cook {cook_id}] [BOARD] Board updated → "
                  f"Ticket #{order['ticket']} {order['dish']} done!")

# ==============================================================
# MAIN ENTRY POINT
# ==============================================================
def main():
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()  # should be 5

    # ----------------------------------------------------------
    # HEAD CHEF — rank 0
    # ----------------------------------------------------------
    if rank == 0:
        num_workers = size - 1  # 4 cooks (ranks 1-4)

        print("=" * 60)
        print("    [DISH]  PALUTO RESTAURANT — DISTRIBUTED KITCHEN  [DISH]")
        print("=" * 60)
        print(f"[Head Chef] Kitchen is open!")
        print(f"[Head Chef] {len(MENU)} orders incoming | {num_workers} cooks on duty\n")

        # --- STAGE 1: Distribute orders via MPI ---
        print("--- STAGE 1: Dispatching Tickets ---")
        for i, order in enumerate(MENU):
            target_cook = (i % num_workers) + 1  # round-robin: ranks 1..4
            comm.send(order, dest=target_cook, tag=1)
            print(f"[Head Chef] [TICKET] Ticket #{order['ticket']} "
                  f"({order['dish']}) → Cook {target_cook} "
                  f"[{order['complexity']}]")

        # Send stop signal to every cook
        for worker_rank in range(1, size):
            comm.send(None, dest=worker_rank, tag=0)

        print(f"\n[Head Chef] All tickets dispatched. Kitchen is running...\n")

        # Collect each cook's assigned orders back (for subprocess launch)
        cook_assignments = {}
        for worker_rank in range(1, size):
            assignments = comm.recv(source=worker_rank, tag=3)
            cook_assignments[worker_rank] = assignments

        # --- STAGE 3: Shared kitchen board ---
        print("--- STAGE 3 & 4: Shared Board + Synchronization ---\n")
        manager = Manager()
        kitchen_board = manager.list()
        lock = Lock()

        start_time = time.time()

        # Launch one subprocess per cook
        processes = []
        for cook_id, orders in cook_assignments.items():
            p = Process(
                target=cook_worker,
                args=(cook_id, orders, kitchen_board, lock)
            )
            processes.append(p)
            p.start()

        for p in processes:
            p.join()

        elapsed = round(time.time() - start_time, 2)

        # --- Final Board Display ---
        print("\n" + "=" * 60)
        print(f"[Head Chef] [DONE] All dishes served! Total time: {elapsed}s")
        print("[Head Chef] [BOARD] Final Kitchen Board:\n")
        print(f"  {'Ticket':<8} {'Dish':<20} {'Cook':<8} {'Prep':<6} Status")
        print(f"  {'-'*8} {'-'*20} {'-'*8} {'-'*6} {'-'*12}")

        board = sorted(list(kitchen_board), key=lambda x: x["ticket"])
        for entry in board:
            print(f"  #{entry['ticket']:<7} {entry['dish']:<20} "
                  f"Cook {entry['cook']:<4} {entry['prep_time']}s    "
                  f"{entry['status']}")

        print(f"\n[Head Chef] [OK] {len(board)}/{len(MENU)} dishes on board.")
        print("=" * 60)

    # ----------------------------------------------------------
    # LINE COOKS — ranks 1 to 4
    # ----------------------------------------------------------
    else:
        my_orders = []

        # Stage 1 & 2: Receive orders from head chef
        while True:
            status = MPI.Status()
            order = comm.recv(source=0, tag=MPI.ANY_TAG, status=status)
            if order is None:
                break  # stop signal
            my_orders.append(order)
            print(f"  [Cook {rank}] [COOK] Got Ticket #{order['ticket']}: "
                  f"{order['dish']} ({order['complexity']})")

        # Send assignment list back to head chef for subprocess launch
        comm.send(my_orders, dest=0, tag=3)

        # Note: actual cooking (delay + board write) happens in
        # cook_worker() launched as a subprocess by the head chef


# ==============================================================
# Windows requires this guard for multiprocessing
# ==============================================================
if __name__ == "__main__":
    main()