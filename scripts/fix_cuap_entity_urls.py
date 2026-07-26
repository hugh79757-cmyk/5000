#!/usr/bin/env python3
"""CUAP 엔티티 URL 백필 수정 스크립트

Phase 25 초기 오염 데이터 16건을 실제 Hugo 콘텐츠 slug로 수정.
"""

import os
import sqlite3
from shared.cuap_entity_linker import BLOG_DOMAINS, DB_PATH

CUAP_BASE = "/Users/twinssn/Projects/cuap"

# 수정 매핑: (blog_id, entity_name) -> correct_slug
# None이면 미발행 글로 간주하여 published=0으로 변경
FIXES = {
    # health-hugo - title-based slugs with date prefix (from actual content folder)
    ("health-hugo", "비오틴 탈모 영양제"): "2026년-7월-비오틴-탈모-영양제-추천-제일헬스사이언스닥터트루-비교-top-4",
    ("health-hugo", "면역력 강화 영양제"): "2026년-7월-면역력-영양제-추천-데이배리어뉴트리코스트-4만원대부터-50만원대까지-실속-선택",
    ("health-hugo", "마그네슘 영양제"): "마그네슘-영양제-추천-나우푸드gnm-실속-선택",
    
    # baby-hugo
    ("baby-hugo", "아기 이유식 용품 추천"): "2026년-7월-아기-이유식-용품-top-5-추천-베어블리글라스락-베이비-실속-선택과-후기",
    ("baby-hugo", "아기 카시트 추천"): "아기-카시트-추천-마드레마노-카시트-머리고정과-어린이-안전-의자",
    ("baby-hugo", "아기 쏘서 추천"): "유닛키즈-쏘서-3in1-vs-브라이트스타트-바운스-액티비티-아기-쏘서-추천",
    
    # fitness-hugo
    ("fitness-hugo", "밸런스보드 추천"): "밸런스보드-추천-스포홀릭-사각-밸런스보드-vs-휴다온-프리미엄-근력",
    ("fitness-hugo", "덤벨 추천"): "덤벨-추천-홈짐-홈트-pev와-아리프-블루밍-실속형-top-5",
    ("fitness-hugo", "스쿼트 보조 기구 추천"): "스쿼트-보조-기구-추천-별의-바다-고탄력-vs-tani-일체형-스쿼트랙",
    
    # kitchen-hugo
    ("kitchen-hugo", "수동착즙기 추천"): "수동착즙기-추천-휴롬-슬림형-착즙기-h310a-bfc04wh-vs-투데이리빙-대형-스텐-착즙기",
    
    # beauty-hugo
    ("beauty-hugo", "파우더 추천"): "2026년-7월-파우더-비교-미팩토리-뿌숭뿌숭-vs-헤브블루-메이크업-프로-7100원-vs-15100원-선택-가이드",
    ("beauty-hugo", "향수 추천"): "2026년-7월-캘빈클라인-씨케이-비-블루-옴므-실속-선택이-가능한-향수-추천-5가지",
    
    # appliance-hugo
    ("appliance-hugo", "여름철 제습기 추천"): "여름철-제습기-추천-미니아-1등급-산업용-vs-신일-1등급-대용량",
    
    # health-hugo (additional)
    ("health-hugo", "피로회복 영양제 추천"): "뉴트리코바일양약품-피로회복-영양제-추천-2026년-7월-실제-후기-top-5",
    ("health-hugo", "간 건강 영양제 추천"): "2026년-7월-간-건강-영양제-추천-뉴트리하루-실리마린과-대원제약-간케어-비교",
    
    # laptop-hugo - 미발행
    ("laptop-hugo", "MSI 게이밍 노트북"): None,
    
    # interior-hugo
    ("interior-hugo", "평상형 침대 추천"): "평상형-침대-추천-쏠앤까사-스텔라-vs-숲에온-편백나무",
}


def verify_slug_exists(blog_id, slug):
    """실제 콘텐츠 폴더에 slug가 존재하는지 확인"""
    blog_path = os.path.join(CUAP_BASE, f"{blog_id}/content/posts/")
    if not os.path.exists(blog_path):
        return False
    return slug in os.listdir(blog_path)


def main():
    print("=== CUAP 엔티티 URL 백필 수정 시작 ===\n")
    
    # 사전 검증: 모든 수정 대상 slug가 실제 존재하는지 확인
    print("사전 검증: 실제 콘텐츠 폴더와 매칭 확인")
    for (blog_id, entity_name), correct_slug in FIXES.items():
        if correct_slug is None:
            print(f"  [SKIP] {blog_id} | {entity_name} -> 미발행 처리")
            continue
        exists = verify_slug_exists(blog_id, correct_slug)
        status = "OK" if exists else "NOT FOUND"
        print(f"  [{status}] {blog_id} | {entity_name} -> {correct_slug}")
    
    print("\nDB 업데이트 실행...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    updated = 0
    unpublished = 0
    errors = 0
    
    for (blog_id, entity_name), correct_slug in FIXES.items():
        domain = BLOG_DOMAINS.get(blog_id, "")
        if not domain:
            print(f"  [ERROR] Unknown blog_id: {blog_id}")
            errors += 1
            continue
            
        if correct_slug is None:
            # 미발행: published=0으로 변경
            cursor.execute("""
                UPDATE cuap_entities 
                SET published = 0 
                WHERE blog_id = ? AND entity_name = ?
            """, (blog_id, entity_name))
            unpublished += 1
            print(f"  [UNPUBLISHED] {blog_id} | {entity_name} (rowcount: {cursor.rowcount})")
        else:
            # slug와 URL 업데이트
            correct_url = f"{domain}/posts/{correct_slug}/"
            cursor.execute("""
                UPDATE cuap_entities 
                SET post_slug = ?, post_url = ?
                WHERE blog_id = ? AND entity_name = ?
            """, (correct_slug, correct_url, blog_id, entity_name))
            updated += 1
            print(f"  [UPDATED] {blog_id} | {entity_name}")
            print(f"    New slug: {correct_slug}")
            print(f"    New URL: {correct_url} (rowcount: {cursor.rowcount})")
    
    conn.commit()
    conn.close()
    
    print(f"\n=== 요약 ===")
    print(f"업데이트됨: {updated}")
    print(f"미발행 처리: {unpublished}")
    print(f"에러: {errors}")
    print(f"총 처리: {updated + unpublished + errors}")
    
    # 사후 검증
    print("\n사후 검증: 수정된 엔티티 확인")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT blog_id, entity_name, post_slug, post_url, published 
        FROM cuap_entities 
        WHERE (blog_id, entity_name) IN ({})
        ORDER BY blog_id, entity_name
    """.format(",".join(["(?,?)"] * len(FIXES))), 
    [item for pair in FIXES.keys() for item in pair])
    
    rows = cursor.fetchall()
    for row in rows:
        print(f"  {row[0]} | {row[1]} | published={row[4]} | {row[3]}")
    
    # 전체 통계
    cursor.execute("SELECT COUNT(*) FROM cuap_entities WHERE published = 1")
    total_published = cursor.fetchone()[0]
    print(f"\n전체 published=1 엔티티: {total_published}개")
    
    conn.close()


if __name__ == "__main__":
    main()