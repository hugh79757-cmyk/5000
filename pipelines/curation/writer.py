"""상품 데이터 → AI 큐레이션 글 생성

상품 5개 데이터를 받아 "TOP5 추천" 형태의 블로그 글을 생성.
각 상품에 어필리에이트 링크 포함.
"""
import logging
import os
import re
import sqlite3
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.ai_writer import generate as ai_generate
from shared.title_templates import TitleTemplatePicker

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

_tt_picker = TitleTemplatePicker()

# -- 금지어 목록 및 검증 --

BLOG_EXTRA_RULES = {
    "laptop-hugo": """
[laptop-hugo 전용 규칙]
- 반드시 노트북 본체 상품만 소개할 것. 마우스, 웹캠, 헤드셋, 키보드, 태블릿, 캡쳐보드 등 주변기기는 절대 포함 금지.
- 스펙 표기 순서: CPU → RAM → SSD → 화면크기 → 무게 순으로 작성.
- 가격대별 분류: 50만원 미만(보급형) / 50~100만원(중급형) / 100만원 이상(고급형).
- 각 상품당 주요 스펙 수치를 반드시 명시할 것 (예: RAM 16GB, SSD 512GB).
- 페르소나는 반드시 구체적인 생활 장면으로 서술. 예: "매일 강의실과 도서관을 오가는 대학생이라면 1.4kg 무게가 큰 장점입니다", "퇴근 후 집에서 영상편집을 시작한 직장인에게 RTX4060은 충분한 성능입니다".
- "추천 대상:", "페르소나:" 같은 라벨 표기 절대 금지.
- 리뷰 점수, 판매량 수치는 상품 데이터에 있는 경우에만 사용. 없으면 절대 지어내지 말 것.
""",
    "baby-hugo": """
[baby-hugo 전용 규칙]
- 반려동물(강아지, 고양이, 개모차 등) 관련 상품은 절대 포함 금지.
- 안전인증(KC인증, 친환경 소재 등) 정보가 상품 데이터에 있으면 반드시 언급할 것.
- 사용 연령대(신생아/0~6개월/6~12개월/12개월 이상 등)를 명시할 것.
- 부모 관점에서 실용성과 안전성을 중심으로 작성.
- 페르소나는 반드시 구체적인 생활 장면으로 서술. 예: "출산 후 3개월, 수유 텀이 불규칙한 엄마", "둘째를 임신 중인 엄마가 첫째 때 못 써본 제품을 고르는 상황".
- "추천 대상:", "페르소나:" 같은 라벨 표기 절대 금지.
- 리뷰 점수, 판매량 수치는 상품 데이터에 있는 경우에만 사용. 없으면 절대 지어내지 말 것.
""",
    "appliance-hugo": """
[appliance-hugo 전용 규칙]
- 가전제품 스펙(흡입력, 소음, 배터리, 용량 등)을 수치로 명시할 것. 데이터에 없으면 생략.
- 페르소나는 반드시 구체적인 생활 장면으로 서술. 예: "반려견 두 마리와 함께 사는 원룸 자취생", "맞벌이라 주말에만 청소하는 30평 아파트 가정".
- "추천 대상:", "페르소나:" 같은 라벨 표기 절대 금지.
- 리뷰 점수, 판매량 수치는 상품 데이터에 있는 경우에만 사용. 없으면 절대 지어내지 말 것.
""",
    "interior-hugo": """
[interior-hugo 전용 규칙]
- 가구/인테리어 소품 위주로 작성.
- 비교표에 반드시 크기(cm), 소재, 색상 옵션 수 컬럼을 포함할 것. 상품 데이터에 수치 없으면 해당 셀 "-"로 표기.
- 각 상품 소개에 가로×세로×높이(cm) 치수를 명시할 것. 상품 데이터에 없으면 치수 언급 생략.
- 로켓배송 상품이 없는 경우 CTA에서 로켓배송 언급 절대 금지. 대신 "설치 서비스 포함 여부를 확인하세요" 또는 "배송 전 사이즈 재측정을 권장합니다"로 대체.
- 페르소나는 반드시 구체적인 생활 장면으로 서술. "신혼부부" 대신 "이사 후 거실 가구를 처음 맞추는 신혼부부", "자취생" 대신 "원룸 12평에 소파와 TV장을 함께 배치해야 하는 자취생"처럼 공간 크기와 상황을 구체화.
- "추천 대상:", "페르소나:" 같은 라벨 표기 절대 금지.
- 리뷰 점수, 판매량 수치는 상품 데이터에 있는 경우에만 사용. 없으면 절대 지어내지 말 것.
""",
    "health-hugo": """
[health-hugo 전용 규칙]
- 각 상품 소개에 주요 성분명과 함량(mg/mcg/IU)을 명시할 것.
- 복용 대상(연령, 성별, 건강 상태)을 구체적인 생활 장면으로 서술할 것.
- 섭취 방법(1일 몇 회, 몇 정)을 반드시 포함할 것.
- 비교표에 반드시 주요 성분, 함량, 캡슐/정 수, 가격 컬럼을 포함할 것.
- 효능 과장 문구 절대 금지. "도움이 될 수 있습니다" 수준의 표현 사용.
- 로켓배송 상품이 없는 경우 CTA에서 로켓배송 언급 금지.
""",
    "pet-hugo": """
[pet-hugo 전용 규칙]
- 각 상품 소개에 적합 동물(강아지/고양이), 적합 체중/연령을 명시할 것.
- 구체적인 반려동물 생활 장면으로 추천 서술.
  예: "산책을 싫어하는 소형견이라면 실내 노즈워크 매트가 운동 부족을 해결해줍니다"
- 비교표에 반드시 적합 동물, 적합 체중, 소재/성분, 가격 컬럼을 포함할 것.
- 로켓배송 상품이 없는 경우 CTA에서 로켓배송 언급 금지.
""",
    "kitchen-hugo": """
[kitchen-hugo 전용 규칙]
- 각 상품 소개에 용량(L) 또는 크기(cm), 소재, 호환 열원(가스/인덕션/전기)을 명시할 것.
- 비교표에 반드시 용량/크기, 소재, 호환 열원, 가격 컬럼을 포함할 것.
- 구체적인 요리/주방 생활 장면으로 추천 서술.
  예: "주 3회 이상 국을 끓이는 4인 가족이라면 스테인리스 편수냄비 22cm가 적합합니다"
- 로켓배송 상품이 없는 경우 CTA에서 로켓배송 언급 금지.
""",
    "beauty-hugo": """
[beauty-hugo 전용 규칙]
- 각 상품 소개에 피부 타입(건성/지성/복합성/민감성) 적합도를 명시할 것.
- 주요 성분명을 자연스러운 문장으로 녹여 서술할 것.
- 비교표에 반드시 피부 타입, 주요 성분, 용량(ml/g), 가격 컬럼을 포함할 것.
- 구체적인 뷰티 루틴 장면으로 추천 서술.
  예: "출근 전 5분 루틴을 원하는 직장인이라면 올인원 수분크림이 단계를 줄여줍니다"
- 로켓배송 상품이 없는 경우 CTA에서 로켓배송 언급 금지.
""",
    "camping-hugo": """
[camping-hugo 전용 규칙]
- 각 상품 소개에 무게(kg/g), 펼쳤을 때 크기(cm), 수납 크기(cm)를 명시할 것.
- 비교표에 반드시 무게, 펼침 크기, 수납 크기, 소재, 가격 컬럼을 포함할 것.
- 캠핑 스타일(오토캠핑/백패킹/글램핑)별 추천을 구분하여 서술할 것.
  예: "백패킹 입문자라면 700g 이하 침낭이 체력 부담을 줄여줍니다"
- 계절 적합성(3계절/4계절)을 명시할 것.
- 로켓배송 상품이 없는 경우 CTA에서 로켓배송 언급 금지.
""",
    "fitness-hugo": """
[fitness-hugo 전용 규칙]
- 운동기구/피트니스 기구만 소개. 의류(타이즈, 장갑, 가방 포함), 영양제, 식품은 절대 포함 금지.
- 하중(kg), 크기(cm), 접이 여부, 소음 수준 등 실용 스펙을 수치로 명시할 것. 데이터에 없으면 생략.
- 페르소나는 반드시 구체적인 생활 장면으로 서술. 예: "퇴근 후 30분 홈트를 하는 직장인", "층간소음 걱정에 쿠션 운동만 하던 30대 주부", "무릎 재활 중이라 저충격 운동이 필요한 40대".
- "추천 대상:", "페르소나:" 같은 라벨 표기 절대 금지.
- 리뷰 점수, 판매량 수치는 상품 데이터에 있는 경우에만 사용. 없으면 절대 지어내지 말 것.
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


def _fix_repeated_image_urls(body_md):
    """Detect and fix image URLs with token repetition patterns (LLM stutter).

    LLMs sometimes repeat trailing tokens in image URLs (e.g.,
    'gLozv0gLozv0gLozv0gLozv0...'). This function detects such repetition
    and strips all repeating content from the URL.

    Detection: substring of length 4+ repeating 5+ times consecutively.
    """
    if not body_md:
        return body_md

    def _has_repeated_pattern(url, min_repeat_len=4, min_repeats=5):
        url_str = url.rstrip("/")
        url_len = len(url_str)
        for sub_len in range(min_repeat_len, min(50, url_len // min_repeats + 1)):
            for start in range(url_len - sub_len * min_repeats + 1):
                sub = url_str[start:start + sub_len]
                count = 0
                pos = start
                while pos + sub_len <= url_len and url_str[pos:pos + sub_len] == sub:
                    count += 1
                    pos += sub_len
                if count >= min_repeats:
                    return sub, count, start
        return None

    def _fix_url(match):
        alt, url = match.group(1), match.group(2)
        result = _has_repeated_pattern(url)
        if result:
            sub, count, pos = result
            clean_url = url[:pos]
            logger.warning(
                f"[URL-REPEAT] Image URL has repeated pattern '{sub}' x{count} "
                f"({len(url)} chars → {len(clean_url)} chars): "
                f"{url[:80]}... → {clean_url[:80]}..."
            )
            return f"![{alt}]({clean_url})"
        return match.group(0)

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", _fix_url, body_md)


def _sanitize_body(body):
    """금지어 치환 + 스펙부족 메타문구 제거 + URL 토큰 반복 수정"""
    # ── URL 토큰 반복(repetition) 버그 수정: LLM이 생성한 비정상 URL 정리 ──
    body = _fix_repeated_image_urls(body)
    for phrase, replacement in BANNED_REPLACEMENTS.items():
        if phrase in body:
            body = body.replace(phrase, replacement)
    # 스펙 부족 메타문구 제거
    body = re.sub(r"[^\.]*스펙\s*정보가?\s*(?:부족|없|미상)[^\.]*\.?\s*", "", body)
    body = re.sub(r"[^\.]*무게\s*범위가?\s*불확실[^\.]*\.?\s*", "", body)
    # ### ### H3 중복 마커 수정
    body = re.sub(r"^#{3,}\s*#{3,}\s*", "### ", body, flags=re.MULTILINE)
    # 라벨 노출 제거
    body = re.sub(r"[-*]*\s*사회적\s*증거\s*[:：]\s*", "", body)
    body = re.sub(r"[-*]*\s*구매\s*포인트\s*[:：]\s*", "", body)
    # "만족도가 높은" 반복 제거
    body = re.sub(r"[^.\n]*만족도가\s*높[은다][^.\n]*\.?\s*", "", body)
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
            f"- 네이버최저가: {p.get('naver_lprice', '')}원\n"
        )
    return "\n".join(lines)


def _build_system_prompt(keyword, blog_id=None, style_hint="", recent_titles=None) -> str:
    year = datetime.now().year
    month = datetime.now().month
    extra = BLOG_EXTRA_RULES.get(blog_id or "", "")
    extra_block = f"\n\n{extra}" if extra else ""

    # 최근 발행 제목 목록을 프롬프트에 주입 (유사 제목 방지)
    recent_block = ""
    if recent_titles:
        recent_block = "\n[피해야 할 제목 — 최근 발행된 글]"
        for rt in recent_titles[-3:]:
            recent_block += f"\n- {rt.strip()[:60]}"
        recent_block += "\n위 제목들과 구조, 표현, 어조가 완전히 다르게 작성하세요.\n"

    extra_title_rules = ""
    if style_hint:
        extra_title_rules = f"""
[이번 발행 제목 스타일]
이번 글의 제목 스타일: {style_hint}
참고용이며 정확히 따를 필요는 없지만, 최근 발행된 글들과 다른 구조로 작성해주세요.

최근 3일 내 발행된 글과 중복되는 제목 구조는 피해주세요. 특히 '1위 X vs Y — ... 비교' 구조는 반복 사용하지 마세요.
제목에 "가성비"라는 단어를 사용하지 마세요. 대신 "합격점", "실속", "가격 대비" 등의 표현을 사용하세요.
"""

    return f"""당신은 10년 경력의 상품 큐레이션 전문 블로거입니다. 반드시 한국어로 작성하세요. 중국어나 다른 언어로 작성하지 마세요.
{year}년 {month}월 기준 "{keyword}" 관련 추천 상품 글을 작성합니다.

[제목 규칙 — 가장 중요]
제목은 반드시 아래 패턴 중 하나를 따라야 합니다:

1. [연도]년 [월]월 [제품명] 추천 — [구체적 혜택/특징]
   예: "2026년 7월 립밤 추천 리엔케이·바세린 — 하루 종일 촉촉한 선택"

2. [제품A] vs [제품B] — [비교 포인트]
   예: "헤라 블랙 쿠션 vs 샵한현재 마스터 핏 — 커버력 비교"

3. [제품명] [체험형 후기] — [공감대]
   예: "센카 퍼펙트 휩 3주 사용 후기 — 여드름 피부에게 딱 맞는 폼클렌저"

4. [대상]을 위한 [제품 유형] 총정리 — [가격대/혜택]
   예: "민감성 피부를 위한 클렌저 총정리 — 1만원대 합격 TOP 5"

[제목 필수 요소]
- 제품명 또는 브랜드명 1~2개 포함
- "추천", "후기", "비교", "총정리" 중 1개 포함
- 구체적 수치 또는 혜택 포함 (예: "1만원대", "3주 사용", "TOP 5")
- "가성비" 사용 금지 → "합격점", "실속", "가격 대비" 사용
- 핵심 키워드가 제목 앞 15자 이내에 위치해야 합니다.
- 제목 길이는 25~55자로 작성하세요 (공백 포함). 65자를 초과하지 않아야 합니다.
- 짧은 제목(25자 미만)은 구체성이 부족해 보일 수 있습니다.
- 긴 제목(55자 초과)은 모바일 화면에서 잘리고 SEO 키워드가 분산됩니다.
{extra_title_rules}{recent_block}

[퍼널 구조 — AIDA 모델 적용]
이 글은 단순 상품 나열이 아닌, 독자의 구매 여정을 설계하는 퍨널 글입니다.

1. **도입부 — Attention (주의) (2~3문장)**:
   - 독자가 "나도 이런 고민을 했는데?" 라고 느끼는 구체적 상황 제시
   - "{year}년 {month}월 기준"을 명시하여 시의성 강조
   - 공감대 형성 후 자연스럽게 선택 가이드로 연결

2. **선택 가이드 — Interest (관심) (H2)**:
   - H2 소제목: "○○ 고를 때 확인할 포인트"
   - 핵심 선택 기준 3~4가지를 본문으로 서술 (예: 흡입력, 배터리, 무게, 소음)
   - 각 기준마다 구체적 수치 기준 제시 (예: "배터리는 최소 30분 이상이 기본입니다")
   - "이 기준으로 비교하면 어떤 제품이 좋을지" 자연스럽게 유도
   - 최소 300자 이상.

3. **비교표 — Desire (욕구 유도) (H2) — 필수**:
   - H2 소제목: "한눈에 보는 비교표"
   - 상품 3~5개의 핵심 정보(가격, 주요 스펙 2~3개, 배송)를 마크다운 표로 정리
   - 비교표를 보고 "이 중에서 골라야겠다"는 생각이 들도록 작성
   - 예시:
     | 제품 | 가격 | CPU | RAM/SSD | 무게 |
     |---|---|---|---|---|
     | 레노버 아이디어패드 | 186만원 | 라이젠 AI | 16GB/1TB | 1.6kg |
     | MSI 게이밍노트북 소드 | 214만원 | 라이젠7 + RTX4060 | 32GB/1TB | 2.7kg |

4. **상품 각각 소개 — Desire (욕구 강화) (각 H2, 제공된 상품 수만큼)**:
   - H2 소제목 형식: "순위+브랜드+한줄요약" (예: "1위: 레노버 아이디어패드 — 가성비 최강 라이젠 AI")
   - 소개 시작에 상품 이미지: ![상품명](이미지URL)
   - 핵심 스펙을 구체적 수치로 표기
   - 가격, 배송정보를 자연스럽게 포함
   - **장점 1~2가지 + 아쉬운 점 1가지** 반드시 포함
   - 이 제품이 어떤 상황의 사람에게 딱 맞는지 구체적인 생활 장면으로 서술할 것. (예: "매일 강의실과 도서관을 오가는 대학생이라면 1.4kg 무게가 큰 장점입니다", "퇴근 후 유튜브 편집까지 하는 직장인에게 RTX4060은 충분한 성능입니다"). "추천 대상:", "페르소나:" 같은 라벨 표기 절대 금지. 자연스러운 문장으로 녹여낼 것.
   - 마지막에 실질 구매 정보 1~2줄 추가. 로켓배송 여부, 구매자 반응(예: "리뷰 4.8점", "누적 판매 1만건+" 등 상품 데이터에 있는 경우만 활용), 적정 연령, 구성품 단가 중 해당되는 것을 자연스러운 문장으로 녹여낼 것. 라벨 표기 절대 금지. 근거 없는 수치 지어내기 금지.
   - 소개 끝에 링크: [쿠팡에서 최저가 확인하기](상품링크)

5. **FAQ 섹션 — Trust (신뢰 구축) (H2) — 필수**:
   - H2 소제목: "자주 묻는 질문"
   - 구매 전 망설임을 해소하는 질문 3~5개를 H3 (###)로 배치
   - 각 질문에 2~3문장 답변
   - "배송은 얼마나 걸리나요?", "AS는 되나요?", "실제 사용해보니 어떤가요?" 같은 실제 구매 고민으로 작성
   - 각 질문은 H3(### )로 시작. 마커 ###는 줄 시작에 한 번만 사용 (### ###처럼 중복 금지)

6. **상황별 추천 — Action (행동 유도) (H2)**:
   - H2 소제목: "상황별 추천 정리"
   - 구체적인 생활 장면 기반으로 추천. "초보 부모" 대신 "출산 후 3개월, 수유 텀이 불규칙한 엄마", "대학생" 대신 "전공 수업 PPT와 과제를 동시에 띄워놓는 공대생" 처럼 실제 상황을 묘사할 것. "가성비 중시" 같은 범용 문구 반복 금지.
   - 각 상황에 맞는 제품을 선정하고, 왜 이 제품인지 1문장으로 이유 제시
   - 행동 유도(CTA): "지금 쿠팡에서 특가로 만나보세요" 또는 "아래 링크에서 바로 확인하세요" 같은 행동 유도 문구 포함
   - 소개한 상품 중 로켓배송 상품이 1개 이상 있을 때만 "로켓배송 표기 제품을 우선 고려하세요" 문구 사용. 로켓배송 상품이 없으면 해당 문구 사용 금지.
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


def _build_user_prompt(keyword, product_block, price_range="") -> str:
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

    price_line = f"\n상품 가격대: {price_range}" if price_range else ""

    return f"""키워드: {keyword}
주요 브랜드/모델: {brand_hint_str}{price_line}

위 브랜드/모델명 중 1~2개를 반드시 제목에 포함하세요.
아래 상품 데이터를 기반으로 추천 큐레이션 글을 작성해주세요. 제공된 상품 수만큼만 소개하세요.
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

    # 제목 스타일 다양화 — 템플릿 기반 선택
    template_type = None
    style_hint = ""
    price_range_str = ""
    try:
        recent_styles = _tt_picker.get_recent_styles(blog_id) if blog_id else []
        template_type = _tt_picker.pick(used_templates=recent_styles)

        # 상품 데이터에서 브랜드/가격대 추출
        brand_data = {}
        if products:
            brands = []
            for p in products[:3]:
                b = p.get("brand", "") or p.get("maker", "") or ""
                if b and b not in brands:
                    brands.append(b)
            for i, b in enumerate(brands, 1):
                brand_data[f"brand{i}"] = b

            prices = [p.get("product_price", 0) or 0 for p in products[:5]]
            valid_prices = [p for p in prices if p > 0]
            if valid_prices:
                min_p = min(valid_prices)
                max_p = max(valid_prices)
                price_range_str = f"{min_p:,}원 ~ {max_p:,}원"
                brand_data["price_range"] = f"{min_p // 10000}~{max_p // 10000}"

        style_hint = _tt_picker.render(template_type, brand_data, keyword)
        logger.info("[title_template] 선택: %s → %s…", template_type, style_hint[:60])
    except Exception as e:
        logger.warning("[title_template] 스타일 선택 오류: %s", e)

    # 최근 발행 제목 수집 (유사 제목 방지용 프롬프트 주입)
    recent_titles = []
    if blog_id:
        try:
            _curation_db = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "data", "curation.db")
            _cn = sqlite3.connect(str(_curation_db))
            _rows = _cn.execute(
                "SELECT title FROM publish_log WHERE blog_id=? AND published_at > datetime('now', '-3 days') ORDER BY published_at DESC",
                (blog_id,),
            ).fetchall()
            _cn.close()
            recent_titles = [r[0] for r in _rows if r[0]]
        except Exception as _e:
            logger.warning(f"[recent_titles] 수집 실패: {_e}")

    system_prompt = _build_system_prompt(keyword, blog_id=blog_id, style_hint=style_hint, recent_titles=recent_titles)
    user_prompt = _build_user_prompt(keyword, product_block, price_range=price_range_str)

    # 글자수 미달 시 최대 2회 시도
    body = ""
    for attempt in range(2):
        result = ai_generate(system_prompt, user_prompt, temperature=0.85)
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
    if template_type:
        logger.info("[title_template] 사용됨: %s (제목: %s…)", template_type, title[:50])

    # 쿠팡 고지 문구 확인 및 추가
    disclosure = "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."
    if disclosure not in body:
        body = body.rstrip() + f"\n\n---\n\n*{disclosure}*\n"

    # 애드센스 광고 삽입 (single.html 템플릿에서 처리 — 본문 raw HTML 삽입 시 Hugo 빌드 오류)
    # body = _insert_adsense(body)

    # description: 본문 첫 2문장 추출
    desc_lines = []
    for line in body.split("\n"):
        line = line.strip()
        if not line or line.startswith(("#", "!", "[")):
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
