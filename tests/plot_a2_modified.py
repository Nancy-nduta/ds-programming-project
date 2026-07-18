import asyncio
import aiohttp
import time
import json
import statistics
import urllib.request
import matplotlib.pyplot as plt
from collections import Counter

LB_URL = "http://localhost:5000/home"
REP_URL = "http://localhost:5000/rep"
NUM_REQUESTS = 10000
CONCURRENCY = 100


async def fetch(session, sem):
    # Semaphore caps how many requests are in flight at once, so all
    # NUM_REQUESTS tasks get created but only CONCURRENCY run at a time.
    async with sem:
        try:
            async with session.get(LB_URL, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                data = await resp.json()
                # Message looks like "handled by: server-2", grab the label.
                return data.get("message", "").split(":")[-1].strip()
        except Exception:
            # Timeouts/connection errors/bad JSON all count as ERROR
            # instead of crashing the whole batch.
            return "ERROR"


async def run_load_test(n=NUM_REQUESTS):
    sem = asyncio.Semaphore(CONCURRENCY)
    async with aiohttp.ClientSession() as session:
        tasks = [fetch(session, sem) for _ in range(n)]
        results = await asyncio.gather(*tasks)
    return Counter(results)


def get_replica_count():
    # Asks the LB how many replicas it currently thinks it has and who they are.
    with urllib.request.urlopen(REP_URL) as r:
        data = json.loads(r.read())
        return data["message"]["N"], data["message"]["replicas"]


def set_replica_count(target_n):
    # Scales the replica pool up or down to hit target_n, using whatever
    # the LB's current count is as the baseline.
    current_n, replicas = get_replica_count()
    diff = target_n - current_n

    if diff > 0:
        # Need more replicas, ask the LB to add them.
        payload = json.dumps({"n": diff, "hostnames": []}).encode()
        req = urllib.request.Request(
            "http://localhost:5000/add", data=payload,
            headers={"Content-Type": "application/json"}, method="POST"
        )
        urllib.request.urlopen(req)
    elif diff < 0:
        # Too many replicas, ask the LB to remove the excess.
        payload = json.dumps({"n": -diff, "hostnames": []}).encode()
        req = urllib.request.Request(
            "http://localhost:5000/rm", data=payload,
            headers={"Content-Type": "application/json"}, method="DELETE"
        )
        urllib.request.urlopen(req)

    time.sleep(2)  # give the new/removed containers a moment to actually settle


if __name__ == "__main__":
    n_values = [2, 3, 4, 5, 6]
    avg_loads = []
    std_loads = []

    for n in n_values:
        print(f"\n--- Setting N={n} ---")
        set_replica_count(n)
        actual_n, replicas = get_replica_count()
        print(f"Replicas now: {replicas}")

        counts = asyncio.run(run_load_test())

        # Errors shouldn't count toward how "fair" the distribution is,
        # but we still want to know if a run had a bunch of them.
        errors = counts.pop("ERROR", 0)
        if errors:
            print(f"  WARNING: {errors} requests failed/errored out")

        # If a replica got zero requests it won't show up in counts at all,
        # so we pad the list with zeros up to actual_n. Otherwise avg/std
        # would be calculated as if that server didn't exist, which would
        # make the load look more even than it really is.
        values = list(counts.values())
        while len(values) < actual_n:
            values.append(0)

        total = sum(values)
        avg_load = total / actual_n if actual_n else 0
        std_load = statistics.pstdev(values) if values else 0

        avg_loads.append(avg_load)
        std_loads.append(std_load)

        print(f"N={n} (actual_n={actual_n}): distribution={dict(counts)}")
        print(f"  avg_load={avg_load:.1f}, std_load={std_load:.1f}")

    # Main required chart: average load per server vs N, using the
    # MODIFIED hash functions. Directly comparable to a2_scalability.png
    # (same plot, same axes, original hash functions).
    plt.figure(figsize=(8, 5))
    plt.plot(n_values, avg_loads, marker="o", color="darkorange")
    plt.xlabel("Number of Servers (N)")
    plt.ylabel("Average Load per Server (requests)")
    plt.title(f"Average Load vs N -- Modified Hash ({NUM_REQUESTS} requests per run)")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig("a2_modified.png")
    print("\nSaved chart to a2_modified.png")

    # Bonus chart: std dev of load across servers vs N. Not required by
    # A-2, but useful supporting evidence for the A-4 writeup, since
    # avg_load alone can't show whether distribution actually got more
    # even -- it's always NUM_REQUESTS / N regardless of hash quality.
    plt.figure(figsize=(8, 5))
    plt.plot(n_values, std_loads, marker="o", color="steelblue")
    plt.xlabel("Number of Servers (N)")
    plt.ylabel("Std Dev of Load per Server (requests)")
    plt.title(f"Load Std Dev vs N -- Modified Hash ({NUM_REQUESTS} requests per run)")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig("a2_modified_std.png")
    print("Saved chart to a2_modified_std.png")