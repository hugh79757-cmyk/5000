"""
백링크 자동 발행 모듈 v1.0
- telegra.ph: 글 발행 직후 요약본 자동 게시
- GitHub README: 글 목록 자동 업데이트 (Phase 1)
"""

import os
import re
import logging
import requests

logger = logging.getLogger(__name__)

# Telegraph 토큰 — .env에서 로드
TELEGRAPH_TOKEN = os.getenv("TELEGRAPH_ACCESS_TOKEN", "")

# 블로그별 Telegraph 저자 설정
BLOG_AUTHOR = {
    "rap-hugo":    {"name": "부동산 시세 리포트", "url": "https://apt.informationhot.kr"},
    "rap2-hugo":   {"name": "청약정보 리포트", "url": "https://apply.informationhot.kr"},
    "rap3-hugo":   {"name": "부동산 세금 가이드", "url": "https://tax.informationhot.kr"},
    "rap4-hugo":   {"name": "전월세 시장 분석", "url": "https://rent.informationhot.kr"},
    "rap5-hugo":   {"name": "브랜드아파트 리포트", "url": "https://brand.informationhot.kr"},
    "ud-blogger":  {"name": "생활정보 매거진", "url": "https://ud.informationhot.kr"},
    "kuta-wordpress": {"name": "쿠따 생활정보", "url": "https://kuta.informationhot.kr"},
    "tvshow-blogger": {"name": "TV-SHOW 매거진", "url": "https://tv-show.informationhot.kr"},
}

DEFAULT_AUTHOR = {"name": "informationhot", "url": "https://informationhot.kr"}


def _md_to_telegraph_content(body_md, original_url):
    """마크다운 본문에서 요약 300자 + 원문 링크 Telegraph 노드 생성"""
    # 마크다운 태그 제거
    plain = re.sub(r'#{1,6}\s*', '', body_md)
    plain = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', plain)
    plain = re.sub(r'[*_`~]', '', plain)
    plain = re.sub(r'<[^>]+>', '', plain)
    plain = re.sub(r'\n{2,}', '\n', plain).strip()

    # 요약 (처음 300자)
    summary = plain[:300]
    if len(plain) > 300:
        summary += "..."

    # H2 헤딩 추출 (최대 5개)
    h2s = re.findall(r'^## (.+)$', body_md, re.MULTILINE)[:5]

    content = []

    # 요약문
    content.append({"tag": "p", "children": [summary]})

    # 목차
    if h2s:
        content.append({"tag": "h4", "children": ["목차"]})
        items = [{"tag": "li", "children": [h]} for h in h2s]
        content.append({"tag": "ul", "children": items})

    # 원문 링크
    content.append({"tag": "p", "children": [" "]})
    content.append({"tag": "p", "children": [
        {"tag": "a", "attrs": {"href": original_url},
         "children": ["📖 전체 글 보기 (원문)"]},
    ]})

    # 면책
    content.append({"tag": "p", "attrs": {"style": "color:#888;font-size:12px"},
                     "children": ["본 글은 공공데이터를 기반으로 자동 생성되었습니다."]})

    return content


def publish_to_telegraph(title, body_md, original_url, blog_id=None):
    """Telegraph에 요약 글 발행, 백링크 URL 반환"""
    if not TELEGRAPH_TOKEN:
        logger.warning("TELEGRAPH_ACCESS_TOKEN 미설정 — 백링크 건너뜀")
        return None

    author = BLOG_AUTHOR.get(blog_id, DEFAULT_AUTHOR)
    content = _md_to_telegraph_content(body_md, original_url)

    try:
        r = requests.post("https://api.telegra.ph/createPage", json={
            "access_token": TELEGRAPH_TOKEN,
            "title": title,
            "author_name": author["name"],
            "author_url": author["url"],
            "content": content,
            "return_content": False,
        }, timeout=15)

        data = r.json()
        if data.get("ok"):
            url = data["result"]["url"]
            logger.info(f"Telegraph 백링크 생성: {url}")
            return url
        else:
            logger.warning(f"Telegraph 발행 실패: {data.get('error')}")
            return None
    except Exception as e:
        logger.warning(f"Telegraph 요청 실패: {e}")
        return None


def post_publish_backlinks(title, body_md, original_url, blog_id=None):
    """발행 후 백링크 일괄 생성 (Phase 1: Telegraph)"""
    results = {}

    # 1. Telegraph
    tg_url = publish_to_telegraph(title, body_md, original_url, blog_id)
    if tg_url:
        results["telegraph"] = tg_url

    # Phase 2: medium, pinterest 등 추가 예정

    if results:
        logger.info(f"백링크 {len(results)}개 생성: {list(results.keys())}")
    else:
        logger.warning("백링크 생성 실패 (0개)")

    return results
