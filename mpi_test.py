from mpi4py import MPI

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

ROLES = {0: "Head Chef"}
role = ROLES.get(rank, f"Line Cook {rank}")

print(f"[Kitchen Staff Check] {role} is present! (Process {rank} of {size})")

if rank == 0:
    print(f"\n[Head Chef] Kitchen is open! {size} staff members ready.")
    print("[Head Chef] All systems go — let's start cooking!\n")