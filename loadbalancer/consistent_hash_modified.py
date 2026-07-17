"""
A-2 (revised): Increment N from 2 to 6, send 10,000 requests per run,
and report STDDEV and MAX load per server instead of the mean.

Why: average load per server is always 10000/N regardless of hash
quality, so it can't show whether the hash function actually improved
distribution. Stddev and max load DO capture that.

"""

import asyncio
import aiohttp
import statistics
import re
import matplotlib.pyplot as plt

LB_BASE_URL = "http://localhost:5000"
N_VALUES = [2, 3, 4, 5, 6]
REQUESTS_PER_RUN = 10000
CONCURRENCY = 200  # simultaneous in-flight requests, tune to avoid overload


async def send_one(session, sem):
    """Send a single request to the load balancer's /home endpoint and
    extract which server handled it from the response message."""
    async with sem:
        try:
            async with session.get(f"{LB_BASE_URL}/home", timeout=5) as resp:
                data = await resp.json()
                # Expecting: {"message": "Hello from Server: <id>", ...}
                match = re.search(r"Server:\s*(\S+)", data.get("message", ""))
                return match.group(1) if match else None
        except Exception:
            return None


async def run_load(n_requests):
    """Fire n_requests concurrently (bounded by CONCURRENCY) and return
    a dict of server_id -> count of requests it handled."""
    sem = asyncio.Semaphore(CONCURRENCY)
    async with aiohttp.ClientSession() as session:
        tasks = [send_one(session, sem) for _ in range(n_requests)]
        results = await asyncio.gather(*tasks)

    counts = {}
    for server_id in results:
        if server_id is None:
            continue
        counts[server_id] = counts.get(server_id, 0) + 1
    return counts


def set_replica_count(n):
    """
    Adjust the load balancer to have exactly n replicas before each run.
    You'll likely already have helper code for this from A-1/A-3 --
    replace this stub with calls to your /add and /rm endpoints to reach
    the target N, e.g.:

        current = get_current_n()
        if n > current:
            requests.post(f"{LB_BASE_URL}/add", json={"n": n - current})
        elif n < current:
            requests.delete(f"{LB_BASE_URL}/rm", json={"n": current - n})
    """
    raise NotImplementedError("Wire this up to your /add and /rm endpoints")


def main():
    ns = []
    stddevs = []
    maxes = []

    for n in N_VALUES:
        set_replica_count(n)
        counts = asyncio.run(run_load(REQUESTS_PER_RUN))

        values = list(counts.values())
        # Pad with zeros if some server got no traffic at all, so stddev
        # reflects the full set of N servers, not just the ones that were hit
        while len(values) < n:
            values.append(0)

        stddev = statistics.pstdev(values)
        max_load = max(values)

        ns.append(n)
        stddevs.append(stddev)
        maxes.append(max_load)

        print(f"N={n}: counts={counts} stddev={stddev:.1f} max={max_load}")

    # Plot stddev
    plt.figure(figsize=(9, 5.5))
    plt.plot(ns, stddevs, marker="o", color="crimson")
    plt.title(f"Load Imbalance (Std Dev) vs N ({REQUESTS_PER_RUN} requests per run)")
    plt.xlabel("Number of Servers (N)")
    plt.ylabel("Std Dev of Requests per Server")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig("a2_stddev.png", dpi=150)
    plt.close()

    # Plot max load
    plt.figure(figsize=(9, 5.5))
    plt.plot(ns, maxes, marker="o", color="darkorange")
    plt.title(f"Max Load on a Single Server vs N ({REQUESTS_PER_RUN} requests per run)")
    plt.xlabel("Number of Servers (N)")
    plt.ylabel("Max Requests Handled by Any Server")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig("a2_max_load.png", dpi=150)
    plt.close()

    print("\nSaved a2_stddev.png and a2_max_load.png")


if __name__ == "__main__":
    main()