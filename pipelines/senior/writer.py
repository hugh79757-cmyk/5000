"""시니어 복지 글 생성 v2 — 서비스 단위 심층 글, 데이터 기반 강제"""

import os
import re
import random
import logging
from datetime import datetime
from openai import OpenAI
from shared.ai_writer import generate as ai_generate

logger = logging.getLogger(__name__)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# 카테고리별 글 구조 템플릿
ARTICLE_STRUCTURES = {
    "의료지원": {
        "sections": ["대상자 조건과 지원 내용", "신청 방법과 필요 서류", "신청 전 반드시 확인할 점", "관련 제도 비교와 활용 팁"],
        "angle": "어르신이 직접 읽고 바로 신청할 수 있도록 쉽고 구체적으로 안내",
    },
    "돌봄서비스": {
        "sections": ["서비스 내용과 이용 대상", "비용과 신청 절차", "이용 시 주의사항", "함께 알아두면 좋은 제도"],
        "angle": "어르신과 가족이 돌봄서비스를 쉽게 이해하고 신청할 수 있도록 안내",
    },
    "교통복지": {
        "sections": ["혜택 내용과 적용 범위", "신청 방법과 필요 서류", "이용 시 주의할 점", "더 알뜰하게 쓰는 방법"],
        "angle": "교통비를 아낄 수 있는 구체적 방법과 신청 절차를 쉽게 안내",
    },
    "일자리금융": {
        "sections": ["참여 조건과 급여 내용", "신청 방법과 선발 기준", "참여 전 꼭 확인할 점", "관련 제도 함께 활용하기"],
        "angle": "시니어 일자리와 금융 지원의 조건, 급여, 신청법을 현실적으로 안내",
    },
    "문화여가": {
        "sections": ["혜택 내용과 지원 금액", "신청 방법과 이용 시설", "이용 시 유의사항", "이렇게 활용하면 더 좋습니다"],
        "angle": "어르신이 문화생활을 즐길 수 있는 혜택과 신청법을 친근하게 안내",
    },
    "연금생활지원": {
        "sections": ["수급 조건과 지급 금액", "신청 방법과 필요 서류", "자주 묻는 질문", "함께 받을 수 있는 제도"],
        "angle": "연금과 생활지원금의 금액, 자격, 신청법을 명확하게 안내",
    },
    "생활지원": {
        "sections": ["지원 내용과 대상 조건", "신청 절차와 구비서류", "놓치기 쉬운 주의사항", "같이 신청하면 좋은 제도"],
        "angle": "생활에 도움이 되는 지원 제도의 조건과 신청법을 알기 쉽게 안내",
    },
}


# 쿠팡 파트너스 카테고리별 추천
COUPANG_PARTNER_IDFF = os.getenv("COUPANG_PARTNER_ID", "")
COUPANG_CATEGORY = {
    "의료지원": "어르신 건강용품 보기",
    "돌봄서비스": "간병 돌봄용품 보기",
    "교통복지": "보행보조용품 보기",
    "생활지원": "어르신 생활용품 보기",
    "연금생활지원": "건강식품 보기",
    "일자리금융": "취업준비용품 보기",
    "문화여가": "여가 취미용품 보기",
}

def _append_links(body_md, service, category):
    """본문 끝에 정부 신청 버튼 + 쿠팡 링크 삽입"""
    from dotenv import load_dotenv as _ld
    _ld("/Users/twinssn/Projects/5000/.env")
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
    elif svc_id:
        url = f"https://www.gov.kr/portal/rcvfvrSvc/dtlEx/{svc_id}"
    else:
        url = "https://www.bokjiro.go.kr"
    dept = service.get("department", "")
    btn_text = f"{dept}에서 신청하기" if dept else "온라인으로 신청하기"
    parts.append(f'\n\n{{{{< btn url="{url}" text="{btn_text}" >}}}}')

    # 2) 쿠팡 파트너스
    coupang_id = os.getenv("COUPANG_PARTNER_ID", "")
    if coupang_id:
        c_text = COUPANG_CATEGORY.get(category, "어르신 생활용품 보기")
        c_url = f"https://link.coupang.com/a/{coupang_id}"
        parts.append(f'\n\n{{{{< coupang url="{c_url}" text="{c_text}" >}}}}')

    # 3) 면책 1회
    parts.append("\n\n---")
    parts.append("\n\n> 이 글은 정부24 공공데이터를 기반으로 작성되었습니다. 최신 정보는 [복지로](https://www.bokjiro.go.kr)에서 확인하세요.")

    return body_md + "".join(parts)


def _build_data_block(service):
    """단일 서비스의 상세 데이터 블록 구성"""
    fields = []
    fields.append(f"서비스명: {service.get('service_name', '미정')}")
    fields.append(f"서비스ID: {service.get('service_id', '')}")
    if service.get('description'):
        fields.append(f"서비스 설명: {service['description']}")
    if service.get('target'):
        fields.append(f"지원 대상: {service['target']}")
    if service.get('support_content'):
        fields.append(f"지원 내용: {service['support_content']}")
    if service.get('apply_method'):
        fields.append(f"신청 방법: {service['apply_method']}")
    if service.get('apply_url'):
        fields.append(f"신청 URL: {service['apply_url']}")
    if service.get('department'):
        fields.append(f"소관기관: {service['department']}")
    if service.get('contact'):
        fields.append(f"문의처: {service['contact']}")
    if service.get('law_basis'):
        fields.append(f"법적 근거: {service['law_basis']}")
    if service.get('purpose'):
        fields.append(f"서비스목적: {service['purpose']}")
    if service.get('selection_criteria'):
        fields.append(f"선정기준: {service['selection_criteria']}")
    if service.get('documents'):
        fields.append(f"구비서류: {service['documents']}")
    if service.get('deadline'):
        fields.append(f"신청기한: {service['deadline']}")
    if service.get('apply_method_detail'):
        fields.append(f"상세 신청방법: {service['apply_method_detail']}")
    if service.get('reception_agency'):
        fields.append(f"접수기관: {service['reception_agency']}")
    if service.get('support_type'):
        fields.append(f"지원유형: {service['support_type']}")
    return "\n".join(fields)


def _build_prompt(service, topic_type, related_services, today):
    """단일 서비스 중심 심층 글 프롬프트"""
    structure = ARTICLE_STRUCTURES.get(topic_type, ARTICLE_STRUCTURES["생활지원"])
    service_name = service.get("service_name", "시니어 복지 제도")

    main_data = _build_data_block(service)

    related_block = ""
    if related_services:
        related_items = []
        for rs in related_services[:3]:
            related_items.append(f"- {rs.get('service_name', '')}: {rs.get('description', '')[:100]}")
        related_block = "\n\n[관련 서비스]\n" + "\n".join(related_items)

    sections_guide = "\n".join([f"## {i+1}. {s}" for i, s in enumerate(structure["sections"])])

    system_msg = f"""당신은 65세 이상 어르신과 그 가족을 위한 복지 정보 전문 블로거입니다.

오늘 날짜: {today}

당신의 임무: "{service_name}" 제도에 대해, {structure['angle']}하는 글을 작성합니다.

핵심 전략 — 롱테일 SEO:
이 글은 대형 포털이나 정부 사이트와 경쟁하지 않습니다. "기초연금 신청방법" 같은 대형 키워드 대신, 구체적 상황·조건·질문을 담은 세부 키워드를 노립니다.

제목 규칙 (가장 중요):
- 대형 키워드를 피하고, 구체적 조건+상황+질문 조합으로 작성하세요.
- 나쁜 예 (대형 키워드, 경쟁 불가):
  "기초연금 신청방법 총정리"
  "노인 임플란트 무료 지원 안내"
  "치매 치료비 지원 제도"
- 좋은 예 (롱테일, 경쟁 낮음):
  "기초연금 받으면서 일하면 감액될까? 소득 기준 정리"
  "만 65세 임플란트 본인부담금 얼마? 의료급여 1종 2종 차이"
  "치매 진단 받았는데 치료비 지원 어떻게 신청하나요"
  "혼자 사는 어르신 방문건강관리 신청하는 법"
  "노인 무릎수술 지원받으려면 소득 기준이 어떻게 되나요"
- 규칙: 제공된 데이터에서 대상자 조건, 금액, 신청방법 중 가장 구체적인 정보를 골라 제목에 넣으세요.
- 질문형("~할까?", "~되나요?", "~인가요?") 또는 조건형("~인 경우", "~대상자")을 활용하세요.
- 25~50자로 작성하세요.

글쓰기 원칙:
1. 제공된 데이터(서비스명, 대상, 지원내용, 신청방법, 소관기관)를 반드시 본문에 인용하세요.
2. 데이터에 없는 금액, 날짜, 기관명, 통계를 절대 지어내지 마세요.
3. 어려운 행정 용어는 괄호 안에 쉬운 설명을 덧붙이세요.
4. "확인해 보세요", "다를 수 있습니다" 같은 빈 문장을 쓰지 마세요.
5. 존댓말(합니다/입니다 체), 친근한 톤.
6. 과거 연도(2023~2025년)를 현재처럼 쓰지 마세요.

본문 구조:
{sections_guide}
- 각 H2 섹션은 최소 8문장, 500자 이상으로 충분히 서술
- 전체 본문 반드시 3,000자 이상. 2,200자 미만 절대 불합격
- 마지막에 "이 글은 정부24 공공데이터를 기반으로 작성되었습니다. 최신 정보는 복지로(www.bokjiro.go.kr)에서 확인하세요."로 마무리

SEO:
- 태그: 사람들이 실제로 검색할 세부 키워드 5~7개. 대형 키워드("기초연금")가 아니라 롱테일("기초연금 소득기준 초과", "기초연금 부부 감액")을 쓰세요.
- 카테고리: {topic_type}
- description: 구체적 상황+핵심 답변을 1문장으로 (80~120자)"""

    user_msg = f"""아래 데이터를 기반으로 글을 작성하세요.

[메인 서비스 데이터]
{main_data}
{related_block}

[분량 규칙 — 반드시 준수]
- 전체 본문 3,000자 이상. 2,200자 미만은 절대 불합격.
- 각 H2 섹션은 최소 8문장, 350자 이상.
- H2는 정확히 4개. 각 H2마다 구체적 데이터를 인용하며 충분히 서술하세요.
- 위 데이터의 지원내용, 문의처, 법적 근거, 신청방법을 본문에 반드시 포함하세요.
- 짧게 끝내지 마세요. 부족하면 실제 신청 시 주의사항, 자주 하는 실수, 비슷한 제도와 차이점을 추가 서술하세요.

출력 형식 (반드시 이 형식을 지키세요):
TITLE: (제목 — 25~50자, 구체적 조건+질문형)
CATEGORY: {topic_type}
TAGS: (롱테일 태그 5~7개, 괄호 없이)
DESCRIPTION: (80~120자, 핵심 정보 1줄 요약)
BODY:
(본문 마크다운 — 반드시 3,000자 이상)"""

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
    
        # 링크 삽입
        if result.get('body_md'):
            result['body_md'] = _append_links(
                result['body_md'], main_service,
                result.get('category', topic_type or '')
            )
    return result


def _select_service(services, topic_type, published=None):
    """카테고리 내에서 미발행 + 데이터 풍부한 서비스 우선 선택"""
    if published is None:
        published = set()

    category_services = [s for s in services if s.get("category") == topic_type]
    if not category_services:
        category_services = services[:10]

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

    unpublished = [s for s in category_services if not any(s.get("service_name", "") in p for p in published)]

    if unpublished:
        unpublished.sort(key=richness, reverse=True)
        return unpublished[0]

    category_services.sort(key=richness, reverse=True)
    return category_services[0]


def _get_related_services(services, main_service, topic_type):
    """같은 카테고리의 다른 서비스 추출"""
    main_name = main_service.get("service_name", "")
    return [
        s for s in services
        if s.get("category") == topic_type and s.get("service_name") != main_name
    ][:3]


def _validate_article(result, min_length=2000):
    """글 품질 검증"""
    issues = []
    if not result.get("title"):
        issues.append("제목 없음")
    elif len(result["title"]) < 15:
        issues.append(f"제목 너무 짧음: {len(result['title'])}자")

    body = result.get("body_md", "")
    if len(body) < min_length:
        issues.append(f"본문 부족: {len(body)}/{min_length}자")

    h2_count = len(re.findall(r'^## ', body, re.MULTILINE))
    if h2_count < 4:
        issues.append(f"H2 부족: {h2_count}개")

    vague_phrases = ["다를 수 있습니다", "확인해 보세요", "문의하시기 바랍니다", "참고하시기 바랍니다"]
    vague_count = sum(body.count(p) for p in vague_phrases)
    if vague_count > 3:
        issues.append(f"빈 문장 과다: {vague_count}회")

    return issues


def generate_senior_article(data, topic_type=None):
    """시니어 복지 글 생성 — 서비스 단위 심층 글"""
    today = data.get("today", datetime.now().strftime("%Y년 %m월 %d일"))
    services = data.get("services", [])

    if not topic_type:
        available = list(set(s["category"] for s in services))
        topic_type = random.choice(available) if available else "생활지원"

    logger.info(f"시니어 글 생성: 토픽={topic_type}")

    main_service = _select_service(services, topic_type)
    related = _get_related_services(services, main_service, topic_type)
    logger.info(f"선택 서비스: {main_service.get('service_name', '?')} (관련 {len(related)}건)")

    system_msg, user_msg = _build_prompt(main_service, topic_type, related, today)

    max_attempts = 1
    for attempt in range(1, max_attempts + 1):
        try:
            ai_result = ai_generate(system_msg, user_msg, tier="default")
            if not ai_result or not ai_result.get("content"):
                raise Exception("ai_generate 빈 응답")
            content = ai_result["content"]
            result = _parse_response(content)

            issues = _validate_article(result)
            if issues:
                logger.info(f"품질 참고: {', '.join(issues)}")

            if issues:
                logger.warning(f"최종 품질: {', '.join(issues)} (자동 보정 진행)")

            if not result["title"]:
                result["title"] = main_service.get("service_name", "시니어 복지 정보")
                logger.info(f"제목 없어서 서비스명으로 대체: {result['title']}")
            if len(result["body_md"]) < 500:
                logger.info(f"본문 짧음: {len(result['body_md'])}자 (발행 진행)")

            result["topic_type"] = topic_type
            result["thumbnail"] = ""
            logger.info(f"글 생성 완료: {result['title']} ({len(result['body_md'])}자)")

            # 정부 신청 버튼 + 쿠팡 링크 삽입
            if result.get('body_md'):
                result['body_md'] = _append_links(
                    result['body_md'], main_service,
                    result.get('category', topic_type or '')
                )
            return result

        except Exception as e:
            logger.error(f"GPT 호출 실패 (시도 {attempt}): {e}")

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
