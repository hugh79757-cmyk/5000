"""ETAP data adapters — resolve unique, verifiable data points from travel-en.db.

Each adapter exposes ``get_unique_data_points(topic_id) -> list[dict]`` returning
facts as ``{label, value, unit, source_table}`` dicts. Adapters never raise: a
missing table or empty result yields ``[]`` (graceful degradation).
"""

import logging
import os
import sqlite3

logger = logging.getLogger(__name__)

_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "travel-en.db")


def _connect():
    """Open a read-only connection to travel-en.db, or None if missing."""
    path = os.path.abspath(_DB_PATH)
    if not os.path.exists(path):
        logger.warning("[data_adapters] DB not found at %s", path)
        return None
    try:
        return sqlite3.connect(path)
    except sqlite3.Error as exc:
        logger.warning("[data_adapters] connect failed: %s", exc)
        return None


def _query(conn, sql, params=()):
    """Run a SELECT, return rows as list of dicts. Empty list on any error."""
    if conn is None:
        return []
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]
    except sqlite3.Error as exc:
        logger.warning("[data_adapters] query failed (%s): %s", sql, exc)
        return []


def _point(label, value, unit, source_table):
    """Build a normalized data point, skipping empty values."""
    if value is None or value == "":
        return None
    return {"label": label, "value": value, "unit": unit, "source_table": source_table}


def flight_adapter(topic_id=None):
    """flight_prices → min_price, min_stops, departure_date, airline."""
    conn = _connect()
    rows = _query(
        conn,
        """
        SELECT price, stops, departure_date, airline, origin, destination
        FROM flight_prices
        ORDER BY price ASC LIMIT 20
        """,
    )
    if conn:
        conn.close()
    if not rows:
        return []

    points = []
    min_row = rows[0]
    points.append(_point("min_price", min_row.get("price"), "USD", "flight_prices"))
    points.append(_point("min_stops", min_row.get("stops"), "stops", "flight_prices"))
    points.append(_point("departure_date", min_row.get("departure_date"), "date", "flight_prices"))
    points.append(_point("airline", min_row.get("airline"), "", "flight_prices"))
    if min_row.get("origin") and min_row.get("destination"):
        points.append(_point("route", f"{min_row['origin']}→{min_row['destination']}", "", "flight_prices"))
    return [p for p in points if p]


def viator_adapter(topic_id=None):
    """viator_tours → tour_name, price, duration, category, image_url."""
    conn = _connect()
    rows = _query(
        conn,
        """
        SELECT product_name, price, category, image_url, currency
        FROM viator_tours
        ORDER BY price ASC LIMIT 5
        """,
    )
    if conn:
        conn.close()
    if not rows:
        return []

    points = []
    for r in rows:
        points.append(_point("tour_name", r.get("product_name"), "", "viator_tours"))
        points.append(_point("price", r.get("price"), r.get("currency") or "USD", "viator_tours"))
        points.append(_point("duration", r.get("duration"), "", "viator_tours"))
        points.append(_point("category", r.get("category"), "", "viator_tours"))
        points.append(_point("image_url", r.get("image_url"), "", "viator_tours"))
    return [p for p in points if p]


def nature_adapter(topic_id=None):
    """nature_topics (+ related viator_tours by city) → tour_name, location, price, duration, activities."""
    conn = _connect()
    topic = None
    if topic_id is not None:
        trows = _query(conn, "SELECT * FROM nature_topics WHERE id = ?", (topic_id,))
        if trows:
            topic = trows[0]
    if topic is None:
        trows = _query(conn, "SELECT * FROM nature_topics ORDER BY priority DESC LIMIT 1")
        if trows:
            topic = trows[0]
    if conn:
        conn.close()
    if not topic:
        return []

    location = f"{topic.get('city', '')}, {topic.get('country', '')}".strip(", ")
    points = [
        _point("tour_name", topic.get("title"), "", "nature_topics"),
        _point("location", location, "", "nature_topics"),
    ]

    # Related viator tours by matching city for price/duration/activities.
    conn2 = _connect()
    related = _query(
        conn2,
        "SELECT price, category FROM viator_tours WHERE city = ? ORDER BY price ASC LIMIT 5",
        (topic.get("city", ""),),
    )
    if conn2:
        conn2.close()
    if related:
        min_price = min(r.get("price") for r in related if r.get("price") is not None)
        points.append(_point("price", min_price, "USD", "viator_tours"))
        durations = [r.get("duration") for r in related if r.get("duration")]
        points.append(_point("duration", durations[0] if durations else None, "", "viator_tours"))
        cats = [r.get("category") for r in related if r.get("category")]
        points.append(_point("activities", ", ".join(sorted(set(cats))[:3]) if cats else None, "", "viator_tours"))
    return [p for p in points if p]


def deals_adapter(topic_id=None):
    """deals_topics (+ flight_prices join on origin) → product_name, price, discount, retailer."""
    conn = _connect()
    topic = None
    if topic_id is not None:
        trows = _query(conn, "SELECT * FROM deals_topics WHERE id = ?", (topic_id,))
        if trows:
            topic = trows[0]
    if topic is None:
        trows = _query(conn, "SELECT * FROM deals_topics ORDER BY priority DESC LIMIT 1")
        if trows:
            topic = trows[0]
    if conn:
        conn.close()
    if not topic:
        return []

    points = [
        _point("product_name", topic.get("title"), "", "deals_topics"),
    ]

    origin = topic.get("origin")
    if origin:
        conn2 = _connect()
        frows = _query(
            conn2,
            "SELECT price, airline FROM flight_prices WHERE origin = ? ORDER BY price ASC LIMIT 5",
            (origin,),
        )
        if conn2:
            conn2.close()
        if frows:
            min_price = min(r.get("price") for r in frows if r.get("price") is not None)
            points.append(_point("price", min_price, "USD", "flight_prices"))
            retailers = [r.get("airline") for r in frows if r.get("airline")]
            points.append(_point("retailer", ", ".join(sorted(set(retailers))[:3]) if retailers else None, "", "flight_prices"))
    points.append(_point("discount", topic.get("deal_count"), "offers", "deals_topics"))
    return [p for p in points if p]


ADAPTER_REGISTRY = {
    "flight": flight_adapter,
    "viator": viator_adapter,
    "nature": nature_adapter,
    "deals": deals_adapter,
}


def get_unique_data_points(topic_type, topic_id=None):
    """Dispatch to the registered adapter for ``topic_type``. Returns [] if unknown."""
    adapter = ADAPTER_REGISTRY.get(topic_type)
    if not adapter:
        logger.warning("[data_adapters] no adapter for topic_type=%s", topic_type)
        return []
    try:
        return adapter(topic_id)
    except Exception as exc:  # never crash the pipeline
        logger.warning("[data_adapters] adapter %s failed: %s", topic_type, exc)
        return []
