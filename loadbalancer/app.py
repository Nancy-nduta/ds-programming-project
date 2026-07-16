from flask import Flask, request, jsonify
import docker
import requests
import threading
import time
import random
import string

from consistent_hash import ConsistentHashMap

app = Flask(__name__)
docker_client = docker.from_env()

NETWORK_NAME = "net1"
SERVER_IMAGE = "server_image"
N_DEFAULT = 3

# Lock protects shared state (hash map, hostname lists) from being
# modified by the heartbeat thread and a request handler at the same time
lock = threading.Lock()
hash_map = ConsistentHashMap(num_slots=512, num_virtual=9)

# Bookkeeping for currently running servers
server_counter = 0          # increments with every server ever created, used as its numeric hash ID
hostname_to_num = {}        # hostname -> numeric ID
active_hostnames = []       # hostnames currently registered and running


def random_hostname():
    # Generates a random container name when the caller doesn't specify one
    return "S" + "".join(random.choices(string.digits, k=4))


def spawn_server(hostname=None):
    # Starts a new server container on the shared Docker network and
    # registers it in the consistent hash map
    global server_counter
    if hostname is None:
        hostname = random_hostname()

    server_counter += 1
    num = server_counter

    docker_client.containers.run(
        SERVER_IMAGE,
        name=hostname,
        network=NETWORK_NAME,
        environment={"SERVER_ID": str(num)},
        detach=True,
    )

    hostname_to_num[hostname] = num
    active_hostnames.append(hostname)
    hash_map.add_server(hostname, num)
    return hostname


def remove_server(hostname):
    # Stops and removes a container, and deregisters it from the hash map
    try:
        c = docker_client.containers.get(hostname)
        c.stop()
        c.remove()
    except docker.errors.NotFound:
        pass

    hash_map.remove_server(hostname)
    hostname_to_num.pop(hostname, None)
    if hostname in active_hostnames:
        active_hostnames.remove(hostname)


def init_servers(n=N_DEFAULT):
    # Spawns the initial N servers when the load balancer starts up
    with lock:
        for _ in range(n):
            spawn_server()


def heartbeat_loop():
    # Runs continuously in a background thread. Every 5 seconds, checks
    # each active server's /heartbeat endpoint. If a server doesn't
    # respond, it's assumed dead, removed, and replaced automatically
    # so the system always maintains N running replicas.
    while True:
        time.sleep(5)
        with lock:
            dead = []
            for hostname in list(active_hostnames):
                try:
                    r = requests.get(f"http://{hostname}:5000/heartbeat", timeout=5)
                    if r.status_code != 200:
                        dead.append(hostname)
                except requests.exceptions.RequestException:
                    dead.append(hostname)

            for hostname in dead:
                print(f"[heartbeat] {hostname} is down, respawning replacement")
                remove_server(hostname)
                spawn_server()


@app.route("/rep", methods=["GET"])
def rep():
    # Returns the current number of replicas and their hostnames
    with lock:
        return jsonify({
            "message": {
                "N": len(active_hostnames),
                "replicas": list(active_hostnames)
            },
            "status": "successful"
        }), 200


@app.route("/add", methods=["POST"])
def add():
    # Scales up by spawning n new servers. If fewer hostnames are given
    # than n, the rest get random names. Rejects payloads where the
    # hostname list is longer than n.
    payload = request.get_json(force=True)
    n = payload.get("n", 0)
    hostnames = payload.get("hostnames", [])

    if len(hostnames) > n:
        return jsonify({
            "message": "<Error> Length of hostname list is more than newly added instances",
            "status": "failure"
        }), 400

    with lock:
        for i in range(n):
            hostname = hostnames[i] if i < len(hostnames) else None
            spawn_server(hostname)

        return jsonify({
            "message": {
                "N": len(active_hostnames),
                "replicas": list(active_hostnames)
            },
            "status": "successful"
        }), 200


@app.route("/rm", methods=["DELETE"])
def rm():
    # Scales down by removing n servers. Named hostnames are removed
    # first; any remaining count is filled by removing random servers.
    # Rejects payloads where the hostname list is longer than n.
    payload = request.get_json(force=True)
    n = payload.get("n", 0)
    hostnames = payload.get("hostnames", [])

    if len(hostnames) > n:
        return jsonify({
            "message": "<Error> Length of hostname list is more than removable instances",
            "status": "failure"
        }), 400

    with lock:
        to_remove = list(hostnames)
        remaining_needed = n - len(hostnames)
        candidates = [h for h in active_hostnames if h not in to_remove]
        to_remove += random.sample(candidates, min(remaining_needed, len(candidates)))

        for hostname in to_remove:
            remove_server(hostname)

        return jsonify({
            "message": {
                "N": len(active_hostnames),
                "replicas": list(active_hostnames)
            },
            "status": "successful"
        }), 200


@app.route("/<path:path>", methods=["GET"])
def route_request(path):
    # Generates a random request ID, uses the consistent hash map to pick
    # a server, and forwards the request to it. Converts both network
    # errors and 404s from the server into the spec's expected error format.
    request_id = random.randint(100000, 999999)

    with lock:
        hostname = hash_map.get_server(request_id)

    if hostname is None:
        return jsonify({
            "message": "<Error> No servers available",
            "status": "failure"
        }), 400

    try:
        r = requests.get(f"http://{hostname}:5000/{path}", timeout=3)
        if r.status_code == 404:
            return jsonify({
                "message": f"<Error> '/{path}' endpoint does not exist in server replicas",
                "status": "failure"
            }), 400
        return (r.content, r.status_code, r.headers.items())
    except requests.exceptions.RequestException:
        return jsonify({
            "message": f"<Error> '/{path}' endpoint does not exist in server replicas",
            "status": "failure"
        }), 400


if __name__ == "__main__":
    init_servers(N_DEFAULT)
    t = threading.Thread(target=heartbeat_loop, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=5000)