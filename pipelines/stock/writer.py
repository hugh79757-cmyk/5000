import json
import logging
import re

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
    def _to_uk(val_str):
        """원 단위 문자열 → 억 원 변환"""
        try:
            v = int(str(val_str).replace(",", ""))
            uk = v / 1e8
            return f"약 {uk:.1f}억 원"
        except (ValueError, TypeError):
            return str(val_str)

    def _yoy(t_str, f_str) -> str:
        """YoY 증감률 계산"""
        try:
            t = int(str(t_str).replace(",", ""))
            f = int(str(f_str).replace(",", ""))
            if f != 0:
                return f" (YoY {(t-f)/abs(f)*100:+.1f}%)"
        except (ValueError, TypeError):
            pass
        return ""

    if financials:
        _KEY_ORDER = ["수익(매출액)", "매출액", "영업수익", "매출원가", "매출총이익",
                      "영업이익", "영업이익(손실)", "당기순이익", "당기순이익(손실)"]
        # 중복 제거: account_nm 기준 첫 번째만 사용
        _seen = {}
        for f in financials:
            nm = f.get("account_nm", "")
            if nm in _KEY_ORDER and nm not in _seen:
                _seen[nm] = f
        # 순서대로 정렬
        key_items = [_seen[k] for k in _KEY_ORDER if k in _seen]
        revenue_t = revenue_f = op_t = op_f = None
        for f in key_items:
            nm = f.get("account_nm", "")
            t_str = f.get("thstrm_amount", "")
            f_str = f.get("frmtrm_amount", "")
            yoy = _yoy(t_str, f_str)
            context_parts.append(
                f"[당기 {f.get('bsns_year', '')}] {nm}: {_to_uk(t_str)} | 전기: {_to_uk(f_str)}{yoy}"
            )
            try:
                if nm in ("수익(매출액)", "매출액", "영업수익"):
                    revenue_t = int(str(t_str).replace(",", ""))
                    revenue_f = int(str(f_str).replace(",", ""))
                if nm in ("영업이익", "영업이익(손실)"):
                    op_t = int(str(t_str).replace(",", ""))
                    op_f = int(str(f_str).replace(",", ""))
            except (ValueError, TypeError):
                pass
        # 영업이익률 미리 계산해서 주입
        if revenue_t and op_t is not None and revenue_t != 0:
            margin_t = op_t / revenue_t * 100
            context_parts.append(f"[계산값] 당기 영업이익률: {margin_t:.1f}%")
        if revenue_f and op_f is not None and revenue_f != 0:
            margin_f = op_f / revenue_f * 100
            context_parts.append(f"[계산값] 전기 영업이익률: {margin_f:.1f}%")

    if financials_prev:
        _KEY_PREV = ["수익(매출액)", "매출액", "영업수익", "영업이익", "영업이익(손실)",
                     "당기순이익", "당기순이익(손실)"]
        _seen_prev = {}
        for f in financials_prev:
            nm = f.get("account_nm", "")
            if nm in _KEY_PREV and nm not in _seen_prev:
                _seen_prev[nm] = f
        for k in _KEY_PREV:
            if k in _seen_prev:
                f = _seen_prev[k]
                context_parts.append(
                    f"[전전기 {f.get('bsns_year', '')}] {k}: {_to_uk(f.get('thstrm_amount',''))} (전기: {_to_uk(f.get('frmtrm_amount',''))})"
                )
    if dividend and isinstance(dividend, dict):
        for item in dividend.get("list", [])[:3]:
            context_parts.append(f"배당: {item.get('se_nm', '')} {item.get('thstrm', '')}원")

    context = "\n".join(context_parts)

    system_prompt = """당신은 네이버 증권 인기 블로거이자 전직 증권사 애널리스트입니다.
아래 DART 공시 데이터를 바탕으로 블로그 글을 작성하세요.

[핵심 원칙]
- 아래 제공된 데이터에 있는 수치만 사용하세요
- 데이터에 없는 주가, 금리, PER, PBR 등의 숫자를 절대 지어내지 마세요
- "함께 읽어보기", "관련 글" 등 내부링크 섹션을 절대 만들지 마세요
- 제공된 재무 데이터를 적극 활용하여 전기 대비 증감률, 영업이익률 등을 직접 계산해서 분석하세요

[글 구조 — 정보전달형]
글 전체를 "자연스러운 도입부(리드) → H2 섹션(짧은 설명 + 핵심 정보 표) → H3(###) 세분화 → 마무리(핵심 재확인)" 구조로 작성하세요.
- 문단은 짧게 끊어 가독성을 높이고, 핵심 정보는 표로 정리하며, 세부 항목은 H3(###)로 나눕니다.
- 도입부: 기업과 공시 내용을 소개하고 핵심 수치를 먼저 보여준 뒤, 이 글에서 다룰 내용을 자연스럽게 안내합니다.
- H2 섹션: "짧은 설명 문단 → 핵심 정보 표 → 필요 시 H3(###) 세분화" 순서로 구성합니다.
- 마무리: 마지막 H2 뒤에 짧은 마무리 문단으로 핵심을 요약하고, 최신 정보 확인(DART 공시·공식 자료)을 안내합니다.

[제목 작성 규칙]
- 패턴: "기업명 + 핵심숫자(금액 또는 증감률) + 의미 요약"
- 제공된 데이터의 실제 숫자를 제목에 포함 (매출, 순이익, 증감률 등)
- 예시: "삼성전자 2025 매출 300조 돌파 영업이익은 36% 감소", "카카오 당기순이익 2400억 전년비 15% 증가 의미는"
- 데이터에 없는 숫자는 제목에 넣지 마세요
- 의문형("~일까?") 최대 1회
- 40~50자

[본문 작성 규칙]
1. 첫 문단: 핵심 수치 포함 후킹 문장 + 반드시 "2026년 04월 DART 공시 기준" 명시
2. 본문 한글 3000자 이상 필수. 3000자 미만이면 실격. 각 H2 섹션을 충분히 서술해서 분량을 채우세요
3. H2 헤딩은 아래 5개를 기본 틀로 사용하세요 (소제목 문구는 자유롭게 변형 가능):
   ## 이 회사는 어떤 곳인가
   ## 최근 실적은 어땠나
   ## 실적 변화의 원인
   ## 리스크와 전망
   ## 투자자라면 주목할 점
   - "최근 실적"과 "리스크와 전망" 섹션은 먼저 짧은 설명을 쓴 뒤 핵심 수치(매출액·영업이익·당기순이익·YoY·영업이익률 등)를 마크다운 표로 정리하세요
   - 필요하면 각 섹션 안에서 H3(###)로 항목을 나누세요. 예: "### 매출", "### 수익성", "### 리스크 요인"
4. 금액은 읽기 쉽게 표현 (12,432,454,206원 → 약 124억 원)
5. 전문 용어는 괄호로 쉬운 설명 추가
6. 제공된 재무 데이터로 계산 가능한 지표만 사용 (영업이익률 = 영업이익/매출액, 순이익률, YoY 증감률). PER/PBR은 제공 데이터에 없으므로 언급하지 마세요. 대신 "투자 판단을 위해 증권사 HTS에서 PER/PBR을 확인하세요"로 안내
7. 각 H2 섹션은 최소 5문장 이상 작성
8. 마지막 섹션 끝에 "※ 본 글은 투자 권유가 아니며, 투자 판단은 본인의 책임입니다." 포함
9. 마지막 섹션 뒤에 짧은 마무리 문단을 두어 핵심을 요약하고 최신 정보 확인을 안내하세요 (정보전달형 마무리)
10. 마크다운 형식, H1(#) 사용 금지. H2(##)와 H3(###)는 자연스럽게 사용
11. "함께 읽어보기", "관련 글" 등 내부링크 섹션은 작성하지 마세요 (별도 자동 생성됩니다)
12. 다른 블로그 글 URL은 작성하지 마세요 (별도 자동 생성됩니다)
13. 데이터에 없는 수치(PER, PBR, 주가 등) 절대 날조 금지
14. [중요] 제공된 재무 데이터(매출액, 영업이익, 당기순이익)를 반드시 본문에서 구체적으로 인용하세요. 각 항목의 금액과 전기 대비 증감률을 직접 계산하여 서술하세요
15. "확인되지 않았습니다", "데이터가 없습니다" 같은 문장은 사용 금지. 제공된 데이터가 충분하므로 반드시 활용하세요
16. 업종 정보가 있으면 해당 업종의 일반적 특성(수요 동향, 원가 구조)을 구체적으로 서술하세요
17. 비교 표에 데이터 없는 행 금지 (TBD/N/A 행 금지)

[출력 형식]
TITLE: (제목)
CATEGORY: (카테고리 1개: 공시분석/실적분석/배당분석/IPO분석/ETF분석/시장분석 중 택1)
TAGS: (쉼표로 구분, 5개 이내)
DESC: (구글 검색결과에 노출될 150자 이내 설명문. 핵심 수치 1개 이상 + 독자가 클릭하고 싶은 호기심 유발 문장. 제목 반복 금지)
BODY:
(본문 마크다운)"""

    user_prompt = f"""아래 DART 공시 데이터를 바탕으로 블로그 글을 작성하세요.

[공시 정보]
{context}"""

    result = ai_generate(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        tier="default",
        temperature=0.7,
        max_tokens=4000,
    )
    if not result or not result.get("content"):
        logger.error("AI generation failed for disclosure article")
        return None
    _parsed = _parse_response(result["content"])
    if _parsed and _parsed.get("body_md"):
        _parsed["body_md"] = _inject_editorial_synthesis(_parsed["body_md"], {"topic_type": "stock_disclosure", "topic_id": disclosure.get("corp_code") or disclosure.get("corp_name", "")})
    return _parsed


def generate_evergreen_article(topic_type, corp_data=None, extra_data=None):
    prompts = {
        "dividend_ranking": """배당주 투자 전략과 고배당주를 고르는 방법을 설명하는 블로그 글을 작성하세요.

[글 구조 — 정보전달형]
글 전체를 "자연스러운 도입부 → 핵심 수치 표 → 종목별 H3 세분화 → 투자 전 체크리스트 → 마무리" 순서로 작성하세요.
- 도입부: 배당주 투자가 주목받는 이유와 이 글에서 다룰 내용을 짧고 자연스럽게 소개
- 핵심 수치 표: 배당수익률 계산법과 함께 제공 데이터의 고배당주 표를 먼저 제시
- 종목별 H3(###) 세분화: 주요 고배당 종목을 H3(###)로 하나씩 나누어 짧은 설명과 함께 소개
- 투자 전 체크리스트: 배당주 매수 전 확인할 항목을 체크리스트 형태로 정리
- 마무리: 핵심 내용을 요약하고 배당락일·기준일 등 최신 정보 확인을 안내

[필수 포함 내용]
1. 배당수익률 계산법 (배당금 / 주가 x 100) 단계별 예시
2. 배당성향과 배당성장률의 차이: 배당성향 100% 초과 시 리스크 경고 명시
3. 배당락일 전후 매매 전략
4. 제공 데이터가 있으면 배당률 TOP10 표 작성 (배당률 내림차순 정렬, 표 앞에 짧은 설명 문단 필수)
5. 1000만원 투자 시 예상 배당금 시뮬레이션 (계산 과정 단계별 표시)
6. 배당성향 이상치(200% 이상) 종목은 별도 리스크 분석
7. 표 아래에서 주요 고배당 종목을 H3(###)로 하나씩 나누어 소개

[주의]
- 배당금 기준일 컬럼 필수 포함
- 구체적인 종목명이나 수치는 제공된 데이터가 있을 때만 사용""",
        "etf_comparison": """국내 인기 ETF를 비교 분석하는 블로그 글을 작성하세요.

[글 구조 — 정보전달형]
글 전체를 "자연스러운 도입부 → 수익률 상위/하위 표 → ETF별 H3 세분화 → 주의사항 → 마무리" 순서로 작성하세요.
- 도입부: ETF 투자가 주목받는 이유와 이 글에서 다룰 내용을 짧고 자연스럽게 소개
- 수익률 상위/하위 표: 제공 데이터의 수익률 상위·하위 ETF를 먼저 표로 정리
- ETF별 H3(###) 세분화: 주요 ETF를 H3(###)로 하나씩 나누어 짧은 설명과 함께 소개
- 주의사항: ETF 투자 시 유의할 점을 정리 (표나 체크리스트 형태 가능)
- 마무리: 핵심 내용을 요약하고 실시간 시세 등 최신 정보 확인을 안내

[필수 포함 내용]
1. 수익률 상위 TOP10: 등락률 양수(+) 종목만 선정, 등락률 내림차순 정렬
2. 수익률 하위 TOP10: 등락률 음수(-) 종목만 선정, 등락률 오름차순 정렬
3. 동일 ETF가 상위/하위 양쪽에 중복 등장 금지
4. 보수비용(TER)은 제공 데이터에 실제 수치가 있을 때만 표기. 데이터에 TER이 없으면 보수비용 컬럼 자체를 표에서 제외
5. 거래량 급증 ETF 별도 분석 (거래량 상위 종목). 반드시 별도 H2 헤딩("## 거래량 급증 ETF")으로 작성
6. KODEX, TIGER, SOL 등 운용사별 대표 ETF 수익률/거래량 비교. 보수비용 데이터가 없으면 보수비용 컬럼 제외하고 수익률과 거래량만으로 표 구성. 빈 표(헤더만 있는 표) 절대 금지
7. 상위/하위 표 다음에 주요 ETF를 H3(###)로 하나씩 나누어 소개하고, 투자 시 주의사항 섹션을 추가하세요

[주의]
- 등락률이 전부 음수라면 "상위 TOP10" 대신 "하락폭이 적은 ETF TOP10"으로 제목 수정
- 실제 데이터에 없는 TER 수치 절대 날조 금지""",
        "sector_analysis": """아래 제공된 기업 재무 데이터를 분석하여 투자 인사이트를 제시하는 블로그 글을 작성하세요.

[글 구조 — 정보전달형]
글 전체를 "자연스러운 도입부 → 핵심 수치 표 → 업종/기업별 H3 세분화 → 비교 체크리스트 → 마무리" 순서로 작성하세요.
- 도입부: 업종 현황과 이 글에서 다룰 내용을 짧고 자연스럽게 소개
- 핵심 수치 표: 제공된 기업들의 재무 수치를 표로 먼저 정리
- 업종/기업별 H3(###) 세분화: 업종 또는 기업을 H3(###)로 나누어 짧은 설명과 함께 비교 분석
- 비교 체크리스트: 투자 판단 전 확인할 항목을 체크리스트 형태로 정리
- 마무리: 핵심 내용을 요약하고 최신 정보 확인을 안내

필수 규칙:
1. 제공된 기업 데이터에 있는 기업명, 매출액, 영업이익, 당기순이익, YoY 증감률을 반드시 본문에 인용하세요.
2. 제공된 모든 기업(최대 5개)을 분석에 포함하세요. 1개만 다루면 0점입니다.
3. 각 기업의 재무 수치를 표(테이블)로 정리하세요: 기업명 | 매출액 | 영업이익 | 당기순이익 | YoY
4. 데이터에 없는 PER, PBR, 시가총액, 업종평균 수치를 절대 날조하지 마세요.
5. 업종(sector) 정보가 있으면 같은 업종끼리 묶어서 비교 분석하세요.
6. 영업이익률(영업이익/매출액)을 직접 계산해서 수익성을 평가하세요.
7. YoY가 음수인 기업은 감소 원인을 업종 특성에 기반하여 분석하세요.
8. 제목은 구체적 기업명 또는 업종명 + 실적 수치를 포함하세요.
9. "확인해 보세요", "투자 판단은 신중하게" 같은 빈 문장 금지.""",
        "ipo_schedule": """아래 제공된 기업 재무 데이터를 활용하여 실적 기반 투자 분석 글을 작성하세요.

[글 구조 — 정보전달형]
글 전체를 "자연스러운 도입부 → 기업별 재무 표 → 기업별 H3 세분화 → 투자 판단 포인트 → 마무리" 순서로 작성하세요.
- 도입부: 상장(IPO) 흐름과 이 글에서 다룰 내용을 짧고 자연스럽게 소개
- 기업별 재무 표: 제공된 기업들의 재무 수치를 표로 먼저 정리
- 기업별 H3(###) 세분화: 기업을 H3(###)로 나누어 짧은 설명과 함께 실적을 비교 분석
- 투자 판단 포인트: 실적 개선·악화 기업을 구분해 확인할 항목을 정리
- 마무리: 핵심 내용을 요약하고 최신 정보 확인을 안내

필수 규칙:
1. 제공된 모든 기업의 매출액, 영업이익, 당기순이익, YoY를 본문에 인용하세요.
2. 기업별 재무 현황을 표로 정리하세요.
3. 데이터에 없는 수치(PER, PBR, 시가총액)를 날조하지 마세요.
4. 실적 개선/악화 기업을 구분하여 분석하세요.
5. 제목에 구체적 기업명이나 업종 + 실적 수치를 포함하세요.""",
        "cma_savings": """아래 제공된 기업 재무 데이터를 분석하여 금융/은행 업종 실적 비교 글을 작성하세요.

[글 구조 — 정보전달형]
글 전체를 "자연스러운 도입부 → 핵심 수치 표 → 업종/기업별 H3 세분화 → 비교 체크리스트 → 마무리" 순서로 작성하세요.
- 도입부: 금융/은행 업종 실적이 주목받는 이유와 이 글에서 다룰 내용을 짧고 자연스럽게 소개
- 핵심 수치 표: 제공된 기업들의 재무 수치를 표로 먼저 정리
- 업종/기업별 H3(###) 세분화: 업종 또는 기업을 H3(###)로 나누어 짧은 설명과 함께 비교 분석
- 비교 체크리스트: 투자 판단 전 확인할 항목을 체크리스트 형태로 정리
- 마무리: 핵심 내용을 요약하고 최신 정보 확인을 안내

필수 규칙:
1. 제공된 기업 데이터의 매출액, 영업이익, 당기순이익, YoY를 모두 인용하세요.
2. 금융 업종이 아닌 기업이 포함되어 있으면 업종별로 구분하여 분석하세요.
3. 재무 수치를 표로 정리하세요.
4. 데이터에 없는 금리, PER, PBR 수치를 날조하지 마세요.""",
    }

    base_prompt = prompts.get(topic_type, prompts["dividend_ranking"])

    if corp_data:
        # [PATCH] 기업 데이터 전체 전달 (5개 기업 모두 포함되도록)
        corp_json = json.dumps(corp_data, ensure_ascii=False, indent=2)
        base_prompt += f"\n\n[제공 기업 재무 데이터 — 반드시 모든 기업을 분석에 포함하세요]\n{corp_json[:8000]}"

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

    if extra_data and isinstance(extra_data, dict) and extra_data.get("rankings"):
        base_prompt += "\n\n[실시간 배당순위 데이터 (KSD 증권정보포털 기준)]\n"
        base_prompt += "| 순위 | 종목명 | 시가배당률(%) | 주당배당금(원) |\n"
        base_prompt += "|---|---|---|---|\n"
        for r in extra_data["rankings"]:
            base_prompt += f"| {r['rank']} | {r['name']} | {r['dividend_yield']} | {r['dividend_per_share']} |\n"
        if extra_data.get("note"):
            base_prompt += f"\n참고: {extra_data['note']}\n"
        base_prompt += "\n위 데이터는 KSD 증권정보포털 실시간 기준입니다. 이 수치만 사용하고 날조하지 마세요."

    system_prompt = """당신은 네이버 증권 인기 블로거이자 전직 증권사 애널리스트입니다.

[글 구조 — 정보전달형]
글 전체를 "자연스러운 도입부(리드) → H2 섹션(짧은 설명 + 핵심 수치 표) → H3(###) 세분화 → 마무리(핵심 재확인)" 구조로 작성하세요.
- 문단은 짧게 끊어 가독성을 높이고, 핵심 정보는 표로 정리하며, 세부 항목은 H3(###)로 나눕니다.
- 도입부: 주제를 소개하고 핵심 수치를 먼저 보여준 뒤, 이 글에서 다룰 내용을 자연스럽게 안내합니다.
- H2 섹션: "짧은 설명 문단 → 핵심 정보 표 → 필요 시 H3(###) 세분화" 순서로 구성합니다.
- 비교 체크리스트: 비교가 필요한 주제(배당주, ETF, 업종 비교)는 확인할 항목을 체크리스트 형태로 정리합니다.
- 마무리: 핵심을 요약하고 데이터 기준 시점과 최신 정보 확인을 안내합니다.

[제목 작성 규칙]
- 패턴: "비교 대상 + 핵심 수치 + 결론 힌트", 제공 데이터의 실제 숫자 1개 이상 포함
- 예시: "2026년 고배당주 TOP 10 연 8% 수익 가능한 종목은", "KODEX vs TIGER ETF 수수료 0.01% 차이가 만드는 수익률 격차"
- 50자 이내

[본문 작성 규칙]
1. 첫 문단: 핵심 데이터 포인트 포함 후킹 문장 + "2026년 3월 기준" 반드시 명시
2. 본문 3000자 이상, 2500자 미만 불합격
3. H2 헤딩 5개 내외, 각 섹션 최소 5문장. 세부 항목은 H3(###)로 나누세요
4. 금액은 읽기 쉽게 (억 원, 만 원 단위)
5. 비교 표 최소 1개 필수. 표 앞뒤 빈 줄 필수. 수치 칸에 "TBD" 절대 금지, 데이터 없으면 해당 행 제외
6. 구체적 종목명과 수치 포함. 수학 계산(배당금, 수익률 시뮬레이션)은 반드시 단계별 표시 후 검증
7. "※ 본 글은 투자 권유가 아니며, 투자 판단은 본인의 책임입니다." 포함
8. 마크다운 형식, H1(#) 사용 금지. H2(##)와 H3(###)는 자연스럽게 사용
9. 2026년 3월 기준 최신 정보로 작성
10. "함께 읽어보기", "관련 글" 등 내부링크 섹션은 작성하지 마세요 (별도 자동 생성됩니다)
11. 다른 블로그 글 URL은 작성하지 마세요 (별도 자동 생성됩니다)
12. 데이터에 없는 수치(PER, PBR, 주가 등) 절대 날조 금지
13. [중요] 제공된 재무 데이터(매출액, 영업이익, 당기순이익)를 반드시 본문에서 구체적으로 인용하세요. 각 항목의 금액과 전기 대비 증감률을 직접 계산하여 서술하세요
14. "확인되지 않았습니다", "데이터가 없습니다" 같은 문장은 사용 금지. 제공된 데이터가 충분하므로 반드시 활용하세요
15. 업종 정보가 있으면 해당 업종의 일반적 특성(수요 동향, 원가 구조)을 구체적으로 서술하세요
16. 비교 표에 데이터 없는 행 금지 (TBD/N/A 행 금지)
17. 재무 데이터 0건이면 "DART 공시 미확인" 명시
18. 데이터 미제공 시 방법론/전략 중심 작성, 빈 수치 표 금지

[출력 형식]
TITLE: (제목)
CATEGORY: (카테고리 1개: 공시분석/실적분석/배당분석/IPO분석/ETF분석/시장분석 중 택1)
TAGS: (쉼표로 구분, 5개 이내)
DESC: (구글 검색결과에 노출될 150자 이내 설명문. 핵심 수치 1개 이상 + 독자가 클릭하고 싶은 호기심 유발 문장. 제목 반복 금지)
BODY:
(본문 마크다운)"""

    user_prompt = f"""아래 데이터를 바탕으로 블로그 글을 작성하세요.

{base_prompt}"""

    result = ai_generate(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        tier="default",
        temperature=0.7,
    )
    if not result or not result.get("content"):
        logger.error("AI generation failed for evergreen article")
        return None
    parsed = _parse_response(result["content"])
    # 후처리: 배당 데이터가 있으면 빈 배당 TOP10 표 채우기
    if extra_data and isinstance(extra_data, dict) and extra_data.get("rankings") and parsed.get("body_md"):
        _body = parsed["body_md"]
        if "| 순위 | 종목명 |" in _body:
            _blines = _body.split("\n")
            _out = []
            _j = 0
            while _j < len(_blines):
                _out.append(_blines[_j])
                if _blines[_j].startswith("| 순위 | 종목명") and _j + 1 < len(_blines) and _blines[_j+1].startswith("|---"):
                    _out.append(_blines[_j+1])
                    for _r in extra_data["rankings"][:10]:
                        _dps = str(_r.get("dividend_per_share", ""))
                        _out.append(f'| {_r["rank"]} | {_r["name"]} | {_r["dividend_yield"]} | {_dps} | 2025년 |')
                    _j += 2
                    continue
                _j += 1
            parsed["body_md"] = "\n".join(_out)

    if parsed and parsed.get("body_md"):
        parsed["body_md"] = _inject_editorial_synthesis(parsed["body_md"], {"topic_type": "stock_evergreen", "topic_id": str(topic_type)})

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

    # 후처리: 내부링크 섹션 전체 제거 (_clean_body와 동일 패턴)
    _cut_patterns = [
        r"\n##\s*함께",
        r"\n##\s*관련",
        r"\n##\s*추천 글",
        r"\n##\s*더 알아보기",
        r"\n##\s*관련 포스트",
        r"\n##\s*같이 읽어보기",
        r"\n##\s*참고 글",
        r"\n##\s*이전 글",
    ]
    for _pat in _cut_patterns:
        _m = re.search(_pat, body)
        if _m:
            body = body[:_m.start()]

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
