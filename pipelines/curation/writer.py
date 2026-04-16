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


ADSENSE_AD = """<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-6677996696534146"
     crossorigin="anonymous"></script>
<!-- CUAP -->
<ins class="adsbygoogle"
     style="display:block"
     data-ad-client="ca-pub-6677996696534146"
     data-ad-slot="2195212287"
     data-ad-format="auto"
     data-full-width-responsive="true"></ins>
<script>
     (adsbygoogle = window.adsbygoogle || []).push({});
</script>"""

logger = logging.getLogger(__name__)

# -- 금지어 목록 및 검증 --

BLOG_EXTRA_RULES = {
    "laptop-hugo": """
[laptop-hugo 전용 규칙]
- 반드시 노트북 본체 상품만 소개할 것. 마우스, 웹캠, 헤드셋, 키보드, 태블릿, 캡쳐보드 등 주변기기는 절대 포함 금지.
- 스펙 표기 순서: CPU → RAM → SSD → 화면크기 → 무게 순으로 작성.
- 가격대별 분류: 50만원 미만(보급형) / 50~100만원(중급형) / 100만원 이상(고급형).
- 각 상품당 주요 스펙 수치를 반드시 명시할 것 (예: RAM 16GB, SSD 512GB).
""",
    "baby-hugo": """
[baby-hugo 전용 규칙]
- 반려동물(강아지, 고양이, 개모차 등) 관련 상품은 절대 포함 금지.
- 안전인증(KC인증, 친환경 소재 등) 정보를 반드시 언급할 것.
- 사용 연령대(신생아/0~6개월/6~12개월/12개월 이상 등)를 명시할 것.
- 부모 관점에서 실용성과 안전성을 중심으로 작성.
""",
}

BANNED_PHRASES = [
    "알아보겠습니다", "소개합니다", "소개해 드리겠습니다", "소개해드리겠습니다",
    "드립니다", "놓치지 마세요", "이번 포스팅에서는", "이번 글에서는",
    "살펴보겠습니다", "안내하겠습니다", "안내해 드리겠습니다",
    "확인해 보겠습니다", "비교해 보겠습니다", "추천해 드리겠습니다",
]

BANNED_REPLACEMENTS = {
    "알아보겠습니다": "정리했습니다",
    "소개합니다": "추천합니다",
    "소개해 드리겠습니다": "추천합니다",
    "소개해드리겠습니다": "추천합니다",
    "놓치지 마세요": "확인해 보세요",
    "이번 포스팅에서는": "",
    "이번 글에서는": "",
    "살펴보겠습니다": "비교했습니다",
    "안내하겠습니다": "정리했습니다",
    "안내해 드리겠습니다": "정리했습니다",
    "확인해 보겠습니다": "확인했습니다",
    "비교해 보겠습니다": "비교했습니다",
    "추천해 드리겠습니다": "추천합니다",
}


def _sanitize_body(body):
    """금지어 치환 + 스펙부족 메타문구 제거"""
    for phrase, replacement in BANNED_REPLACEMENTS.items():
        if phrase in body:
            body = body.replace(phrase, replacement)
    # 스펙 부족 메타문구 제거
    body = re.sub(r"[^\.]*스펙\s*정보가?\s*(?:부족|없|미상)[^\.]*\.?\s*", "", body)
    body = re.sub(r"[^\.]*무게\s*범위가?\s*불확실[^\.]*\.?\s*", "", body)
    # 빈 줄 정리
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()



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
        spec_str = "\n".join(spec_lines) if spec_lines else "  (상품명에서 스펙을 확인하세요)"

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


def _build_system_prompt(keyword, blog_id=None):
    year = datetime.now().year
    month = datetime.now().month
    extra = BLOG_EXTRA_RULES.get(blog_id or "", "")
    extra_block = f"\n\n{extra}" if extra else ""

    return f"""당신은 10년 경력의 상품 큐레이션 전문 블로거입니다.
{year}년 {month}월 기준 "{keyword}" 관련 추천 상품 글을 작성합니다.

[제목 규칙 — 가장 중요]
- 제목에 반드시 실제 제품명 또는 브랜드명을 1~2개 포함해야 합니다.
- 상품 데이터에서 가장 인기 있는 제품의 브랜드명/모델명을 추출하여 제목에 넣으세요.
- 좋은 제목 예시:
  * "1위 갤럭시북5 프로 vs LG그램 프로 — 사무용 노트북 {year} 비교"
  * "다이슨 V15 vs 삼성 비스포크 제트 — 무선청소기 실사용 리뷰"
- 핵심 키워드가 제목 앞 15자 이내에 위치해야 합니다.

[본문 구조]
1. **도입부 (2~3문장)**: 이 제품을 고를 때 겪는 구체적 고민. 공감하는 톤으로. "{year}년 {month}월 기준"을 명시하여 시의성 강조.

2. **선택 가이드 (H2)**: 
   - H2 소제목: "○○ 고를 때 확인할 포인트"
   - 핵심 선택 기준 3~4가지를 본문으로 서술 (예: 흡입력, 배터리, 무게, 소음)
   - 각 기준마다 구체적 수치 기준 제시 (예: "배터리는 최소 30분 이상이 기본입니다")
   - 최소 300자 이상.

3. **비교표 (H2) — 필수**:
   - H2 소제목: "한눈에 보는 비교표"
   - 상품 3~5개의 핵심 정보(가격, 주요 스펙 2~3개, 배송)를 마크다운 표로 정리
   - 예시:
     | 제품 | 가격 | CPU | RAM/SSD | 무게 |
     |---|---|---|---|---|
     | 레노버 아이디어패드 | 186만원 | 라이젠 AI | 16GB/1TB | 1.6kg |
     | MSI 게이밍노트북 소드 | 214만원 | 라이젠7 + RTX4060 | 32GB/1TB | 2.7kg |

4. **상품 5개 각각 소개 (각 H2)**:
   - H2 소제목 형식: "순위+브랜드+한줄요약" (예: "1위: 레노버 아이디어패드 — 가성비 최강 라이젠 AI")
   - 소개 시작에 상품 이미지: ![상품명](이미지URL)
   - 핵심 스펙을 구체적 수치로 표기
   - 가격, 배송정보를 자연스럽게 포함
   - **장점 1~2가지 + 아쉬운 점 1가지** 반드시 포함
   - **추천 대상 페르소나 명시** (예: "대학생 과제/영상편집용으로 적합", "FPS/배그 고사양 게임 유저에게 추천")
   - 사회적 증거 문구 포함 (예: "로켓배송으로 하루만에 받을 수 있어 구매 만족도가 높은 제품입니다")
   - 소개 끝에 링크: [쿠팡에서 최저가 확인하기](상품링크)

5. **FAQ 섹션 (H2) — 필수**:
   - H2 소제목: "자주 묻는 질문"
   - 구매 전 궁금한 질문 3~5개를 H3 (###)로 배치
   - 각 질문에 2~3문장 답변
   - 예: "### SSD 1TB면 충분한가요?" → "일반 업무와 영상 시청용으로는 충분합니다. 다만 게임이나 영상편집을 자주 한다면 외장 SSD 추가를 권장합니다."

6. **정리 (H2)**:
   - H2 소제목: "상황별 추천 정리"
   - 페르소나별 구체적 추천: "가성비 중시 직장인은 ○○, 게이밍 유저는 ○○, 휴대성 중시는 ○○"
   - 행동 유도(CTA): "로켓배송으로 빠르게 받고 싶다면 ○○, 최저가 할인 혜택은 ○○에서 확인하세요"
   - "마무리", "결론" 소제목 금지.

[문체 규칙]
- "~입니다/~습니다" 체로 통일
- 글 마지막에 반드시 포함: "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."

[스펙 서술 규칙 — 매우 중요]
- "확인된 스펙"에 있는 수치만 본문에 사용하세요.
- 스펙 정보가 없는 항목은 추측하거나 지어내지 마세요.
- "뛰어난 성능", "강력한 흡입력" 같은 추상적 표현 대신, 스펙 수치가 있으면 수치를 쓰고 없으면 해당 항목을 언급하지 마세요.
- 브랜드 정보가 있으면 제목과 본문에 적극 활용하세요.

[절대 금지]
- "알아보겠습니다", "소개합니다", "소개해 드리겠습니다", "드립니다", "놓치지 마세요"
- "마무리", "결론" 소제목
- 취소선(~~), 이모지, 【】, ★, ♥ 등 특수 장식 문자
- "이번 포스팅에서는", "이번 글에서는" 표현
- "스펙 정보가 부족", "스펙 정보가 없", "무게 범위가 불확실" 등 메타 문구
- "아쉬운 점: 스펙 정보가 부족" 같은 스펙 미상 언급. 모르면 해당 항목을 생략할 것

[상품 필터 규칙 — 반드시 준수]
- 키워드와 명백히 무관한 상품은 소개하지 마세요.
- 제외 후 남은 상품이 3개 미만이면 남은 상품만으로 작성하세요.
- 같은 브랜드의 색상만 다른 동일 제품은 하나만 소개하세요.

[글자수]
- 총 2500~3500자 (한글 기준). 비교표/FAQ 추가로 기존 대비 확대.
- 각 상품 소개는 최소 150자 이상.
- 선택 가이드는 최소 300자 이상.
- FAQ 섹션은 최소 400자 이상.
- 전체 글이 2500자 미만이면 절대 안 됩니다.{extra_block}"""


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



def _insert_adsense(body):
    """본문에 애드센스 광고 2개 삽입: 첫 문단 직후 + 두 번째 H2 아래
    
    구조: 도입문단 → [광고1] → ## 구매포인트(내용) → ## 첫상품 → [광고2] → 나머지
    두 광고 사이에 반드시 H2 섹션 내용이 들어가도록 분리.
    """
    lines = body.split("\n")
    result = []
    ad_inserted = {"top": False, "h2": False}
    h2_count = 0

    for i, line in enumerate(lines):
        result.append(line)

        # 첫 번째 광고: 첫 문단(비어있지 않은 줄) 직후
        if not ad_inserted["top"] and line.strip() and not line.startswith("#"):
            if i + 1 < len(lines) and (not lines[i + 1].strip() or lines[i + 1].startswith("#")):
                result.append("\n" + ADSENSE_AD.strip() + "\n")
                ad_inserted["top"] = True

        # H2 카운트
        if line.startswith("## "):
            h2_count += 1

        # 두 번째 광고: 두 번째 H2 아래 (첫 상품 섹션 직후 한 단락 삽입)
        if not ad_inserted["h2"] and h2_count == 2 and line.startswith("## "):
            result.append("\n" + ADSENSE_AD.strip() + "\n")
            ad_inserted["h2"] = True

    return "\n".join(result)


def generate_curation_article(keyword, products, blog_id=None):
    """키워드 + 상품 5개 → 큐레이션 글 생성, dict 반환"""
    if not products or len(products) < 3:
        logger.warning(f"상품 부족: {keyword} ({len(products) if products else 0}개)")
        return None

    product_block = _build_product_block(products[:5])
    system_prompt = _build_system_prompt(keyword, blog_id=blog_id)
    user_prompt = _build_user_prompt(keyword, product_block)

    # 글자수 미달 시 최대 2회 시도
    body = ""
    for attempt in range(2):
        result = ai_generate(system_prompt, user_prompt)
        if not result:
            logger.error(f"AI 생성 실패 (시도 {attempt+1}): {keyword}")
            continue

        body = result if isinstance(result, str) else result.get("content", "")
        if not body:
            continue

        # 금지어 치환 + 메타문구 제거
        body = _sanitize_body(body)

        if len(body) >= 1800:
            break
        logger.warning(f"글자수 미달 (시도 {attempt+1}): {keyword} ({len(body)}자)")

    if not body or len(body) < 800:
        logger.error(f"최종 생성 결과 부족: {keyword} ({len(body)}자)")
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

    # 애드센스 광고 삽입
    body = _insert_adsense(body)

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
