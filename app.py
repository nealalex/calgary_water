"""
app.py
Calgary Water Quality & pH Monitoring Web Service.
Listens on port 8521.
"""

import os
import threading
import time
from flask import Flask, render_template, jsonify
from data_fetcher import get_summary_stats, sync_data, init_db

app = Flask(__name__)


def background_sync_worker():
    """Runs a periodic data sync every 6 hours."""
    while True:
        try:
            time.sleep(6 * 3600)
            sync_data()
        except Exception as e:
            print(f"Background sync error: {e}")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/stats")
def api_stats():
    try:
        stats = get_summary_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    try:
        n = sync_data()
        return jsonify({"status": "success", "records_synced": n})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/health")
def health():
    return jsonify({"status": "healthy", "service": "calgary_water", "port": 8521})


if __name__ == "__main__":
    init_db()
    # Start background synchronization daemon
    t = threading.Thread(target=background_sync_worker, daemon=True)
    t.start()

    port = int(os.environ.get("PORT", 8521))
    print(f"Starting Calgary Water Service on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)
