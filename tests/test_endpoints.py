"""
Integration tests for the load balancer's live HTTP endpoints.
Requires the system to be running: `make up` first.
Run with: pytest tests/test_endpoints.py -v
"""
import time
import subprocess
import requests
import pytest

BASE_URL = "http://localhost:5000"


def test_rep_returns_replica_list():
    r = requests.get(f"{BASE_URL}/rep")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "successful"
    assert "N" in data["message"]
    assert isinstance(data["message"]["replicas"], list)
    # N is supposed to be a count of the same list, not a separately
    # tracked number, so these two need to actually agree.
    assert data["message"]["N"] == len(data["message"]["replicas"])


def test_home_routes_successfully():
    r = requests.get(f"{BASE_URL}/home")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "successful"
    assert "Hello from Server" in data["message"]


def test_unregistered_endpoint_returns_error():
    r = requests.get(f"{BASE_URL}/does-not-exist")
    assert r.status_code == 400
    data = r.json()
    assert data["status"] == "failure"


def test_add_increases_replica_count():
    before = requests.get(f"{BASE_URL}/rep").json()["message"]["N"]

    r = requests.post(f"{BASE_URL}/add", json={"n": 1, "hostnames": ["TestServerA"]})
    assert r.status_code == 200

    after = requests.get(f"{BASE_URL}/rep").json()["message"]["N"]
    assert after == before + 1

    # cleanup so this test doesn't leave a stray replica for the next one
    requests.delete(f"{BASE_URL}/rm", json={"n": 1, "hostnames": ["TestServerA"]})


def test_add_rejects_hostname_list_longer_than_n():
    # Asking to add 1 server but naming 2 hostnames is a contradiction,
    # the endpoint should reject it rather than silently picking one.
    r = requests.post(f"{BASE_URL}/add", json={"n": 1, "hostnames": ["A", "B"]})
    assert r.status_code == 400
    assert r.json()["status"] == "failure"


def test_rm_decreases_replica_count():
    # Add one first so we know for sure there's something to remove,
    # rather than relying on whatever state earlier tests left behind.
    requests.post(f"{BASE_URL}/add", json={"n": 1, "hostnames": ["TestServerB"]})
    before = requests.get(f"{BASE_URL}/rep").json()["message"]["N"]

    r = requests.delete(f"{BASE_URL}/rm", json={"n": 1, "hostnames": ["TestServerB"]})
    assert r.status_code == 200

    after = requests.get(f"{BASE_URL}/rep").json()["message"]["N"]
    assert after == before - 1


def test_rm_rejects_hostname_list_longer_than_n():
    r = requests.delete(f"{BASE_URL}/rm", json={"n": 1, "hostnames": ["A", "B"]})
    assert r.status_code == 400
    assert r.json()["status"] == "failure"


@pytest.mark.slow
def test_failure_recovery_spawns_replacement():
    """Stops a live server container and confirms the load balancer
    detects the failure and spawns a replacement within one heartbeat
    interval (~5-6 seconds)."""
    before = requests.get(f"{BASE_URL}/rep").json()["message"]["replicas"]
    target = before[0]

    # Kill one of the actual running containers, not just tell the LB
    # about it, this is meant to simulate a real crash.
    subprocess.run(["docker", "stop", target], check=True)
    time.sleep(7)  # allow one heartbeat cycle to detect and respawn

    after = requests.get(f"{BASE_URL}/rep").json()["message"]["replicas"]

    # The dead one should be gone, but the LB should have spun up a
    # replacement so the total count stays the same.
    assert target not in after
    assert len(after) == len(before)