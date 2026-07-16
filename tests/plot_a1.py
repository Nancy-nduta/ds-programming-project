import asyncio
import aiohttp
import matplotlib.pyplot as plt
from collections import Counter

# Endpoint we're hammering. Change this if your LB listens somewhere else.
LB_URL = "http://localhost:5000/home"

# Total number of requests to fire over the whole test.
NUM_REQUESTS = 10000

# Max number of requests allowed to be in flight at the same time.
# This is what actually controls how "hard" the test hits the server,
# not NUM_REQUESTS.
CONCURRENCY = 100


async def fetch(session, sem):
    # The semaphore is what keeps us from opening 10,000 connections
    # at once. Only CONCURRENCY tasks can be past this point at any
    # given moment, the rest just wait their turn.
    async with sem:
        try:
            async with session.get(LB_URL, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                data = await resp.json()
                # Expecting something like {"message": "handled by: server-2"}.
                # We just want the server label after the last colon.
                return data.get("message", "").split(":")[-1].strip()
        except Exception:
            # Timeouts, connection resets, bad JSON, whatever, all get
            # lumped into "ERROR" so one flaky request doesn't kill the run.
            return "ERROR"


async def run_load_test(n=NUM_REQUESTS):
    sem = asyncio.Semaphore(CONCURRENCY)
    async with aiohttp.ClientSession() as session:
        # All n tasks get created immediately, but the semaphore inside
        # fetch() is what throttles how many actually run concurrently.
        tasks = [fetch(session, sem) for _ in range(n)]
        results = await asyncio.gather(*tasks)
    # Tally up how many times each server (or "ERROR") shows up.
    return Counter(results)


if __name__ == "__main__":
    counts = asyncio.run(run_load_test())

    # Sort so the chart's x-axis is in a consistent, readable order.
    servers = sorted(counts.keys())
    values = [counts[s] for s in servers]

    plt.figure(figsize=(8, 5))
    plt.bar(servers, values, color="steelblue")
    plt.xlabel("Server ID")
    plt.ylabel("Number of Requests Handled")
    plt.title(f"Load Distribution across {len(servers)} Servers (N=3, {NUM_REQUESTS} requests)")
    plt.tight_layout()
    plt.savefig("a1_load_distribution.png")

    print("Saved chart to a1_load_distribution.png")
    print(dict(counts))