from flask import Flask, jsonify
import os

app = Flask(__name__)

# Each server container gets a unique ID passed in as an environment
# variable at startup, so it can identify itself in responses.
SERVER_ID = os.environ.get("SERVER_ID", "unknown")


@app.route("/home", methods=["GET"])
def home():
    # Returns a simple identifying message so the load balancer (and the
    # client, indirectly) can confirm which replica handled the request.
    return jsonify({"message": f"Hello from Server: {SERVER_ID}", "status": "successful"}), 200


@app.route("/heartbeat", methods=["GET"])
def heartbeat():
    # Used by the load balancer's health check thread. An empty 200
    # response is enough to confirm the server is alive and responsive.
    return "", 200


if __name__ == "__main__":
    # threaded=True lets Flask handle multiple simultaneous requests
    # (including heartbeat checks) instead of queueing them one at a time,
    # which matters once the load balancer is sending concurrent traffic.
    app.run(host="0.0.0.0", port=5000, threaded=True)