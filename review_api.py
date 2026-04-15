from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import urllib.request
import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, '/Users/twinssn/Projects/5000')
from shared.image_handler import process_and_upload

app = Flask(__name__)
CORS(app)

DB_PATH = '/Users/twinssn/Projects/5000/data/car.db'

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/api/verify', methods=['POST'])
def verify():
    data = request.json
    img_id = data.get('id')
    action = data.get('action')  # 'pass' or 'fail'

    if not img_id or action not in ('pass', 'fail'):
        return jsonify({'ok': False, 'error': 'invalid params'}), 400

    conn = get_conn()
    row = conn.execute('SELECT * FROM car_images WHERE id=?', (img_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'ok': False, 'error': 'not found'}), 404

    if action == 'fail':
        conn.execute('UPDATE car_images SET verified=-1 WHERE id=?', (img_id,))
        conn.execute('INSERT OR IGNORE INTO blocked_images (image_url) VALUES (?)', (row['image_url'],))
        conn.commit()
        conn.close()
        return jsonify({'ok': True, 'action': 'fail', 'id': img_id})

    if action == 'pass':
        if row['r2_url']:
            conn.execute('UPDATE car_images SET verified=1 WHERE id=?', (img_id,))
            conn.commit()
            conn.close()
            return jsonify({'ok': True, 'action': 'pass', 'id': img_id, 'r2_url': row['r2_url'], 'cached': True})

        origin_url = row['image_url']
        try:
            req = urllib.request.Request(origin_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                image_data = resp.read()
            r2_url = process_and_upload(image_data)
            conn.execute('UPDATE car_images SET verified=1, r2_url=? WHERE id=?', (r2_url, img_id))
            conn.commit()
            conn.close()
            return jsonify({'ok': True, 'action': 'pass', 'id': img_id, 'r2_url': r2_url})
        except Exception as e:
            conn.execute('UPDATE car_images SET verified=-1 WHERE id=?', (img_id,))
            conn.execute('INSERT OR IGNORE INTO blocked_images (image_url) VALUES (?)', (origin_url,))
            conn.commit()
            conn.close()
            return jsonify({'ok': False, 'error': str(e), 'auto_failed': True})

@app.route('/api/status', methods=['GET'])
def status():
    conn = get_conn()
    rows = conn.execute("""
        SELECT verified, COUNT(*) as cnt FROM car_images GROUP BY verified
    """).fetchall()
    conn.close()
    return jsonify({str(r['verified']): r['cnt'] for r in rows})

@app.route('/api/images/<car_id>', methods=['GET'])
def images(car_id):
    conn = get_conn()
    rows = conn.execute("""
        SELECT id, image_url, r2_url, verified
        FROM car_images
        WHERE car_id=?
          AND image_url NOT IN (SELECT image_url FROM blocked_images)
        ORDER BY id
    """, (car_id,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5051, debug=False)
