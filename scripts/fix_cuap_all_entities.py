#!/usr/bin/env python3
"""CUAP 엔티티 슬러그 종합 수정 - 실제 배포된 포스트 슬러그와 DB 동기화"""

import os
import sqlite3
from shared.cuap_entity_linker import BLOG_DOMAINS, DB_PATH

CUAP_BASE = "/Users/twinssn/Projects/cuap"

def find_matching_slug(blog_id, entity_name):
    """실제 콘텐츠 폴더에서 entity_name과 매칭되는 슬러그 찾기"""
    blog_path = os.path.join(CUAP_BASE, f"{blog_id}/content/posts/")
    if not os.path.exists(blog_path):
        return None
    
    slugs = os.listdir(blog_path)
    entity_keywords = entity_name.replace(" 추천", "").replace(" ", "-")
    
    # 1순위: 정확한 키워드 포함
    for slug in slugs:
        if entity_keywords in slug:
            return slug
    
    # 2순위: 부분 매칭 (엔티티명의 주요 단어들)
    main_words = [w for w in entity_name.split() if len(w) >= 2 and w not in ["추천", "비교", "선택", "가이드", "총정리", "실속"]]
    for slug in slugs:
        matches = sum(1 for w in main_words if w in slug)
        if matches >= 2:  # 주요 단어 2개 이상 매칭
            return slug
    
    return None

def main():
    print("=== CUAP 엔티티 슬러그 종합 수정 시작 ===\n")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 모든 published=1 엔티티 조회
    cursor.execute("""
        SELECT blog_id, entity_name, post_slug, post_url, rowid
        FROM cuap_entities 
        WHERE published = 1
    """)
    entities = cursor.fetchall()
    
    print(f"총 {len(entities)}개 엔티티 검사 대상\n")
    
    updated = 0
    unpublished = 0
    already_correct = 0
    
    for blog_id, entity_name, db_slug, db_url, rowid in entities:
        domain = BLOG_DOMAINS.get(blog_id, "")
        if not domain:
            continue
            
        # 실제 파일시스템에서 매칭되는 슬러그 찾기
        actual_slug = find_matching_slug(blog_id, entity_name)
        
        if actual_slug is None:
            # 매칭되는 포스트가 없음 - unpublished 처리
            cursor.execute("UPDATE cuap_entities SET published = 0 WHERE rowid = ?", (rowid,))
            unpublished += 1
            print(f"[UNPUBLISHED] {blog_id} | {entity_name} (실제 포스트 없음)")
        elif actual_slug != db_slug:
            # 슬러그 불일치 - 업데이트
            new_url = f"{domain}/posts/{actual_slug}/"
            cursor.execute("""
                UPDATE cuap_entities 
                SET post_slug = ?, post_url = ? 
                WHERE rowid = ?
            """, (actual_slug, new_url, rowid))
            updated += 1
            print(f"[UPDATED] {blog_id} | {entity_name}")
            print(f"  Old: {db_slug}")
            print(f"  New: {actual_slug}")
        else:
            already_correct += 1
    
    conn.commit()
    conn.close()
    
    print(f"\n=== 요약 ===")
    print(f"이미 정확: {already_correct}")
    print(f"슬러그 수정: {updated}")
    print(f"미발행 처리: {unpublished}")
    print(f"총 처리: {already_correct + updated + unpublished}")

if __name__ == "__main__":
    main()