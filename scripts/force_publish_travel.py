#!/usr/bin/env python3
"""travel-hugo 쿼터 우회 직접 발행 스크립트.
dispatcher의 _is_duplicate 체크와 pipeline의 내부 quota 체크를 모두 우회한다.
"""
import os
import sys

# 경로 설정
FIVEK_ROOT = "/Users/twinssn/Projects/5000"
TAP_ROOT = "/Users/twinssn/Projects/TAP"

sys.path.insert(0, FIVEK_ROOT)
sys.path.insert(0, TAP_ROOT)
os.chdir(TAP_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(TAP_ROOT, ".env"))
load_dotenv(os.path.join(FIVEK_ROOT, ".env"))

from pipelines.travel.pipeline import _run_single
from pipelines.travel.writer import generate_content
from shared.content_store import init_db, get_today_count
from shared.publisher import get_blog_config as _original_get_blog_config

# 로그 설정
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

blog_id = "travel-hugo"

# 블로그 설정 직접 구성 (dispatcher.get_blog_config 대체)
blog_cfg = {
    "id": blog_id,
    "daily_quota": 999,  # 쿼터 우회
    "platform": "hugo",
    "site_path": "/Users/twinssn/Projects/TAP/travel-hugo",
    "domain": "tour1.rotcha.kr",
    "shortcodes_enabled": True,
    "prompt_map": {"camping": "tour1_camping"},
}

# publisher.py 내부 get_blog_config() 패치 → daily_quota=999 반환
_original_get_blog_config_fn = _original_get_blog_config
def _patched_get_blog_config(blog_id_inner):
    if blog_id_inner == blog_id:
        return blog_cfg
    return _original_get_blog_config_fn(blog_id_inner)

import shared.publisher
shared.publisher.get_blog_config = _patched_get_blog_config

print(f"[{blog_id}] 오늘 발행 건수: {get_today_count(blog_id)} / 쿼터 우회 (999)")

# quota 체크가 없는 직접 실행 경로
result = _run_single(blog_id, blog_cfg=blog_cfg)

if result and result.get("success"):
    print(f"\n✅ 발행 성공!")
    print(f"   제목: {result.get('title', '')}")
    print(f"   URL: {result.get('url', result.get('published_url', 'N/A'))}")
    print(f"   Slug: {result.get('slug', 'N/A')}")
else:
    reason = result.get("reason") if result else "결과 없음"
    print(f"\n❌ 발행 실패: {reason}")
    sys.exit(1)
