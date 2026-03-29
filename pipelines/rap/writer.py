"""RAP writer — 부동산 기사 생성 (GAP frontmatter 방식)"""
import os
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def _build_trade_reference(keyword, trades, region_info=None):
    """실거래가 데이터를 참고자료 블록으로 변환"""
    lines = []
    month = datetime.now().strftime("%Y년 %m월")
    city = region_info.get("city", "") if region_info else ""
    district = region_info.get("district", "") if region_info else ""
    lines.append(f"## 키워드: {keyword}")
    lines.append(f"지역: {city} {district}")
    lines.append(f"기준: {month}")
    lines.append(f"총 거래건수: {len(trades)}건\n")

    # 통계 계산
    prices = [t.get("dealAmountInt", 0) for t in trades if t.get("dealAmountInt")]
    if prices:
        lines.append("### 시세 요약")
        lines.append(f"- 최고가: {max(prices):,}만원")
        lines.append(f"- 최저가: {min(prices):,}만원")
        lines.append(f"- 평균: {sum(prices)//len(prices):,}만원")
        lines.append("")

    lines.append("### 최근 거래 내역")
    for t in trades[:15]:
        apt = t.get("aptNm", "")
        amount = t.get("dealAmount", "").strip()
        area = t.get("excluUseAr", "")
        floor = t.get("floor", "")
        dong = t.get("umdNm", "")
        year = t.get("buildYear", "")
        deal_date = f"{t.get('dealYear','')}.{t.get('dealMonth','').zfill(2)}.{t.get('dealDay','').zfill(2)}"
        # 취득세 구간 자동 계산
        price_int = t.get("dealAmountInt", 0)
        if price_int > 0:
            if price_int <= 60000:
                tax_info = f"취득세구간: 6억이하 1.1%→{int(price_int*0.011):,}만원"
            elif price_int <= 90000:
                rate = 0.01 + (price_int - 60000) / 30000 * 0.02
                tax_info = f"취득세구간: 6억~9억 {rate*100:.1f}%→{int(price_int*rate):,}만원"
            else:
                tax_info = f"취득세구간: 9억초과 3.3%→{int(price_int*0.033):,}만원"
        else:
            tax_info = ""
        lines.append(f"- {dong} {apt}({year}년식) {area}㎡ {floor}층: {amount}만원 ({deal_date}) [{tax_info}]")

    return "\n".join(lines)


def _build_subscription_reference(keyword, subscriptions):
    """청약 공고 데이터를 참고자료 블록으로 변환"""
    lines = []
    month = datetime.now().strftime("%Y년 %m월")
    lines.append(f"## 키워드: {keyword}")
    lines.append(f"기준: {month}")
    lines.append(f"총 공고: {len(subscriptions)}건\n")

    lines.append("### 분양/임대 공고 목록")
    for s in subscriptions[:10]:
        name = s.get("PAN_NM", "")
        region = s.get("CNP_CD_NM", "")
        start = s.get("PAN_NT_ST_DT", "")
        end = s.get("CLSG_DT", "")
        typ = s.get("AIS_TP_CD_NM", "")
        status = s.get("PAN_SS", "")
        url = s.get("DTL_URL", "")
        lines.append(f"- [{typ}] {name}")
        lines.append(f"  지역: {region} | 공고: {start} ~ 마감: {end} | 상태: {status}")
        if url:
            lines.append(f"  상세: {url}")

    return "\n".join(lines)



def _base_trade_rules():
    """공통 규칙 (모든 trade 블로그)"""
    return """[핵심 규칙]
1. 참고자료에 없는 가격, 날짜를 절대 지어내지 마세요
2. 제공된 실거래가 데이터의 수치만 사용하세요
3. "투자 추천"이나 "매수/매도 권유"는 절대 하지 마세요
4. 참고자료 원문을 그대로 복사하지 말고 자연스럽게 재구성
5. 같은 내용을 반복하지 마세요
6. "특히", "또한", "그리고" 로 문장을 시작하지 마세요. "특히"는 본문 어디에도 사용 금지
7. 반드시 3,000자 이상 작성하세요. 2,500자 미만은 불합격입니다. 각 H2 섹션마다 최소 4~6문장, 한 문장은 40자 이상으로 작성하세요. 짧은 글은 절대 불가합니다
8. 전월 데이터가 참고자료에 없으면 '전월 대비' 비교를 절대 하지 마세요. 데이터 없이 추측 금지
9. '상승세', '하락세' 등 시장 전망은 참고자료 수치 근거가 있을 때만 사용하세요
10. 거래 건수가 10건 미만이면 '거래 사례가 제한적이므로 참고용'이라고 반드시 명시하세요
11. 금액이 10억 이상일 때는 괄호 안에 억 환산을 병기하세요. 예: 250,000만원(25억)"""


def _base_output_format():
    """공통 출력 형식"""
    return """출력 형식:
---
title: "제목"
category: "{category}"
tags: "태그1, 태그2, 태그3"
description: "120자 이내 설명"
---

본문 마크다운"""


def _build_trade_system_prompt(keyword, month, blog_id=None):
    """blog_id별 특화 프롬프트 생성"""
    rules = _base_trade_rules()

    # ─── rap3-hugo: 세금 계산 중심 ───
    if blog_id == "rap3-hugo":
        return f"""당신은 부동산 세금 전문 블로그 작가입니다.
아래 국토교통부 실거래가 데이터를 바탕으로 해당 아파트의 세금 분석 글을 작성하세요.

{rules}

[세금 계산 지침 — 반드시 아래 구간표대로 계산하세요]
- 실거래가 데이터의 실제 가격을 사용하여 세금 시뮬레이션

[취득세 구간표 (1주택 기준, 지방교육세+농특세 포함)]
- 6억원 이하: 취득세율 1.1% (취득세 1% + 지방교육세 0.1%)
  예) 5억 × 1.1% = 550만원
- 6억원 초과 ~ 9억원 이하: 세율이 점진적으로 증가
  7억 약 1.5%, 8억 약 2.2%, 9억 약 3.0%
  예) 7억 × 1.5% = 1,050만원 / 8억 × 2.2% = 1,760만원
- 9억원 초과: 취득세율 3.3% (취득세 3% + 지방교육세 0.3%)
  예) 10억 × 3.3% = 3,300만원 / 15억 × 3.3% = 4,950만원
- 다주택자 중과: 2주택 8.4%, 3주택 이상 12.4% (조정대상지역)

[중요] 거래가 6.6억이면 반드시 "6억 초과~9억 이하" 구간을 적용하세요.
[중요] 거래가 15.2억(152,000만원)이면 반드시 "9억 초과 3.3%" 구간을 적용하세요.
[중요] 각 거래 사례마다 해당 구간과 세율을 명시하고 계산 과정을 보여주세요.

[억 환산 규칙 — 필수]
- 만원 단위 금액은 반드시 억 환산을 병기하세요
- 152,000만원 = 15억 2천만원 (15.2억)
- 182,203만원 = 18억 2천만원 (18.2억)
- 415,000만원 = 41억 5천만원 (41.5억)
- 63,000만원 = 6억 3천만원 (6.3억)
- 절대로 152,000만원을 "1억 5천만원"으로 쓰지 마세요. 만원 단위입니다!

[양도소득세 누진세율표 — 반드시 이 표대로 계산]
- 1,400만원 이하: 6%
- 1,400만~5,000만원: 15% (누진공제 126만원)
- 5,000만~8,800만원: 24% (누진공제 576만원)
- 8,800만~1억 5천만원: 35% (누진공제 1,544만원)
- 1억 5천만~3억: 38% (누진공제 1,994만원)
- 3억~5억: 40% (누진공제 2,594만원)
- 5억~10억: 42% (누진공제 3,594만원)
- 10억 초과: 45% (누진공제 6,594만원)

[양도세 계산 예시 — 이 형식을 따르세요]
예) 매입가 12억, 매도가 15억인 경우:
  양도차익 = 15억 - 12억 = 3억
  필요경비 = 약 3,000만원 (가정)
  과세표준 = 3억 - 3,000만원 = 2억 7천만원
  세율: 38% (1.5억~3억 구간)
  양도세 = 2억 7천만원 × 38% - 1,994만원 = 8,266만원
- 다주택자: 2주택 8.4%, 3주택 이상 12.4% (조정대상지역)
- 양도소득세:
  보유 1년 미만 → 45% / 1~2년 → 기본세율(6~45%) / 2년 이상 → 기본세율 + 장기보유특별공제
  장기보유특별공제: 3년 이상 연 2%, 최대 30% (1주택 거주요건 시 최대 80%)
  1주택 비과세: 보유 2년 + 실거주 2년 + 양도가 12억 이하
  다주택자 중과: 기본세율 + 20%p(2주택) 또는 +30%p(3주택)
- 계산 순서: 매입가(가정) → 양도차익 → 필요경비 공제 → 과세표준 → 세율 적용 → 세액
- 종합부동산세: 공시가격 기준 (실거래가와 구분하여 설명)
- 반드시 실거래가 데이터에서 2~3개 거래를 골라 구체적 세금 계산 예시를 보여주세요

[제목]
- SEO 최적화 한국어, 반드시 32자 이내 (절대 35자 초과 금지). 짧고 임팩트 있게
- "{month}" 포함 권장
- "취득세", "양도세", "세금" 중 하나 포함
- 키워드 "{keyword}" 반영

[본문 형식]
- 마크다운 형식, 반드시 2,500자~3,500자 (2,200자 미만 불합격)
- H2(##) 소제목 4~6개로 구조화
- H3(###)을 활용하여 세부 항목 정리
- 자연스러운 구어체, 한 단락 3~5문장
- 실거래가 + 세금 계산 결과를 마크다운 표(table)로 정리
- 도입부: 해당 지역 부동산 세금 이슈 개요
- 중반: 실거래 사례별 취득세·양도세 시뮬레이션 (구체적 금액 제시)
- 후반: 절세 팁 3~5항목 (장기보유특별공제, 1주택 비과세 요건 등)
- 마지막: 핵심 요약 3줄
- 면책 문구를 본문에 넣지 마세요 (시스템이 자동 삽입합니다)

[최종 확인 — 반드시 지키세요]
- 제목: 32자 이내
- 본문: 3,000자 이상 (부족하면 각 섹션에 구체적 사례와 계산 과정을 추가하세요)
- "특히" 단어 사용 금지

""" + _base_output_format().replace("{category}", "부동산세금")

    # ─── rap4-hugo: 전월세 가이드 중심 ───
    if blog_id == "rap4-hugo":
        return f"""당신은 전세·월세 전문 블로그 작가입니다.
아래 국토교통부 실거래가(매매) 데이터를 참고하여 해당 지역의 전월세 시장 분석 글을 작성하세요.

{rules}
7. 매매가 데이터를 활용하되, 전세가율(일반적으로 매매가의 55~70%)을 적용하여 전세 시세를 추정하세요
8. 추정치임을 반드시 명시하세요

[전월세 분석 지침]
- 본문 서두에 반드시 다음 문구 삽입: "본 분석은 매매 실거래가 기반 추정치이며, 실제 전월세 시세와 차이가 있을 수 있습니다."
- 매매가 기준 전세가율 추정: 서울 평균 55~65%, 수도권 60~70%, 지방 65~75%

[월세 환산 공식 — 반드시 이 공식대로 계산]
- 기준 보증금: 5,000만원 (고정)
- 전환이율: 연 4.0~5.0% (중간값 4.5% 사용)
- 월세 = (추정전세가 - 보증금) × 전환이율 ÷ 12
- 예시) 매매가 80,000만원(8억), 전세가율 60%
  → 추정전세가 = 80,000 × 0.60 = 48,000만원(4억 8천)
  → 월세 = (48,000 - 5,000) × 0.045 ÷ 12 = 161만원/월
- 예시) 매매가 50,000만원(5억), 전세가율 60%
  → 추정전세가 = 50,000 × 0.60 = 30,000만원(3억)
  → 월세 = (30,000 - 5,000) × 0.045 ÷ 12 = 94만원/월

[중요] 월세 단위는 반드시 '만원/월'로 표기. 연 단위 금액을 월세로 쓰지 마세요.
[중요] 표 컬럼: 단지명 | 면적(㎡) | 매매가(만원) | 추정전세가(만원) | 월세환산(만원/월)

- 전세 안전 체크리스트: 등기부등본 확인, 전세보증보험(HUG/SGI), 확정일자, 전입신고, 깡통전세 여부 확인
- 실거래 매매가에서 전세 추정가를 계산하여 구체적 금액으로 제시

[제목]
- SEO 최적화 한국어, 반드시 32자 이내 (절대 35자 초과 금지). 짧고 임팩트 있게
- "{month}" 포함 권장
- "전세", "월세", "임대" 중 하나 포함
- 키워드 "{keyword}" 반영

[본문 형식]
- 마크다운 형식, 반드시 2,500자~3,500자 (2,200자 미만 불합격)
- H2(##) 소제목 4~6개로 구조화
- H3(###)을 활용하여 세부 항목 정리
- 자연스러운 구어체, 한 단락 3~5문장
- 매매가 → 추정 전세가 → 월세 환산을 마크다운 표(table)로 정리
- 도입부: 해당 지역 전월세 시장 동향
- 중반: 주요 단지별 전세 추정가 분석 + 월세 환산 비교
- 후반: 전세 계약 시 필수 체크리스트 5항목
- 마지막: 핵심 요약 3줄
- 면책 문구를 본문에 넣지 마세요 (시스템이 자동 삽입합니다)

[최종 확인 — 반드시 지키세요]
- 제목: 32자 이내
- 본문: 3,000자 이상 (부족하면 단지별 분석과 월세 환산 예시를 추가하세요)
- "특히" 단어 사용 금지
- 월세 단위: 반드시 "만원/월"

""" + _base_output_format().replace("{category}", "전월세")

    # ─── rap5-hugo: 브랜드 아파트 분석 중심 ───
    if blog_id == "rap5-hugo":
        return f"""당신은 브랜드 아파트 전문 블로그 작가입니다.
아래 국토교통부 실거래가 데이터를 바탕으로 해당 브랜드 아파트 분석 글을 작성하세요.

{rules}

[브랜드 분석 지침]
- 해당 브랜드(건설사)의 특징과 강점 소개
- 같은 지역 내 브랜드 vs 비브랜드 시세 차이 분석
- 브랜드 프리미엄이 실거래가에 얼마나 반영되는지 구체적 수치로 설명
- 해당 브랜드의 대표 단지와 최근 분양/입주 현황

[건설사별 참고 정보]
- 래미안(삼성물산): 강남권 프리미엄, 고급 마감재
- 자이(GS건설): 조경 특화, 커뮤니티 시설
- 힐스테이트(현대건설): 대단지 중심, 인프라 연계
- 푸르지오(대우건설): 가성비, 넓은 평면
- 더샵(포스코이앤씨): 친환경, 에너지 효율
- 아크로(DL이앤씨): 하이엔드 럭셔리
- e편한세상(DL이앤씨): 실용적 평면
- 롯데캐슬(롯데건설): 상업시설 연계

[제목]
- SEO 최적화 한국어, 반드시 32자 이내 (절대 35자 초과 금지). 짧고 임팩트 있게
- "{month}" 포함 권장
- 브랜드명 또는 단지명 포함
- 키워드 "{keyword}" 반영

[본문 형식]
- 마크다운 형식, 반드시 2,500자~3,500자 (2,200자 미만 불합격)
- H2(##) 소제목 4~6개로 구조화
- H3(###)을 활용하여 세부 항목 정리
- 자연스러운 구어체, 한 단락 3~5문장
- 실거래 데이터를 마크다운 표(table)로 정리 (단지명, 면적, 층, 가격)
- 도입부: 해당 브랜드 아파트 개요 + 건설사 소개
- 중반: 실거래가 분석 + 주변 시세 비교 + 브랜드 프리미엄 분석
- 후반: 투자 포인트 + 입주 예정 단지 정보
- 마지막: 핵심 요약 3줄
- 면책 문구를 본문에 넣지 마세요 (시스템이 자동 삽입합니다)

[최종 확인 — 반드시 지키세요]
- 제목: 32자 이내
- 본문: 3,000자 이상 (부족하면 브랜드 비교와 시세 분석을 추가하세요)
- "특히" 단어 사용 금지

""" + _base_output_format().replace("{category}", "브랜드아파트")

    # ─── rap-hugo (기본): 시세 분석 중심 ───
    return f"""당신은 부동산 시세 분석 전문 블로그 작가입니다.
아래 국토교통부 실거래가 데이터를 바탕으로 블로그 글을 작성하세요.

{rules}

[제목]
- SEO 최적화 한국어, 반드시 32자 이내 (절대 35자 초과 금지). 짧고 임팩트 있게
- "{month}" 포함 권장
- 키워드 "{keyword}" 반영

[본문 형식]
- 마크다운 형식, 반드시 2,500자~3,500자 (2,200자 미만 불합격)
- H2(##) 소제목 4~6개로 구조화
- H3(###)을 활용하여 세부 항목 정리
- 자연스러운 구어체, 한 단락 3~5문장
- 실거래 데이터를 마크다운 표(table)로 정리 (단지명, 면적, 층, 가격)
- 도입부: 해당 지역 부동산 시장 개요
- 중반: 주요 단지별 거래 분석 (참고자료에 전월 데이터가 있을 때만 비교, 없으면 생략)
- 후반: 투자 시 체크리스트 3~5항목
- 마지막: 핵심 요약 3줄
- 면책 문구를 본문에 넣지 마세요 (시스템이 자동 삽입합니다)

[최종 확인 — 반드시 지키세요]
- 제목: 32자 이내
- 본문: 3,000자 이상 (부족하면 단지별 상세 분석을 추가하세요)
- "특히" 단어 사용 금지

""" + _base_output_format().replace("{category}", "부동산")



def generate_trade_article(keyword, trades, region_info=None, blog_id=None):
    """실거래가 기반 기사 생성"""
    from shared.ai_writer import generate as ai_generate
    reference = _build_trade_reference(keyword, trades, region_info)
    month = datetime.now().strftime("%Y년 %m월")

    system_prompt = _build_trade_system_prompt(keyword, month, blog_id)

    user_prompt = f"키워드: {keyword}\n\n참고자료:\n{reference}"
    result = ai_generate(system_prompt, user_prompt)
    if not result or not result.get("content"):
        logger.error(f"RAP 실거래가 글 생성 실패: {keyword}")
        return None
    return _parse_article(result["content"], keyword)


def generate_subscription_article(keyword, subscriptions):
    """청약 정보 기반 기사 생성"""
    from shared.ai_writer import generate as ai_generate
    reference = _build_subscription_reference(keyword, subscriptions)
    month = datetime.now().strftime("%Y년 %m월")

    system_prompt = f"""당신은 부동산 청약 전문 블로그 작가입니다.
아래 한국부동산원 청약홈 공고 데이터를 바탕으로 블로그 글을 작성하세요.

[핵심 규칙]
1. 참고자료에 없는 일정, 조건을 절대 지어내지 마세요
2. 청약 자격, 일정, 신청 방법 등 실용 정보 중심으로 작성
3. "당첨 보장" 등 과장 표현 금지
4. 같은 내용을 반복하지 마세요
5. "특히" 표현 사용 금지

[제목]
- SEO 최적화 한국어, 반드시 32자 이내 (절대 35자 초과 금지). 짧고 임팩트 있게
- "{month}" 포함 권장
- 키워드 "{keyword}" 반영

[본문 형식]
- 마크다운 형식, 반드시 2,500자~3,500자 (2,200자 미만 불합격)
- H2(##) 소제목 4~6개로 구조화
- H3(###)을 활용하여 세부 항목 정리
- 자연스러운 구어체, 한 단락 3~5문장
- 공고 목록을 마크다운 표(table)로 정리 (공고명, 유형, 지역, 접수기간)
- 신청 자격과 준비 서류 체크리스트 포함
- 청약 당첨 확률 높이는 팁 포함
- 반드시 3,000자 이상 작성하세요. 2,500자 미만은 불합격입니다. 각 H2 섹션마다 최소 4~6문장, 한 문장은 40자 이상으로 충실하게 작성하세요
- 마지막: 핵심 요약 3줄
- 면책 문구를 본문에 넣지 마세요 (시스템이 자동 삽입합니다)

출력 형식:
---
title: "제목"
category: "청약정보"
tags: "태그1, 태그2, 태그3"
description: "120자 이내 설명"
---

본문 마크다운"""

    user_prompt = f"키워드: {keyword}\n\n참고자료:\n{reference}"
    result = ai_generate(system_prompt, user_prompt)
    if not result or not result.get("content"):
        logger.error(f"RAP 청약 글 생성 실패: {keyword}")
        return None
    return _parse_article(result["content"], keyword)


def _parse_article(response, keyword):
    """GAP과 동일한 frontmatter(---) 방식 파싱"""
    fm_match = re.search(r"---\s*\n(.+?)\n---", response, re.DOTALL)
    if not fm_match:
        logger.warning(f"frontmatter 파싱 실패: {keyword}")
        return None

    fm_text = fm_match.group(1)
    body_md = response[fm_match.end():].strip()

    title = ""
    category = "부동산"
    tags = ""
    description = ""

    for line in fm_text.split("\n"):
        line = line.strip()
        if line.startswith("title:"):
            title = line.split(":", 1)[1].strip().strip('"').strip("'")
        elif line.startswith("category:"):
            category = line.split(":", 1)[1].strip().strip('"').strip("'")
        elif line.startswith("tags:"):
            tags = line.split(":", 1)[1].strip().strip('"').strip("'")
        elif line.startswith("description:"):
            description = line.split(":", 1)[1].strip().strip('"').strip("'")

    if not title or not body_md:
        logger.warning(f"제목 또는 본문 없음: {keyword}")
        return None

    return {
        "title": title,
        "body_md": body_md,
        "category": category,
        "tags": tags,
        "description": description,
        "keyword": keyword,
    }
