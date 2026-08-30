"""trackc_task7_select.py — Track C Task 7: 자가 개선 대상 선정 + 루프 실행.

입력: data/analytics.db.gsc_pages (GSC 수집 완료)
출력:
  - blog_id별 tier(1/2/3) + 대상 포스트 목록 + Gate 1/2/3 통과 여부
  - (기본 스코프 michelin-hugo 파일럿) 선택된 michelin 대상에 대해
    generate -> validate(E1~E5) 루프 실행

Tier 정의:
  Tier 1: clicks > 0                  -> 즉시 개선(체류/전환)
  Tier 2: impressions > 0 & clicks=0  -> CTR 개선
  Tier 3: gsc_pages에 없음(미색인)    -> 색인 유도 (ETAP 블로그 중 0행)

Gate:
  Gate 1: blog_id in URL_TO_BLOG_ID roster (writer/route 존재)
  Gate 2: publish_ledger 7일 이력 기반 (PASS/FAIL/UNKNOWN)
  Gate 3: 대상 포스트 frontmatter title+slug+content>=50자

실행 루프 (michelin 대상):
  generate -> validate(E1~E5)
    PASS      -> "PUBLISH candidate" (배포 안 함)
    FAIL(1)   -> 재생성 1회
    FAIL(2)   -> "TELEGRAM ESCALATE" + hold (send_alert 1회, 실패 시 로그만)

중요: --dry-run(default True)은 절대 파일/배포를 하지 않음.
"""
import sqlite3
import os
import sys
import json
import re
import urllib.parse
import yaml
import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("trackc_task7")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from shared.analytics_collector import URL_TO_BLOG_ID  # valid writer/route roster

DB = os.path.join(BASE, "data", "analytics.db")
CONTENT_DB = os.path.join(BASE, "data", "content.db")
GA4_MAP = os.path.join(BASE, "config", "ga4_measurement_map.yaml")
ETAP_ROOT = "/Users/twinssn/Projects/ETAP"
SITE_ROOTS = [ETAP_ROOT, BASE]
TRAVEL_DB = os.path.join(BASE, "data", "travel-en.db")

VALID = set(URL_TO_BLOG_ID.values())

# 소스 고갈로 간주하는 stage
EXHAUSTED_STAGES = {
    "no_result", "no_data", "no_content", "no_keyword",
    "no_trade_data", "no_subscription_data", "collect_error",
    "irrelevant_products", "low_relevance",
}
from datetime import datetime, timedelta


def load_pages():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    rows = c.execute("SELECT blog_id, page, clicks, impressions FROM gsc_pages").fetchall()
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
    """publish_ledger 7일 이력 기반 판정 -> (verdict, reason)."""
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
    for r in rows:
        try:
            dt = datetime.fromisoformat(r["created_at"])
        except Exception:
            continue
        if (now - dt) > timedelta(days=7):
            break
        if r["status"] == "published" or r["stage"] == "published":
            return ("PASS", "recent_success")
        if r["stage"] in EXHAUSTED_STAGES:
            return ("FAIL", "source_exhausted:" + r["stage"])
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


def select_targets(scope="michelin-hugo"):
    """Return (agg_dict, tier3_list) for the given scope."""
    pages = load_pages()
    agg = {}
    for r in pages:
        bid = r["blog_id"]
        if scope and bid != scope:
            continue
        t = tier_of(r["clicks"], r["impressions"])
        if t is None:
            continue
        a = agg.setdefault(bid, {"t1": [], "t2": []})
        (a["t1"] if t == 1 else a["t2"]).append(r["page"])

    present = set(agg.keys())
    if scope:
        tier3 = [scope] if scope not in present else []
    else:
        tier3 = [bid for bid in etap_ids() if bid not in present]
    return agg, tier3


def summarize(agg, tier3, scope="michelin-hugo"):
    results = {}
    for bid, a in sorted(agg.items()):
        g2 = gate2(bid)
        g3 = True
        for pg in a["t1"] + a["t2"]:
            ok, _ = gate3(bid, pg)
            if not ok:
                g3 = False
                break
        passed = gate1(bid) and _g2_ok(g2) and g3
        results[bid] = {
            "tier1_count": len(a["t1"]), "tier2_count": len(a["t2"]),
            "target_posts": a["t1"] + a["t2"],
            "gate": {"gate1": gate1(bid), "gate2": {"verdict": g2[0], "reason": g2[1], "passed": _g2_ok(g2)}, "gate3": g3},
            "gate_passed": passed, "gate2_reason": g2[1],
        }
    for bid in tier3:
        g2 = gate2(bid)
        results[bid] = {
            "tier1_count": 0, "tier2_count": 0, "target_posts": [],
            "tier3_not_indexed": True,
            "gate": {"gate1": gate1(bid), "gate2": {"verdict": g2[0], "reason": g2[1], "passed": _g2_ok(g2)}, "gate3": True},
            "gate_passed": gate1(bid) and _g2_ok(g2), "gate2_reason": g2[1],
        }

    total_t1 = sum(r["tier1_count"] for r in results.values())
    total_t2 = sum(r["tier2_count"] for r in results.values())
    total_t3 = len(tier3)
    gate_filtered = sum(1 for r in results.values() if not r.get("gate_passed"))
    blogs_with_targets = len([r for r in results.values() if r["tier1_count"] or r["tier2_count"]])

    return {
        "scope": scope, "tier_1_count": total_t1, "tier_2_count": total_t2,
        "tier_3_count": total_t3, "blogs_with_targets": blogs_with_targets,
        "gate_filtered": gate_filtered, "per_blog": results,
    }


def _sample_topics(limit=2):
    c = sqlite3.connect(TRAVEL_DB)
    c.row_factory = sqlite3.Row
    rows = c.execute(
        "SELECT id, city, country, slug FROM michelin_topics "
        "WHERE exhausted=0 ORDER BY priority DESC, id LIMIT ?", (limit,)
    ).fetchall()
    c.close()
    return [dict(r) for r in rows]


def _escalate(blog_id, slug, issues):
    try:
        from shared.telegram_notifier import send_alert
        send_alert(blog_id, slug, issues)
        logger.info("[%s] TELEGRAM ESCALATE sent for %s", blog_id, slug)
    except Exception as e:
        logger.warning("[%s] TELEGRAM ESCALATE skipped (send failed): %s", blog_id, e)


def self_improve_loop(scope="michelin-hugo", dry_run=True, max_sample=2):
    """For each selected michelin target: generate -> validate(E1~E5).

    michelin-hugo has 0 GSC rows, so when no live targets resolve we run the
    identical loop on sample michelin_topics to exercise generate+validate.
    """
    from pipelines.etap.michelin_writer import generate_michelin_post, validate_structure

    agg, tier3 = select_targets(scope)
    targets = []
    for bid, a in agg.items():
        for pg in a["t1"] + a["t2"]:
            targets.append((bid, pg))
    if not targets:
        logger.info("[loop] no live GSC targets for scope=%s; demoing on sample michelin_topics", scope)
        for t in _sample_topics(max_sample):
            targets.append(("michelin-hugo", t))

    outcomes = []
    for bid, target in targets:
        topic = target if isinstance(target, dict) else {"city": str(target), "country": "", "slug": ""}
        city = topic.get("city", str(target))
        logger.info("[loop] target=%s city=%s", bid, city)
        article = generate_michelin_post(topic)
        if article is None:
            logger.error("[loop] %s/%s: generate FAILED (FAIL2) -> escalate", bid, city)
            _escalate(bid, city, ["generate_failed"])
            outcomes.append((bid, city, "FAIL", "generate_failed"))
            continue
        passed, issues = validate_structure(article["content"])
        if passed:
            print(f"[loop] {bid}/{city}: PUBLISH candidate (E1~E5 PASS)")
            outcomes.append((bid, city, "PASS", issues))
            continue
        # FAIL(1) -> regenerate once
        logger.info("[loop] %s/%s: FAIL(1) %s -> regenerate", bid, city, issues)
        article2 = generate_michelin_post(topic)
        if article2 is None:
            _escalate(bid, city, issues)
            outcomes.append((bid, city, "FAIL", issues))
            continue
        passed2, issues2 = validate_structure(article2["content"])
        if passed2:
            print(f"[loop] {bid}/{city}: PUBLISH candidate (regenerate PASS)")
            outcomes.append((bid, city, "PASS", issues2))
        else:
            logger.error("[loop] %s/%s: FAIL(2) %s -> TELEGRAM ESCALATE + hold", bid, city, issues2)
            _escalate(bid, city, issues2)
            outcomes.append((bid, city, "ESCALATE", issues2))
    return outcomes


def _selftest():
    """Validate E1~E5 on a passing and a failing fixture (no LLM, no IO)."""
    from pipelines.etap.michelin_writer import validate_structure

    pass_md = (
        "# Test\n\nIntro paragraph about the city Michelin scene.\n\n"
        "## At a Glance\n\nSome text.\n\n"
        "## Where to Eat\n\nSome text.\n\n"
        "## Compare\n\n"
        "<table><tr><th>Restaurant</th><th>Award</th><th>Cuisine</th><th>Price</th><th>Best For</th></tr>"
        + "".join(
            f"<tr><td>R{i}</td><td>1 Star</td><td>X</td><td>$50</td><td>Y</td></tr>"
            for i in range(1, 15)
        )
        + "</table>\n\n"
        "## FAQ\n\n"
        "### Q: Book ahead?\n### A: Yes.\n"
        "### Q: Vegetarian?\n### A: Yes.\n"
        "### Q: Dress code?\n### A: Smart casual.\n"
        + "word " * 800
    )
    fail_md = (
        "# Test\n\n## Where to Eat\n\ntext\n\n## FAQ\n\n### Q: A?\n### A: B\n"
    )
    p, pi = validate_structure(pass_md)
    f, fi = validate_structure(fail_md)
    print("SELFTEST pass-fixture:", "PASS" if p else "FAIL", pi)
    print("SELFTEST fail-fixture:", "PASS" if f else "FAIL", fi)
    assert p is True, "pass fixture should pass"
    assert f is False, "fail fixture should fail"
    print("SELFTEST OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", dest="dry_run", action="store_true", default=True,
                    help="Default True: never write files or deploy. Print generate+validate only.")
    ap.add_argument("--no-dry-run", dest="dry_run", action="store_false")
    ap.add_argument("--scope", default="michelin-hugo", help="Pilot scope (default michelin-hugo).")
    ap.add_argument("--json", default=None, help="Write summary JSON to path.")
    ap.add_argument("--selftest", action="store_true", help="Run E1~E5 fixture self-test and exit.")
    args = ap.parse_args()

    if args.selftest:
        _selftest()
        return

    summary = summarize(*select_targets(args.scope), scope=args.scope)
    print(json.dumps(
        {k: summary[k] for k in ("scope", "tier_1_count", "tier_2_count", "tier_3_count",
                                 "blogs_with_targets", "gate_filtered")},
        ensure_ascii=False, indent=2,
    ))

    if args.dry_run:
        print("\n[DRY-RUN] running self-improve loop (no files written, no deploy)")
        outcomes = self_improve_loop(scope=args.scope, dry_run=True)
        print(f"\n[DRY-RUN] loop outcomes: {len(outcomes)} target(s)")
        for bid, city, verdict, _ in outcomes:
            print(f"  - {bid}/{city}: {verdict}")
    else:
        logger.info("Non-dry-run execution not implemented in this pilot; use dispatcher.py to publish.")


if __name__ == "__main__":
    main()
