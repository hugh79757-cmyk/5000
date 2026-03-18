import os
import json
import logging
import requests

logger = logging.getLogger(__name__)

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


def generate_disclosure_article(disclosure, company_info=None, financials=None, financials_prev=None, dividend=None):
    corp_name = disclosure.get("corp_name", "")
    report_nm = disclosure.get("report_nm", "")
    rcept_dt = disclosure.get("rcept_dt", "")

    context_parts = [
        f"기업명: {corp_name}",
        f"공시명: {report_nm}",
        f"접수일: {rcept_dt}",
    ]
    if company_info:
        context_parts.append(f"CEO: {company_info.get('ceo_nm', '')}")
        context_parts.append(f"업종: {company_info.get('induty_code', '')}")
        context_parts.append(f"종목코드: {company_info.get('stock_code', '')}")
    if financials:
        key_items = [f for f in financials if any(k in f.get("account_nm", "") for k in ("수익(매출액)", "매출액", "영업이익", "당기순이익", "매출원가", "매출총이익"))][:5]
        for f in key_items[:3]:
            context_parts.append(f"[당기] {f.get('account_nm')}: {f.get('thstrm_amount', '')}원")
    if financials_prev:
        key_prev = [f for f in financials_prev if any(k in f.get("account_nm", "") for k in ("수익(매출액)", "매출액", "영업이익", "당기순이익", "매출원가", "매출총이익"))][:5]
        for f in key_prev[:3]:
            context_parts.append(f"[전기] {f.get('account_nm')}: {f.get('thstrm_amount', '')}원")
    if dividend and isinstance(dividend, dict):
        for item in dividend.get("list", [])[:3]:
            context_parts.append(f"배당: {item.get('se_nm', '')} {item.get('thstrm', '')}원")

    context = "\n".join(context_parts)

    prompt = f"""당신은 네이버 증권 인기 블로거이자 전직 증권사 애널리스트입니다.
아래 DART 공시 데이터를 바탕으로 블로그 글을 작성하세요.

[핵심 원칙]
- 아래 제공된 데이터에 있는 수치만 사용하세요
- 데이터에 없는 주가, 금리, PER, PBR 등의 숫자를 절대 지어내지 마세요
- "함께 읽어보기", "관련 글" 등 내부링크 섹션을 절대 만들지 마세요
- 제공된 재무 데이터를 적극 활용하여 전기 대비 증감률, 영업이익률 등을 직접 계산해서 분석하세요

[공시 정보]
{context}

[제목 작성 규칙]
- "기업명 + 공시 핵심 + 데이터 기반 숫자" 패턴 사용
- 제공된 데이터의 실제 숫자를 제목에 포함 (매출, 순이익, 증감률 등)
- 예시: "삼성전자 2025 매출 300조 돌파 영업이익은 36% 감소", "카카오 당기순이익 2400억 전년비 15% 증가 의미는"
- 데이터에 없는 숫자는 제목에 넣지 마세요
- 50자 이내

[본문 작성 규칙]
1. 첫 문단에서 독자의 관심을 사로잡는 후킹 문장으로 시작 (질문형 또는 충격적 사실)
2. 본문 3000자 이상
3. H2 헤딩 4~6개, 자연스러운 소제목 (예: "이 회사가 하는 일", "실적은 어땠나", "지금 투자해도 될까")
4. 금액은 읽기 쉽게 표현 (12,432,454,206원 → 약 124억 원)
5. 전문 용어는 괄호로 쉬운 설명 추가
6. 구체적인 투자 판단 근거 제시 (PER, PBR, 동종업계 비교)
7. 리스크 요인도 균형있게 서술
8. 마지막에 "※ 본 글은 투자 권유가 아니며, 투자 판단은 본인의 책임입니다." 포함
9. 마크다운 형식, H1(#) 사용 금지
10. 절대 "함께 읽어보기", "관련 글", "추천 글" 같은 내부링크 섹션을 만들지 마세요
11. 다른 블로그 글 URL을 절대 생성하지 마세요

[출력 형식]
TITLE: (제목)
CATEGORY: (카테고리 1개: 공시분석/실적분석/배당분석/IPO분석/ETF분석/시장분석 중 택1)
TAGS: (쉼표로 구분, 5개 이내)
BODY:
(본문 마크다운)"""

    api_key = os.getenv("OPENAI_API_KEY", "")
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": OPENAI_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4000,
            "temperature": 0.7,
        },
        timeout=60,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return _parse_response(content)


def generate_evergreen_article(topic_type, corp_data=None, extra_data=None):
    prompts = {
        "dividend_ranking": """배당주 투자 전략과 고배당주를 고르는 방법을 설명하는 블로그 글을 작성하세요.
배당수익률 계산법, 배당성향과 배당성장률의 차이, 배당락일 전후 전략, 배당 ETF 활용법을 다루세요.
구체적인 종목명이나 수치는 제공된 데이터가 있을 때만 사용하세요.""",
        "etf_comparison": """국내 인기 ETF를 비교 분석하는 블로그 글을 작성하세요.
KODEX, TIGER, SOL 등 운용사별 대표 ETF의 수익률, 보수, 구성종목을 비교하세요.""",
        "sector_analysis": """한국 주식시장에서 PER과 PBR을 활용해 저평가 종목을 찾는 방법을 설명하는 블로그 글을 작성하세요.
PER/PBR 개념 설명, 업종별 평균 PER이 다른 이유, 저PBR 투자 전략(밸류 트랩 주의점 포함), 실제 스크리닝 방법(HTS/MTS 활용법)을 다루세요.
구체적인 종목명이나 수치는 제공된 데이터가 없으면 사용하지 마세요.""",
        "ipo_schedule": """공모주(IPO) 투자 방법과 청약 전략을 설명하는 블로그 글을 작성하세요.
공모주 청약 절차, 균등배정/비례배정 차이, 증거금 계산법, 상장일 매도 전략, 공모주 분석 시 확인할 항목(증권신고서 핵심 체크포인트)을 다루세요.
구체적인 종목명이나 일정은 제공된 데이터가 있을 때만 사용하세요.""",
        "cma_savings": """CMA 및 예금 금리 비교 분석 글을 작성하세요.
증권사별 CMA 금리, 은행 예금 금리를 비교하고 최적 전략을 제시하세요.""",
    }

    base_prompt = prompts.get(topic_type, prompts["dividend_ranking"])

    if corp_data:
        base_prompt += f"\n\n참고 기업 데이터: {json.dumps(corp_data, ensure_ascii=False)[:1000]}"

    prompt = f"""당신은 네이버 증권 인기 블로거이자 전직 증권사 애널리스트입니다.

{base_prompt}

[제목 작성 규칙]
- 클릭을 유도하는 흥미로운 제목, 숫자 반드시 포함
- 예시: "2026년 고배당주 TOP 10 연 8% 수익 가능한 종목은", "KODEX vs TIGER ETF 수수료 0.01% 차이가 만드는 수익률 격차"
- 50자 이내

[본문 작성 규칙]
1. 첫 문단에서 독자의 관심을 사로잡는 후킹 문장
2. 본문 3000자 이상
3. H2 헤딩 4~6개, 대화체 소제목
4. 금액은 읽기 쉽게 (억 원, 만 원 단위)
5. 비교 표가 있으면 마크다운 테이블 사용
6. 구체적 종목명과 수치 포함
7. "※ 본 글은 투자 권유가 아니며, 투자 판단은 본인의 책임입니다." 포함
8. 마크다운 형식, H1(#) 사용 금지
9. 2026년 3월 기준 최신 정보로 작성
10. 절대 "함께 읽어보기", "관련 글", "추천 글" 같은 내부링크 섹션을 만들지 마세요
11. 다른 블로그 글 URL을 절대 생성하지 마세요
12. [중요] 제공된 데이터에 없는 수치(금리, PER, PBR, 배당률, 주가, 수익률 등)를 절대 지어내지 마세요. 구체적 숫자가 필요한 곳에는 "○○증권 홈페이지에서 최신 금리를 확인하세요" 식으로 안내하세요
13. 데이터가 제공되지 않은 경우, 구체적 수치 대신 분석 방법론과 투자 전략 중심으로 작성하세요

[출력 형식]
TITLE: (제목)
CATEGORY: (카테고리 1개: 공시분석/실적분석/배당분석/IPO분석/ETF분석/시장분석 중 택1)
TAGS: (쉼표로 구분, 5개 이내)
BODY:
(본문 마크다운)"""

    api_key = os.getenv("OPENAI_API_KEY", "")
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": OPENAI_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4000,
            "temperature": 0.7,
        },
        timeout=60,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return _parse_response(content)


def _parse_response(content):
    title = ""
    category = ""
    tags = ""
    body = ""

    lines = content.strip().split("\n")
    body_start = False
    body_lines = []

    for line in lines:
        if line.startswith("TITLE:"):
            title = line.replace("TITLE:", "").strip().strip('"')
        elif line.startswith("CATEGORY:"):
            category = line.replace("CATEGORY:", "").strip()
        elif line.startswith("TAGS:"):
            tags = line.replace("TAGS:", "").strip()
        elif line.startswith("BODY:"):
            body_start = True
        elif body_start:
            body_lines.append(line)

    body = "\n".join(body_lines).strip()

    if not title and body:
        for line in body_lines:
            if line.startswith("# "):
                title = line.replace("# ", "").strip()
                break

    return {
        "title": title,
        "category": category,
        "tags": tags,
        "body_md": body,
    }
