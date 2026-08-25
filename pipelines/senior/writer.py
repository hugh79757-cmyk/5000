"""시니어 복지 글 생성 v2 — 서비스 단위 심층 글, 데이터 기반 강제"""

import logging
import os
import random
import re
from datetime import datetime

from openai import OpenAI

from shared.ai_writer import generate as ai_generate

logger = logging.getLogger(__name__)

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


# 상세 데이터 보강
def _enrich_service(service):
    """서비스 상세 API로 데이터 보강 (캐시 체크 후 1회만)"""
    if service.get("_enriched"):
        return service
    try:
        import os
        import sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from fetcher import enrich_service_detail
        service = enrich_service_detail(service)
        service["_enriched"] = True
    except Exception as e:
        logger.warning(f"상세 보강 실패: {e}")
    return service

logger = logging.getLogger(__name__)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
MODEL = os.getenv("OPENAI_MODEL", "mimo-v2.5")

# 카테고리별 글 구조 템플릿 — 정보 전달형: 짧은 문단 + 핵심 정보 표 + 절차 H3/체크리스트
# 공통 골격: 도입부 → [지원 대상/금액/기간 표] → [신청 절차/서류] → [문의처·주의사항] → 마무리
ARTICLE_STRUCTURES = {
    "의료지원": {
        "sections": ["의료 지원 내용과 지원 금액", "지원 대상과 조건 한눈에 보기", "신청 방법과 필요 서류", "문의처와 신청 전 주의사항"],
        "angle": "어르신이 의료 지원의 금액과 대상 조건을 표로 한눈에 보고, 신청 절차를 체크리스트로 확인할 수 있도록 안내",
    },
    "돌봄서비스": {
        "sections": ["돌봄서비스 내용과 이용 요금", "이용 대상과 이용 기간", "신청 방법과 준비 서류", "문의처와 이용 시 주의사항"],
        "angle": "어르신과 가족이 돌봄서비스의 요금·대상·이용 기간을 표로 파악하고 신청 절차를 체크리스트로 확인할 수 있도록 안내",
    },
    "교통복지": {
        "sections": ["교통 혜택 내용과 지원 금액", "지원 대상과 이용 기간", "신청 방법과 필요 서류", "문의처와 이용 시 주의사항"],
        "angle": "교통비 지원의 금액과 대상 조건을 표로 한눈에 보고 신청 절차를 체크리스트로 확인할 수 있도록 안내",
    },
    "일자리금융": {
        "sections": ["참여 조건과 급여 금액", "근무 내용과 기간", "신청 방법과 선발 절차", "문의처와 참여 전 주의사항"],
        "angle": "시니어 일자리와 금융 지원의 급여·조건·신청 절차를 표와 체크리스트로 한눈에 안내",
    },
    "문화여가": {
        "sections": ["혜택 내용과 지원 금액", "지원 대상과 이용 기간", "신청 방법과 이용 시설", "문의처와 이용 시 유의사항"],
        "angle": "어르신 문화 혜택의 금액·대상·이용 방법을 표로 정리하고 신청 절차를 체크리스트로 안내",
    },
    "연금생활지원": {
        "sections": ["지급 금액과 지급 주기", "수급 조건과 신청 기간", "신청 방법과 필요 서류", "문의처와 신청 전 확인할 점"],
        "angle": "연금과 생활지원금의 금액·조건·신청 절차를 표와 체크리스트로 명확하게 안내",
    },
    "생활지원": {
        "sections": ["지원 내용과 지원 금액", "지원 대상과 신청 기간", "신청 방법과 필요 서류", "문의처와 신청 전 주의사항"],
        "angle": "생활 지원 제도의 금액·대상 조건을 표로 한눈에 보고 신청 절차를 체크리스트로 확인할 수 있도록 안내",
    },
}


# 쿠팡 파트너스 카테고리별 추천

def _append_links(body_md, service, category):
    """본문 끝에 정부 신청 버튼 + 쿠팡 API 상품 링크 삽입"""
    import re as _re

    # GPT 면책 문구 제거 (중복 방지)
    body_md = _re.sub(r"\n*이 글은 정부24[^\n]*", "", body_md)
    body_md = _re.sub(r"\n*> 이 글은[^\n]*", "", body_md)
    body_md = _re.sub(r"\n*---\s*$", "", body_md.rstrip())
    body_md = body_md.rstrip()

    parts = []

    # 1) 정부 신청 버튼
    apply_url = service.get("apply_url", "")
    svc_id = service.get("service_id", "")
    if apply_url:
        url = apply_url
        if url and not url.startswith("http"):
            url = "https://" + url
    elif svc_id:
        url = f"https://www.gov.kr/portal/rcvfvrSvc/dtlEx/{svc_id}"
    else:
        url = "https://www.bokjiro.go.kr"
    dept = service.get("department", "")
    btn_text = f"{dept}에서 신청하기" if dept else "온라인으로 신청하기"
    parts.append(f'\n\n{{{{< btn url="{url}" text="{btn_text}" >}}}}')

    # 2) 쿠팡 파트너스 API 상품 링크 — 서비스 내용 기반 매칭
    try:
        from shared.coupang_senior import CoupangSenior
        coupang = CoupangSenior()
        if coupang.is_configured():
            # [PATCH] 서비스명/대상에서 키워드 추출하여 관련 상품만 추천
            svc_name = service.get("service_name", "")
            svc_target = service.get("target", "")
            svc_desc = service.get("description", "")
            svc_text = f"{svc_name} {svc_target} {svc_desc}"

            # 서비스 내용과 매칭되는 키워드 결정
            keyword_hint = None
            keyword_rules = [
                (["혈압", "고혈압", "심장", "심혈관"], "혈압계"),
                (["혈당", "당뇨"], "혈당측정기"),
                (["보행", "거동", "이동", "휠체어", "장애"], "보행보조기"),
                (["난방", "동절기", "겨울", "연료", "난방비"], "난방용품"),
                (["돌봄", "요양", "간병", "간호", "수발"], "간병용품"),
                (["청력", "보청", "난청"], "보청기"),
                (["낙상", "안전", "미끄럼"], "미끄럼방지"),
                (["영양", "건강", "급식", "식사", "반찬"], "건강식품"),
                (["운동", "체육", "건강관리", "체력"], "운동용품"),
                (["시력", "안경", "저시력"], "돋보기"),
                (["전동", "보장구", "스쿠터", "전동휠체어"], "전동스쿠터"),
                (["보험", "배상", "책임보험"], "실버보험"),
                (["임플란트", "틀니", "치과"], "치아관리용품"),
                (["기저귀", "배변", "요실금"], "성인기저귀"),
                (["목욕", "세신", "위생"], "목욕용품"),
                (["교통", "버스", "지하철", "승차", "택시", "이동지원"], "교통카드"),
                (["주거", "집수리", "주택", "난방비", "도배", "장판"], "실내용품"),
            ]
            for keywords, hint in keyword_rules:
                if any(kw in svc_text for kw in keywords):
                    keyword_hint = hint
                    break

            if keyword_hint:
                coupang_md = coupang.get_senior_product_links(category=keyword_hint, count=2)
            else:
                # 매칭 키워드 없으면 무관한 상품 노출 방지 — 쿠팡 링크 생략
                coupang_md = None

            if coupang_md:
                parts.append(coupang_md)
    except Exception as e:
        logger.warning(f"쿠팡 링크 생성 실패: {e}")

    # 3) 면책 1회

    parts.append("\n\n---")
    parts.append("\n\n> 이 글은 정부24 공공데이터를 기반으로 작성되었습니다. 최신 정보는 [복지로](https://www.bokjiro.go.kr)에서 확인하세요.")

    return body_md + "".join(parts)


def _build_data_block(service):
    """단일 서비스의 상세 데이터 블록 구성"""
    fields = []
    fields.append(f"서비스명: {service.get('service_name', '미정')}")
    fields.append(f"서비스ID: {service.get('service_id', '')}")
    if service.get("description"):
        fields.append(f"서비스 설명: {service['description']}")
    if service.get("target"):
        fields.append(f"지원 대상: {service['target']}")
    if service.get("support_content"):
        fields.append(f"지원 내용: {service['support_content']}")
    if service.get("apply_method"):
        fields.append(f"신청 방법: {service['apply_method']}")
    if service.get("apply_url"):
        fields.append(f"신청 URL: {service['apply_url']}")
    if service.get("department"):
        fields.append(f"소관기관: {service['department']}")
    if service.get("contact"):
        fields.append(f"문의처: {service['contact']}")
    if service.get("law_basis"):
        fields.append(f"법적 근거: {service['law_basis']}")
    if service.get("purpose"):
        fields.append(f"서비스목적: {service['purpose']}")
    if service.get("selection_criteria"):
        fields.append(f"선정기준: {service['selection_criteria']}")
    if service.get("documents"):
        fields.append(f"구비서류: {service['documents']}")
    if service.get("deadline"):
        fields.append(f"신청기한: {service['deadline']}")
    if service.get("apply_method_detail"):
        fields.append(f"상세 신청방법: {service['apply_method_detail']}")
    if service.get("reception_agency"):
        fields.append(f"접수기관: {service['reception_agency']}")
    if service.get("support_type"):
        fields.append(f"지원유형: {service['support_type']}")
    # [PATCH] 오늘 날짜 주입 - GPT가 마감 여부 판단하도록
    from datetime import datetime as _dt
    fields.append(f"\n[오늘 날짜: {_dt.now().strftime('%Y년 %m월 %d일')}]")
    return "\n".join(fields)


def _build_prompt(service, topic_type, related_services, today):
    """단일 서비스 중심 심층 글 프롬프트"""
    structure = ARTICLE_STRUCTURES.get(topic_type, ARTICLE_STRUCTURES["생활지원"])
    service_name = service.get("service_name", "시니어 복지 제도")

    # 지역 한정 서비스 판별
    dept = service.get("department", "")
    region_markers = ["시 ", "시)", "군 ", "군)", "구 ", "구)", "특별자치", "광역시", "특별시"]
    is_local = any(m in dept for m in region_markers) or any(dept.endswith(x) for x in ["시", "군", "구"])
    region_name = dept if is_local else ""

    main_data = _build_data_block(service)

    related_block = ""
    if related_services:
        # [PATCH] 메인 서비스와 같은 지역의 관련 서비스만 선택
        main_dept = service.get("department", "")
        main_region_tokens = [t for t in main_dept.replace("(", " ").replace(")", " ").split()
                              if any(t.endswith(s) for s in ["시", "군", "구"])]
        if main_region_tokens:
            region_filtered = []
            for rs in related_services:
                rs_dept = rs.get("department", "")
                if any(tok in rs_dept for tok in main_region_tokens):
                    region_filtered.append(rs)
            # 지역 매칭이 없으면 전국 서비스(지역 미표기)만 사용
            if not region_filtered:
                region_filtered = [rs for rs in related_services
                                   if not any(m in rs.get("department", "")
                                              for m in ["시 ", "군 ", "구 ", "시)", "군)", "구)"])]
            related_services = region_filtered[:3]
        else:
            related_services = related_services[:3]
        related_items = []
        for rs in related_services[:3]:
            name = rs.get("service_name", "")
            desc = rs.get("description", "")[:80]
            target = rs.get("target", "")[:60]
            related_items.append(f"- {name}: {desc} (대상: {target})")
        related_block = "\n\n[관련 서비스 — 비교 서술에 활용]\n" + "\n".join(related_items)

    sections_guide = "\n".join([f"## {s}" for s in structure["sections"]])

    region_line = f"\n\n이 서비스는 [{region_name}] 지역 한정입니다. 제목 앞부분에 반드시 지역명을 넣으세요." if region_name else ""

    system_msg = f"""당신은 65세 이상 어르신과 그 가족을 위한 복지 정보 전문 블로거입니다. 반드시 한국어로 작성하세요. 중국어나 다른 언어로 작성하지 마세요.

당신의 임무: "{service_name}" 제도에 대해, {structure['angle']}하는 글을 작성합니다.

핵심 전략 — 롱테일 SEO:
이 글은 대형 포털이나 정부 사이트와 경쟁하지 않습니다.
"기초연금 신청방법" 같은 대형 키워드 대신, 구체적 상황·조건·질문을 담은 세부 키워드를 노립니다.

■ 제목 규칙 (가장 중요):
- 대형 키워드를 피하고, 구체적 조건+상황을 담은 롱테일 제목을 작성
- 나쁜 예: "기초연금 신청방법 총정리", "노인 임플란트 무료 지원 안내", "치매 치료비 지원 제도"
- 좋은 예 (5가지 패턴을 골고루 사용):
  1. 질문형: "기초연금 받으면서 일하면 감액될까? 소득 기준 정리"
  2. 숫자형: "만 65세 임플란트 본인부담금 최대 120만원, 1종 2종 차이"
  3. 조건형: "혼자 사는 75세 어르신이 받을 수 있는 난방비 지원"
  4. 비교형: "치매 치료관리비 vs 치매안심센터, 뭐가 다를까"
  5. 후기형: "어머니 틀니 지원 신청해봤더니, 실제 절차 정리"
- 같은 패턴이 연속되면 안 됩니다. 5건 발행 시 최소 3가지 패턴을 섞으세요.
- 제공된 데이터에서 대상자 조건, 금액, 지역명 중 가장 구체적인 정보를 제목에 포함
- "~방법은?" "~안내" "~총정리"로 끝내지 마세요
- 지역 한정 서비스인 경우, 반드시 제목 앞부분에 지역명(시/군/구)을 포함하세요. 예: "화성시 65세 이상 무상교통, 연 156만원 받는 조건"
- 전국 대상 서비스라면 지역명 불필요
- 25~50자

■ 글쓰기 원칙:
1. 제공된 데이터의 모든 필드를 본문에 반드시 인용하세요. 특히 지원내용, 문의처(전화번호 포함), 법적 근거, 선정기준, 구비서류, 신청기한은 빠짐없이 넣으세요.
   - [중요-마감판단] 데이터에 신청기한/접수기간이 있으면 오늘 날짜(데이터 블록 하단 참조)와 비교하세요. 마감일이 오늘보다 과거이면 반드시 "현재 신청기간이 종료되었습니다. 다음 접수 일정은 해당 기관(문의처 전화번호)에 문의하세요."라고 본문에 명시하세요. 마감된 기한을 마치 현재 진행 중인 것처럼 쓰면 0점 처리됩니다.
2. 데이터에 없는 금액, 날짜, 기관명, 통계를 절대 지어내지 마세요.
3. 어려운 행정 용어는 괄호 안에 쉬운 설명을 덧붙이세요. 예: 본인부담금(환자가 직접 내는 비용)
4. 아래 표현은 절대 사용 금지 (발견 시 0점 처리):
   - "확인해 보세요", "다를 수 있습니다", "도움이 될 것입니다", "도움이 될 수 있습니다"
   - "삶의 질을 높일 수 있도록", "더욱 풍요롭게", "이러한 제도는 ~ 큰 도움이"
   - "이와 같은 다양한 제도를 종합적으로 활용하면"
   - "이 점을 유념하시기 바랍니다", "참고하시기 바랍니다", "권장합니다"
   - 모든 문장은 구체적 정보(금액, 조건, 절차, 전화번호)를 포함해야 합니다. 정보 없이 분위기만 채우는 문장은 삭제하세요.
5. 존댓말(합니다/입니다 체), 친근한 톤.
6. 과거 연도(2023~2025년)를 현재처럼 쓰지 마세요.

■ 반복 금지 규칙 (매우 중요):
- 같은 사실을 다른 H2에서 반복하지 마세요. 한 번 언급한 내용은 다시 쓰지 않습니다.
- "최대 월 3만원"처럼 핵심 수치는 본문 전체에서 1~2회만 언급하세요.
- 각 H2는 반드시 새로운 정보를 다뤄야 합니다. 앞 섹션과 내용이 겹치면 삭제하고 다른 내용으로 채우세요.

■ 어미 다양화:
- "~합니다", "~입니다"만 반복하지 마세요.
- "~됩니다", "~받을 수 있습니다", "~필요합니다", "~이루어집니다", "~드립니다" 등을 섞으세요.
- 연속 3문장이 같은 어미로 끝나면 안 됩니다.

■ 본문 구조 — 정보 전달형 (글 전체가 아래 흐름을 따르세요):
1) 도입부 (H2 없이 바로 시작): 이 글이 어떤 지원인지 한눈에 알 수 있도록, 핵심 팩트(어떤 혜택인지, 누가 받을 수 있는지, 주요 금액과 신청처)를 2~3문장으로 바로 제시하세요. "이 글에서는 ~을 정리했습니다" 식의 안내는 쓰지 마세요.

2) H2 4개 (번호 붙이지 말 것):
{sections_guide}

3) 마무리 (H2 없이): 핵심 내용을 1~2문장으로 재요약하고, "문의처: OOO (전화번호)"로 마무리하세요.

■ H2별 구성 원칙 (각 H2는 아래 방식을 활용하세요):
- H2 1(지원 내용과 금액): 금액·기간·내용이 담긴 마크다운 표(| 항목 | 내용 |)를 먼저 제시하고, 표에 담기 어려운 세부 내용만 짧은 문단(2~3문장)으로 보충하세요. 표에는 데이터에 있는 금액, 기간, 대상만 정확히 넣고 지어내지 마세요.
- H2 2(지원 대상과 조건): 지원 대상을 표로 정리하세요. 조건이 여러 개라면 H3(###)로 나눠 항목별로 설명하세요.
- H2 3(신청 방법): 신청 절차를 H3(###)로 단계별 세분화하거나, 순서가 있는 체크리스트로 정리하세요. "### 신청 준비물" 같은 H3 아래에서는 "- [ ] 구비서류 OOO 준비" 형태의 체크리스트를 사용하고, 구비서류·신청 채널·방문처를 빠짐없이 나열하세요.
- H2 4(문의처·주의사항): 문의처(전화번호 포함), 신청 기한, 유의사항을 표나 짧은 체크리스트로 정리하세요.
- 각 H2는 도입 문단 1~2문장을 제시한 뒤 표나 체크리스트로 핵심 정보를 모으세요. 문단은 짧게(3문장 이하) 끊고, 표로 담을 수 있는 정보는 문장 대신 표로 옮기세요. 한 표에 4개 이하의 열을 쓰고 셀은 간결하게 유지하세요.

- H2 제목에 "1.", "2." 같은 번호를 붙이지 마세요. "## 지원 내용과 지원 금액" 처럼 번호 없이 쓰세요.
- 전체 본문 2,500자 이상 (필수). 2,500자 미만이면 각 H2에 표 항목과 구체적 사례를 추가하세요
- 면책 문구를 본문에 넣지 마세요 (시스템이 자동 삽입합니다)

■ SEO:
- 태그: 실제 검색되는 롱테일 키워드 5~7개 (대형 키워드 금지)
- 카테고리: {topic_type}
- description: 구체적 상황+핵심 답변 1문장 (80~120자). "안내드립니다"로 끝내지 말고 핵심 정보를 담으세요.

오늘 날짜: {today}{region_line}"""

    user_msg = f"""아래 데이터를 기반으로 글을 작성하세요.

[메인 서비스 데이터]
{main_data}
{related_block}

[작성 규칙]
1. 위 데이터의 모든 필드(지원내용, 문의처, 법적 근거, 선정기준, 구비서류, 신청기한)를 본문에 반드시 포함하세요.
2. 정보 전달형 구조를 따르세요: 도입부(핵심 팩트 바로 제시) → H2 4개(지원 내용/금액 → 대상/조건 → 신청 방법 → 문의처·주의사항) → 마무리.
3. 금액·기간·조건·문의처 같은 핵심 정보는 반드시 마크다운 표로 정리하세요. 각 H2에 표를 1개 이상 넣으세요.
4. 신청 방법 H2는 H3(###)로 절차를 세분화하거나 "- [ ] 항목" 형태 체크리스트로 정리하세요. 구비서류와 신청 채널을 빠짐없이 나열하세요.
5. 문단은 짧게(3문장 이하) 끊고, 같은 정보를 문단과 표에 중복해서 풀지 마세요.
6. H2는 정확히 4개. 각 H2는 새로운 정보만 다루고, 앞 섹션과 절대 중복하지 마세요.
7. 각 H2 최소 8문장, 350자 이상. 전체 3,000자 이상.
8. 연속 3문장이 같은 어미("~합니다")로 끝나지 않게 하세요.
9. 관련 서비스가 있으면 마지막 H2에서 차이점을 비교 서술하세요.
10. 데이터에 없는 금액·기간·조건·기관명은 절대 지어내지 마세요. 표 안에도 데이터에 없는 수치는 넣지 마세요.

출력 형식:
TITLE: (25~50자, 구체적 조건+질문형)
CATEGORY: {topic_type}
TAGS: (롱테일 5~7개, 쉼표 구분)
DESCRIPTION: (80~120자, 핵심 정보)
BODY:
(마크다운 본문 — 3,000자 이상, H2 4개 + 표 4개 이상 + 체크리스트, 면책 문구 넣지 말 것)"""

    return system_msg, user_msg


def _parse_response(content):
    """LLM 응답 파싱 — TITLE/BODY 또는 제목/본문 형식 모두 대응"""
    result = {"title": "", "body_md": "", "tags": [], "category": "", "description": ""}

    lines = content.strip().split("\n")
    body_lines = []
    in_body = False

    for line in lines:
        stripped = line.strip()
        low = stripped.lower()

        if low.startswith("title:") or stripped.startswith("제목:"):
            result["title"] = stripped.split(":", 1)[1].strip().strip('"').strip("'").strip()
            continue
        if low.startswith("category:") or stripped.startswith("카테고리:"):
            result["category"] = stripped.split(":", 1)[1].strip()
            continue
        if low.startswith("tags:") or stripped.startswith("태그:"):
            tag_str = stripped.split(":", 1)[1].strip().strip("()[]")
            result["tags"] = [t.strip().strip("'\"") for t in tag_str.split(",") if t.strip()]
            continue
        if low.startswith("description:") or stripped.startswith("설명:"):
            result["description"] = stripped.split(":", 1)[1].strip().strip('"')
            continue
        if low.startswith("body:"):
            in_body = True
            continue

        if stripped.startswith("## ") or in_body:
            in_body = True
            body_lines.append(line)

    result["body_md"] = "\n".join(body_lines).strip()

    if not result["body_md"] and "## " in content:
        first_h2 = content.find("## ")
        result["body_md"] = content[first_h2:].strip()

    if not result["body_md"]:
        result["body_md"] = content.strip()

    if not result["description"] and result["body_md"]:
        clean = result["body_md"].replace("## ", "").strip()
        first_para = clean.split("\n\n")[0] if "\n\n" in clean else clean[:120]
        result["description"] = first_para[:120]

    return result


def _select_service(services, topic_type, published=None, published_svc_ids=None):
    """카테고리 내에서 미발행 + 데이터 풍부한 서비스 우선 선택"""
    if published is None:
        published = set()
    if published_svc_ids is None:
        published_svc_ids = set()

    # 시니어 무관 서비스 제외 (서비스명 기준)
    _EXCLUDE_NAMES = ["청년", "청장년", "미혼모", "미혼부", "영유아", "아동복지", "어린이",
                      "장학금", "대학생", "세대융합", "예비창업", "창업지원", "청소년",
                      "신혼부부", "다자녀", "영아", "산모", "출산"]
    def _is_senior(s) -> bool:
        name = s.get("service_name", "")
        return not any(kw in name for kw in _EXCLUDE_NAMES)

    category_services = [s for s in services if s.get("category") == topic_type and _is_senior(s)]
    if not category_services:
        category_services = [s for s in services if _is_senior(s)][:10]

    def richness(s):
        score = 0
        if s.get("description") and len(s["description"]) > 50:
            score += 2
        if s.get("target") and len(s["target"]) > 20:
            score += 2
        if s.get("support_content") and len(s["support_content"]) > 30:
            score += 3
        if s.get("apply_method") and len(s["apply_method"]) > 20:
            score += 2
        if s.get("apply_url"):
            score += 1
        return score

    # [PATCH] 서비스명 포함 매칭 + 핵심 키워드 중복 체크 (제목만 다른 중복 방지)
    def _is_dup(svc_name, published_set) -> bool:
        if not svc_name:
            return False
        for p in published_set:
            if svc_name in p or p in svc_name:
                return True
            # 핵심 단어 3개 이상 겹치면 중복 간주
            svc_words = set(svc_name.replace("(", " ").replace(")", " ").split())
            pub_words = set(p.replace("(", " ").replace(")", " ").split())
            overlap = svc_words & pub_words
            if len(overlap) >= 3 and len(overlap) / max(len(svc_words), 1) >= 0.5:
                return True
        return False

    unpublished = [
        s for s in category_services
        if not _is_dup(s.get("service_name", ""), published)
        and s.get("service_id", "") not in published_svc_ids
    ]

    if unpublished:
        unpublished.sort(key=richness, reverse=True)
        return unpublished[0]

    category_services.sort(key=richness, reverse=True)
    return category_services[0]


def _get_related_services(services, main_service, topic_type):
    """같은 카테고리 + 같은 지역(또는 전국)의 다른 서비스 추출"""
    main_name = main_service.get("service_name", "")
    main_dept = main_service.get("department", "")

    # 메인 서비스의 지역 토큰 추출
    region_suffixes = ["시", "군", "구"]
    main_tokens = [t for t in main_dept.replace("(", " ").replace(")", " ").split()
                   if any(t.endswith(s) for s in region_suffixes)]

    same_cat = [s for s in services
                if s.get("category") == topic_type and s.get("service_name") != main_name]

    if main_tokens:
        # 지역 한정 서비스 → 같은 지역 서비스만
        local = [s for s in same_cat
                 if any(tok in s.get("department", "") for tok in main_tokens)]
        if local:
            return local[:3]
        # 같은 지역 없으면 전국 서비스(지역 미표기)만
        national = [s for s in same_cat
                    if not any(m in s.get("department", "")
                               for m in ["시 ", "군 ", "구 ", "시)", "군)", "구)"])]
        return national[:3]

    return same_cat[:3]


def _validate_article(result, min_length=1500):
    """글 품질 검증"""
    issues = []
    if not result.get("title"):
        issues.append("제목 없음")
    elif len(result["title"]) < 15:
        issues.append(f"제목 너무 짧음: {len(result['title'])}자")

    body = result.get("body_md", "")
    if len(body) < min_length:
        issues.append(f"본문 부족: {len(body)}/{min_length}자")

    h2_count = len(re.findall(r"^## ", body, re.MULTILINE))
    if h2_count < 4:
        issues.append(f"H2 부족: {h2_count}개")

    vague_phrases = ["다를 수 있습니다", "확인해 보세요", "문의하시기 바랍니다", "참고하시기 바랍니다"]
    vague_count = sum(body.count(p) for p in vague_phrases)
    if vague_count > 3:
        issues.append(f"빈 문장 과다: {vague_count}회")

    return issues


def _clean_vague_phrases(body_md):
    """[PATCH] 금지 표현이 포함된 문장을 통째로 제거"""
    banned = [
        "확인해 보세요", "확인해 보아야", "다를 수 있습니다",
        "도움이 될 것입니다", "도움이 될 수 있습니다",
        "삶의 질을 높일 수 있도록", "더욱 풍요롭게",
        "이러한 제도는", "이와 같은 다양한 제도를 종합적으로",
        "유념하시기 바랍니다", "참고하시기 바랍니다", "권장합니다",
        "준비하는 것이 좋습니다", "미리 체크함으로써",
        "활용할 수 있습니다", "누릴 수 있습니다",
    ]
    lines = body_md.split("\n")
    cleaned = []
    for line in lines:
        if any(phrase in line for phrase in banned):
            stripped = line.strip()
            # H2 제목은 보존
            if stripped.startswith("## "):
                cleaned.append(line)
            # 문장 단위로 제거
            else:
                continue
        else:
            cleaned.append(line)
    return "\n".join(cleaned)


def generate_senior_article(data, topic_type=None, enriched_service=None):
    """시니어 복지 글 생성 — 서비스 단위 심층 글

    enriched_service: pipeline에서 상세 API로 보강된 서비스 (있으면 재선택 안 함)
    """
    today = data.get("today", datetime.now().strftime("%Y년 %m월 %d일"))
    services = data.get("services", [])

    if not topic_type:
        available = list({s["category"] for s in services})
        topic_type = random.choice(available) if available else "생활지원"

    logger.info(f"시니어 글 생성: 토픽={topic_type}")

    if enriched_service and enriched_service.get("support_content"):
        main_service = enriched_service
        logger.info(f"pipeline에서 전달된 enriched 서비스 사용: {main_service.get('service_name', '?')}")
    else:
        main_service = _select_service(services, topic_type)
        main_service = _enrich_service(main_service)

    related = _get_related_services(services, main_service, topic_type)
    related = [_enrich_service(rs) for rs in related]
    logger.info(f"선택 서비스: {main_service.get('service_name', '?')} (관련 {len(related)}건, enriched)")

    system_msg, user_msg = _build_prompt(main_service, topic_type, related, today)

    max_attempts = 2
    for attempt in range(1, max_attempts + 1):
        try:
            ai_result = ai_generate(system_msg, user_msg, tier="default")
            if not ai_result or not ai_result.get("content"):
                raise Exception("ai_generate 빈 응답")
            content = ai_result["content"]
            result = _parse_response(content)

            issues = _validate_article(result)
            if issues:
                logger.info(f"품질 체크 (시도 {attempt}/{max_attempts}): {', '.join(issues)}")
                if attempt < max_attempts and any("본문 부족" in i for i in issues):
                    logger.info("본문 부족 — 재생성 시도")
                    continue

            if not result["title"]:
                result["title"] = main_service.get("service_name", "시니어 복지 정보")
                logger.info(f"제목 없어서 서비스명으로 대체: {result['title']}")
            if len(result["body_md"]) < 500:
                logger.info(f"본문 짧음: {len(result['body_md'])}자 (발행 진행)")

            result["topic_type"] = topic_type
            result["service_id"] = main_service.get("service_id", "")
            result["service_name"] = main_service.get("service_name", "")
            result["department"] = main_service.get("department", "")
            result["thumbnail"] = ""
            logger.info(f"글 생성 완료: {result['title']} ({len(result['body_md'])}자)")

            # [PATCH] 금지 표현 제거 후 링크 추가
            if result.get("body_md"):
                result["body_md"] = _clean_vague_phrases(result["body_md"])
                result["body_md"] = _append_links(
                    result["body_md"], main_service,
                    result.get("category", topic_type or "")
                )
                result["body_md"] = _inject_editorial_synthesis(result["body_md"], {"topic_type": "senior", "topic_id": main_service.get("service_id", "")})
            return result

        except Exception as e:
            logger.exception(f"GPT 호출 실패 (시도 {attempt}): {e}")

    return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from fetcher import fetch_all
    data = fetch_all()
    article = generate_senior_article(data)
    if article:
        print(f"\n제목: {article['title']}")
        print(f"카테고리: {article['category']}")
        print(f"태그: {article['tags']}")
        print(f"본문 길이: {len(article['body_md'])}자")
        print(f"\n{article['body_md'][:800]}...")
