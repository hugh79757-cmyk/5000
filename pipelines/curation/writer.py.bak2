"""상품 데이터 → AI 큐레이션 글 생성

상품 5개 데이터를 받아 "TOP5 추천" 형태의 블로그 글을 생성.
각 상품에 어필리에이트 링크 포함.
"""
import os
import sys
import logging
import re
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.ai_writer import generate as ai_generate

logger = logging.getLogger(__name__)


def _build_product_block(products):
    """상품 데이터를 프롬프트용 텍스트로 변환 (enriched 데이터 포함)"""
    lines = []
    for i, p in enumerate(products, 1):
        rocket = "로켓배송" if p.get("is_rocket") else ""
        free_ship = "무료배송" if p.get("is_free_shipping") else ""
        badges = " / ".join(filter(None, [rocket, free_ship]))

        # 브랜드/제조사
        brand = p.get("brand", "")
        maker = p.get("maker", "")
        brand_str = brand or maker or ""

        # 파싱된 스펙
        specs = p.get("parsed_specs", {})
        spec_lines = []
        for k, v in specs.items():
            spec_lines.append(f"  {k}: {v}")
        spec_str = "\n".join(spec_lines) if spec_lines else "  (스펙 정보 없음)"

        lines.append(
            f"[상품{i}]\n"
            f"- 상품명: {p['product_name']}\n"
            f"- 브랜드: {brand_str}\n"
            f"- 가격: {p.get('product_price', 0):,}원\n"
            f"- 카테고리: {p.get('category_name', '')}\n"
            f"- 배송: {badges or '일반배송'}\n"
            f"- 쿠팡순위: {p.get('rank', '-')}위\n"
            f"- 확인된 스펙:\n{spec_str}\n"
            f"- 링크: {p.get('product_url', '')}\n"
            f"- 이미지: {p.get('product_image', '')}\n"
        )
    return "\n".join(lines)


def _build_system_prompt(keyword):
    year = datetime.now().year
    month = datetime.now().month
    return f"""당신은 10년 경력의 상품 큐레이션 전문 블로거입니다.
{year}년 {month}월 기준 "{keyword}" 관련 추천 상품 글을 작성합니다.

[제목 규칙 — 가장 중요]
- 제목에 반드시 실제 제품명 또는 브랜드명을 1~2개 포함해야 합니다.
- 상품 데이터에서 가장 인기 있는 제품의 브랜드명/모델명을 추출하여 제목에 넣으세요.
- 좋은 제목 예시:
  * "갤럭시북5 프로 vs LG그램 프로 사무용 노트북 비교"
  * "다이슨 V15 삼성 비스포크 제트 무선청소기 추천 비교"
  * "대학생 노트북 추천 갤럭시북5 LG그램 가성비 비교 {year}"
  * "에어프라이어 추천 필립스 vs 쿠쿠 실사용 비교"
  * "삼성 비스포크 제트 무선청소기 실사용 후기 및 추천"
- 나쁜 제목 예시 (이렇게 쓰지 마세요):
  * "노트북 추천 TOP5" — 제품명 없음
  * "무선청소기 인기 순위" — 브랜드명 없음
  * "○○ 추천 (2026년 3월)" — 너무 일반적
- 핵심 키워드가 제목 앞 15자 이내에 위치해야 합니다.

[본문 구조]
1. 도입부(2~3문장): 이 제품을 고를 때 겪는 구체적 고민. 공감하는 톤으로.
2. 선택 가이드(제품 소개 전에 배치):
   - H2 소제목: "○○ 고를 때 확인할 포인트"
   - 핵심 선택 기준 3~4가지를 본문으로 서술 (예: 흡입력, 배터리, 무게, 소음)
   - 각 기준마다 구체적 수치 기준 제시 (예: "배터리는 최소 30분 이상이 기본입니다")
3. 상품 5개 각각 소개:
   - H2 소제목에 상품명 포함 (번호 붙이지 말 것)
   - 소개 시작에 상품 이미지: ![상품명](이미지URL)
   - 핵심 스펙을 상품명에서 추출하여 구체적 수치로 표기 (예: "32GB RAM, 1TB SSD", "185AW 흡입력")
   - 가격, 배송정보를 자연스럽게 포함
   - 이 제품의 장점 1~2가지와 아쉬운 점 1가지를 반드시 포함
   - 추천 대상을 구체적으로 명시 (예: "영상편집 작업이 많은 직장인에게 적합합니다")
   - 소개 끝에 링크: [쿠팡에서 최저가 확인하기](상품링크)
4. 정리(2~3문장): "이런 사람은 A제품, 저런 사람은 B제품" 식으로 간단 요약. "마무리", "결론" 소제목 금지.

[문체 규칙]
- "~입니다/~습니다" 체로 통일
- 글 마지막에 반드시 포함: "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."

[스펙 서술 규칙 — 매우 중요]
- "확인된 스펙"에 있는 수치만 본문에 사용하세요.
- 스펙 정보가 없는 항목은 추측하거나 지어내지 마세요.
- "뛰어난 성능", "강력한 흡입력" 같은 추상적 표현 대신, 스펙 수치가 있으면 수치를 쓰고 없으면 해당 항목을 언급하지 마세요.
- 브랜드 정보가 있으면 제목과 본문에 적극 활용하세요.

[절대 금지 — 아래 표현이 하나라도 있으면 실패입니다]
- "살펴보겠습니다", "알아보겠습니다", "소개합니다", "소개해 드리겠습니다"
- "바랍니다", "드립니다", "놓치지 마세요"
- "마무리", "결론" 소제목
- 취소선(~~), 이모지, 마크다운 테이블
- "이번 포스팅에서는" 표현

[글자수]
- 총 2000~3000자"""


def _build_user_prompt(keyword, product_block):
    # 상품명에서 브랜드/모델명 추출하여 제목 힌트 제공
    brand_hints = []
    for line in product_block.split("\n"):
        if line.startswith("- 상품명:"):
            name = line.replace("- 상품명:", "").strip()
            # 첫 2~3단어가 보통 브랜드+모델명
            tokens = name.split()[:3]
            hint = " ".join(tokens)
            if hint and hint not in brand_hints:
                brand_hints.append(hint)
    brand_hint_str = ", ".join(brand_hints[:3])

    return f"""키워드: {keyword}
주요 브랜드/모델: {brand_hint_str}

위 브랜드/모델명 중 1~2개를 반드시 제목에 포함하세요.
아래 5개 상품 데이터를 기반으로 추천 큐레이션 글을 작성해주세요.
상품 순서는 가격 대비 가치가 높은 순으로 재배치해도 좋습니다.
각 상품의 링크와 이미지 URL은 반드시 그대로 사용하세요.

{product_block}"""


def generate_curation_article(keyword, products):
    """키워드 + 상품 5개 → 큐레이션 글 생성, dict 반환"""
    if not products or len(products) < 3:
        logger.warning(f"상품 부족: {keyword} ({len(products) if products else 0}개)")
        return None

    product_block = _build_product_block(products[:5])
    system_prompt = _build_system_prompt(keyword)
    user_prompt = _build_user_prompt(keyword, product_block)

    result = ai_generate(system_prompt, user_prompt)
    if not result:
        logger.error(f"AI 생성 실패: {keyword}")
        return None

    body = result if isinstance(result, str) else result.get("content", "")
    if not body or len(body) < 500:
        logger.error(f"생성 결과 너무 짧음: {keyword} ({len(body)}자)")
        return None

    # 제목 추출: 첫 번째 # 헤딩 또는 첫 줄
    title = ""
    for line in body.split("\n"):
        line = line.strip()
        if line.startswith("# "):
            title = line.lstrip("# ").strip()
            body = body.replace(line, "", 1).strip()
            break
    if not title:
        title = f"{keyword} 추천 TOP5 ({datetime.now().year}년)"

    # 쿠팡 고지 문구 확인 및 추가
    disclosure = "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."
    if disclosure not in body:
        body = body.rstrip() + f"\n\n---\n\n*{disclosure}*\n"

    # description: 본문 첫 2문장 추출
    desc_lines = []
    for line in body.split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("!") or line.startswith("["):
            continue
        desc_lines.append(line)
        if len("".join(desc_lines)) > 80:
            break
    description = " ".join(desc_lines)[:160]

    return {
        "title": title,
        "body_md": body,
        "keyword": keyword,
        "product_count": min(len(products), 5),
        "description": description,
    }
