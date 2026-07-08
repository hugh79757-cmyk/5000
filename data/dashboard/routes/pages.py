"""Page routes — HTML template rendering."""

from flask import Blueprint, render_template

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def index():
    return render_template("index.html")


@pages_bp.route("/revenue")
def revenue():
    return render_template("revenue.html")


@pages_bp.route("/traffic")
def traffic():
    return render_template("traffic.html")


@pages_bp.route("/search")
def search():
    return render_template("search.html")


@pages_bp.route("/health")
def health():
    return render_template("health.html")


@pages_bp.route("/quality")
def quality():
    return render_template("quality.html")
