import asyncio
import aiohttp
import matplotlib.pyplot as plt
from collections import Counter

LB_URL = "http://localhost:5000/home"
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

if __name__ == "__main__":
    counts = asyncio.run(run_load_test())
    servers = sorted(counts.keys())
    values = [counts[s] for s in servers]

    plt.figure(figsize=(8,5))
    plt.bar(servers, values, color="steelblue")
    plt.xlabel("Server ID")
    plt.ylabel("Number of Requests Handled")
    plt.title(f"Load Distribution across {len(servers)} Servers (N=3, {NUM_REQUESTS} requests)")
    plt.tight_layout()
    plt.savefig("a1_load_distribution.png")
    print("Saved chart to a1_load_distribution.png")
    print(dict(counts))
