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
    async with sem:
        try:
            async with session.get(LB_URL, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                data = await resp.json()
                return data.get("message", "").split(":")[-1].strip()
        except Exception:
            return "ERROR"


async def run_load_test(n=NUM_REQUESTS):
    sem = asyncio.Semaphore(CONCURRENCY)
    async with aiohttp.ClientSession() as session:
        tasks = [fetch(session, sem) for _ in range(n)]
        results = await asyncio.gather(*tasks)
    return Counter(results)


def get_replica_count():
    with urllib.request.urlopen(REP_URL) as r:
        data = json.loads(r.read())
        return data["message"]["N"], data["message"]["replicas"]


def set_replica_count(target_n):
    current_n, replicas = get_replica_count()
    diff = target_n - current_n

    if diff > 0:
        payload = json.dumps({"n": diff, "hostnames": []}).encode()
        req = urllib.request.Request(
            "http://localhost:5000/add", data=payload,
            headers={"Content-Type": "application/json"}, method="POST"
        )
        urllib.request.urlopen(req)
    elif diff < 0:
        payload = json.dumps({"n": -diff, "hostnames": []}).encode()
        req = urllib.request.Request(
            "http://localhost:5000/rm", data=payload,
            headers={"Content-Type": "application/json"}, method="DELETE"
        )
        urllib.request.urlopen(req)

    time.sleep(2)


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

        errors = counts.pop("ERROR", 0)
        if errors:
            print(f"  WARNING: {errors} requests failed/errored out")

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

    plt.figure(figsize=(8, 5))
    plt.plot(n_values, avg_loads, marker="o", color="darkorange")
    plt.xlabel("Number of Servers (N)")
    plt.ylabel("Average Load per Server (requests)")
    plt.title(f"Average Load vs N -- Original Hash ({NUM_REQUESTS} requests per run)")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig("a2_scalability.png")
    print("\nSaved chart to a2_scalability.png")

    plt.figure(figsize=(8, 5))
    plt.plot(n_values, std_loads, marker="o", color="steelblue")
    plt.xlabel("Number of Servers (N)")
    plt.ylabel("Std Dev of Load per Server (requests)")
    plt.title(f"Load Std Dev vs N -- Original Hash ({NUM_REQUESTS} requests per run)")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig("a2_original_std.png")
    print("Saved chart to a2_original_std.png")
