"""trackc_task7_select.py — Track C Task 7: 자가 개선 대상 선정 로직.

입력: data/analytics.db.gsc_pages (563행, collect_gsc 수집 완료)
출력: blog_id별 tier(1/2/3), 대상 포스트 목록, topic-suitability 3단계 AND 게이트 통과 여부.

Tier 정의:
  Tier 1: clicks > 0            → 즉시 개선(체류/전환)
  Tier 2: impressions > 0 & clicks = 0 → CTR 개선
  Tier 3: gsc_pages에 없음(미색인) → 색인 유도 필요 (ETAP 36 블로그 중 0행)

topic-suitability 3단계 AND 게이트:
  Gate 1: blog_id의 writer/route 존재 (URL_TO_BLOG_ID roster)
  Gate 2: 데이터 원소스 유효 (파이프라인별 DB에 미사용 원소 존재 — simplified heuristic)
  Gate 3: Stage 1 스키마 위반 아님 (대상 포스트 frontmatter: title+slug+content≥50자)

실행: python3 scripts/trackc_task7_select.py [--json out.json]
"""
import sqlite3, os, sys, json, re, urllib.parse, yaml

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from shared.analytics_collector import URL_TO_BLOG_ID  # valid writer/route roster

DB = os.path.join(BASE, "data", "analytics.db")
CONTENT_DB = os.path.join(BASE, "data", "content.db")
GA4_MAP = os.path.join(BASE, "config", "ga4_measurement_map.yaml")
ETAP_ROOT = "/Users/twinssn/Projects/ETAP"
SITE_ROOTS = [ETAP_ROOT, BASE]

VALID = set(URL_TO_BLOG_ID.values())

# 소스 고갈로 간주하는 stage (데이터 없음/수집 실패)
EXHAUSTED_STAGES = {
    "no_result", "no_data", "no_content", "no_keyword",
    "no_trade_data", "no_subscription_data", "collect_error",
    "irrelevant_products", "low_relevance",
}
from datetime import datetime, timedelta


def load_pages():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    rows = c.execute(
        "SELECT blog_id, page, clicks, impressions FROM gsc_pages"
    ).fetchall()
    c.close()
    return rows


def etap_ids():
    with open(GA4_MAP) as f:
        g = yaml.safe_load(f)
    return [f"{k}" for k in g.get("blogs", {}).keys()]


def tier_of(clicks, impr):
    if clicks and clicks > 0:
        return 1
    if impr and impr > 0:
        return 2
    return None


def gate1(blog_id):
    return blog_id in VALID


def gate2(blog_id):
    """데이터 원소스 유효성: publish_ledger 최근 생성 이력 기반 실질 판정.

    반환: (verdict, reason)
      - PASS    : 최근 7일 내 성공 생성 있음 (소스 유효)
      - FAIL    : 최근 생성이 exhausted/no_result (소스 고갈)
      - UNKNOWN : 생성 이력 없음 또는 7일 내 신호 없음 → 보수적 PASS + 경고
    """
    try:
        c = sqlite3.connect(CONTENT_DB)
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT stage, status, created_at FROM publish_ledger "
            "WHERE blog_id=? ORDER BY created_at DESC LIMIT 30",
            (blog_id,),
        ).fetchall()
        c.close()
    except Exception:
        return ("UNKNOWN", "db_unavailable")
    if not rows:
        return ("UNKNOWN", "no_history")
    now = datetime.now()
    recent_success = None
    recent_exhausted = None
    for r in rows:
        try:
            dt = datetime.fromisoformat(r["created_at"])
        except Exception:
            continue
        if (now - dt) > timedelta(days=7):
            break
        if r["status"] == "published" or r["stage"] == "published":
            recent_success = r
            break
        if r["stage"] in EXHAUSTED_STAGES:
            recent_exhausted = r
            break
    if recent_success is not None:
        return ("PASS", "recent_success")
    if recent_exhausted is not None:
        return ("FAIL", "source_exhausted:" + recent_exhausted["stage"])
    return ("UNKNOWN", "no_recent_signal")


def _g2_ok(res):
    return res[0] in ("PASS", "UNKNOWN")


def _slug_from_url(u):
    dec = urllib.parse.unquote(u)
    m = re.search(r"/posts/([^/]+)/?$", dec)
    if m:
        return m.group(1)
    seg = dec.rstrip("/").split("/")[-1]
    return seg or None


def gate3(blog_id, page):
    slug = _slug_from_url(page)
    if not slug:
        return (True, "skip_no_slug")
    for root in SITE_ROOTS:
        site = os.path.join(root, blog_id.replace("-hugo", "") + "-hugo")
        p = os.path.join(site, "content", "posts", slug, "index.md")
        if os.path.exists(p):
            txt = open(p, encoding="utf-8").read()
            parts = txt.split("---", 2)
            ok = (
                len(parts) >= 3
                and "title:" in parts[1]
                and "slug:" in parts[1]
                and len(parts[2].strip()) > 50
            )
            return (ok, "found")
    return (True, "not_found")


def main():
    pages = load_pages()
    agg = {}  # blog_id -> {t1:[], t2:[]}
    for r in pages:
        bid = r["blog_id"]
        t = tier_of(r["clicks"], r["impressions"])
        if t is None:
            continue
        a = agg.setdefault(bid, {"t1": [], "t2": []})
        (a["t1"] if t == 1 else a["t2"]).append(r["page"])

    results = {}
    for bid, a in sorted(agg.items()):
        g2 = gate2(bid)
        gates = {"gate1": gate1(bid), "gate2": {"verdict": g2[0], "reason": g2[1], "passed": _g2_ok(g2)}}
        # gate3: 대상 포스트 중 하나라도 Stage1 위반 시 fail
        g3 = True
        for pg in a["t1"] + a["t2"]:
            ok, _ = gate3(bid, pg)
            if not ok:
                g3 = False
                break
        gates["gate3"] = g3
        passed = gates["gate1"] and gates["gate2"]["passed"] and gates["gate3"]
        results[bid] = {
            "tier1_count": len(a["t1"]),
            "tier2_count": len(a["t2"]),
            "target_posts": a["t1"] + a["t2"],
            "gate": gates,
            "gate_passed": passed,
            "gate2_reason": g2[1],
        }

    # Tier 3: ETAP 36 중 gsc_pages 0행 (미색인)
    present = set(agg.keys())
    tier3 = [bid for bid in etap_ids() if bid not in present]
    for bid in tier3:
        g2 = gate2(bid)
        results[bid] = {
            "tier1_count": 0,
            "tier2_count": 0,
            "target_posts": [],
            "tier3_not_indexed": True,
            "gate": {"gate1": gate1(bid), "gate2": {"verdict": g2[0], "reason": g2[1], "passed": _g2_ok(g2)}, "gate3": True},
            "gate_passed": gate1(bid) and _g2_ok(g2),
            "gate2_reason": g2[1],
        }

    total_t1 = sum(r["tier1_count"] for r in results.values())
    total_t2 = sum(r["tier2_count"] for r in results.values())
    total_t3 = len(tier3)
    gate_filtered = sum(
        1 for r in results.values() if not r.get("gate_passed")
    )

    summary = {
        "tier_1_count": total_t1,
        "tier_2_count": total_t2,
        "tier_3_count": total_t3,
        "blogs_with_targets": len([r for r in results.values() if r["tier1_count"] or r["tier2_count"]]),
        "gate_filtered": gate_filtered,
        "implementation_path": "scripts/trackc_task7_select.py",
        "per_blog": results,
    }
    if "--json" in sys.argv:
        out = sys.argv[sys.argv.index("--json") + 1]
        with open(out, "w") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"wrote {out}")
    print(json.dumps(
        {k: summary[k] for k in ("tier_1_count", "tier_2_count", "tier_3_count", "blogs_with_targets", "gate_filtered", "implementation_path")},
        ensure_ascii=False, indent=2,
    ))


if __name__ == "__main__":
    main()
