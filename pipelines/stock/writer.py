import os
import json
import logging
import re
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
        context_parts.append(f"업종: {company_info.get('induty_nm', company_info.get('induty_code', ''))}")
        context_parts.append(f"종목코드: {company_info.get('stock_code', '')}")
    if financials:
        key_items = [f for f in financials if any(k in f.get("account_nm", "") for k in ("수익(매출액)", "매출액", "영업이익", "당기순이익", "매출원가", "매출총이익"))][:5]
        for f in key_items[:3]:
            context_parts.append(f"[당기 {f.get('bsns_year', '')}] {f.get('account_nm')}: {f.get('thstrm_amount', '')}원 (전기: {f.get('frmtrm_amount', '')}원)")
    if financials_prev:
        key_prev = [f for f in financials_prev if any(k in f.get("account_nm", "") for k in ("수익(매출액)", "매출액", "영업이익", "당기순이익", "매출원가", "매출총이익"))][:5]
        for f in key_prev[:3]:
            context_parts.append(f"[전전기 {f.get('bsns_year', '')}] {f.get('account_nm')}: {f.get('thstrm_amount', '')}원 (전기: {f.get('frmtrm_amount', '')}원)")
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
- 패턴: "기업명 + 핵심숫자(금액 또는 증감률) + 의미 요약"
- 제공된 데이터의 실제 숫자를 제목에 포함 (매출, 순이익, 증감률 등)
- 예시: "삼성전자 2025 매출 300조 돌파 영업이익은 36% 감소", "카카오 당기순이익 2400억 전년비 15% 증가 의미는"
- 데이터에 없는 숫자는 제목에 넣지 마세요
- 의문형("~일까?") 최대 1회
- 40~50자

[본문 작성 규칙]
1. 첫 문단: 핵심 수치 포함 후킹 문장 + 반드시 "2026년 3월 DART 공시 기준" 명시
2. 본문 3000자 이상, 2500자 미만 불합격
3. H2 헤딩 정확히 5개, 각 섹션 최소 5문장, 자연스러운 소제목 (예: "이 회사가 하는 일", "실적은 어땠나", "지금 투자해도 될까")
4. 금액은 읽기 쉽게 표현 (12,432,454,206원 → 약 124억 원)
5. 전문 용어는 괄호로 쉬운 설명 추가
6. 구체적인 투자 판단 근거 제시 (PER, PBR, 동종업계 비교)
7. 리스크 요인도 균형있게 서술
8. 마지막에 "※ 본 글은 투자 권유가 아니며, 투자 판단은 본인의 책임입니다." 포함
9. 마크다운 형식, H1(#) 사용 금지
10. "함께 읽어보기", "관련 글" 등 내부링크 섹션 절대 금지
11. 다른 블로그 글 URL 절대 생성 금지
12. 데이터에 없는 수치(PER, PBR, 주가 등) 절대 날조 금지. 재무 0건이면 "DART 공시 미확인" 명시
13. 비교 표에 데이터 없는 행 금지 (TBD/N/A 행 금지)

[출력 형식]
TITLE: (제목)
CATEGORY: (카테고리 1개: 공시분석/실적분석/배당분석/IPO분석/ETF분석/시장분석 중 택1)
TAGS: (쉼표로 구분, 5개 이내)
DESC: (검색결과에 표시될 150자 이내 설명문. 핵심 수치 포함)
BODY:
(본문 마크다운)"""

    api_key = os.getenv("OPENAI_API_KEY", "")
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": OPENAI_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 8000,
            "temperature": 0.7,
        },
        timeout=60,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    parsed = _parse_response(content)
    if parsed.get("body_md") and len(parsed["body_md"]) < 2500:
        logger.info(f"disclosure 글자수 미달 ({len(parsed['body_md'])}자), 재생성")
        _retry = prompt + "\n\n[경고] 이전 응답이 2500자 미만. 3000자 이상, H2 5개, 각 섹션 5문장 이상 필수."
        _r2 = requests.post("https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": OPENAI_MODEL, "messages": [{"role": "user", "content": _retry}], "max_tokens": 8000, "temperature": 0.7}, timeout=60)
        _r2.raise_for_status()
        _p2 = _parse_response(_r2.json()["choices"][0]["message"]["content"])
        if _p2.get("body_md") and len(_p2["body_md"]) > len(parsed["body_md"]):
            parsed = _p2
    return parsed


def generate_evergreen_article(topic_type, corp_data=None, extra_data=None):
    prompts = {
        "dividend_ranking": """배당주 투자 전략과 고배당주를 고르는 방법을 설명하는 블로그 글을 작성하세요.

[필수 포함 내용]
1. 배당수익률 계산법 (배당금 / 주가 x 100) 단계별 예시
2. 배당성향과 배당성장률의 차이: 배당성향 100% 초과 시 리스크 경고 명시
3. 배당락일 전후 매매 전략
4. 제공 데이터가 있으면 배당률 TOP10 표 작성 (배당률 내림차순 정렬)
5. 1000만원 투자 시 예상 배당금 시뮬레이션 (계산 과정 단계별 표시)
6. 배당성향 이상치(200% 이상) 종목은 별도 리스크 분석

[주의]
- 배당금 기준일 컬럼 필수 포함
- 구체적인 종목명이나 수치는 제공된 데이터가 있을 때만 사용""",
        "etf_comparison": """국내 인기 ETF를 비교 분석하는 블로그 글을 작성하세요.

[필수 포함 내용]
1. 수익률 상위 TOP10: 등락률 양수(+) 종목만 선정, 등락률 내림차순 정렬
2. 수익률 하위 TOP10: 등락률 음수(-) 종목만 선정, 등락률 오름차순 정렬
3. 동일 ETF가 상위/하위 양쪽에 중복 등장 금지
4. 보수비용(TER)은 제공 데이터에 실제 수치가 있을 때만 표기. 데이터에 TER이 없으면 보수비용 컬럼 자체를 표에서 제외
5. 거래량 급증 ETF 별도 분석 (거래량 상위 종목). 반드시 별도 H2 헤딩("## 거래량 급증 ETF")으로 작성
6. KODEX, TIGER, SOL 등 운용사별 대표 ETF 수익률/거래량 비교. 보수비용 데이터가 없으면 보수비용 컬럼 제외하고 수익률과 거래량만으로 표 구성. 빈 표(헤더만 있는 표) 절대 금지

[주의]
- 등락률이 전부 음수라면 "상위 TOP10" 대신 "하락폭이 적은 ETF TOP10"으로 제목 수정
- 실제 데이터에 없는 TER 수치 절대 날조 금지""",
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

    if extra_data and isinstance(extra_data, dict):
        if extra_data.get("gainers"):
            base_prompt += "\n\n[실시간 ETF 수익률 상위 데이터]\n"
            for g in extra_data["gainers"][:10]:
                base_prompt += f"- {g['name']}: 등락률 {g['change_rate']}%, 현재가 {g['price']:,}원, 거래량 {g['volume']:,}\n"
        if extra_data.get("losers"):
            base_prompt += "\n[실시간 ETF 수익률 하위 데이터]\n"
            for l in extra_data["losers"][:10]:
                base_prompt += f"- {l['name']}: 등락률 {l['change_rate']}%, 현재가 {l['price']:,}원, 거래량 {l['volume']:,}\n"
        if extra_data.get("volume_top"):
            base_prompt += "\n[거래량 상위 ETF]\n"
            for v in extra_data["volume_top"][:5]:
                base_prompt += f"- {v['name']}: 거래량 {v['volume']:,}, 등락률 {v['change_rate']}%\n"
        base_prompt += "\n위 데이터는 네이버 금융 실시간 API 기준입니다. 이 수치만 사용하고 날조하지 마세요."

    prompt = f"""당신은 네이버 증권 인기 블로거이자 전직 증권사 애널리스트입니다.

{base_prompt}

[제목 작성 규칙]
- 패턴: "비교 대상 + 핵심 수치 + 결론 힌트", 제공 데이터의 실제 숫자 1개 이상 포함
- 예시: "2026년 고배당주 TOP 10 연 8% 수익 가능한 종목은", "KODEX vs TIGER ETF 수수료 0.01% 차이가 만드는 수익률 격차"
- 50자 이내

[본문 작성 규칙]
1. 첫 문단: 핵심 데이터 포인트 포함 후킹 문장 + "2026년 3월 기준" 반드시 명시
2. 본문 3000자 이상, 2500자 미만 불합격
3. H2 헤딩 정확히 5개, 각 섹션 최소 5문장
4. 금액은 읽기 쉽게 (억 원, 만 원 단위)
5. 비교 표 최소 1개 필수. 표 앞뒤 빈 줄 필수. 수치 칸에 "TBD" 절대 금지, 데이터 없으면 해당 행 제외
6. 구체적 종목명과 수치 포함. 수학 계산(배당금, 수익률 시뮬레이션)은 반드시 단계별 표시 후 검증
7. "※ 본 글은 투자 권유가 아니며, 투자 판단은 본인의 책임입니다." 포함
8. 마크다운 형식, H1(#) 사용 금지
9. 2026년 3월 기준 최신 정보로 작성
10. "함께 읽어보기", "관련 글" 등 내부링크 섹션 절대 금지
11. 다른 블로그 글 URL 절대 생성 금지
12. 데이터에 없는 수치(PER, PBR, 주가 등) 절대 날조 금지. 재무 0건이면 "DART 공시 미확인" 명시
13. 비교 표에 데이터 없는 행 금지 (TBD/N/A 행 금지)
12. 제공 데이터에 없는 수치 절대 날조 금지. 재무 0건이면 "DART 공시 미확인" 명시
13. 데이터 미제공 시 방법론/전략 중심 작성, 빈 수치 표 금지
14. 비교 표에 TBD/N/A 행 절대 금지. 있는 데이터만 표에 포함

[출력 형식]
TITLE: (제목)
CATEGORY: (카테고리 1개: 공시분석/실적분석/배당분석/IPO분석/ETF분석/시장분석 중 택1)
TAGS: (쉼표로 구분, 5개 이내)
DESC: (검색결과에 표시될 150자 이내 설명문. 핵심 수치 포함)
BODY:
(본문 마크다운)"""

    api_key = os.getenv("OPENAI_API_KEY", "")
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": OPENAI_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 8000,
            "temperature": 0.7,
        },
        timeout=60,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    parsed = _parse_response(content)
    if parsed.get("body_md") and len(parsed["body_md"]) < 2500:
        logger.info(f"evergreen 글자수 미달 ({len(parsed['body_md'])}자), 재생성")
        _retry = prompt + "\n\n[경고] 이전 응답 2500자 미만. 3000자 이상, H2 5개, 각 섹션 5문장 이상 필수."
        _r2 = requests.post("https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": OPENAI_MODEL, "messages": [{"role": "user", "content": _retry}], "max_tokens": 8000, "temperature": 0.7}, timeout=60)
        _r2.raise_for_status()
        _p2 = _parse_response(_r2.json()["choices"][0]["message"]["content"])
        if _p2.get("body_md") and len(_p2["body_md"]) > len(parsed["body_md"]):
            parsed = _p2
    return parsed


def _parse_response(content):
    title = ""
    category = ""
    tags = ""
    desc = ""
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
        elif line.startswith("DESC:"):
            desc = line.replace("DESC:", "").strip()
        elif line.startswith("BODY:"):
            body_start = True
        elif body_start:
            body_lines.append(line)

    body = "\n".join(body_lines).strip()
    # H3 -> H2 통일
    body = re.sub(r"^### ", "## ", body, flags=re.MULTILINE)
    # 거래량 급증 섹션에 H2 없으면 추가
    if "거래량" in body and not re.search(r"^## .*거래량", body, re.MULTILINE):
        body = body.replace("\n거래량 급증 ETF는", "\n## 거래량 급증 ETF\n\n거래량 급증 ETF는")
        body = body.replace("\n거래량이 전일", "\n## 거래량 급증 ETF\n\n거래량이 전일")
    # 빈 테이블 제거 (헤더+구분선만 있고 데이터행 없는 경우)
    _table_lines = body.split("\n")
    _cleaned = []
    i = 0
    while i < len(_table_lines):
        if _table_lines[i].startswith("|") and i + 1 < len(_table_lines) and re.match(r"^\|[-| :]+\|$", _table_lines[i + 1]):
            if i + 2 >= len(_table_lines) or not _table_lines[i + 2].startswith("|"):
                i += 2
                continue
        _cleaned.append(_table_lines[i])
        i += 1
    body = "\n".join(_cleaned)

    if not title and body:
        for line in body_lines:
            if line.startswith("# "):
                title = line.replace("# ", "").strip()
                break

    # 후처리: "함께 읽어보기" 제거

    _cut = re.search(r"\n## 함께 읽어보기", body)
    if _cut:
        body = body[:_cut.start()]
    _cut2 = re.search(r"\n## 관련 글", body)
    if _cut2:
        body = body[:_cut2.start()]

    # TBD 포함 표 행 제거
    _blines = body.split("\n")
    _blines = [ln for ln in _blines if not (ln.strip().startswith("|") and "TBD" in ln)]
    body = "\n".join(_blines)

    # 표 전후 빈 줄 보장
    _out = []
    _blines2 = body.split("\n")
    for _i, _ln in enumerate(_blines2):
        if _ln.strip().startswith("|") and _i > 0 and _out and not _out[-1].strip().startswith("|") and _out[-1].strip() != "":
            _out.append("")
        _out.append(_ln)
        if _ln.strip().startswith("|") and _i + 1 < len(_blines2) and not _blines2[_i + 1].strip().startswith("|") and _blines2[_i + 1].strip() != "":
            _out.append("")
    body = "\n".join(_out)

    return {
        "title": title,
        "category": category,
        "tags": tags,
        "body_md": body,
        "description": desc,
    }
