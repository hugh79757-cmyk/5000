#!/usr/bin/env python3
"""키워드 격리 현황 보고서 — CLI 실행

사용법:
    python scripts/quarantine_report.py              # 전체 블로그
    python scripts/quarantine_report.py laptop-hugo   # 특정 블로그만
    python scripts/quarantine_report.py --reset 게이밍노트북  # 키워드 격리 해제
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipelines.curation.keyword_health import KeywordHealthStore

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "curation.db")


def main():
    store = KeywordHealthStore(DB_PATH)
    store.ensure_table()

    args = sys.argv[1:]

    # --reset 플래그 처리
    if "--reset" in args:
        idx = args.index("--reset")
        if idx + 1 < len(args):
            keyword = args[idx + 1]
            # blog_id가 지정되지 않았으면 전체 블로그에서 해당 키워드 찾기
            blog_filter = None
            for a in args:
                if not a.startswith("--") and a != keyword:
                    blog_filter = a
                    break
            if blog_filter:
                store.reset_keyword(blog_filter, keyword)
                print(f"✅ '{blog_filter}'의 '{keyword}' 격리 해제됨")
            else:
                # blog_id 없이 키워드만 있으면 모든 블로그에서 해제
                for row in store.get_quarantined_keywords():
                    if row["keyword"] == keyword:
                        store.reset_keyword(row["blog_id"], keyword)
                        print(f"✅ '{row['blog_id']}'의 '{keyword}' 격리 해제됨")
            return

    # 블로그 필터
    blog_filter = None
    for a in args:
        if not a.startswith("--"):
            blog_filter = a
            break

    keywords = store.get_quarantined_keywords(blog_filter)
    if not keywords:
        print("No quarantined keywords.")
        return

    from datetime import datetime

    # 블로그별 그룹화
    by_blog: dict[str, list[dict]] = {}
    for kw in keywords:
        bid = kw["blog_id"]
        if bid not in by_blog:
            by_blog[bid] = []
        by_blog[bid].append(kw)

    total_quarantined = len(keywords)
    total_keywords_all = 0

    print(f"🔒 키워드 격리 현황 ({datetime.now().strftime('%Y-%m-%d')})")
    print("━" * 40)

    for bid, kws in sorted(by_blog.items()):
        from pipelines.curation.keywords import get_keywords

        total = len(get_keywords(bid))
        total_keywords_all += total
        qty = len(kws)
        print(f"\n{bid}: {qty}/{total} 격리")
        for kw in kws[:10]:  # 최대 10개 표시
            reason = kw.get("last_failure_reason", "unknown")
            q_until = kw.get("quarantined_until", "")
            # 남은 시간 계산
            try:
                remaining = datetime.fromisoformat(q_until) - datetime.now()
                days = remaining.days
                hours = remaining.seconds // 3600
                if days > 0:
                    time_str = f"{days}일 {hours}시간"
                else:
                    time_str = f"{hours}시간"
            except (ValueError, TypeError):
                time_str = q_until
            print(
                f"  - {kw['keyword']}: {kw['consecutive_failures']}회 실패 "
                f"({reason}) → {time_str} 남음"
            )
        if len(kws) > 10:
            print(f"  ... 외 {len(kws) - 10}개")

    print("━" * 40)
    print(f"총 {total_quarantined}개 키워드 격리 중 "
          f"(전체 {total_keywords_all}개 중 "
          f"{total_quarantined / total_keywords_all * 100:.1f}%)")


if __name__ == "__main__":
    main()
