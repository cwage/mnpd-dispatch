"""
Flask server exposing the MNPD Dispatch proximity API.

Endpoints:
    GET /nearby?address=<addr>&radius=<miles> - dispatches near an address
    GET /dispatches                           - all active police dispatches
    GET /dispatches/fire                      - all active fire dispatches
    GET /dispatches/all                       - all active dispatches (police + fire)
    GET /health                               - health check
"""

from flask import Flask, request, jsonify
from mnpd_service import (
    find_nearby_by_address,
    fetch_mnpd_dispatches,
    fetch_nfd_dispatches,
    fetch_all_dispatches,
)

app = Flask(__name__)


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/dispatches")
def dispatches():
    """Return all active MNPD police dispatches."""
    events = fetch_mnpd_dispatches()
    return jsonify({
        "count": len(events),
        "dispatches": [e.to_dict() for e in events],
    })


@app.route("/dispatches/fire")
def dispatches_fire():
    """Return all active NFD fire dispatches."""
    events = fetch_nfd_dispatches()
    return jsonify({
        "count": len(events),
        "dispatches": [e.to_dict() for e in events],
    })


@app.route("/dispatches/all")
def dispatches_all():
    """Return all active dispatches (police + fire)."""
    events = fetch_all_dispatches()
    return jsonify({
        "count": len(events),
        "dispatches": [e.to_dict() for e in events],
    })


@app.route("/nearby")
def nearby():
    """
    Find dispatches near an address.

    Query params:
        address (required): Street address to geocode
        radius (optional):  Miles radius to search (default 2.0)
        fire (optional):    Include fire dispatches (default false)
    """
    address = request.args.get("address")
    if not address:
        return jsonify({"error": "Missing required 'address' parameter"}), 400

    try:
        radius = float(request.args.get("radius", 2.0))
    except ValueError:
        return jsonify({"error": "Invalid 'radius' parameter"}), 400

    include_fire = request.args.get("fire", "").lower() in ("1", "true", "yes")

    result = find_nearby_by_address(address, radius_miles=radius, include_fire=include_fire)

    if "error" in result:
        return jsonify(result), 404

    return jsonify(result)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MNPD Dispatch API Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", "-p", type=int, default=5000, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    print(f"Starting MNPD Dispatch API on http://{args.host}:{args.port}")
    print("Endpoints:")
    print("  GET /nearby?address=<addr>&radius=<miles>&fire=<bool>")
    print("  GET /dispatches")
    print("  GET /dispatches/fire")
    print("  GET /dispatches/all")
    print("  GET /health")

    app.run(host=args.host, port=args.port, debug=args.debug)
