"""GAP 내부링크 + CTA 자동 삽입"""

import sqlite3
import re
import logging
import random

logger = logging.getLogger(__name__)

ENTITIES_DB = "/Users/twinssn/Projects/kuta-wordpress/storage/entities.db"

# CTA 블록 풀 (rotcha.kr, informationhot.kr, techpawz.com)
CTA_BLOCKS = [
    {
        "url": "https://hotissue.rotcha.kr/",
        "text": "자동차 핫이슈 모아보기",
        "color": "#2563eb",
    },
    {
        "url": "https://travel.rotcha.kr/",
        "text": "전국 여행지 추천 보러가기",
        "color": "#059669",
    },
    {
        "url": "https://deal.rotcha.kr/",
        "text": "자동차 프로모션/딜 확인하기",
        "color": "#d97706",
    },
    {
        "url": "https://stock.informationhot.kr/",
        "text": "오늘의 주식 공시 분석 보기",
        "color": "#7c3aed",
    },
    {
        "url": "https://65.informationhot.kr/",
        "text": "65세 이상 시니어 복지혜택 확인",
        "color": "#11998e",
    },
    {
        "url": "https://tour1.rotcha.kr/",
        "text": "캠핑장 추천 & 예약 정보",
        "color": "#2d6a4f",
    },
    {
        "url": "https://tour2.rotcha.kr/",
        "text": "전국 맛집 & 카페 추천",
        "color": "#e63946",
    },
    {
        "url": "https://ev.rotcha.kr/",
        "text": "전기차 비교 분석 보러가기",
        "color": "#0077b6",
    },
]

# 카테고리별 CTA 매핑 (관련도 높은 CTA 우선)
CATEGORY_CTA_MAP = {
    "세금/재테크": ["stock.informationhot", "65.informationhot"],
    "세금/납부": ["stock.informationhot", "65.informationhot"],
    "금융/부동산": ["stock.informationhot", "deal.rotcha"],
    "생활/행정": ["65.informationhot", "travel.rotcha"],
    "건강/복지": ["65.informationhot", "tour2.rotcha"],
    "자동차/교통": ["hotissue.rotcha", "deal.rotcha", "ev.rotcha"],
    "여행/축제": ["travel.rotcha", "tour1.rotcha", "tour2.rotcha"],
    "여행/항공": ["travel.rotcha", "tour1.rotcha"],
    "여행/자연": ["tour1.rotcha", "travel.rotcha"],
    "생활정보": ["65.informationhot", "tour2.rotcha"],
    "생활/보조금": ["65.informationhot", "stock.informationhot"],
}


def _load_entity_links():
    """entities.db에서 life_info/service 엔티티와 연결된 글 URL 로드"""
    try:
        conn = sqlite3.connect(ENTITIES_DB)
        rows = conn.execute("""
            SELECT e.name, p.title, p.url
            FROM post_entities pe
            JOIN entities e ON pe.entity_id = e.id
            JOIN posts p ON pe.post_id = p.id
            WHERE e.type IN ('life_info', 'service')
            AND p.url IS NOT NULL AND p.url != ''
            AND LENGTH(e.name) >= 2
            ORDER BY LENGTH(e.name) DESC
        """).fetchall()
        conn.close()

        # 엔티티명 → (글제목, URL) 매핑 (가장 긴 엔티티부터)
        entity_map = {}
        for name, title, url in rows:
            if name not in entity_map:
                entity_map[name] = {"title": title, "url": url}
        logger.info(f"내부링크용 엔티티 {len(entity_map)}건 로드")
        return entity_map
    except Exception as e:
        logger.warning(f"엔티티 DB 로드 실패: {e}")
        return {}


def inject_internal_links(html_content, max_links=3):
    """HTML 본문에서 엔티티 키워드를 찾아 내부링크 삽입"""
    entity_map = _load_entity_links()
    if not entity_map:
        return html_content

    inserted = 0
    used_urls = set()

    # 긴 엔티티명부터 매칭 (부분 매칭 방지)
    sorted_entities = sorted(entity_map.keys(), key=len, reverse=True)

    for entity_name in sorted_entities:
        if inserted >= max_links:
            break

        info = entity_map[entity_name]
        if info["url"] in used_urls:
            continue

        # <a> 태그 안의 텍스트는 건너뛰고 첫 번째 매칭만 링크로 변환
        escaped = re.escape(entity_name)

        def _replace_first(m):
            # 매칭 위치 앞에 열린 <a 태그가 닫히지 않았으면 스킵
            before = html_content[:m.start()]
            open_a = before.rfind("<a ")
            close_a = before.rfind("</a>")
            if open_a > close_a:
                return m.group(0)  # <a> 태그 내부 → 변환 안 함
            return f'<a href="{info["url"]}" target="_blank" rel="noopener" title="{info["title"]}">{m.group(0)}</a>'

        new_html = re.sub(escaped, _replace_first, html_content, count=1, flags=re.IGNORECASE)
        if new_html != html_content:
            html_content = new_html
            inserted += 1
            used_urls.add(info["url"])
            logger.info(f"내부링크 삽입: {entity_name} → {info['url']}")

    return html_content


def build_cta_block(category="생활정보", count=2):
    """카테고리에 맞는 CTA HTML 블록 생성"""
    # 카테고리별 우선 CTA 선택
    preferred = CATEGORY_CTA_MAP.get(category, [])
    selected = []

    # 우선 CTA 중에서 선택
    for cta in CTA_BLOCKS:
        if any(pref in cta["url"] for pref in preferred):
            selected.append(cta)
        if len(selected) >= count:
            break

    # 부족하면 랜덤 보충
    remaining = [c for c in CTA_BLOCKS if c not in selected]
    while len(selected) < count and remaining:
        pick = random.choice(remaining)
        selected.append(pick)
        remaining.remove(pick)

    # HTML 생성
    html_parts = []
    for cta in selected:
        html_parts.append(f'''<div style="background:{cta['color']}; padding:14px; border-radius:10px; margin:8px 0; text-align:center;">
<a href="{cta['url']}" target="_blank" rel="noopener" style="color:#fff; text-decoration:none; font-size:16px; font-weight:600;">{cta['text']} →</a>
</div>''')

    return "\n".join(html_parts)


def process_gap_content(html_content, category="생활정보"):
    """GAP 글에 내부링크 + CTA 삽입 (발행 직전 호출)"""
    # 1. 내부링크 삽입
    html_content = inject_internal_links(html_content, max_links=3)

    # 2. CTA 블록 생성 및 본문 하단에 삽입
    cta_html = build_cta_block(category, count=2)

    # 마지막 </p> 앞에 CTA 삽입 (마무리 문단 직전)
    last_p = html_content.rfind("</p>")
    if last_p > 0:
        html_content = html_content[:last_p] + "</p>\n" + cta_html + "\n" + html_content[last_p + 4:]
    else:
        html_content += "\n" + cta_html

    return html_content
