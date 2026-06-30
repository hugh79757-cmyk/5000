"""RAP writer — 부동산 기사 생성 (GAP frontmatter 방식)"""
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)


def _build_trade_reference(keyword, trades, region_info=None):
    """실거래가 데이터를 참고자료 블록으로 변환
    trades: list (기존 호환) 또는 dict {"apt_kw","keyword_trades","other_trades"}
    """
    lines = []
    month = datetime.now().strftime("%Y년 %m월")
    city = region_info.get("city", "") if region_info else ""
    district = region_info.get("district", "") if region_info else ""

    # dict 형식 (신규) vs list 형식 (하위호환)
    if isinstance(trades, dict):
        apt_kw         = trades.get("apt_kw", "")
        keyword_trades = trades.get("keyword_trades", [])
        other_trades   = trades.get("other_trades", [])
        all_trades     = keyword_trades + other_trades
    else:
        apt_kw         = ""
        keyword_trades = []
        other_trades   = trades
        all_trades     = trades

    lines.append(f"## 키워드: {keyword}")
    lines.append(f"지역: {city} {district}")
    lines.append(f"기준: {month}")
    lines.append("")

    # ── 공시가격 추정치 조회 (gongsijiga 테이블) ──
    try:
        import os as _os3
        import sqlite3 as _sq3
        _RAP_DB = _os3.path.join(
            _os3.path.dirname(_os3.path.dirname(_os3.path.dirname(_os3.path.abspath(__file__)))),
            "data", "rap.db"
        )
        if apt_kw and _os3.path.exists(_RAP_DB):
            _gc = _sq3.connect(_RAP_DB, timeout=10)
            _grow = _gc.execute(
                "SELECT avg_deal_amount, estimated_price, deal_year FROM gongsijiga "
                "WHERE apt_name LIKE ? ORDER BY deal_year DESC LIMIT 1",
                (f"%{apt_kw}%",)
            ).fetchone()
            _gc.close()
            if _grow:
                _avg_deal, _est_price, _gyear = _grow
                _gongsi_rate = round(_est_price / _avg_deal * 100, 1) if _avg_deal else 0
                lines.append(f"### 공시가격 추정 ({_gyear}년 기준, 공시가율 69% 적용)")
                lines.append(f"- 평균 실거래가: {_avg_deal:,}만원 ({_avg_deal/10000:.1f}억)")
                lines.append(f"- 추정 공시가격: {_est_price:,}만원 ({_est_price/10000:.1f}억)")
                lines.append(f"- 공시가율: 약 {_gongsi_rate}% (국토부 평균 적용)")
                lines.append("- ※ 실제 공시가격은 국토부 부동산공시가격알리미에서 확인하세요")
                lines.append("")
    except Exception as _ge:
        pass  # 공시가 조회 실패 시 무시


    # ── 키워드 단지 실거래 (최우선 섹션) ──
    _is_rent_kw = isinstance(trades, dict) and trades.get("data_type") == "rent"
    _is_brand_kw = isinstance(trades, dict) and trades.get("data_type") == "brand"
    if keyword_trades:
        if _is_brand_kw:
            brand_kw = trades.get("brand_kw", apt_kw)
            kw_prices = [t.get("dealAmountInt", 0) for t in keyword_trades if t.get("dealAmountInt")]
            lines.append(f"### ★ [{apt_kw}] 실거래가 ({len(keyword_trades)}건) ← 키워드 단지 (브랜드: {brand_kw})")
            if kw_prices:
                lines.append(f"- 최고가: {max(kw_prices):,}만원")
                lines.append(f"- 최저가: {min(kw_prices):,}만원")
                if len(kw_prices) > 1:
                    lines.append(f"- 평균: {sum(kw_prices)//len(kw_prices):,}만원")
            for t in keyword_trades:
                amt   = t.get("dealAmount", "").strip()
                area  = t.get("excluUseAr", "")
                floor = t.get("floor", "")
                city  = t.get("city", "")
                dist  = t.get("district", "")
                year  = t.get("buildYear", "")
                ddate = f"{t.get('dealYear','')}.{t.get('dealMonth','').zfill(2)}.{t.get('dealDay','').zfill(2)}"
                lines.append(f"  - [{city} {dist}] {apt_kw}({year}년식) {area}㎡ {floor}층: {amt}만원 ({ddate})")
            lines.append("")
        elif _is_rent_kw:
            lines.append(f"### ★ [{apt_kw}] 전월세 거래 ({len(keyword_trades)}건) ← 이 단지가 키워드 단지입니다")
            for t in keyword_trades:
                area  = t.get("excluUseAr", "")
                floor = t.get("floor", "")
                dong  = t.get("umdNm", "")
                year  = t.get("buildYear", "")
                rtype = t.get("rentType", "전세")
                dep   = t.get("depositInt", 0)
                mr    = t.get("monthlyRentInt", 0)
                ddate = f"{t.get('dealYear','')}.{t.get('dealMonth','').zfill(2)}.{t.get('dealDay','').zfill(2)}"
                if mr and mr > 0:
                    price_str = f"보증금 {dep:,}만원 / 월세 {mr:,}만원"
                else:
                    price_str = f"전세 {dep:,}만원"
                lines.append(f"  - {dong} {apt_kw}({year}년식) {area}㎡ {floor}층: [{rtype}] {price_str} ({ddate})")
        else:
            kw_prices = [t.get("dealAmountInt", 0) for t in keyword_trades if t.get("dealAmountInt")]
            lines.append(f"### ★ [{apt_kw}] 실거래가 ({len(keyword_trades)}건) ← 이 단지가 키워드 단지입니다")
            if kw_prices:
                lines.append(f"- 최고가: {max(kw_prices):,}만원")
                lines.append(f"- 최저가: {min(kw_prices):,}만원")
                if len(kw_prices) > 1:
                    lines.append(f"- 평균: {sum(kw_prices)//len(kw_prices):,}만원")
            for t in keyword_trades:
                amt   = t.get("dealAmount", "").strip()
                area  = t.get("excluUseAr", "")
                floor = t.get("floor", "")
                dong  = t.get("umdNm", "")
                year  = t.get("buildYear", "")
                ddate = f"{t.get('dealYear','')}.{t.get('dealMonth','').zfill(2)}.{t.get('dealDay','').zfill(2)}"
                lines.append(f"  - {dong} {apt_kw}({year}년식) {area}㎡ {floor}층: {amt}만원 ({ddate})")
        lines.append("")
    else:
        if _is_brand_kw:
            brand_kw = trades.get("brand_kw", apt_kw)
            lines.append(f"### ★ [{apt_kw}] 해당 기간 직접 거래 없음 — 전국 {brand_kw} 브랜드 데이터로 분석")
            lines.append(f"- 아래 전국 {brand_kw} 브랜드 거래 데이터를 참고하여 브랜드 시세를 분석하세요.")
            lines.append(f"- {apt_kw} 단지의 매매가를 임의로 가정하거나 추측하지 마세요.")
        else:
            lines.append(f"### ★ [{apt_kw}] 해당 기간 실거래 없음")
            lines.append(f"- 아래 {district} 내 인근 단지 데이터를 참고하여 분석하세요.")
            lines.append("- 이 단지의 매매가를 임의로 가정하거나 추측하지 마세요.")
        lines.append("")

    # ── 구 내 인근 단지 참고 데이터 ──
    _is_rent_other = isinstance(trades, dict) and trades.get("data_type") == "rent"
    _is_brand_other = isinstance(trades, dict) and trades.get("data_type") == "brand"
    if other_trades:
        if _is_brand_other:
            brand_kw = trades.get("brand_kw", apt_kw)
            lines.append(f"### 전국 {brand_kw} 브랜드 거래 참고 데이터 ({len(other_trades)}건)")
        else:
            lines.append(f"### {district} 인근 단지 참고 데이터 ({len(other_trades)}건)")
        if _is_rent_other:
            dep_prices = [t.get("depositInt", 0) for t in other_trades if t.get("depositInt")]
            if dep_prices:
                lines.append(f"- (참고) 보증금 최고: {max(dep_prices):,}만원 / 최저: {min(dep_prices):,}만원 / 평균: {sum(dep_prices)//len(dep_prices):,}만원")
                lines.append(f"- ※ 위 수치는 구 전체 전월세 통계이며 키워드 단지({apt_kw}) 시세가 아닙니다.")
        else:
            other_prices = [t.get("dealAmountInt", 0) for t in other_trades if t.get("dealAmountInt")]
            if other_prices:
                lines.append(f"- (참고) 구 전체 최고가: {max(other_prices):,}만원 / 최저가: {min(other_prices):,}만원 / 평균: {sum(other_prices)//len(other_prices):,}만원")
                lines.append(f"- ※ 위 수치는 구 전체 통계이며 키워드 단지({apt_kw}) 시세가 아닙니다.")
        lines.append("")

    # ── rent 데이터 전용 거래 내역 출력 ──
    is_rent = isinstance(trades, dict) and trades.get("data_type") == "rent"
    if is_rent:
        lines.append("### 최근 전월세 거래 내역 (키워드 단지 우선)")
        for t in all_trades[:15]:
            apt       = t.get("aptNm", "")
            area      = t.get("excluUseAr", "")
            floor     = t.get("floor", "")
            dong      = t.get("umdNm", "")
            year      = t.get("buildYear", "")
            rtype     = t.get("rentType", "전세")
            deposit   = t.get("depositInt", 0)
            mrent     = t.get("monthlyRentInt", 0)
            deal_date = f"{t.get('dealYear','')}.{t.get('dealMonth','').zfill(2)}.{t.get('dealDay','').zfill(2)}"
            if mrent and mrent > 0:
                price_str = f"보증금 {deposit:,}만원 / 월세 {mrent:,}만원"
            else:
                price_str = f"전세 {deposit:,}만원"
            lines.append(f"- {dong} {apt}({year}년식) {area}㎡ {floor}층: [{rtype}] {price_str} ({deal_date})")
    else:
        lines.append("### 최근 거래 내역 (키워드 단지 우선)")
        for t in all_trades[:15]:
            apt = t.get("aptNm", "")
            amount = t.get("dealAmount", "").strip()
            area = t.get("excluUseAr", "")
            floor = t.get("floor", "")
            dong = t.get("umdNm", "")
            year = t.get("buildYear", "")
            deal_date = f"{t.get('dealYear','')}.{t.get('dealMonth','').zfill(2)}.{t.get('dealDay','').zfill(2)}"
            price_int = t.get("dealAmountInt", 0)
            if price_int > 0:
                if price_int <= 60000:
                    tax_info = f"취득세구간: 6억이하 1.1%→{int(price_int*0.011):,}만원"
                elif price_int <= 90000:
                    # 국토부 공식: 세율(%) = (취득가액억 × 2/3 - 3) / 100
                    _bil = price_int / 10000  # 만원→억 환산
                    rate = (_bil * 2 / 3 - 3) / 100
                    rate = max(0.01, min(rate, 0.03))  # 1%~3% 범위 클램프
                    tax_total = int(price_int * (rate + 0.001))  # 지방교육세 0.1% 포함
                    tax_info = f"취득세구간: 6억~9억 {rate*100:.2f}%→{tax_total:,}만원(지방교육세포함)"
                else:
                    tax_info = f"취득세구간: 9억초과 3.3%→{int(price_int*0.033):,}만원"
            else:
                tax_info = ""
            lines.append(f"- {dong} {apt}({year}년식) {area}㎡ {floor}층: {amount}만원 ({deal_date}) [{tax_info}]")

    # ── rap3-hugo 전용: 양도세 시뮬레이션용 가격 쌍 자동 생성 ──
    _all_prices = sorted(
        [t.get("dealAmountInt", 0) for t in all_trades if t.get("dealAmountInt", 0) > 0]
    )
    if len(_all_prices) >= 2:
        _buy_price  = _all_prices[0]   # 최저가 → 매입가 시뮬레이션
        _sell_price = _all_prices[-1]  # 최고가 → 매도가 시뮬레이션
        _gain       = _sell_price - _buy_price
        if _gain > 0:
            lines.append("")
            lines.append("### [rap3 전용] 양도세 시뮬레이션 기준값 (실거래가 기반)")
            lines.append(f"- 매입가(최저 실거래가): {_buy_price:,}만원 ({_buy_price/10000:.1f}억)")
            lines.append(f"- 매도가(최고 실거래가): {_sell_price:,}만원 ({_sell_price/10000:.1f}억)")
            lines.append(f"- 양도차익(매도-매입): {_gain:,}만원 ({_gain/10000:.1f}억)")
            # 필요경비 추정 (취득세+중개보수+수리비 등 통상 1~2%)
            _expense = int(_buy_price * 0.015)
            _taxable = max(0, _gain - _expense)
            lines.append(f"- 필요경비 추정(취득가×1.5%): {_expense:,}만원")
            lines.append(f"- 과세표준(양도차익-필요경비): {_taxable:,}만원 ({_taxable/10000:.1f}억)")
            # 양도세 누진세율 계산
            _TAX_BRACKETS = [
                (1400,   0.06,      0),
                (5000,   0.15,    126),
                (8800,   0.24,    576),
                (15000,  0.35,   1544),
                (30000,  0.38,   1994),
                (50000,  0.40,   2594),
                (100000, 0.42,   3594),
                (float("inf"), 0.45, 6594),
            ]
            _tax = 0
            for _limit, _rate, _deduct in _TAX_BRACKETS:
                if _taxable <= _limit:
                    _tax = int(_taxable * _rate - _deduct)
                    lines.append(f"- 양도세 추정(1주택 기본세율): {_tax:,}만원 (세율 {_rate*100:.0f}%, 누진공제 {_deduct:,}만원)")
                    break
            lines.append("- ※ 위 수치는 실거래가 기반 참고값입니다. 보유기간/거주요건에 따라 달라집니다.")

    return "\n".join(lines)


def _build_subscription_reference(keyword, subscriptions):
    """청약 공고 데이터를 참고자료 블록으로 변환 (실제 DB 스키마 반영)"""
    from datetime import datetime
    month = datetime.now().strftime("%Y년 %m월")
    lines = [f"## 키워드: {keyword}", f"기준: {month}", f"총 공고: {len(subscriptions)}건\n"]

    # 마크다운 표 헤더
    lines.append("| 번호 | 공고명 | 유형 | 지역 | 접수기간 | 상태 |")
    lines.append("|------|--------|------|------|----------|------|")

    for i, s in enumerate(subscriptions[:15], 1):
        pan_nm = s.get("pan_nm", "미상")
        pan_type = s.get("pan_type", "미상")
        region_nm = s.get("region_nm", "미상")
        pan_start = s.get("pan_start", "미정")
        pan_end = s.get("pan_end", "미정")
        pan_status = s.get("pan_status", "미상")
        detail_url = s.get("detail_url", "")

        lines.append(f"| {i} | {pan_nm} | {pan_type} | {region_nm} | {pan_start} ~ {pan_end} | {pan_status} |")

    # 상세 정보 블록
    lines.append("\n### 공고 상세 정보")
    for i, s in enumerate(subscriptions[:15], 1):
        pan_nm = s.get("pan_nm", "미상")
        pan_type = s.get("pan_type", "미상")
        region_nm = s.get("region_nm", "미상")
        pan_start = s.get("pan_start", "미정")
        pan_end = s.get("pan_end", "미정")
        pan_status = s.get("pan_status", "미상")
        detail_url = s.get("detail_url", "")

        lines.append(f"\n**{i}. {pan_nm}**")
        lines.append(f"  - 유형: {pan_type}")
        lines.append(f"  - 지역: {region_nm}")
        lines.append(f"  - 접수기간: {pan_start} ~ {pan_end}")
        lines.append(f"  - 상태: {pan_status}")
        if detail_url:
            lines.append(f"  - 상세보기: {detail_url}")

    return "\n".join(lines)


def _base_trade_rules() -> str:
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
11. 금액이 10억 이상일 때는 괄호 안에 억 환산을 병기하세요. 예: 250,000만원(25억)

[마크다운 표 작성 규칙 — 절대 준수]
- 구분선 셀 수는 반드시 헤더 셀 수와 동일하게 작성
  올바른 예) | 단지명 | 면적 | 층 | 가격 |
             |--------|------|----|----|
  잘못된 예) | 단지명 | 면적 | 층 | 가격 |
             |--||---|   ← 셀 수 불일치, 절대 금지
- 구분선은 반드시 --- (하이픈 3개 이상)만 사용. –(en-dash), —(em-dash) 사용 금지
- 표 바로 앞 줄은 반드시 빈 줄(엔터 한 줄)을 넣으세요
- 표의 모든 행은 반드시 각각 별도 줄에 작성 (한 줄로 압축 금지)"""


def _base_output_format() -> str:
    """공통 출력 형식"""
    return """출력 형식:
---
title: "제목"
category: "{category}"
tags: "태그1, 태그2, 태그3"
description: "120자 이내 설명"
---

본문 마크다운"""


def _build_trade_system_prompt(blog_id=None):
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
[중요] 참고자료에 "[rap3 전용] 양도세 시뮬레이션 기준값" 섹션이 있으면
반드시 해당 섹션의 매입가/매도가/양도차익/과세표준/양도세 수치를 그대로 사용하세요.
절대로 매입가를 임의로 가정하거나 만들지 마세요.

참고자료 시뮬레이션 기준값 활용 예시:
  참고자료: 매입가 21.7억, 매도가 65억, 양도차익 43.3억, 과세표준 43억, 양도세 186,791만원
  → 위 수치를 그대로 본문 양도세 계산에 사용
  → "실거래가 기반 시뮬레이션" 임을 명시
- 다주택자: 2주택 8.4%, 3주택 이상 12.4% (조정대상지역)
- 양도소득세:
  보유 1년 미만 → 45% / 1~2년 → 기본세율(6~45%) / 2년 이상 → 기본세율 + 장기보유특별공제
  장기보유특별공제: 3년 이상 연 2%, 최대 30% (1주택 거주요건 시 최대 80%)
  1주택 비과세: 보유 2년 + 실거주 2년 + 양도가 12억 이하
  다주택자 중과: 기본세율 + 20%p(2주택) 또는 +30%p(3주택)
- 계산 순서: 참고자료 시뮬레이션 기준값(매입가/매도가) → 양도차익 → 필요경비 공제 → 과세표준 → 세율 적용 → 세액
- [절대금지] 매입가를 임의로 설정하거나 "가정"으로 처리하지 마세요. 참고자료에 기준값이 없으면 양도세 계산을 생략하세요.
- 종합부동산세: 공시가격 기준 (실거래가와 구분하여 설명)
- 반드시 실거래가 데이터에서 2~3개 거래를 골라 구체적 세금 계산 예시를 보여주세요

[제목]
- SEO 최적화 한국어, 반드시 32자 이내 (절대 35자 초과 금지). 짧고 임팩트 있게
- 현재 월 포함 권장
- "취득세", "양도세", "세금" 중 하나 포함
- 제공된 키워드 반영

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
아래 국토교통부 실거래(전월세) 데이터를 참고하여 해당 지역의 전월세 시장 분석 글을 작성하세요.

{rules}
7. 참고자료의 실제 전월세 거래 데이터(보증금, 월세)를 그대로 활용하세요. 매매가 기반 추정값 사용 금지.
8. 참고자료에 실제 거래가 있으면 반드시 해당 수치를 표에 사용하고, 없을 때만 추정치임을 명시하세요

[전월세 분석 지침]
- 매매가 기준 전세가율 추정 (2026년 기준 참고치):
  서울 강남3구(강남/서초/송파): 50~58%
  서울 마포/용산/성동: 55~63%
  서울 기타: 58~66%
  경기 성남/과천/하남: 55~63%
  경기 기타: 60~70%
  지방 광역시: 65~75%
  ※ 신축(5년 이내)은 위 비율에서 -3~5%p, 구축(20년 이상)은 +3~5%p 조정

[전월세 데이터 활용 원칙]
- 참고자료에 전세 거래가 있으면: 보증금 수치를 그대로 표에 기재하세요
- 참고자료에 월세 거래가 있으면: 보증금 + 월세 수치를 그대로 표에 기재하세요
- 참고자료에 거래가 전혀 없을 때만: 아래 전환이율 공식으로 추정
  * 전환이율 참고: 연 4.0~5.0% (중간값 4.5% 사용)
  * 월세 = (전세보증금 - 기준보증금5000만원) × 0.045 ÷ 12
- 실제 거래 수치와 추정값을 절대 혼용하지 마세요

[중요] 월세 단위는 반드시 '만원/월'로 표기. 연 단위 금액을 월세로 쓰지 마세요.
[중요] 표 컬럼(전세): 단지명 | 면적(㎡) | 건축연도 | 층 | 전세보증금(만원)
[중요] 표 컬럼(월세): 단지명 | 면적(㎡) | 건축연도 | 층 | 보증금(만원) | 월세(만원/월)
[중요] 전세와 월세 거래를 분리하여 각각 별도 표로 작성하세요. 전세 표와 월세 표의 컬럼 수를 반드시 일치시키세요.
[중요] 참고자료의 실제 보증금·월세 수치를 그대로 사용하세요. 매매가 기반 추정값 사용 금지.

- 전세 안전 체크리스트 (반드시 본문에 포함할 것):
  1. 등기부등본 확인: 근저당/가압류/소유권 이전 여부
  2. 깡통전세 판별: 매매가 대비 전세가 비율 80% 이상이면 위험
  3. 전세보증보험: HUG(주택도시보증공사) 또는 SGI(서울보증보험) 가입 필수
     - HUG 가입 조건: 전세가 ÷ 매매가 ≤ 90%, 보증료 연 0.1~0.2%
  4. 확정일자: 전입신고 + 확정일자 같은 날 처리 (주민센터 또는 인터넷등기소)
  5. 임대차 3법 핵심: 계약갱신청구권(1회, +2년), 전월세상한제(5% 이내 인상)
  6. 계약 전 확인: 공인중개사 자격증, 중개보수 요율표, 계약서 특약사항

[실전 팁 — 본문 마지막 섹션에 포함]
- "전세 계약 전 반드시 확인해야 할 5가지" 형태로 체크리스트 섹션 작성
- 각 항목에 구체적 행동 지침 포함 (예: "등기부등본은 계약 당일 다시 발급받으세요")
- HUG 전세보증보험 가입 절차 간략 안내 (인터넷 신청 → 심사 → 보증서 발급)
- 실거래 매매가에서 전세 추정가를 계산하여 구체적 금액으로 제시

[제목]
- SEO 최적화 한국어, 반드시 32자 이내 (절대 35자 초과 금지). 짧고 임팩트 있게
- 현재 월 포함 권장
- "전세", "월세", "임대" 중 하나 포함
- 제공된 키워드 반영

[본문 형식]
- 마크다운 형식, 반드시 2,500자~3,500자 (2,200자 미만 불합격)
- H2(##) 소제목 4~6개로 구조화
- H3(###)을 활용하여 세부 항목 정리
- 자연스러운 구어체, 한 단락 3~5문장
- 실제 전월세 거래 데이터를 마크다운 표(table)로 정리 (전세/월세 분리)
- 전세 표 헤더 고정: | 단지명 | 면적(㎡) | 건축연도 | 층 | 전세보증금(만원) |
                     |--------|----------|----------|----|--------------------|
- 월세 표 헤더 고정: | 단지명 | 면적(㎡) | 건축연도 | 층 | 보증금(만원) | 월세(만원/월) |
                     |--------|----------|----------|----|--------------|--------------------|
- 도입부: 해당 지역 전월세 시장 동향
- 중반: 주요 단지별 실거래 전세/월세 분석
- 후반: 전세 계약 시 필수 체크리스트 5항목
- 마지막: 핵심 요약 3줄
- 면책 문구를 본문에 넣지 마세요 (시스템이 자동 삽입합니다)

[단지 데이터 사용 원칙 — 반드시 준수]
- 표에는 참고자료 "최근 거래 내역"에 실제로 존재하는 단지명과 거래금액만 사용하세요.
- 참고자료에 없는 단지명을 임의로 만들어 표에 넣지 마세요. (예: "A아파트", "B아파트" 금지)
- 키워드 단지명(예: 거여1단지, 만민하늘애)과 일치하는 거래가 참고자료에 있으면 반드시 표 첫 번째 행에 배치하고 해당 실거래금액을 그대로 사용하세요.
- 키워드 단지 거래가 참고자료에 없으면: "해당 기간 [단지명] 실거래 없음. 아래는 동일 구 인근 단지 참고 데이터입니다." 라고 명시 후 표를 작성하세요.
- 참고자료의 "시세 요약(최고가/최저가/평균)"은 구 전체 통계입니다. 이 평균값을 키워드 단지의 매매가로 절대 사용하지 마세요.
- 비교 단지는 참고자료 "최근 거래 내역" 중 키워드 단지와 면적이 유사한 것으로 선택하세요.
- 단지 분석 시 건축연도(구축/신축 여부), 전용면적, 층수를 함께 언급하세요.

[최종 확인 — 반드시 지키세요]
- 제목: 32자 이내
- 본문: 3,000자 이상 (부족하면 단지별 분석과 월세 환산 예시를 추가하세요)
- "특히" 단어 사용 금지
- 월세 단위: 반드시 "만원/월"
- 표의 보증금·월세는 반드시 참고자료의 실제 전월세 거래금액 사용 (추정값·평균값 대입 금지)
- 거래 데이터가 없는 단지는 표에 포함하지 마세요"

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

[브랜드 아파트 심층 분석 지침]
■ 브랜드 프리미엄 수치 분석 (반드시 포함):
  - 같은 지역·면적 기준 브랜드 vs 비브랜드 가격 차이를 만원/억 단위로 명시
  - 프리미엄 비율(%) 계산: (브랜드가 - 비브랜드가) ÷ 비브랜드가 × 100
  - 데이터에 비브랜드 거래가 없으면 "비교 데이터 부족으로 프리미엄 산출 불가"라고 명시

■ 단지 상세 분석 (반드시 포함):
  - 거래된 브랜드 단지의 준공연도, 세대수, 동수 (참고자료에 있을 때만 — 없으면 절대 만들지 마세요)
  - [절대금지] 세대수("약 N세대"), 총 층수("N층"), 동수("N개동")를 참고자료 없이 임의로 작성 금지
  - 참고자료에 없는 시설명(피트니스, 골프연습장 등)을 해당 단지에 있다고 단정하지 마세요
  - 면적별·층별 실거래가를 마크다운 표로 정리
  - 최근 거래 트렌드 (거래량이 증가/감소 추세인지 — 데이터 근거 있을 때만)

■ 브랜드 가치 요소 (반드시 포함):
  - 마감재/커뮤니티/조경은 해당 브랜드(건설사)의 일반적 특징으로만 서술하세요
  - [절대금지] "이 단지에는 피트니스가 있습니다" 등 해당 단지에 특정 시설이 있다고 단정 금지
  - 브랜드 공통 특징: 래미안(삼성물산-고급마감), 자이(GS-조경특화), 롯데캐슬(상업연계) 등
  - 브랜드 AS/하자보수 체계는 건설사 일반 수준으로 서술 가능

■ 매수 시 체크리스트 (반드시 포함):
  1. 동일 브랜드의 다른 지역 단지와 시세 비교
  2. 입주 후 브랜드 프리미엄 유지율 확인
  3. 재건축/리모델링 시 시공사(브랜드) 변경 가능성
  4. 관리비 수준 (브랜드 단지는 일반 대비 10~20% 높을 수 있음)
  5. 전매 제한 및 실거주 의무 확인

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
- 현재 월 포함 권장
- 브랜드명 또는 단지명 포함
- 제공된 키워드 반영

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
    return f"""당신은 부동산 시세 분석 전문 블로그 작가입니다. 반드시 한국어로 작성하세요. 중국어나 다른 언어로 작성하지 마세요.
아래 국토교통부 실거래가 데이터를 바탕으로 블로그 글을 작성하세요.

{rules}

[제목]
- SEO 최적화 한국어, 반드시 32자 이내 (절대 35자 초과 금지). 짧고 임팩트 있게
- 현재 월 포함 권장
- 제공된 키워드 반영

[본문 형식]
- 마크다운 형식, 반드시 2,500자~3,500자 (2,200자 미만 불합격)
- H2(##) 소제목 4~6개로 구조화
- H3(###)을 활용하여 세부 항목 정리
- 자연스러운 구어체, 한 단락 3~5문장
- 실거래 데이터를 마크다운 표(table)로 정리 (단지명, 면적, 층, 가격)
- 도입부: 해당 지역 부동산 시장 개요 (거래 건수, 가격대 범위, 평균가 요약으로 시작)

[매매 시세 전문 분석 지침]
■ 가격대 분석 (반드시 포함):
  - 최고가/최저가/평균가를 억 환산과 함께 명시
  - 면적별(전용 59㎡, 84㎡, 114㎡) 시세 구간 정리
  - 같은 단지 내 층별 가격 차이 언급 (데이터 있을 때)

■ 단지별 거래 분석 (반드시 포함):
  - 거래량 상위 3~5개 단지를 중심으로 분석
  - 각 단지의 준공연도, 세대수 등 기본 정보 포함 (데이터 있을 때)
  - 실거래가를 마크다운 표로 정리: | 단지명 | 전용면적 | 층 | 거래가(만원) | 억환산 |

■ 지역 특성 분석 (반드시 포함):
  - 교통 (지하철역, 주요 도로 접근성)
  - 학군 (초중고, 학원가)
  - 생활 인프라 (대형마트, 병원, 공원)
  ※ 위 정보는 해당 지역의 일반적 특성이며, 구체적 거리/시간은 데이터 없으면 생략

■ 매수 전 체크리스트 (반드시 포함):
  1. 등기부등본 확인 (근저당, 가압류, 전세권)
  2. 관리비 및 장기수선충당금 확인
  3. 재건축/리모델링 추진 여부 확인
  4. 실거래가와 호가 차이 비교
  5. 전세가율로 갭투자 위험도 판단 (전세가율 70% 이상 주의)
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

    system_prompt = _build_trade_system_prompt(blog_id)

    user_prompt = f"키워드: {keyword}\n기준: {month}\n\n참고자료:\n{reference}"
    result = ai_generate(system_prompt, user_prompt)
    if not result or not result.get("content"):
        logger.error(f"RAP 실거래가 글 생성 실패: {keyword}")
        return None
    return _parse_article(result["content"], keyword)


def generate_subscription_article(keyword, subscriptions):
    """청약 정보 기반 기사 생성 (rap2-hugo 전용 강화 프롬프트)"""
    from shared.ai_writer import generate as ai_generate
    reference = _build_subscription_reference(keyword, subscriptions)
    month = datetime.now().strftime("%Y년 %m월")

    system_prompt = """당신은 10년 경력의 부동산 청약 전문 블로그 작가입니다.
한국부동산원 청약홈 공고 데이터를 바탕으로 실용적인 청약 안내 글을 작성하세요.

[핵심 규칙]
1. 참고자료에 없는 일정, 조건, 경쟁률을 절대 지어내지 마세요
2. 청약 자격, 일정, 신청 방법 등 실용 정보 중심으로 작성
3. "당첨 보장", "무조건 당첨" 등 과장 표현 금지
4. 같은 내용을 반복하지 마세요
5. "특히", "또한", "그리고"로 시작하는 문장 금지
6. 참고자료에 없는 과거 청약 경쟁률이나 미래 분양 일정을 추측하지 마세요
7. 공고마다 접수 시작일과 마감일을 반드시 명시하세요

[청약 전문 콘텐츠 지침]
■ 청약 자격 요건 안내 (반드시 포함):
  - 특별공급: 신혼부부(혼인 7년 이내, 소득기준 도시근로자 월평균 140%), 생애최초(5년 이상 소득세 납부), 다자녀(미성년 3명 이상), 노부모부양(만 65세 이상 직계존속 3년 이상 부양)
  - 일반공급: 1순위(청약통장 가입 24개월+, 지역별 예치금 충족), 2순위(그 외)
  - 가점제 핵심: 무주택기간(최대 32점), 부양가족수(최대 35점), 청약통장 가입기간(최대 17점) = 만점 84점
  ※ 위 기준은 일반 참고사항이며, 각 공고의 실제 자격 조건을 반드시 확인하세요

■ 청약 신청 절차 안내 (반드시 포함):
  1단계: 청약홈(applyhome.co.kr) 또는 모바일 앱에서 본인인증
  2단계: 청약통장 순위 및 예치금 확인
  3단계: 원하는 주택형(면적) 선택 후 신청
  4단계: 당첨자 발표 확인 → 서류 제출 → 계약

■ 준비 서류 체크리스트 (반드시 포함):
  - 주민등록등본, 가족관계증명서, 소득증빙(원천징수영수증 등)
  - 무주택확인서, 청약통장 납입증명서
  - 특별공급 해당 시: 혼인관계증명서, 다자녀 증빙 등 추가 서류

■ 당첨 확률 높이는 실전 팁 (반드시 포함):
  - 가점 낮으면 추첨제 비율 높은 85㎡ 초과 평형 노리기
  - 비인기 지역·저층 물량에 전략적 신청
  - 예비 당첨번호도 포기하지 말 것 (계약 포기 물량 발생 가능)
  - 특별공급 먼저 신청 후 떨어지면 일반공급 재도전 가능

■ 주의사항 (반드시 포함):
  - 부적격 당첨 시 재당첨 제한 최대 10년
  - 1순위 제한: 투기과열지구는 세대주만, 5년 이내 당첨 이력 없어야
  - 전매제한: 투기과열지구 최대 소유권이전등기까지, 조정대상지역 최대 3년

[마크다운 표 작성 규칙 — 절대 준수]
- 구분선 셀 수는 반드시 헤더 셀 수와 동일하게 작성
  올바른 예) | 단지명 | 면적 | 층 | 가격 |
             |--------|------|----|----|
  잘못된 예) | 단지명 | 면적 | 층 | 가격 |
             |--||---|   ← 셀 수 불일치, 절대 금지
- 구분선은 반드시 --- (하이픈 3개 이상)만 사용. –(en-dash), —(em-dash) 사용 금지
- 표 바로 앞 줄은 반드시 빈 줄(엔터 한 줄)을 넣으세요
- 표의 모든 행은 반드시 각각 별도 줄에 작성 (한 줄로 압축 금지)

[제목]
- SEO 최적화 한국어, 반드시 32자 이내 (절대 35자 초과 금지)
- 현재 월 포함 권장
- 제공된 키워드 반영

[본문 형식]
- 마크다운, 각 H2 섹션마다 최소 4~6문장, 한 문장 40자 이상
- H2(##) 소제목 5~7개로 구조화:
  ## 1. 이번 달 주요 청약 공고 (표 포함)
  ## 2. 청약 자격 요건 총정리
  ## 3. 신청 절차 및 일정
  ## 4. 필요 서류 체크리스트
  ## 5. 당첨 확률 높이는 전략
  ## 6. 주의사항 및 불이익
  ## 7. 핵심 요약
- 공고 목록 표는 아래 형식을 그대로 복사하여 사용하세요 (열 수·구분선 변경 절대 금지):
  | 번호 | 공고명 | 유형 | 지역 | 접수기간 | 상태 |
  |------|--------|------|------|----------|------|
  (위 구분선을 그대로 사용. 셀 수는 반드시 6개)
- 청약홈 링크 반드시 포함: [청약홈 바로가기](https://www.applyhome.co.kr)
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

    user_prompt = f"키워드: {keyword}\n기준: {month}\n\n참고자료:\n{reference}"
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
