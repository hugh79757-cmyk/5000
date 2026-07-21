"""backfill_cuap_entities.py — CUAP 크로스셀 카드용 실제 발행 글 백필

Phase 27 / Task 27-02.
travel-en.db `cuap_entities` 가 Phase 25 테스트 데이터(-rec 등)로 채워져
크로스셀 카드가 404를 가리키던 문제를 해결하기 위해, 각 CUAP 블로그의
실제 `content/posts/<slug>` 디렉토리를 스캔해 `published=1` 행을 등록한다.

규칙:
- BLOG_DOMAINS / register_cuap_entity() 재사용 (외부 입력 차단 유지)
- 기존 (blog_id, post_slug) 행이 있으면 skip (idempotent)
- 각 블로그 최신 N개(기본 5, argv[1]로 오버라이드)만 등록
- newest가 가장 높은 rowid를 갖도록 삽입 순서 정렬 (카드 LIMIT 1 rowid DESC)

사용: python3 scripts/backfill_cuap_entities.py [N]
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.cuap_entity_linker import BLOG_DOMAINS, register_cuap_entity, _get_db

CUAP_ROOT = "/Users/twinssn/Projects/cuap"
N_DEFAULT = 5


def clean_label(slug: str) -> str:
    """slug에서 '추천'만 분리한 카드 라벨. (PLAN 27-02 명세)"""
    label = slug.replace("추천", "").replace("--", "-").strip("-").strip()
    return label or slug


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else N_DEFAULT
    summary = {}
    for blog_id, _domain in BLOG_DOMAINS.items():
        posts_dir = os.path.join(CUAP_ROOT, blog_id, "content", "posts")
        if not os.path.isdir(posts_dir):
            summary[blog_id] = "NO_DIR"
            continue
        entries = []
        for slug in os.listdir(posts_dir):
            d = os.path.join(posts_dir, slug)
            if os.path.isdir(d):
                entries.append((slug, os.path.getmtime(d)))
        if not entries:
            summary[blog_id] = 0
            continue
        # newest N (mtime desc)
        entries.sort(key=lambda x: x[1], reverse=True)
        newest = entries[:n]
        # oldest-of-N first -> newest gets highest rowid (card picks rowid DESC)
        newest.reverse()
        added = 0
        for slug, _ in newest:
            conn = _get_db()
            try:
                exists = conn.execute(
                    "SELECT 1 FROM cuap_entities WHERE blog_id=? AND post_slug=?",
                    (blog_id, slug),
                ).fetchone()
            finally:
                conn.close()
            if exists:
                continue
            register_cuap_entity(
                "post", slug, blog_id, slug, clean_label(slug), priority=50, published=1
            )
            added += 1
        summary[blog_id] = added

    print("=== backfill summary (added rows per blog) ===")
    for b, c in summary.items():
        print(f"  {b}: {c}")
    print("BACKFILL DONE")


if __name__ == "__main__":
    main()
