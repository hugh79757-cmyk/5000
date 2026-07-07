"""
5000 Unified Dashboard — Flask Application
Monitors 49 auto blogs across 5000(Hub) + SAP + aikorea24 + money-aikorea24
"""

import logging
import os
import sys
from pathlib import Path

from flask import Flask

# ── Path setup ──
_FIVEK = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_FIVEK))

from shared.paths import DATA_DIR
from shared.db_paths import ARTICLES_DB

app = Flask(__name__)
app.config["DATA_DIR"] = str(DATA_DIR)
app.config["CONTENT_DB"] = str(ARTICLES_DB)
app.config["ANALYTICS_DB"] = os.path.join(DATA_DIR, "analytics.db")
app.config["DASHBOARD_DIR"] = str(Path(__file__).parent)

# ── Routes ──
from routes.api import api_bp
from routes.pages import pages_bp

app.register_blueprint(api_bp, url_prefix="/api")
app.register_blueprint(pages_bp)

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(_FIVEK, "logs", "dashboard.log")),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


@app.errorhandler(404)
def not_found(e):
    return {"error": "not found"}, 404


@app.errorhandler(500)
def server_error(e):
    return {"error": "internal server error"}, 500


if __name__ == "__main__":
    port = int(os.environ.get("DASHBOARD_PORT", 5050))
    logger.info(f"Dashboard starting on http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)
