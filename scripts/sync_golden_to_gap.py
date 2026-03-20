#!/usr/bin/env python3
"""news-keyword-pro golden CSV → gap.db keywords 자동 동기화"""

import csv
import sqlite3
import re
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

GOLDEN_CSV_DIR = Path("/Users/twinssn/Projects/news-keyword-pro/output/csv")
GAP_DB_PATH = Path("/Users/twinssn/Projects/5000/data/gap.db")

CATEGORY_MAP = {
    "정부정책": "생활/행정",
    "금융": "금융/부동산",
    "건강/의료": "건강/복지",
    "부동산": "금융/부동산",
    # "자동차": CAP 파이프라인과 충돌하므로 제외
    "IT/모바일": "IT/기술",
    "생활/문화": "생활정보",
    "사회": "생활/행정",
}
ALLOWED_CATEGORIES = set(CATEGORY_MAP.keys())

BLACKLIST_PATTERNS = [
    r"코인$", r"시세$", r"시세조회", r"환율$",
    r"비트코인", r"이더리움", r"리플", r"빗썸", r"업비트",
    r"솔라나", r"도지", r"에이다", r"카이아", r"테더",
    r"^XRP", r"엑스알피",
    r"계산기$",
    r"오목게임", r"초시계",
    r"주가$", r"주가전망",
    r"PPT", r"스케치업",
    r"KODEX", r"코덱스", r"ETF$",
    r"TQQQ", r"SOXL", r"곱버스", r"레버리지",
    r"포토$", r"사진$",
    r"다시보기", r"누누티비",
    r"번역기", r"파파고",
    r"게임$", r"겜$",
    r"실구매가", r"출고가", r"견적",
    r"^EV\d", r"^K\d", r"^BMW", r"^벤츠", r"^아우디", r"^볼보",
    r"^현대모비스", r"^기아", r"^제네시스",
    r"에스턴마틴", r"마세라티", r"람보르기니", r"페라리",
    r"엔진오일", r"5W30", r"5W40",
    r"컷소$", r"DCH\d",
]
BLACKLIST_RE = [re.compile(p, re.IGNORECASE) for p in BLACKLIST_PATTERNS]

MIN_MONTHLY_SEARCH = 1000
MAX_MONTHLY_SEARCH = 100000
MAX_SATURATION = 0.5
MAX_BLOG_COUNT = 10000


def is_blacklisted(keyword):
    for p in BLACKLIST_RE:
        if p.search(keyword):
            return True
    return False


def compute_priority(row):
    sat = float(row.get("포화도", 999) or 999)
    monthly = int(row.get("월간검색량", 0) or 0)
    trend = row.get("트렌드", "-")
    if trend == "🔥" and sat <= 0.2:
        return 1
    if sat <= 0.2 and monthly >= 5000:
        return 1
    if sat <= 0.3 and monthly >= 3000:
        return 2
    if sat <= 0.5 and monthly >= 1000:
        return 3
    return 5


def load_golden_csv(date_str):
    csv_path = GOLDEN_CSV_DIR / f"golden_{date_str}.csv"
    if not csv_path.exists():
        return []
    rows = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def filter_keywords(rows):
    accepted = []
    stats = {"total": len(rows), "cat_rejected": 0, "blacklisted": 0,
             "search_low": 0, "search_high": 0, "saturated": 0,
             "blog_high": 0, "difficulty": 0, "accepted": 0}
    for row in rows:
        category = row.get("카테고리", "")
        keyword = row.get("키워드", "").strip()
        monthly = int(row.get("월간검색량", 0) or 0)
        blog_count = int(row.get("블로그수", 0) or 0)
        sat = float(row.get("포화도", 999) or 999)
        difficulty = row.get("난이도", "")
        if not keyword or len(keyword) <= 3:
            continue
        if category not in ALLOWED_CATEGORIES:
            stats["cat_rejected"] += 1
            continue
        if is_blacklisted(keyword):
            stats["blacklisted"] += 1
            continue
        if difficulty != "🟢":
            stats["difficulty"] += 1
            continue
        if monthly < MIN_MONTHLY_SEARCH:
            stats["search_low"] += 1
            continue
        if monthly > MAX_MONTHLY_SEARCH:
            stats["search_high"] += 1
            continue
        if sat > MAX_SATURATION:
            stats["saturated"] += 1
            continue
        if blog_count > MAX_BLOG_COUNT:
            stats["blog_high"] += 1
            continue
        accepted.append({
            "keyword": keyword,
            "category": CATEGORY_MAP[category],
            "priority": compute_priority(row),
            "monthly_search": monthly,
            "saturation": sat,
        })
    stats["accepted"] = len(accepted)
    return accepted, stats


def upsert_to_gap_db(keywords, dry_run=False):
    result = {"inserted": 0, "upgraded": 0, "skipped": 0}
    if dry_run:
        for kw in keywords:
            print(f"    [DRY] P{kw['priority']} | {kw['category']:10s} | 검색:{kw['monthly_search']:>6d} 포화:{kw['saturation']:.2f} | {kw['keyword']}")
        result["inserted"] = len(keywords)
        return result
    conn = sqlite3.connect(GAP_DB_PATH)
    cur = conn.cursor()
    for kw in keywords:
        try:
            cur.execute("INSERT INTO keywords (keyword, category, priority, status, use_count) VALUES (?, ?, ?, 'active', 0)",
                        (kw["keyword"], kw["category"], kw["priority"]))
            result["inserted"] += 1
        except sqlite3.IntegrityError:
            cur.execute("UPDATE keywords SET priority = ? WHERE keyword = ? AND priority > ?",
                        (kw["priority"], kw["keyword"], kw["priority"]))
            if cur.rowcount > 0:
                result["upgraded"] += 1
            else:
                result["skipped"] += 1
    conn.commit()
    conn.close()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str)
    parser.add_argument("--backfill", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    kst = timezone(timedelta(hours=9))
    today = datetime.now(kst).strftime("%Y-%m-%d")
    if args.backfill:
        dates = [(datetime.now(kst) - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(args.backfill)]
        dates.reverse()
    elif args.date:
        dates = [args.date]
    else:
        dates = [today]
    print(f"golden CSV → gap.db sync | {dates[0]} ~ {dates[-1]} ({len(dates)}일) | dry-run={args.dry_run}")
    total_ins, total_upg, total_skip = 0, 0, 0
    for d in dates:
        rows = load_golden_csv(d)
        if not rows:
            continue
        accepted, stats = filter_keywords(rows)
        print(f"  {d}: 전체={stats['total']} 카테고리제외={stats['cat_rejected']} 블랙={stats['blacklisted']} 난이도={stats.get('difficulty',0)} 검색량↓={stats['search_low']} 포화={stats['saturated']} → 통과={stats['accepted']}")
        if accepted:
            r = upsert_to_gap_db(accepted, dry_run=args.dry_run)
            print(f"         신규={r['inserted']} 업그레이드={r['upgraded']} 스킵={r['skipped']}")
            total_ins += r["inserted"]
            total_upg += r["upgraded"]
            total_skip += r["skipped"]
    print(f"\n완료: 신규={total_ins} 업그레이드={total_upg} 스킵={total_skip}")
    if not args.dry_run:
        conn = sqlite3.connect(GAP_DB_PATH)
        cur = conn.cursor()
        total = cur.execute("SELECT COUNT(*) FROM keywords WHERE status='active'").fetchone()[0]
        cats = cur.execute("SELECT category, COUNT(*) FROM keywords WHERE status='active' GROUP BY category ORDER BY COUNT(*) DESC").fetchall()
        pris = cur.execute("SELECT priority, COUNT(*) FROM keywords WHERE status='active' GROUP BY priority ORDER BY priority").fetchall()
        conn.close()
        print(f"\ngap.db 총 키워드: {total}")
        for p, c in pris:
            print(f"  P{p}: {c}건")
        for cat, cnt in cats:
            print(f"  {cat}: {cnt}")


if __name__ == "__main__":
    main()
