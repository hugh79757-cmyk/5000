from flask import Flask, request, jsonify
import sqlite3
from pathlib import Path

app = Flask(__name__)
DB = "/Users/twinssn/Projects/5000/data/car.db"

@app.route("/api/delete-images", methods=["POST"])
def delete_images():
    ids = request.json.get("ids", [])
    if not ids:
        return jsonify({"error": "no ids"}), 400

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    deleted = 0
    blocked = 0
    for img_id in ids:
        row = c.execute(
            "SELECT image_url FROM car_images WHERE id=?", (img_id,)
        ).fetchone()
        if row:
            url = row[0]
            c.execute("DELETE FROM car_images WHERE id=?", (img_id,))
            c.execute(
                "INSERT OR IGNORE INTO blocked_images (image_url) VALUES (?)", (url,)
            )
            deleted += 1
            blocked += 1

    conn.commit()
    conn.close()
    return jsonify({"deleted": deleted, "blocked": blocked})

@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5100, debug=False)
