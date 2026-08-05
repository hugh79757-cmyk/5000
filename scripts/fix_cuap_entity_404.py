#!/usr/bin/env python3
"""CUAP 엔티티 링커 404 오류 해결 - 일괄 처리 스크립트

문제:
1. beauty-hugo 등 CUAP 블로그의 엔티티 커넥터에 중국어 (한자) 가 섞여들어감
2. '엔티티 공스킨 추천' 등 링크가 404 오류 발생

해결:
1. keywords.py 에서 한자 키워드 제거 (완료)
2. DB 에 등록된 잘못된 엔티티 전수 조사 및 수정
3. 재발 방지 장치 마련
"""

import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.cuap_entity_linker import BLOG_DOMAINS, DB_PATH, _get_db

CUAP_ROOT = "/Users/twinssn/Projects/cuap"
HANJA_PATTERN = re.compile(r'[\u4e00-\u9fff]')


def scan_blog_posts(blog_id):
    """블로그의 실제 포스트 슬러그와 제목을 스캔"""
    posts_dir = os.path.join(CUAP_ROOT, blog_id, "content", "posts")
    if not os.path.isdir(posts_dir):
        return []
    
    results = []
    for slug in os.listdir(posts_dir):
        post_path = os.path.join(posts_dir, slug, "index.md")
        if os.path.isfile(post_path):
            with open(post_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # front matter 에서 title 추출
            title_match = re.search(r'title:\s*["\']?([^"\']+)["\']?', content)
            title = title_match.group(1).strip() if title_match else slug
            
            # 본문의 첫 번째 단락에서 entity_name 후보 추출
            body_match = re.search(r'---\s*\n\s*\n(.+?)\n\n', content, re.DOTALL)
            first_para = body_match.group(1) if body_match else ""
            
            results.append({
                'slug': slug,
                'title': title,
                'first_paragraph': first_para[:200],
                'has_hanja': bool(HANJA_PATTERN.search(title) or HANJA_PATTERN.search(first_para))
            })
    
    return results


def check_entities_in_db():
    """DB 의 모든 엔티티를 검사하여 문제 항목 보고"""
    conn = _get_db()
    
    print("=== CUAP 엔티티 DB 전수 조사 ===\n")
    
    # 모든 published 엔티티 조회
    cursor = conn.execute("""
        SELECT rowid, blog_id, entity_name, post_slug, post_url, link_label
        FROM cuap_entities
        WHERE published = 1
        ORDER BY blog_id, entity_name
    """)
    
    entities = cursor.fetchall()
    total = len(entities)
    problems = {
        'hanja_in_name': [],
        'hanja_in_label': [],
        'slug_mismatch': [],
        'missing_posts': []
    }
    
    for row in entities:
        rowid, blog_id, entity_name, post_slug, post_url, link_label = row
        
        # 1. entity_name 에 한자가 있는지 확인
        if HANJA_PATTERN.search(entity_name):
            problems['hanja_in_name'].append({
                'rowid': rowid,
                'blog_id': blog_id,
                'entity_name': entity_name,
                'post_slug': post_slug
            })
        
        # 2. link_label 에 한자가 있는지 확인
        if link_label and HANJA_PATTERN.search(link_label):
            problems['hanja_in_label'].append({
                'rowid': rowid,
                'blog_id': blog_id,
                'link_label': link_label
            })
        
        # 3. 실제 포스트 존재 여부 확인
        posts_dir = os.path.join(CUAP_ROOT, blog_id, "content", "posts", post_slug)
        if not os.path.isdir(posts_dir):
            problems['missing_posts'].append({
                'rowid': rowid,
                'blog_id': blog_id,
                'entity_name': entity_name,
                'post_slug': post_slug,
                'post_url': post_url
            })
    
    conn.close()
    
    # 결과 보고
    print(f"총 엔티티 수: {total}")
    print(f"\n문제 항목:")
    print(f"  - entity_name 에 한자 포함: {len(problems['hanja_in_name'])}개")
    print(f"  - link_label 에 한자 포함: {len(problems['hanja_in_label'])}개")
    print(f"  - 포스트 없음 (404 원인): {len(problems['missing_posts'])}개")
    
    if problems['hanja_in_name']:
        print("\n=== entity_name 에 한자 포함된 항목 (최대 20 개) ===")
        for i, item in enumerate(problems['hanja_in_name'][:20]):
            print(f"  {i+1}. [{item['blog_id']}] {item['entity_name']} (slug: {item['post_slug']})")
    
    if problems['hanja_in_label']:
        print("\n=== link_label 에 한자 포함된 항목 (최대 20 개) ===")
        for i, item in enumerate(problems['hanja_in_label'][:20]):
            print(f"  {i+1}. [{item['blog_id']}] {item['link_label']}")
    
    if problems['missing_posts']:
        print("\n=== 실제 포스트가 없는 항목 (404 발생, 최대 20 개) ===")
        for i, item in enumerate(problems['missing_posts'][:20]):
            print(f"  {i+1}. [{item['blog_id']}] {item['entity_name']}")
            print(f"      URL: {item['post_url']}")
            print(f"      Slug: {item['post_slug']}")
    
    return problems


def fix_hanja_entities(dry_run=True):
    """한자가 포함된 엔티티 수정 (published=0 으로 비활성화)"""
    conn = _get_db()
    mode = "DRY-RUN" if dry_run else "APPLY"
    
    print(f"\n=== 한자 엔티티 비활성화 ({mode}) ===\n")
    
    cursor = conn.execute("""
        SELECT rowid, blog_id, entity_name, link_label
        FROM cuap_entities
        WHERE published = 1
    """)
    
    updated_count = 0
    for row in cursor:
        rowid, blog_id, entity_name, link_label = row
        
        has_hanja = HANJA_PATTERN.search(entity_name) or (link_label and HANJA_PATTERN.search(link_label))
        if has_hanja:
            if not dry_run:
                conn.execute("UPDATE cuap_entities SET published = 0 WHERE rowid = ?", (rowid,))
            print(f"  [FIX] {blog_id}: {entity_name[:50]}...")
            updated_count += 1
    
    if not dry_run:
        conn.commit()
    conn.close()
    
    print(f"\n총 {updated_count}개 엔티티 비활성화")
    return updated_count


def main():
    print("CUAP 엔티티 링커 404 오류 해결 스크립트\n")
    print("=" * 60)
    
    # 1. 현재 상태 진단
    problems = check_entities_in_db()
    
    # 2. 한자 엔티티 수정 제안
    print("\n" + "=" * 60)
    action = input("\n한자가 포함된 엔티티를 비활성화하시겠습니까? (y/n): ").strip().lower()
    
    if action == 'y':
        dry_run = input("Dry-run 으로 먼저 확인하시겠습니까? (y/n): ").strip().lower() == 'y'
        fix_hanja_entities(dry_run=dry_run)
    
    # 3. 블로그별 실제 포스트 현황
    print("\n" + "=" * 60)
    print("\n블로그별 포스트 현황:")
    for blog_id in sorted(BLOG_DOMAINS.keys()):
        posts = scan_blog_posts(blog_id)
        hanja_count = sum(1 for p in posts if p['has_hanja'])
        print(f"  {blog_id}: {len(posts)}개 포스트, {hanja_count}개 한자 포함")
    
    print("\n작업 완료!")


if __name__ == "__main__":
    main()
