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
from shared.validators import has_cjk
from shared.title_templates import TitleTemplatePicker

try:
    from pipelines.etap.editorial_synthesis import editorial_synthesis_step
except ImportError:
    editorial_synthesis_step = None


def _inject_editorial_synthesis(body, topic=None):
    """Phase 70 Wave 3: append deterministic editorial synthesis paragraph.

    No-op unless the topic carries a recognized ``topic_type`` (graceful
    degradation — returns body unchanged when no unique data resolves).
    """
    if not body or editorial_synthesis_step is None:
        return body
    try:
        from pipelines.etap.data_adapters import get_unique_data_points
        _t = topic or {}
        _tt = _t.get("topic_type")
        _ud = get_unique_data_points(_tt, _t.get("topic_id")) if _tt else []
        _s = editorial_synthesis_step(body, _ud, _t)
    except Exception as _e:
        logger.warning("[editorial] synthesis skipped: %s", _e)
        return body
    if not _s:
        return body
    return body.rstrip() + "\n\n" + _s + "\n"

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
- 로켓배송 상품이 없는 경우 CTA에서 로켓배송 언급 금지.
[국내 표시광고 규칙 준수 — 건강기능식품 효능 표현]
- 질병의 치료·예방·개선을 단정하는 표현 절대 금지.
  금지 예시: "혈액 순환에 도움을 줍니다", "기억력이 향상됩니다", "면역력이 강화됩니다",
  "혈행 개선에 좋습니다", "스트레스 완화에 효과적입니다", "피부에 탄력을 더해줍니다"
- 허용 표현 수준: "식약처 인증 원료를 함유하고 있습니다", "주요 성분 OOO를 포함하고 있습니다",
  "XX에 관심 있는 분들에게 적합한 제품입니다", "성분표를 확인하여 본인에게 맞는 제품을 선택하세요"
- 건강기능식품 관련 표현은 반드시 "식약처 인증", "기능성 원료" 등 인증 기반 표현만 사용.
- 의학적 효과 단정, 신체 기능 개선 약속, 질병 관련 표현 일절 금지.
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
[국내 표시광고 규칙 준수 — 화장품 효능 표현]
- 화장품은 의약품이 아니므로 효능·효과를 단정하는 표현 절대 금지.
  금지 예시: "피부를 환하게 정돈해 줍니다", "피부에 탄력을 더해줍니다",
  "활력을 더하고", "수분을 공급해 피부가 개선됩니다", "피부가 좋아집니다"
- 허용 표현 수준: "OO 성분을 함유하고 있습니다", "피부 타입에 따른 선택이 가능합니다",
  "성분표를 확인하여 본인 피부에 맞는 제품을 선택하세요",
  "사용감(질감, 흡수력)에 대한 설명은 가능하나 효과 단정은 금지"
- 화장품 관련 표현은 성분 함량, 사용감, 질감 묘사 위주로 작성.
- 피부 개선·탄력·환기·활력 등 효과 약속 표현 일절 금지.
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

# ── Q5: global_forbidden_words (config/quality_checklist.yaml) ──
# 주관적·광고성 표현 중립어 치환 맵. YAML 단어 → 대체 표현 (치환 없으면 삭제).
# YAML에 단어가 추가/삭제되면 GLOBAL_FORBIDDEN_WORDS가 따라가므로 dead config 해소.
_FORBIDDEN_WORD_REPLACEMENTS = {
    "추천드립니다": "추천합니다",
    "인기가 많습니다": "널리 이용되고 있습니다",
    "맛있는": "",
    "좋은": "적합한",
    "훌륭한": "뛰어난",
    "최고의": "가장 적합한",
}


def _load_global_forbidden_words():
    """config/quality_checklist.yaml의 global_forbidden_words 로딩 (Q5).

    fail-open: 파일 없음/파싱 오류 시 빈 목록 + 경고 로그. 금지어 필터만
    미동작하며 발행 자체는 차단하지 않음 (기존 BANNED_REPLACEMENTS 동작 불변).
    """
    import yaml
    cfg_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "config", "quality_checklist.yaml",
    )
    try:
        with open(cfg_path, encoding="utf-8") as _f:
            cfg = yaml.safe_load(_f) or {}
        words = ((cfg.get("global_criteria") or {}).get("global_forbidden_words")) or []
        words = [w for w in words if isinstance(w, str) and w.strip()]
        logger.info("[Q5] global_forbidden_words 로딩: %d개 %s", len(words), words)
        return words
    except Exception as _e:
        logger.warning("[Q5] quality_checklist.yaml 로딩 실패 — 금지어 필터 미적용: %s", _e)
        return []


GLOBAL_FORBIDDEN_WORDS = _load_global_forbidden_words()


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
    """금지어 치환 + 스펙부족 메타문구 제거 + URL 토큰 반복 수정 + CoT/프롬프트 지시문 필터"""
    # ── URL 토큰 반복(repetition) 버그 수정: LLM이 생성한 비정상 URL 정리 ──
    body = _fix_repeated_image_urls(body)
    for phrase, replacement in BANNED_REPLACEMENTS.items():
        if phrase in body:
            body = body.replace(phrase, replacement)
    # ── Q5: global_forbidden_words 필터 (quality_checklist.yaml 로딩, 중립어 치환) ──
    for _word in GLOBAL_FORBIDDEN_WORDS:
        _replacement = _FORBIDDEN_WORD_REPLACEMENTS.get(_word, "")
        body = body.replace(_word, _replacement)
    body = re.sub(r" {2,}", " ", body)  # 삭제 치환("" ) 잔여 공백 정리
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
    # ── CoT/프롬프트 지시문 필터 (작성 계획 접두사만 매치, 정상 리뷰 표현 보존) ──
    # 작성 계획/사고 과정 문구 제거
    cot_patterns = [
        r"^우선\s.*$",
        r".*사용자\s*요청.*$",
        r"^제목\s*규칙.*$",
        r"^제목\s*예시.*$",
        r"^제품\s*데이터를\s*살펴보면.*$",
        r"^이제\s*글의\s*구조를\s*생각해보자.*$",
        r"^이제\s*글을\s*작성해?보자.*$",
        r"^순위를\s*매겨보자.*$",
        r"^가격을\s*비교해보자.*$",
        r"^이제\s*작성\s*시작하?겠다.*$",
        r"^이제\s*서론에서\s*제품\s*나열을\s*시작하자.*$",
    ]
    for pat in cot_patterns:
        body = re.sub(pat, "", body, flags=re.MULTILINE)
    # 빈 줄 정리
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()


def _count_h2(body):
    """본문의 H2 (## ) 헤딩 개수 — Q6 H2>=1 가드용.

    `### `(H3) 이상은 매치하지 않음 (`^##\\s`는 `##` 바로 뒤에 공백/탭만 허용).
    """
    if not body:
        return 0
    return len(re.findall(r"^##\s", body, flags=re.MULTILINE))



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

3. [대상]을 위한 [제품 유형] — [가격대/혜택]
   예: "민감성 피부를 위한 클렌저 — 1만원대 합격 TOP 5"

[제목 필수 요소]
- 제품명 또는 브랜드명 1~2개 포함
- "가성비" 사용 금지 → "합격점", "실속", "가격 대비" 사용
- 핵심 키워드가 제목 앞 15자 이내에 위치해야 합니다.
- 제목 길이는 35자 이내로 작성하세요 (공백 포함).
- "{keyword} 추천 TOP5 (연도년)" 같은 통짜 포맷은 사용하지 마세요. 구체적 제품명·브랜드·혜택을 제목에 직접 넣으세요.
- **검색니즈 키워드 필수**: 사람들이 실제 검색하는 구체적 단어(제품 특성·용도·대상)를 최소 1개 반드시 포함하세요.
  예: 프라이팬 → "인덕션", "코팅 오래가는"; 선풍기 → "저소음", "BLDC"; 안마의자 → "가정용", "무중력"
- **추상·감성 수식어 금지**: "요리 즐거움을 더하는", "실속 있는 선택", "행복한 일상" 같은 검색 유입이 안 되는 추상 표현은 사용하지 마세요.
- **뻔한 어미 금지**: "추천 가이드", "선택 가이드", "구매 가이드", "고르는 법", "총정리", "선택지 N종"으로 끝내지 마세요. 어미는 매번 다르게 작성하세요.
- **괄호 () 절대 금지**: 괄호 대신 하이픈(-)을 사용하세요. 구분이 필요하면 "제품A - 제품B" 형태로 작성.
- 좋은 예: "인덕션 프라이팬 코팅 오래가는 TOP 5 - 삼성"
- 좋은 예: "저소음 BLDC 선풍기 추천 - 가정용 에어컨 대안"
- 나쁜 예: "2026년 인덕션 프라이팬 추천 가이드 (베스트 5)" ← 괄호 + 뻔한 어미
- 나쁜 예: "민감성 피부 클렌저 총정리 (선택지 3종)" ← 괄호 + 뻔한 어미

[제목 다양화 — 필수]
아래 관점 중 최소 1개를 제목에 녹여 매번 다른 구조를 만드세요:
- 사용 상황/목적 (예: "1인가구", "첫 살 때", "이사 후", "선물용")
- 비교 대상 전환 (브랜드 vs 브랜드, 입문형 vs 고급형, 크기별)
- 구매 조건 (예산대, 사이즈/용량, 설치 환경)
- 정보 각도 (유지비, 수명, 청소/관리, A/S)
동일 키워드로 재발행 시에도 이전 제목과 앞 2단어가 겹치지 않게 하세요.
{extra_title_rules}{recent_block}

[출력 형식 규칙 — 가장 중요, 반드시 준수]
응답의 구조는 아래 4단계를 정확히 따르세요:

1. 첫 번째 줄은 반드시 '# ' 로 시작하는 H1 제목이어야 합니다.
   - 예: "# 2026년 8월 네덜란드산 산양유 단백질 추천 - 유당분해 99%"
   - H1 제목 앞에 아무 텍스트도 쓰지 마세요. 첫 글자가 반드시 '#' 여야 합니다.
   - **응답의 맨 첫 줄에 반드시 '# ' 마크다운 H1 제목을 작성할 것** — H1 누락 시 재생성 루프가 발동되므로 이를 1차 방어로 차단.
2. H1 제목 다음에 빈 줄을 한 칸 넣습니다.
3. 빈 줄 다음에 본문 첫 문단이 시작됩니다.
4. H1 제목 없이 본문을 시작하지 마세요. '# ' 없는 상태로 글을 시작하면 응답 전체가 무효 처리됩니다.

- 나열형 템플릿 제목 금지: "{{키워드}} 추천 TOP N (연도년)" 형태의 단순 나열형 제목은 작성하지 마세요. (예: "네덜란드 추천 TOP5 (2026년)" 금지)
- 사고 과정/검토 텍스트 금지: "우선 사용자 요청은~", "제목 규칙을 확인해야 한다~", "제목 예시를 만들어보자~", "제품 데이터를 살펴보면", "이제 글의 구조를 생각해보자", "이제 글을 작성해보자", "제품은 총 N개~" 형태의 문장을 제목이나 본문에 출력하지 마세요. 작성 과정을 설명하는 문구는 일절 포함하지 마세요.

[글 구조 — 정보 전달형]
이 글은 단순 상품 나열이 아니라, 독자가 필요한 핵심 정보(상품명·가격·주요 특징·추천 대상)를 표와 체크리스트로 또렷하게 전달하는 "정보 전달형" 글입니다. 아래 5단계 구조를 따르되, 문장은 자연스럽게 쓰세요.

1. **도입부 — 어떤 기준으로 골랐는지 (2~4문장)**:
   - 이번에 어떤 기준으로 상품을 골랐는지(가격, 스펙, 사용 편의성, 배송 등) 짧게 밝히기
   - 이 글에 어떤 정보가 담겨 있는지(비교표, 상품별 특징, 구매 전 체크리스트) 한두 문장으로 안내
   - "{year}년 {month}월 기준"을 넣어 시의성을 살리고, 공감 가는 문장으로 자연스럽게 시작

2. **핵심 비교 표 (H2) — 필수**:
   - H2 소제목: "한눈에 보는 비교표"
   - 상품명 / 가격 / 주요 특징 / 추천 대상 4개 열을 포함한 마크다운 표로 정리 (블로그별 추가 열 규칙이 있으면 함께 포함)
   - 가격과 특징은 상품 데이터에 있는 값만 사용하고, 없는 값은 "-"로 표기
   - 표 아래에 표를 읽는 방법을 한두 문장으로 설명

3. **상품별 상세 소개 (H2 + 상품마다 H3) — 필수**:
   - H2 소제목: "상품별 상세 비교"
   - 각 상품을 H3 (###)로 세분화. H3 제목: "상품명 — 한 줄 특징" (예: "### 삼성 갤럭시북4 프로 — 가벼운 16인치 사무용")
   - 각 상품마다: 상품 이미지 → 핵심 스펙(수치) → 장점 1~2가지 + 아쉬운 점 1가지 → 어떤 상황의 사람에게 적합한지
   - "추천 대상:", "페르소나:" 같은 라벨 표기 절대 금지. 추천 대상을 자연스러운 문장으로 녹여낼 것.
   - 마지막에 실질 구매 정보 1~2줄 추가. 로켓배송 여부, 구매자 반응(예: "리뷰 4.8점", "누적 판매 1만건+" 등 상품 데이터에 있는 경우만 활용) 등을 자연스러운 문장으로 녹여낼 것. 근거 없는 수치 지어내기 금지.
   - 소개 끝에 링크: [쿠팡에서 최저가 확인하기](상품링크)
   - 각 H3 마커(###)는 줄 시작에 한 번만 사용 (### ###처럼 중복 금지)

4. **구매 전 체크리스트 (H2) — 필수**:
   - H2 소제목: "구매 전 체크리스트"
   - 구매 전 확인할 실용 항목을 체크리스트(대시 목록)로 정리
   - 예: 가격 비교, 스펙·호환성 확인, 배송/설치 조건, 할인·혜택 확인, 구매 후 확인 사항
   - 데이터에 없는 내용은 단정하지 말고 "확인하세요" 형태로 안내

5. **마무리 — 추천과 재확인 (H2)**:
   - H2 소제목은 "마무리", "결론"이 아니라 자연스러운 문장형으로 작성 (예: "정리 — 용도별로 다시 한번")
   - 소개한 상품 중 어떤 상황의 누구에게 어떤 상품이 어울리는지 1~2문장으로 다시 짚기
   - 가격·배송·할인 정보는 변경될 수 있으니 최신 정보를 재확인하라는 안내 1문장
   - 행동 유도(CTA): "아래 링크에서 가격을 확인해 보세요" 같은 문구 포함
   - 소개한 상품 중 로켓배송 상품이 1개 이상 있을 때만 "로켓배송 표기 제품을 우선 고려하세요" 문구 사용. 없으면 해당 문구 사용 금지.

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
[1인칭 경험 주장 금지 — 매우 중요]
- "저도", "저는", "내가", "직접 사용", "실제 사용", "실사용", "써보니", "사용해보니",
  "써본", "경험했", "느꼈", "만족스러웠", "체험" 등 1인칭 경험/체험 주장 표현 절대 금지.
- 이 규칙은 모든 블로그(hugo)에 공통 적용됩니다.
- 대신 상품 데이터(스펙, 가격, 배송, 리뷰 수치)와 구체적 생활 장면으로 서술하세요.
  예시 (O): "1.4kg 무게는 강의실과 도서관을 오가는 대학생에게 큰 장점입니다"
  예시 (X): "실제 사용해보니 1.4kg 무게가 정말 가볍습니다"
- 3인칭 정보 서술 강제: 제품에 대한 설명은 항상 객관적 서술로 작성할 것.

[상품 필터 규칙 — 반드시 준수]
- 키워드와 명백히 무관한 상품은 소개하지 마세요.
- 제외 후 남은 상품이 3개 미만이면 남은 상품만으로 작성하세요.
- 같은 브랜드의 색상만 다른 동일 제품은 하나만 소개하세요.

[글자수]
- 총 2500~3500자 (한글 기준). 비교표/체크리스트 포함해 기존 대비 확대.
- 각 상품 소개는 최소 150자 이상.
- 핵심 비교 표 섹션은 최소 200자 이상.
- 구매 전 체크리스트는 최소 200자 이상.
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
아래 상품 데이터를 기반으로 정보 전달형 추천 큐레이션 글을 작성해주세요. 제공된 상품 수만큼만 소개하세요.
상품 순서는 가격 대비 가치가 높은 순으로 재배치해도 좋습니다.
각 상품의 링크와 이미지 URL은 반드시 그대로 사용하세요.

글은 다음 구조로 작성하세요:
1. 도입부 — 이번에 어떤 기준으로 상품을 골랐는지 짧게
2. "한눈에 보는 비교표" — 상품명/가격/주요 특징/추천 대상이 담긴 마크다운 표
3. 상품별 상세 소개 — 각 상품을 H3(###)로 세분화
4. "구매 전 체크리스트" — 대시 목록 형태
5. 마무리 — 상황별 추천과 최신 정보 재확인 안내

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


_TITLE_TEMPLATE_PATTERNS = [
    re.compile(r"추천\s*TOP\s*\d+", re.I),
    re.compile(r"\(\d{4}년\)$"),
    re.compile(r"BEST\s*\d+", re.I),
    # 뻔한 어미 차단 패턴
    re.compile(r"(추천|선택|구매)\s*가이드$"),
    re.compile(r"고르는\s*법$"),
    re.compile(r"총정리$"),
    re.compile(r"선택지(\s*\d+종)?$"),
]


def sanitize_title(title):
    """제목 후처리 - 괄호 () 금지, 필요 시 하이픈(-)으로 대체 (RAP writer 동일)"""
    if not title:
        return title
    t = title.strip()
    t = re.sub(r"\s*[\(（]\s*", " - ", t)
    t = re.sub(r"\s*[\)）]\s*", " ", t)
    t = re.sub(r"\s{2,}", " ", t)
    t = re.sub(r"(\s*-\s*)+$", "", t)
    t = re.sub(r"^(\s*-\s*)+", "", t)
    return t.strip()


def _validate_title(title):
    """제목 수용 조건 검증 — False면 재생성/차단 대상.

    - 길이 10~35자
    - CoT 마커 미포함: "우선", "사용자 요청"
    - 괄호 (, ), 전각 （, ） 미포함
    - 템플릿 패턴 미포함: 추천 TOP N / (연도년)$ / BEST N / 뻔한 어미
    - 주의: ^\\d{4}년(연도-접두)은 거부하지 않음 (제목 규칙 1이 연도-접두를 지시)
    """
    if not title:
        return False
    title = title.strip()
    if not (10 <= len(title) <= 35):
        return False
    if "우선" in title or "사용자 요청" in title:
        return False
    # 괄호 절대 금지
    if re.search(r"[()（）]", title):
        return False
    # (2026) CJK(한중일 한자/가나) 포함 시 거부 → 재생성 트리거
    if has_cjk(title):
        return False
    for pat in _TITLE_TEMPLATE_PATTERNS:
        if pat.search(title):
            return False
    return True


def _regenerate_title(keyword, blog_id=None, max_attempts=2):
    """H1 누락 시 제목 전용 재생성 — 최대 max_attempts회, 실패 시 None (fail-closed).

    전용 프롬프트(본문 작성 프롬프트 재사용 금지)로 제목 한 줄만 요청하고,
    ai_generate는 tier="economy" 고정 파라미터로 호출한다 (결정 2).
    RuntimeError(전 tier 실패)도 무효로 취급해 재시도한다 (MINOR-4).
    """
    system_prompt = (
        "당신은 상품 큐레이션 블로그 제목 작성 전문가입니다. 반드시 한국어로 작성하세요.\n"
        "아래 키워드에 대한 블로그 글 제목을 한 줄만 출력하세요.\n"
        "제목 앞에 '# ' 마크다운 H1 마커를 붙이세요.\n"
        "검토 문구, 사고 과정, 설명은 출력하지 마세요.\n"
        '나열형 템플릿 제목("{keyword} 추천 TOP N (연도년)" 형태)은 금지합니다.\n'
        "제목 길이는 35자 이내로 작성하세요.\n"
        "괄호 (), 전각 （）는 절대 사용하지 마세요. 구분은 하이픈(-)을 사용하세요.\n"
        "사람들이 실제 검색하는 구체적 단어(제품 특성·용도·대상)를 최소 1개 포함하세요.\n"
        "추상·감성 수식어('요리 즐거움', '실속 있는 선택')는 금지합니다.\n"
        '"추천 가이드", "선택 가이드", "구매 가이드", "고르는 법", "총정리", "선택지 N종"으로 끝내지 마세요.'
    )
    user_prompt = f"키워드: {keyword}\n\n제목 한 줄만 출력하세요."
    for attempt in range(max_attempts):
        try:
            result = ai_generate(system_prompt, user_prompt, tier="economy", temperature=0.5, max_tokens=200)
        except RuntimeError as e:
            logger.warning(f"[title_regenerate] LLM 실패 (RuntimeError, 시도 {attempt+1}): {keyword} — {e}")
            continue
        text = result if isinstance(result, str) else result.get("content", "")
        if not text:
            continue
        first_line = text.strip().split("\n")[0].strip()
        if first_line.startswith("# "):
            first_line = first_line.lstrip("# ").strip()
        if _validate_title(first_line):
            return sanitize_title(first_line)
        logger.warning(f"[title_regenerate] 무효 제목 (시도 {attempt+1}): {keyword} → {first_line[:60]}")
    logger.warning(f"[title_regenerate] {max_attempts}회 모두 실패: {keyword}")
    return None


# CoT body 판정을 위한 임계값 상수 (모듈 레벨로 분리해 튜닝 용이)
_COT_ENGLISH_RATIO_THRESHOLD = 0.30
_COT_WRITING_INSTRUCTION_MIN_MATCHES = 3
_COT_MARKER_MIN_MATCHES = 1

# C04 패턴 단일 소스 통합: leak_tracker의 패턴 중 writer.py post-generate
# 단계에서 재사용할 패턴을 명확한 패턴(재시도 대상)과 모호한 패턴(WARNING 관찰)
# 으로 분리 정의. leak_tracker와 동일 소스에서 파생했으나 writer 용도에 맞게
# ambiguous 분류 추가.
#
# 명확한 패턴: CoT/프롬프트 지시문 성격이 강해 재시도 대상
_C04_CLEAR_PATTERNS_KO = [
    r"먼저\s*생각", r"생각해보자", r"생각해\s*보자",
    r"다음\s*단계", r"단계별로",
    r"우리가\s*해야\s*할", r"생각\s*과정", r"결론부터\s*말하면",
]
_C04_CLEAR_PATTERNS_EN = [
    r"\bNeed\s+think\b", r"\bWe\s+need\s+to\s+write\b",
    r"Let.s\s+think\s+step\s+by\s+step", r"think\s+step\s+by\s+step",
    r"let.s\s+break\s+this\s+down", r"here.?s\s+the\s+plan",
    r"in\s+order\s+to\s+achieve", r"as\s+an\s+AI\s+language\s+model",
]
# 모호한 패턴: 자연어에도 등장 가능 → WARNING 관찰만, 재시도 대상 아님
_C04_AMBIGUOUS_PATTERNS = [
    (r"우선", "본문 첫머리 + 명령형 어미 + 지시문 구조 동시 충족 시 관찰"),
    (r"필요한\s*것", "자연어에도 빈출 — 문맥 확인 필요"),
]

# RULE-C04-S01: 단일 마커("우선") 문맥 관찰 규칙
# 본문 첫 3줄 이내 + 명령형 어미 + 지시문 구조 동시 충족 시 WARNING 관찰 대상
_C04_SINGLE_MARKER_CONTEXT = {
    "position_markers": ["우선"],
    "imperative_endings": [
        "해야 한다", "해야 합니다", "해야 할", "해야", "필수다",
        "필요하다", "중요하다", "반드시", "꼭",
    ],
    "instruction_structure": [
        "첫째", "둘째", "셋째", "다음", "제품명", "선택 기준",
        "비교", "비교표", "FAQ", "자주 묻는 질문",
    ],
}


def _is_cot_body(body):
    """본문이 CoT/프롬프트 지시문인지 판정.

    - 영어 문장 비율 > 30% (LLM CoT는 영어 지시문 다량 포함)
    - 프롬프트 지시문 키워드 다수 매치: "AIDA", "퍼널", "H2", "H3", "비교표",
      "자주 묻는 질문", "상황별 추천", "도입부", "선택 가이드", "FAQ",
      "장점", "아쉬운 점", "CTA" 등 글쓰기 지시어 3개 이상
    - CoT 마커("우선", "사용자 요청", "제목 규칙", "제목 예시") 포함
    - 위 3개 조건 중 2개 이상 충족 시 CoT로 판정
    """
    if not body:
        return False
    text = body.strip()
    total_chars = len(text)
    if total_chars == 0:
        return False

    # 1) 영어 문자 비율
    english_chars = sum(1 for c in text if c.isascii() and c.isalpha())
    english_ratio = english_chars / total_chars

    # 2) 글쓰기 지시어 키워드 매치 수
    writing_instruction_keywords = [
        "AIDA", "퍼널", "CTA", "H2 헤딩", "H3 헤딩",
        "다음 형식", "아래 형식", "작성하세요", "작성해주세요",
        "출력 형식", "프롬프트", "지시사항",
    ]
    writing_matches = sum(1 for kw in writing_instruction_keywords if kw in text)

    # 3) CoT 마커 매치
    cot_markers = ["사용자 요청", "제목 규칙는", "제목 예시:", "Here is", "Here's", "다음은 요청하신"]
    cot_matches = sum(1 for m in cot_markers if m in text)

    # 판정: 3개 조건 중 2개 이상 충족
    conditions_met = 0
    if english_ratio > _COT_ENGLISH_RATIO_THRESHOLD:
        conditions_met += 1
    if writing_matches >= _COT_WRITING_INSTRUCTION_MIN_MATCHES:
        conditions_met += 1
    if cot_matches >= _COT_MARKER_MIN_MATCHES:
        conditions_met += 1

    return conditions_met >= 2


def _extract_description(body, title, keyword):
    """본문에서 CoT/마커 줄을 제외한 첫 의미 문단 추출 (meta description용).

    - 빈 줄 / '#'·'!'·'[' 시작 줄 제외 (기존 동작 유지)
    - CoT/검토 마커 줄 제외: '우선' 시작, '사용자 요청' 포함, '제목 규칙'/'제목 예시' 시작,
      '제품 데이터를 살펴보면', '이제 글의 구조', '이제 글을 작성' 등 작성 계획 문구
    - 누적 길이 >= 20자 되는 지점에서 첫 문단 확정 (문단 시작 '우선' 금지)
    - ~150자 트렁케이션 (기존 160자 → 결정 5 기준 150자)
    - 문단을 못 찾으면 키워드 기반 최후 fallback
    """
    desc_lines = []
    for line in (body or "").split("\n"):
        line = line.strip()
        if not line or line.startswith(("#", "!", "[")):
            continue
        if line.startswith("우선") or "사용자 요청" in line:
            continue
        if line.startswith("제목 규칙") or line.startswith("제목 예시"):
            continue
        if line.startswith("제품 데이터를 살펴보면") or line.startswith("이제 글의 구조") or line.startswith("이제 글을 작성"):
            continue
        desc_lines.append(line)
        if len("".join(desc_lines)) >= 20:
            break
    paragraph = " ".join(desc_lines).strip()
    if not paragraph or paragraph.startswith("우선"):
        return f"{keyword} 관련 상품 비교와 선택 가이드를 제공합니다."
    return paragraph[:150]


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
        template_type = _tt_picker.pick(used_templates=recent_styles, blog_id=blog_id)

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

    # 글자수 미달 시 최대 3회 시도 (2→3 확대, 시도별 temperature 변화)
    body = ""
    cot_body_detected = False
    _temps = [0.85, 0.95, 0.75]  # 시도별 다양화
    for attempt in range(3):
        _temp = _temps[attempt] if attempt < len(_temps) else 0.85
        try:
            result = ai_generate(system_prompt, user_prompt, temperature=_temp)
        except RuntimeError as _re:
            # ── Phase 58 P22 — LLM 폴백 체인 전체 실패 (ai_writer 전 tier 소진) ──
            # 기존 전파/흡수 흐름 불변 (re-raise), P22 정확 원인 알림만 추가.
            try:
                from shared.problem_monitor import get_monitor
                get_monitor().report(blog_id, {"reason": "llm_fallback_exhausted"}, phase="result_parse", extra={})
            except Exception as _me:
                logger.error(f"[problem_monitor] P22 보고 실패: {_me}")
            raise
        if not result:
            logger.error(f"AI 생성 실패 (시도 {attempt+1}/3): {keyword}")
            continue

        body = result if isinstance(result, str) else result.get("content", "")
        if not body:
            continue

        # ── Phase 58 post-generate raw 훅 (sanitize 이전 raw 감지 — BUG-54-001 교훈) ──
        # 감지만 수행. 기존 _sanitize_body/_is_cot_body 흐름은 수정하지 않음.
        try:
            from shared.problem_monitor import get_monitor
            for det in get_monitor().detect("post_generate", body, blog_id):
                get_monitor().report(blog_id, {"detection": det}, phase="post_generate", extra={})
        except Exception as _me:
            logger.error(f"[problem_monitor] post_generate 보고 실패: {_me}")

        # CoT/프롬프트 지시문 본문 감지 — 즉시 재시도 (sanitization 전에 검사)
        if _is_cot_body(body):
            cot_body_detected = True
            logger.warning(f"[cot_body] CoT 본문 감지 (시도 {attempt+1}): {keyword} — 재시도")
            body = ""
            continue

        # ── C04 패턴 단일 소스 통합 (writer.py 내 패턴으로 post-generate 검사) ──
        # _is_cot_body가 놓친 C04 패턴을 writer.py 내 명확한/모호한 패턴으로
        # 구분하여 검사. 명확한 패턴은 재시도, 모호한 패턴은 WARNING 관찰.
        _c04_detected_clear = False
        _c04_detected_ambiguous = []
        _c04_patterns_source = _C04_CLEAR_PATTERNS_KO  # writer.py는 한국어 파이프라인 전용
        for _pat in _c04_patterns_source:
            if re.search(_pat, body, re.IGNORECASE):
                _c04_detected_clear = True
                break
        # 모호한 패턴 별도 검사
        for _amb_pat, _amb_desc in _C04_AMBIGUOUS_PATTERNS:
            if re.search(_amb_pat, body, re.IGNORECASE):
                _c04_detected_ambiguous.append(_amb_pat)
        if _c04_detected_clear:
            # 명확한 C04 패턴 → 재시도
            cot_body_detected = True
            logger.warning(f"[cot_body] C04 누수 감지 (시도 {attempt+1}): {keyword} — 명확한 프롬프트 누수 — 재시도")
            body = ""
            continue
        if _c04_detected_ambiguous:
            # 모호한 패턴만 탐지 → 문맥 조건 검사 후 WARNING 관찰 여부 결정
            _body_lines = body.strip().split("\n")
            _first_lines = "\n".join(_body_lines[:3])
            _position_hit = any(m in _first_lines for m in _C04_SINGLE_MARKER_CONTEXT["position_markers"])
            _imperative_hits = sum(1 for e in _C04_SINGLE_MARKER_CONTEXT["imperative_endings"] if e in body)
            _structure_hits = sum(1 for s in _C04_SINGLE_MARKER_CONTEXT["instruction_structure"] if s in body)
            _context_score = sum([_position_hit, _imperative_hits >= 1, _structure_hits >= 2])
            if _context_score >= 2:
                logger.warning(f"[C04-WARNING] RULE-C04-S01 단일 마커 문맥 의심 (시도 {attempt+1}): {keyword} — {_c04_detected_ambiguous} — 관찰 대상 (7일)")
            else:
                logger.info(f"[c04_ambiguous] C04 모호 패턴만 탐지 (시도 {attempt+1}): {keyword} — {_c04_detected_ambiguous} — 문맥 불일치, 자연어로 간주")

        # 금지어 치환 + 메타문구 제거
        body = _sanitize_body(body)

        # H2 가드 (Q6): H2가 0이면 재생성 유도 — 옛 TOP5 포맷(H3-only) 방지
        if _count_h2(body) == 0:
            logger.warning(f"H2 없음 (시도 {attempt+1}/3): {keyword} — 재시도")
            body = ""
            continue

        if len(body) >= 1800:
            break
        logger.warning(f"글자수 미달 (시도 {attempt+1}/3): {keyword} ({len(body)}자)")

    if not body or len(body) < 800:
        logger.error(f"최종 생성 결과 부족: {keyword} ({len(body)}자)")
        return None

    # H2 가드 최종 확인 (Q6): 재시도 3회 후에도 H2=0이면 명시적 fail (침묵 통과 방지)
    if _count_h2(body) == 0:
        logger.error(f"H2 없는 최종 본문 차단 (재시도 3회 소진): {keyword}")
        return None

    # CoT 본문 재생성 실패 검사 — 2회 시도 후에도 CoT 본문이면 차단
    body_regeneration_failed = False
    if cot_body_detected and not body:
        body_regeneration_failed = True
        logger.warning(f"[cot_body] CoT 본문 재생성 실패: {keyword} — 발행 차단")

    # 제목 추출: 첫 번째 # 헤딩 또는 첫 줄
    title_generation_failed = False
    title = ""
    for line in body.split("\n"):
        line = line.strip()
        if line.startswith("# "):
            title = line.lstrip("# ").strip()
            # 백스톱: H1이 있어도 템플릿/CoT 패턴이면 재생성 (fail-closed 유지)
            if not _validate_title(title):
                title = _regenerate_title(keyword, blog_id)
                if not title:
                    title_generation_failed = True
                    logger.warning(f"[title] H1 템플릿 패턴 + 재생성 2회 실패: {keyword} — 발행 차단 마커 반환")
            body = body.replace(line, "", 1).strip()
            break
    if not title:
        # 계층적 안전 폴백: pick() → 날짜 조합 (옛 TOP5 포맷 사용 금지)
        _FALLBACK_FRAME = ["실사용", "후기", "느낌", "써본", "리뷰"]
        try:
            _fb_template = _tt_picker.pick(used_templates=[], blog_id=blog_id)
            if _fb_template:
                _fb_brand = {}
                if products:
                    _b = products[0].get("brand", "") or products[0].get("maker", "")
                    if _b:
                        _fb_brand["brand1"] = _b
                _fb_title = _tt_picker.render(_fb_template, _fb_brand, keyword)
                if _fb_title and len(_fb_title) >= 10 and not any(f in _fb_title for f in _FALLBACK_FRAME):
                    title = _fb_title
        except Exception as _e:
            logger.warning(f"[title-fallback] pick() 예외: blog_id={blog_id} keyword={keyword} err={_e}")
        if not title:
            # 최후 폴백: "{keyword} 추천 · YYYY년 M월" — 옛 TOP5 포맷 금지
            _now = datetime.now()
            title = f"{keyword} 추천 · {_now.year}년 {_now.month}월"
            logger.warning(f"[title-fallback] blog_id={blog_id} keyword={keyword} pick 실패 → 최후 폴백 사용: {title}")
    if template_type:
        logger.info("[title_template] 사용됨: %s (제목: %s…)", template_type, (title or "")[:50])

    # 쿠팡 고지 문구 확인 및 추가
    disclosure = "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."
    if disclosure not in body:
        body = body.rstrip() + f"\n\n---\n\n*{disclosure}*\n"

    # 애드센스 광고 삽입 (single.html 템플릿에서 처리 — 본문 raw HTML 삽입 시 Hugo 빌드 오류)
    # body = _insert_adsense(body)

    # description: 본문에서 CoT/마커 줄 제외 첫 의미 문단 추출
    description = _extract_description(body, title or "", keyword)

    # Phase 70 Wave 3: editorial synthesis (no-op unless topic carries topic_type)
    body = _inject_editorial_synthesis(body, {"topic_type": "curation", "topic_id": keyword})

    # 제목 최종 후처리: 괄호 → 하이픈 (LLM이 괄호를 뱉어도 발행물엔 괄호 없음)
    title = sanitize_title(title)

    result = {
        "title": title or "",
        "body_md": body,
        "keyword": keyword,
        "product_count": min(len(products), 5),
        "description": description,
    }
    if title_generation_failed:
        result["title"] = ""
        result["title_generation_failed"] = True
    if body_regeneration_failed:
        result["body_regeneration_failed"] = True
        result["is_draft"] = True
    return result
