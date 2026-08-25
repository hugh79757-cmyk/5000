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
_CAR_DB = os.path.join(os.path.dirname(__file__), "..", "..", "data", "car.db")
_STOCK_DB = os.path.join(os.path.dirname(__file__), "..", "..", "data", "stock.db")
_RAP_DB = os.path.join(os.path.dirname(__file__), "..", "..", "data", "rap.db")
_CURATION_DB = os.path.join(os.path.dirname(__file__), "..", "..", "data", "curation.db")
_SENIOR_DB = os.path.join(os.path.dirname(__file__), "..", "..", "data", "senior.db")


def _connect_db(path):
    """Open a connection to the given sqlite DB, or None if missing/broken."""
    p = os.path.abspath(path)
    if not os.path.exists(p):
        logger.warning("[data_adapters] DB not found at %s", p)
        return None
    try:
        return sqlite3.connect(p)
    except sqlite3.Error as exc:
        logger.warning("[data_adapters] connect failed: %s", exc)
        return None


def _connect():
    """Open a read-only connection to travel-en.db, or None if missing."""
    return _connect_db(_DB_PATH)


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
    """flight_prices → min_price, min_stops, departure_date, airline.

    Phase 72 W2 T2.1 (threat T-72-01): when the topic row resolves, prices are
    scoped to that topic's own route (origin AND destination) so other routes'
    fares cannot leak into this article's synthesis. Falls back to the legacy
    global query only when the topic row is missing (behavior preserved).
    """
    conn = _connect()
    rows = []
    if topic_id is not None and conn is not None:
        trows = _query(
            conn,
            "SELECT origin, destination FROM flight_topics WHERE id = ?",
            (topic_id,),
        )
        t = trows[0] if trows else {}
        if t.get("origin") and t.get("destination"):
            rows = _query(
                conn,
                """
                SELECT price, stops, departure_date, airline, origin, destination
                FROM flight_prices
                WHERE origin = ? AND destination = ?
                ORDER BY price ASC LIMIT 20
                """,
                (t["origin"], t["destination"]),
            )
    if not rows:
        # Legacy global fallback (unchanged behavior when topic row missing).
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


def car_adapter(topic_id=None):
    """car.db topics → cars + trims join → model, brand, fuel_type, min_price.

    Phase 72 W2 T2.2. topic_id = car.db topics.id. Never raises.
    """
    conn = _connect_db(_CAR_DB)
    try:
        if conn is None or topic_id is None:
            return []
        trows = _query(conn, "SELECT car_id FROM topics WHERE id = ?", (topic_id,))
        if not trows or trows[0].get("car_id") is None:
            return []
        car_id = trows[0]["car_id"]
        crows = _query(
            conn,
            "SELECT brand, model, year, fuel_type, segment, body_type FROM cars WHERE car_id = ? LIMIT 1",
            (car_id,),
        )
        if not crows:
            return []
        c = crows[0]
        points = [
            _point("model", c.get("model"), "", "cars"),
            _point("brand", c.get("brand"), "", "cars"),
            _point("fuel_type", c.get("fuel_type"), "", "cars"),
            _point("segment", c.get("segment"), "", "cars"),
            _point("body_type", c.get("body_type"), "", "cars"),
            _point("model_year", c.get("year"), "년", "cars"),
        ]
        trims_ = _query(
            conn,
            "SELECT trim_name, price, fuel_efficiency FROM trims WHERE car_id = ? ORDER BY price ASC LIMIT 5",
            (car_id,),
        )
        prices = [t.get("price") for t in trims_ if isinstance(t.get("price"), (int, float))]
        if prices:
            points.append(_point("min_price", min(prices), "만원", "trims"))
            cheapest = trims_[0]
            points.append(_point("entry_trim", cheapest.get("trim_name"), "", "trims"))
            effs = [t.get("fuel_efficiency") for t in trims_ if isinstance(t.get("fuel_efficiency"), (int, float))]
            if effs:
                points.append(_point("max_fuel_efficiency", max(effs), "km/L", "trims"))
        return [p for p in points if p]
    finally:
        if conn:
            conn.close()


def stock_evergreen_adapter(topic_id=None):
    """stock.db dividend_ranking latest top ranks → date, rank, corp, yield, dps.

    Phase 72 W2 T2.2. topic_id = evergreen topic_type string (e.g.
    "dividend_ranking") — informational only; the query is date-scoped.
    """
    conn = _connect_db(_STOCK_DB)
    try:
        rows = _query(
            conn,
            """
            SELECT date, rank, corp_name, dividend_yield, dividend_per_share
            FROM dividend_ranking
            WHERE date = (SELECT MAX(date) FROM dividend_ranking)
            ORDER BY rank ASC LIMIT 3
            """,
        )
        if not rows:
            return []
        top = rows[0]
        points = [
            _point("ranking_date", top.get("date"), "date", "dividend_ranking"),
            _point("top_rank", top.get("rank"), "위", "dividend_ranking"),
            _point("top_corp", top.get("corp_name"), "", "dividend_ranking"),
            _point("top_yield", top.get("dividend_yield"), "%", "dividend_ranking"),
            _point("top_dps", top.get("dividend_per_share"), "KRW", "dividend_ranking"),
        ]
        if len(rows) > 1:
            second = rows[1]
            points.append(_point("second_corp", second.get("corp_name"), "", "dividend_ranking"))
            points.append(_point("second_yield", second.get("dividend_yield"), "%", "dividend_ranking"))
        return [p for p in points if p]
    finally:
        if conn:
            conn.close()


def stock_disclosure_adapter(topic_id=None):
    """stock.db corps (+ dividend_ranking) → corp_code, corp_name, dividend facts.

    Phase 72 W2 T2.2. topic_id = corp_code or corp_name (writer passes
    disclosure's corp_code with corp_name fallback). Never raises.
    """
    key = str(topic_id).strip() if topic_id is not None else ""
    if not key:
        return []
    conn = _connect_db(_STOCK_DB)
    try:
        corps_ = _query(
            conn,
            "SELECT corp_code, corp_name FROM corps WHERE corp_code = ? OR corp_name = ? LIMIT 1",
            (key, key),
        )
        if not corps_:
            return []
        corp_code = corps_[0].get("corp_code")
        corp_name = corps_[0].get("corp_name") or key
        points = [
            _point("corp_code", corp_code, "", "corps"),
            _point("corp_name", corp_name, "", "corps"),
        ]
        div = _query(
            conn,
            """
            SELECT date, rank, dividend_yield, dividend_per_share
            FROM dividend_ranking
            WHERE corp_name = ?
            ORDER BY date DESC, rank ASC LIMIT 1
            """,
            (corp_name,),
        )
        if div:
            d = div[0]
            points.append(_point("dividend_yield", d.get("dividend_yield"), "%", "dividend_ranking"))
            points.append(_point("dividend_per_share", d.get("dividend_per_share"), "KRW", "dividend_ranking"))
            points.append(_point("dividend_date", d.get("date"), "date", "dividend_ranking"))
        return [p for p in points if p]
    finally:
        if conn:
            conn.close()


def rap_trade_adapter(topic_id=None):
    """rap.db trades → region deal counts, min/max amounts, latest apt sample.

    Phase 72 W2 T2.2. topic_id = keyword (region name, e.g. "강남구"). Never raises.
    """
    kw = str(topic_id).strip() if topic_id is not None else ""
    if not kw:
        return []
    conn = _connect_db(_RAP_DB)
    try:
        like = f"%{kw}%"
        stats = _query(
            conn,
            """
            SELECT COUNT(*) AS cnt, MIN(deal_amount) AS min_amt, MAX(deal_amount) AS max_amt
            FROM trades
            WHERE district LIKE ? OR city LIKE ?
            """,
            (like, like),
        )
        s = stats[0] if stats else {}
        if not s.get("cnt"):
            return []
        points = [
            _point("trade_region", kw, "", "trades"),
            _point("trade_count", s.get("cnt"), "건", "trades"),
            _point("min_deal_amount", s.get("min_amt"), "만원", "trades"),
            _point("max_deal_amount", s.get("max_amt"), "만원", "trades"),
        ]
        sample = _query(
            conn,
            """
            SELECT apt_name, exclu_use_ar, deal_amount
            FROM trades
            WHERE district LIKE ? OR city LIKE ?
            ORDER BY deal_ymd DESC LIMIT 1
            """,
            (like, like),
        )
        if sample:
            points.append(_point("latest_apt", sample[0].get("apt_name"), "", "trades"))
            points.append(_point("latest_area", sample[0].get("exclu_use_ar"), "㎡", "trades"))
        return [p for p in points if p]
    finally:
        if conn:
            conn.close()


def rap_sub_adapter(topic_id=None):
    """rap.db subscriptions → region announcement count, types, latest dates.

    Phase 72 W2 T2.2. topic_id = keyword (region/project name). Never raises.
    """
    kw = str(topic_id).strip() if topic_id is not None else ""
    if not kw:
        return []
    conn = _connect_db(_RAP_DB)
    try:
        like = f"%{kw}%"
        stats = _query(
            conn,
            "SELECT COUNT(*) AS cnt FROM subscriptions WHERE region_nm LIKE ? OR pan_nm LIKE ?",
            (like, like),
        )
        cnt = stats[0].get("cnt") if stats else 0
        if not cnt:
            return []
        rows = _query(
            conn,
            """
            SELECT pan_nm, pan_type, pan_start, pan_end
            FROM subscriptions
            WHERE region_nm LIKE ? OR pan_nm LIKE ?
            ORDER BY pan_start DESC LIMIT 5
            """,
            (like, like),
        )
        points = [_point("sub_count", cnt, "건", "subscriptions")]
        types = sorted({r.get("pan_type") for r in rows if r.get("pan_type")})
        if types:
            points.append(_point("sub_types", ", ".join(types[:3]), "", "subscriptions"))
        latest = rows[0] if rows else {}
        points.append(_point("latest_pan", latest.get("pan_nm"), "", "subscriptions"))
        points.append(_point("latest_pan_start", latest.get("pan_start"), "date", "subscriptions"))
        return [p for p in points if p]
    finally:
        if conn:
            conn.close()


def curation_adapter(topic_id=None):
    """curation.db products → keyword product count, price range, top item.

    Phase 72 W2 T2.2. topic_id = keyword (e.g. "노트북 추천"). Exact match
    first, LIKE fallback. Never raises.
    """
    kw = str(topic_id).strip() if topic_id is not None else ""
    if not kw:
        return []
    conn = _connect_db(_CURATION_DB)
    try:
        prods = _query(
            conn,
            """
            SELECT product_name, product_price, category_name, rank
            FROM products WHERE keyword = ?
            ORDER BY rank ASC, collected_at DESC LIMIT 5
            """,
            (kw,),
        )
        if not prods:
            prods = _query(
                conn,
                """
                SELECT product_name, product_price, category_name, rank
                FROM products WHERE keyword LIKE ?
                ORDER BY collected_at DESC LIMIT 5
                """,
                (f"%{kw}%",),
            )
        if not prods:
            return []
        points = [
            _point("product_count", len(prods), "개", "products"),
            _point("category", prods[0].get("category_name"), "", "products"),
        ]
        name = prods[0].get("product_name")
        if name:
            points.append(_point("top_product", str(name)[:60], "", "products"))
        prices = [p.get("product_price") for p in prods if isinstance(p.get("product_price"), (int, float))]
        if prices:
            points.append(_point("min_price", min(prices), "KRW", "products"))
            points.append(_point("max_price", max(prices), "KRW", "products"))
        return [p for p in points if p]
    finally:
        if conn:
            conn.close()


def senior_adapter(topic_id=None):
    """senior.db services → service name, category, department, target.

    Phase 72 W2 T2.2. topic_id = service_id (e.g. "131200000005"). Never raises.
    """
    sid = str(topic_id).strip() if topic_id is not None else ""
    if not sid:
        return []
    conn = _connect_db(_SENIOR_DB)
    try:
        rows = _query(
            conn,
            "SELECT service_id, service_name, category, target, department FROM services WHERE service_id = ? LIMIT 1",
            (sid,),
        )
        if not rows:
            return []
        s = rows[0]
        target = s.get("target")
        points = [
            _point("service_name", s.get("service_name"), "", "services"),
            _point("service_category", s.get("category"), "", "services"),
            _point("department", s.get("department"), "", "services"),
            _point("service_target", (str(target)[:80] if target else None), "", "services"),
        ]
        return [p for p in points if p]
    finally:
        if conn:
            conn.close()


ADAPTER_REGISTRY = {
    "flight": flight_adapter,
    "viator": viator_adapter,
    "nature": nature_adapter,
    "deals": deals_adapter,
    "car": car_adapter,
    "stock_evergreen": stock_evergreen_adapter,
    "stock_disclosure": stock_disclosure_adapter,
    "rap_trade": rap_trade_adapter,
    "rap_sub": rap_sub_adapter,
    "curation": curation_adapter,
    "senior": senior_adapter,
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
