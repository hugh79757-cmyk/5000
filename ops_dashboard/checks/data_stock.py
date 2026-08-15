"""ops_dashboard.checks.data_stock — 브랜드별 재고 임계 검사 (DATA-01).

브랜드(brand) 기준으로 각 블로그가 아직 발행할 수 있는 콘텐츠 재고(남은
publishable stock)를 읽기 전용(read-only) 산출하고, 부족 임계(
STOCK_EMPTY / STOCK_LOW)를 벗어나면 fail로 알린다.

배경
----
* blog_lifecycle에는 `pipeline` 컬럼이 없고 `pipeline_path`만 있으며 전부 비어
  있음 → 파이프라인 구분은 `brand` 컬럼으로 한다. (작업2 결정 없음)
* 파이프라인별 재고 산출 fn 매핑이 현재 부재 → 여기서 신설한다 (BRAND_STOCK_FNS).
* 재고는 read-only 산출만 수행하고, 자동 보충 트리거는 이 단계에서 만들지 않는다.
* 노출은 /api/attention(register_check로 자동)과 /api/registry(RULES 엔트리,
  check_name==rule_id)에 additive로만.

접근 방식
---------
브랜드마다 재고의 의미가 다르다.
  - etap   : travel-en.db의 블로그별 topic 테이블에서 exhausted=0 수
  - cap    : car.db의 topics status='pending' 수 (공유 풀)
  - rap    : rap.db keywords status='active' 수
  - seap   : senior.db services status='pending' 수
  - stap   : STAP stap.db에서 소스별 수집 − 발행 수 (블로그별 소스 매핑)
  - cuap   : curation.db 정의 키워드 − published_products 사용 수
재고를 확정 산출할 수 없는 브랜드/블로그는 status="unknown"으로 돌려
오염(fail 오판)을 막는다.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ops_dashboard.checks import register_check

# 중앙 임계 상수 (freshness.py와 병렬 배치하는 전역 수준)
STOCK_EMPTY = 0    # 남은 재고 0 → fail (고갈)
STOCK_LOW = 10     # 남은 재고 <= 10 → fail (부족)

# 프로젝트 루트 (ops_dashboard/checks/data_stock.py → 5000/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# etapa pipeline 파일의 TOPIC_TABLE 상수로부터 도출한 블로그→topic 테이블 매핑
# (pipelines/etap/*_pipeline.py 의 BLOG_ID/TOPIC_TABLE 일치 기준)
ETAP_BLOG_TOPIC: dict[str, str] = {
    "adventure-hugo": "adventure_topics",
    "airlines-hugo": "airlines_topics",
    "airports-hugo": "airports_topics",
    "bus-hugo": "bus_topics",
    "citytours-hugo": "citytours_topics",
    "cruise-hugo": "cruise_topics",
    "culture-hugo": "culture_topics",
    "daytrips-hugo": "daytrips_topics",
    "deals-hugo": "deals_topics",
    "dining-hugo": "dining_topics",
    "escape-hugo": "escape_topics",
    "esim-hugo": "esim_topics",
    "eurail-hugo": "eurail_topics",
    "extreme-hugo": "extreme_topics",
    "ferry-hugo": "ferry_topics",
    "flights-hugo": "flight_topics",
    "foodtour-hugo": "foodtour_topics",
    "ghost-hugo": "ghost_topics",
    "hiking-hugo": "hiking_topics",
    "layover-hugo": "layover_topics",
    "luxury-hugo": "luxury_topics",
    "michelin-hugo": "michelin_topics",
    "multiday-hugo": "multiday_topics",
    "nature-hugo": "nature_topics",
    "nightlife-hugo": "nightlife_topics",
    "nomad-hugo": "nomad_topics",
    "phototour-hugo": "phototour_topics",
    "tours-hugo": "tours_topics",
    "trains-hugo": "trains_topics",
    "transfers-hugo": "transfers_topics",
    "visa-hugo": "visa_topics",
    "visafree-hugo": "visafree_topics",
    "walking-hugo": "walking_topics",
    "watersports-hugo": "watersports_topics",
    "watertours-hugo": "watertours_topics",
}

# STAP 블로그 → 소스 목록 (publish_log에서 블로그별 DISTINCT source 기준)
STAP_BLOG_SOURCES: dict[str, list[str]] = {
    "finance-hugo": ["deposit", "deposit_opt", "saving", "saving_opt"],
    "dividend-hugo": ["dividend", "rights", "krx"],
    "etf-hugo": ["etf", "index"],
    "sector-hugo": ["sector", "index", "krx"],
    "ipo-hugo": ["rights"],
    # stock-hugo: source 매핑 미확정 → unknown 처리 (재고 오판 방지)
}


def _etap_stock(blog_id: str) -> int | None:
    """etap 브랜드: 블로그의 topic 테이블에서 exhausted=0 수."""
    table = ETAP_BLOG_TOPIC.get(blog_id)
    if not table:
        return None
    db = PROJECT_ROOT / "data" / "travel-en.db"
    try:
        conn = sqlite3.connect(str(db))
        try:
            row = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE exhausted = 0"
            ).fetchone()
            return int(row[0]) if row else None
        finally:
            conn.close()
    except sqlite3.Error:
        return None


def _car_stock(_blog_id: str) -> int | None:
    """cap 브랜드: car.db topics pending 수 (공유 풀)."""
    db = PROJECT_ROOT / "data" / "car.db"
    try:
        conn = sqlite3.connect(str(db))
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM topics WHERE status = 'pending'"
            ).fetchone()
            return int(row[0]) if row else None
        finally:
            conn.close()
    except sqlite3.Error:
        return None


def _rap_stock(_blog_id: str) -> int | None:
    """rap 브랜드: rap.db keywords active 수."""
    db = PROJECT_ROOT / "data" / "rap.db"
    try:
        conn = sqlite3.connect(str(db))
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM keywords WHERE status = 'active'"
            ).fetchone()
            return int(row[0]) if row else None
        finally:
            conn.close()
    except sqlite3.Error:
        return None


def _seap_stock(_blog_id: str) -> int | None:
    """seap 브랜드: senior.db services pending 수."""
    db = PROJECT_ROOT / "data" / "senior.db"
    try:
        conn = sqlite3.connect(str(db))
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM services WHERE status = 'pending'"
            ).fetchone()
            return int(row[0]) if row else None
        finally:
            conn.close()
    except sqlite3.Error:
        return None


def _stap_stock(blog_id: str) -> int | None:
    """stap 브랜드: 소스별 수집 − 발행 수. 매핑 없으면 None(unknown)."""
    sources = STAP_BLOG_SOURCES.get(blog_id)
    if not sources:
        return None
    db = Path("/Users/twinssn/Projects/STAP/data/stap.db")
    if not db.exists():
        return None
    try:
        conn = sqlite3.connect(str(db))
        try:
            total = 0
            for src in sources:
                coll = conn.execute(
                    "SELECT COUNT(*) FROM collected_data WHERE source = ?", (src,)
                ).fetchone()[0]
                pub = conn.execute(
                    "SELECT COUNT(DISTINCT data_key) FROM publish_log "
                    "WHERE blog_id = ? AND source = ?",
                    (blog_id, src),
                ).fetchone()[0]
                total += max(int(coll) - int(pub), 0)
            return total
        finally:
            conn.close()
    except sqlite3.Error:
        return None


def _cuap_stock(blog_id: str) -> int | None:
    """cuap 브랜드: 정의 키워드 − published_products 사용수."""
    try:
        import importlib.util
        kw_path = PROJECT_ROOT / "pipelines" / "curation" / "keywords.py"
        if not kw_path.exists():
            return None
        spec = importlib.util.spec_from_file_location("keywords", str(kw_path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        defined = set(getattr(mod, "KEYWORD_MAP", {}).get(blog_id, []))
        if not defined:
            return None
        db = PROJECT_ROOT / "data" / "curation.db"
        conn = sqlite3.connect(str(db))
        try:
            rows = conn.execute(
                "SELECT DISTINCT keyword FROM published_products WHERE blog_id = ?",
                (blog_id,),
            ).fetchall()
            used = {r[0] for r in rows}
        finally:
            conn.close()
        return max(len(defined) - len(used), 0)
    except Exception:
        return None


# 브랜드 → 재고 산출 fn 매핑 (파이프라인별 재고 산출 fn 매핑 신설)
BRAND_STOCK_FNS: dict[str, callable] = {
    "etap": _etap_stock,
    "cap": _car_stock,
    "rap": _rap_stock,
    "seap": _seap_stock,
    "stap": _stap_stock,
    "cuap": _cuap_stock,
}


def _get_brand(conn: sqlite3.Connection, blog_id: str) -> str | None:
    """blog_lifecycle에서 brand 조회. 없으면 None."""
    try:
        row = conn.execute(
            "SELECT brand FROM blog_lifecycle WHERE blog_id = ?", (blog_id,)
        ).fetchone()
        return row[0] if row else None
    except sqlite3.Error:
        return None


@register_check("data_stock")
def check_data_stock(conn: sqlite3.Connection, blog_id: str) -> dict:
    """브랜드별 남은 재고를 산출하고 임계(STOCK_EMPTY/STOCK_LOW)로 판정."""
    brand = _get_brand(conn, blog_id)
    if not brand:
        return {"status": "unknown", "detail": f"data_stock: {blog_id} 브랜드 미확인"}
    fn = BRAND_STOCK_FNS.get(brand)
    if fn is None:
        return {
            "status": "unknown",
            "detail": f"data_stock: {blog_id} 브랜드({brand}) 재고 산출 fn 없음",
        }
    remaining = fn(blog_id)
    if remaining is None:
        return {
            "status": "unknown",
            "detail": f"data_stock: {blog_id} 재고 산출 불가 (브랜드 {brand})",
        }
    if remaining <= STOCK_EMPTY:
        return {
            "status": "fail",
            "detail": f"data_stock: {blog_id} 재고 고갈 (남은 {remaining}건, "
                      f"STOCK_EMPTY={STOCK_EMPTY}) [브랜드 {brand}]",
        }
    if remaining <= STOCK_LOW:
        return {
            "status": "fail",
            "detail": f"data_stock: {blog_id} 재고 부족 (남은 {remaining}건, "
                      f"STOCK_LOW={STOCK_LOW}) [브랜드 {brand}]",
        }
    return {
        "status": "pass",
        "detail": f"data_stock: {blog_id} 남은 재고 {remaining}건 [브랜드 {brand}]",
    }