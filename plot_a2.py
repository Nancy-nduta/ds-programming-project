import asyncio
import aiohttp
import subprocess
import time
import json
import matplotlib.pyplot as plt
from collections import Counter

LB_URL = "http://localhost:5000/home"
REP_URL = "http://localhost:5000/rep"
NUM_REQUESTS = 10000
CONCURRENCY = 200

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
    import urllib.request
    with urllib.request.urlopen(REP_URL) as r:
        data = json.loads(r.read())
        return data["message"]["N"], data["message"]["replicas"]

def set_replica_count(target_n):
    current_n, replicas = get_replica_count()
    diff = target_n - current_n
    import urllib.request
    if diff > 0:
        payload = json.dumps({"n": diff, "hostnames": []}).encode()
        req = urllib.request.Request("http://localhost:5000/add", data=payload,
                                      headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req)
    elif diff < 0:
        payload = json.dumps({"n": -diff, "hostnames": []}).encode()
        req = urllib.request.Request("http://localhost:5000/rm", data=payload,
                                      headers={"Content-Type": "application/json"}, method="DELETE")
        urllib.request.urlopen(req)
    time.sleep(2)  # let containers settle

if __name__ == "__main__":
    n_values = [2, 3, 4, 5, 6]
    avg_loads = []

    for n in n_values:
        print(f"\n--- Setting N={n} ---")
        set_replica_count(n)
        actual_n, replicas = get_replica_count()
        print(f"Replicas now: {replicas}")

        counts = asyncio.run(run_load_test())
        total = sum(counts.values())
        avg_load = total / len(counts) if counts else 0
        avg_loads.append(avg_load)
        print(f"N={n}: distribution={dict(counts)}, avg_load={avg_load:.1f}")

    plt.figure(figsize=(8,5))
    plt.plot(n_values, avg_loads, marker="o", color="darkorange")
    plt.xlabel("Number of Servers (N)")
    plt.ylabel("Average Load per Server (requests)")
    plt.title(f"Average Load vs N ({NUM_REQUESTS} requests per run)")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig("a2_scalability.png")
    print("\nSaved chart to a2_scalability.png")
