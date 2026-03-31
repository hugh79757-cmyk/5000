#!/usr/bin/env python3
"""사이트별 고CTR 타이틀 템플릿 엔진
- 공용 풀 20개 (비교 10 + 단독 10)
- 사이트 특화 풀 120개 (6사이트 x 비교 10 + 단독 10)
- 선택 시 공용 + 해당 사이트 = 30개 풀에서 random.choice
- 7가지 클릭 요소: 손실회피, 시간긴급성, 월환산, 반전, 사이트특성, 결론힌트, 괄호부가정보
"""
import random
from datetime import datetime


def _has_batchim(word):
    if not word:
        return False
    last = ord(word[-1])
    if 0xAC00 <= last <= 0xD7A3:
        return (last - 0xAC00) % 28 != 0
    return False


def _jwa(w):
    return "과" if _has_batchim(w) else "와"


def _jeul(w):
    return "을" if _has_batchim(w) else "를"


def _ji(w):
    return "이" if _has_batchim(w) else ""


def _build_vars(data):
    _raw_m = data.get("model", "")
    _raw_c = data.get("competitor", "")
    _KR_BRANDS = ["현대 ", "기아 ", "제네시스 ", "쉐보레 ", "르노 ", "쌍용 ", "KG "]
    m = _raw_m
    for _b in _KR_BRANDS:
        m = m.replace(_b, "")
    c = _raw_c
    for _b in _KR_BRANDS:
        c = c.replace(_b, "")
    # 수입차 브랜드는 모델명에 유지 (BMW X7, 토요타 GR86 등)
    _IMPORT_BRANDS = ["BMW", "벤츠", "아우디", "폭스바겐", "볼보", "렉서스",
                       "토요타", "혼다", "테슬라", "포르쉐", "링컨", "캐딜락",
                       "지프", "랜드로버", "재규어", "마세라티", "람보르기니",
                       "페라리", "벤틀리", "롤스로이스", "미니", "푸조", "시트로엥"]
    for _ib in _IMPORT_BRANDS:
        if _ib in _raw_m and _ib not in m:
            m = _ib + " " + m
            break
    for _ib in _IMPORT_BRANDS:
        if _ib in _raw_c and _ib not in c:
            c = _ib + " " + c
            break
    p = data.get("base_price", 0)
    t = data.get("trim", "")
    r_pct = data.get("resale_rate_percent", 0)
    r_3yr = data.get("resale_3yr", 0)
    dep = data.get("three_year_depreciation", 0)
    total = data.get("three_year_total_cost", 0)
    fuel = data.get("annual_fuel_cost", 0)
    eff = data.get("fuel_efficiency", 0)
    tax = data.get("tax_annual", 0)
    ins = data.get("insurance_estimate", 0)
    yr = data.get("year", 2026)
    m48 = data.get("monthly_payment_48", 0)
    m36 = data.get("monthly_payment_36", 0)
    ftype = data.get("fuel_type", "")
    cp = data.get("competitor_price", 0)
    cr_pct = data.get("competitor_resale_rate_percent", 0)
    c_dep = data.get("competitor_three_year_depreciation", 0)
    c_total = data.get("competitor_three_year_total_cost", 0)
    dep_diff = abs(total - c_total) if c_total else 0
    price_diff = abs(p - cp) if cp else 0
    maint_monthly = round((fuel + tax + ins) / 12) if (fuel + tax + ins) > 0 else 0
    now = datetime.now()
    month_kr = f"{now.year}년 {now.month}월"

    return {
        "m": m, "c": c, "p": p, "t": t,
        "r_pct": r_pct, "r_3yr": r_3yr, "dep": dep, "total": total,
        "fuel": fuel, "eff": eff, "tax": tax, "ins": ins, "yr": yr,
        "m48": m48, "m36": m36, "ftype": ftype,
        "cp": cp, "cr_pct": cr_pct, "c_dep": c_dep, "c_total": c_total,
        "dep_diff": dep_diff, "price_diff": price_diff,
        "maint_m": maint_monthly, "month_kr": month_kr,
        "wa": _jwa(c), "eul": _jeul(m), "ji": _ji(m),
    }


# ════════════════════════════════════════════════════════════
# 공용 비교 템플릿 (10개)
# ════════════════════════════════════════════════════════════
def _common_vs(v):
    return [
        f"{v['m']} vs {v['c']}, 3년 뒤 {v['dep_diff']:,}만원 차이 나는 진짜 이유",
        f"{v['p']:,}만원 {v['m']}{v['wa']} {v['cp']:,}만원 {v['c']} — 실비용은 역전된다",
        f"{v['m']}{v['wa']} {v['c']} 중 3년 후 덜 손해 보는 차는? [{v['month_kr']} 기준]",
        f"신차값 {v['price_diff']:,}만원 차이, 3년 총비용은 {v['dep_diff']:,}만원 차이 — {v['m']} vs {v['c']}",
        f"{v['m']} 잔존가치 {v['r_pct']}% vs {v['c']} {v['cr_pct']}% — 감가 적은 쪽이 이긴다",
        f"{v['m']} vs {v['c']} 유지비 비교 — 보험·세금·유류비 월 {v['maint_m']:,}만원의 차이",
        f"같은 세그먼트 {v['m']}{v['wa']} {v['c']}, 어느 쪽이 돈 덜 드는 차일까",
        f"{v['yr']} {v['m']} vs {v['c']} 비교 — 감가·유지비·잔존가치 총정리 [{v['month_kr']}]",
        f"중고로 팔 때 덜 떨어지는 차는? {v['m']} vs {v['c']} 잔존가치 비교",
        f"{v['c']}보다 {v['price_diff']:,}만원 비싼 {v['m']}, 3년 뒤엔 오히려 이득?",
    ]


# ════════════════════════════════════════════════════════════
# 공용 단독 템플릿 (10개)
# ════════════════════════════════════════════════════════════
def _common_solo(v):
    return [
        f"{v['p']:,}만원 {v['m']}, 3년 타면 실제로 {v['total']:,}만원 나간다",
        f"{v['m']} 잔존가치 {v['r_pct']}% — {v['dep']:,}만원 감가의 의미 [{v['month_kr']}]",
        f"{v['m']} {v['t']} 월 유지비 {v['maint_m']:,}만원, 감당 가능한 수준일까",
        f"신차 {v['p']:,}만원 {v['m']}, 3년 뒤 중고값 {v['r_3yr']:,}만원의 현실",
        f"{v['yr']} {v['m']} {v['t']} — 가격·감가·유지비 한눈에 보기",
        f"{v['m']}{v['eul']} 사면 매달 얼마가 빠질까? 유지비 총정리 [{v['month_kr']}]",
        f"{v['m']} 3년 총비용 {v['total']:,}만원 — 신차값보다 중요한 숫자",
        f"{v['dep']:,}만원 감가 vs 유지비 {v['maint_m']*36:,}만원 — {v['m']} 실비용 분해",
        f"연봉 대비 {v['m']} 유지 가능할까? 월 {v['maint_m']:,}만원의 진실",
        f"{v['m']} {v['t']} {v['p']:,}만원, 지금 이 가격 적정한가 [{v['month_kr']}]",
    ]


# ════════════════════════════════════════════════════════════
# hotissue: 잔존가치·감가 중심, 손실회피 트리거
# ════════════════════════════════════════════════════════════
def _hotissue_vs(v):
    return [
        f"{v['m']} 샀다가 3년 뒤 {v['dep']:,}만원 날릴 수 있다 — {v['c']}와 감가 비교",
        f"{v['c']}보다 잔존가치 {abs(v['r_pct']-v['cr_pct'])}%p 높은 {v['m']}, 감가에서 판가름 난다",
        f"3년 후 중고값 {v['r_3yr']:,}만원 vs {v['c']} — 되팔 때 후회 없는 선택은?",
        f"{v['m']} vs {v['c']} 감가 비교 — 몰랐으면 {v['dep_diff']:,}만원 손해 볼 뻔",
        f"잔존가치로 보면 답 나온다 — {v['m']}{v['wa']} {v['c']} 3년 실비용 비교",
        f"{v['m']} 중고시세 {v['r_pct']}% 유지, {v['c']}는 {v['cr_pct']}% — 차이가 {v['dep_diff']:,}만원",
        f"{v['m']} 감가 {v['dep']:,}만원 vs {v['c']} {v['c_dep']:,}만원 — 어느 쪽이 더 빠지나",
        f"{v['p']:,}만원 {v['m']}과 {v['cp']:,}만원 {v['c']}, 3년 뒤 남는 돈은?",
        f"신차가 {v['price_diff']:,}만원 차이인데 잔존가치는 역전 — {v['m']} vs {v['c']}",
        f"{v['month_kr']} 기준 {v['m']} {v['c']} 감가율 최신 분석",
    ]

def _hotissue_solo(v):
    return [
        f"{v['m']} 3년 타고 팔면 {v['dep']:,}만원 빠진다 — 잔존가치 {v['r_pct']}%의 의미",
        f"{v['p']:,}만원에 산 {v['m']}, 3년 뒤 {v['r_3yr']:,}만원 — 감가 분석",
        f"중고로 팔 때 {v['r_pct']}% 남는 {v['m']}, 이 감가율이면 괜찮은 걸까",
        f"{v['m']} 잔존가치 연차별 하락 — 1년 뒤, 2년 뒤, 3년 뒤 예상 시세",
        f"신차 {v['p']:,}만원 {v['m']}, 감가 {v['dep']:,}만원 — 감당할 수 있는 수준?",
        f"{v['month_kr']} {v['m']} 중고시세 전망 — 잔존가치 {v['r_pct']}% 유지될까",
        f"{v['m']} 감가가 큰 이유 3가지와 대처법",
        f"{v['yr']} {v['m']} {v['t']} 잔존가치 분석 — 이 트림이 감가 적다",
        f"{v['m']}{v['eul']} 3년 보유하면 실제 비용 {v['total']:,}만원, 감가가 80%",
        f"잔존가치 {v['r_pct']}%로 본 {v['m']} 실질 소유비용",
    ]


# ════════════════════════════════════════════════════════════
# tco: 월환산, 체감비용 중심
# ════════════════════════════════════════════════════════════
def _tco_vs(v):
    return [
        f"{v['m']} 월 유지비 {v['maint_m']:,}만원 vs {v['c']} — 매달 이만큼 차이 난다",
        f"보험·세금·유류비 합치면? {v['m']}{v['wa']} {v['c']} 월 유지비 비교",
        f"{v['m']} 연 유지비 {v['fuel']+v['tax']+v['ins']:,}만원 — {v['c']}보다 저렴한가",
        f"월급에서 차값 빼면 남는 건? {v['m']} vs {v['c']} 실질 유지비 비교",
        f"{v['m']} 48개월 할부 월 {v['m48']:,}만원 + 유지비 {v['maint_m']:,}만원 = 매달 이 만큼",
        f"{v['c']}보다 유지비 싼 차는 {v['m']}? — 세금·보험·유류비 항목별 비교",
        f"유지비까지 합친 진짜 월 부담 — {v['m']} vs {v['c']} [{v['month_kr']}]",
        f"{v['m']} {v['c']} 3년 유지비 총합 비교 — {v['dep_diff']:,}만원 차이의 구성",
        f"연비 {v['eff']}km/L {v['m']}의 연간 유류비는 {v['fuel']:,}만원 — {v['c']}와 비교",
        f"할부+유지비 매달 합산하면? {v['m']} vs {v['c']} 실부담 비교",
    ]

def _tco_solo(v):
    return [
        f"{v['m']} 한 달 유지비 {v['maint_m']:,}만원 — 보험·세금·유류비 상세 분해",
        f"월 {v['m48']:,}만원 할부 + 유지비 {v['maint_m']:,}만원, {v['m']} 매달 총 지출은?",
        f"{v['m']} 연비 {v['eff']}km/L, 연간 유류비 {v['fuel']:,}만원의 현실",
        f"자동차세 {v['tax']:,}만원 + 보험 {v['ins']:,}만원 — {v['m']} 고정 지출 정리",
        f"{v['m']} 3년 유지비 {v['total']-v['dep']:,}만원, 감가 {v['dep']:,}만원 — 어디서 새는 걸까",
        f"연봉 4천이면 {v['m']} 유지할 수 있을까? 월 {v['maint_m']:,}만원의 현실",
        f"{v['m']} {v['t']} 연간 유지비 항목별 분석 [{v['month_kr']} 기준]",
        f"주유비만 월 {round(v['fuel']/12):,}만원, {v['m']} 유류비 절감법은?",
        f"{v['m']} 36개월 vs 48개월 vs 60개월 할부 비교 — 이자 차이는 얼마?",
        f"차값 {v['p']:,}만원 외에 3년간 {v['total']-v['dep']:,}만원 더 든다 — {v['m']} 유지비 총정리",
    ]


# ════════════════════════════════════════════════════════════
# deal: 구매 타이밍, 긴급성 중심
# ════════════════════════════════════════════════════════════
def _deal_vs(v):
    return [
        f"{v['month_kr']} {v['m']} vs {v['c']} — 지금 사야 할 차와 기다릴 차",
        f"{v['m']} {v['p']:,}만원 vs {v['c']} {v['cp']:,}만원 — 어느 쪽이 지금 사기 좋은 타이밍?",
        f"{v['m']} 재고 할인 가능성은? {v['c']}와 구매 타이밍 비교",
        f"분기말 할인 노린다면 — {v['m']}{v['wa']} {v['c']} 중 유리한 쪽은?",
        f"{v['m']} 신모델 출시 전 구모델 할인 vs {v['c']} 현행 가격 비교",
        f"지금 {v['m']} 사면 월 {v['m48']:,}만원, {v['c']}는 월 얼마? 할부 비교",
        f"{v['m']} {v['c']} {v['month_kr']} 가격 동향 — 인상 전에 사야 할까",
        f"3월 출고 대기 {v['m']} vs 즉시 출고 {v['c']} — 어느 쪽이 현명한 선택?",
        f"{v['m']} 할부 48개월 월 {v['m48']:,}만원 — {v['c']}와 월 부담 비교",
        f"가격 인하 가능성으로 본 {v['m']}{v['wa']} {v['c']} 구매 적기",
    ]

def _deal_solo(v):
    return [
        f"{v['month_kr']} {v['m']} {v['t']} {v['p']:,}만원 — 지금이 적정 가격인가",
        f"{v['m']} 출고 대기 {v['month_kr']} 현황과 할인 가능성",
        f"할부 48개월 월 {v['m48']:,}만원, {v['m']} 지금 질러도 될까",
        f"{v['m']} 전 트림 가격 비교 — 가성비 트림은 이것 [{v['month_kr']}]",
        f"{v['m']} 분기말 할인 받을 수 있을까? 구매 타이밍 분석",
        f"신차 {v['p']:,}만원 {v['m']}, 6개월 후 가격은 오를까 내릴까",
        f"{v['m']} {v['t']} 계약 전 체크리스트 — 할부·보험·탁송비",
        f"{v['m']} 36개월 월 {v['m36']:,}만원 vs 48개월 월 {v['m48']:,}만원 — 이자 차이 확인",
        f"지금 {v['m']} 사면 3년 뒤 {v['r_3yr']:,}만원에 팔 수 있다",
        f"{v['month_kr']} {v['m']} 구매 가이드 — 할인·할부·출고 총정리",
    ]


# ════════════════════════════════════════════════════════════
# compare: 승부·랭킹 중심
# ════════════════════════════════════════════════════════════
def _compare_vs(v):
    return [
        f"{v['m']} vs {v['c']} 7개 항목 비교 — 가격·연비·감가·유지비 종합 승자는?",
        f"가격은 {v['m']}, 연비는 {v['c']}? 항목별 승자 비교표",
        f"같은 예산 {v['p']:,}만원대, {v['m']}{v['wa']} {v['c']} 중 합리적인 선택은",
        f"{v['m']} vs {v['c']} 항목별 승패 — 5전 3선 결과는?",
        f"잔존가치 {v['r_pct']}% vs {v['cr_pct']}%, 유지비 {v['maint_m']:,}만원 vs ? — {v['m']} vs {v['c']} 데이터 대결",
        f"{v['m']}{v['wa']} {v['c']}, 데이터로 보면 답은 하나다 [{v['month_kr']}]",
        f"스펙·비용·잔존가치 종합 비교 — {v['m']} vs {v['c']} 최종 판정",
        f"{v['m']}{v['wa']} {v['c']} 구매 고민 중이라면 이 7가지 수치를 보세요",
        f"예산별 추천: {v['p']:,}만원 {v['m']} vs {v['cp']:,}만원 {v['c']}",
        f"{v['yr']} {v['m']} vs {v['c']} 비교 — 승자가 갈리는 단 하나의 항목",
    ]

def _compare_solo(v):
    return [
        f"{v['m']} {v['t']} 전 항목 분석 — 가격·연비·감가·유지비 점수표",
        f"{v['p']:,}만원대에서 {v['m']}보다 나은 선택이 있을까? [{v['month_kr']}]",
        f"{v['m']} 세그먼트 내 위치 — 가격 대비 잔존가치 랭킹",
        f"{v['m']} {v['t']} 종합 평가 — 어떤 항목에서 강하고 약한가",
        f"{v['yr']} {v['m']} 데이터 리뷰 — 연비 {v['eff']}km/L, 감가 {v['dep']:,}만원",
        f"이 세그먼트 최강자는? {v['m']} 가격·성능·비용 종합 분석",
        f"{v['m']} 트림별 가성비 랭킹 — 어떤 트림이 가장 합리적인가",
        f"수치로 본 {v['m']} 강점과 약점 — 객관 데이터 분석 [{v['month_kr']}]",
        f"{v['p']:,}만원 {v['m']}, 동급 대비 비싼가 싼가?",
        f"{v['m']} 잔존가치 {v['r_pct']}% — 세그먼트 평균 대비 높은 편일까",
    ]


# ════════════════════════════════════════════════════════════
# guide: 초보·공감 중심
# ════════════════════════════════════════════════════════════
def _guide_vs(v):
    return [
        f"첫차 고민 {v['m']} vs {v['c']} — 초보 운전자에게 맞는 차는?",
        f"{v['m']}{v['wa']} {v['c']}, 초보가 유지하기 쉬운 쪽은?",
        f"사회 초년생 첫차 {v['m']} vs {v['c']} — 보험·할부·유지비 비교",
        f"월급 250만원으로 {v['m']} 유지 가능? {v['c']}와 월 부담 비교",
        f"첫차로 {v['m']}{v['wa']} {v['c']} 중 고민이라면 이것부터 확인하세요",
        f"{v['m']} {v['c']} 보험료 비교 — 초보 할증 포함 실비용은?",
        f"첫차 예산 {v['p']:,}만원, {v['m']}{v['wa']} {v['c']} 월 부담 비교",
        f"{v['m']} 월 {v['maint_m']:,}만원 vs {v['c']} — 첫차 유지비 어느 쪽이 가벼울까",
        f"초보 운전자 첫차 {v['m']} vs {v['c']} — 할부·보험·유지비 현실 비교",
        f"{v['m']}{v['wa']} {v['c']}, 첫차로 3년 유지하면 총 얼마 차이 날까",
    ]

def _guide_solo(v):
    return [
        f"첫차로 {v['m']} 괜찮을까? 초보 운전자 관점 총정리",
        f"{v['m']} {v['t']} {v['p']:,}만원, 사회 초년생이 감당할 수 있을까",
        f"초보 운전자가 {v['m']} 사기 전 확인할 5가지",
        f"{v['m']} 월 유지비 {v['maint_m']:,}만원 — 첫차 유지비 시뮬레이션",
        f"{v['m']} 보험료 초보 할증 포함하면 얼마? 월 {v['maint_m']:,}만원의 현실",
        f"월급 250만원으로 {v['m']} 유지할 수 있을까? 월 부담 {v['maint_m']:,}만원 분석",
        f"첫차 {v['m']} {v['t']} 구매 가이드 — 트림 선택부터 보험까지",
        f"{v['p']:,}만원 {v['m']}, 첫차로 월 {v['m48']:,}만원 할부 감당 가능할까",
        f"대학생·직장인 첫차로 {v['m']} — 할부·유지비·보험 현실 체크",
        f"{v['m']} 48개월 할부 월 {v['m48']:,}만원 + 유지비 — 첫차 총 지출 시뮬레이션",
    ]


# ════════════════════════════════════════════════════════════
# ev: 전기차 전환, 충전비 중심
# ════════════════════════════════════════════════════════════
def _ev_vs(v):
    return [
        f"전기차 {v['m']} vs {v['c']} — 충전비·유류비 3년 차이는 {v['dep_diff']:,}만원",
        f"{v['m']} 충전비 월 {round(v['fuel']/12):,}만원 vs {v['c']} 주유비 — 진짜 저렴한 쪽은?",
        f"전기차로 갈아타면 이득일까? {v['m']}{v['wa']} {v['c']} 3년 비용 비교",
        f"{v['m']} 잔존가치 {v['r_pct']}% vs {v['c']} {v['cr_pct']}% — 전기차 감가가 더 큰가?",
        f"보조금 빼면 {v['m']} 실구매가는? {v['c']}와 비교한 실비용",
        f"충전 인프라까지 고려한 {v['m']} vs {v['c']} — 현실적인 전기차 전환 비용",
        f"하이브리드 {v['c']} vs 전기차 {v['m']} — 어느 쪽이 3년 뒤 유리할까",
        f"{v['m']} vs {v['c']} 세금 혜택 비교 — 전기차 연 {v['tax']:,}만원의 메리트",
        f"전기차 {v['m']} 매달 충전비 얼마? {v['c']}와 에너지 비용 비교",
        f"{v['month_kr']} 기준 {v['m']} vs {v['c']} — 전환 비용 손익 분석",
    ]

def _ev_solo(v):
    return [
        f"{v['m']} 충전비 월 {round(v['fuel']/12):,}만원 — 전기차 유지비의 현실",
        f"{v['p']:,}만원 {v['m']}, 보조금 받으면 실구매가는 얼마?",
        f"전기차 {v['m']} 3년 총비용 {v['total']:,}만원 — 내연기관 대비 이득일까",
        f"{v['m']} 잔존가치 {v['r_pct']}% — 전기차 감가가 걱정된다면 이 숫자를 보세요",
        f"아파트 거주자가 {v['m']} 사도 될까? 충전 현실 체크",
        f"{v['m']} 세금 연 {v['tax']:,}만원 — 전기차 세제 혜택 상세 정리",
        f"전기차 입문 {v['m']} {v['t']} {v['p']:,}만원 — 충전비·감가·보험 총정리",
        f"{v['m']} 1회 충전 주행거리와 전비 — 일상 주행에 충분한가",
        f"자택 충전 가능하면 {v['m']} 월 충전비 {round(v['fuel']/12):,}만원, 불가능하면?",
        f"{v['month_kr']} 전기차 {v['m']} 구매 가이드 — 보조금·충전·잔존가치",
    ]


# ════════════════════════════════════════════════════════════


# ════════════════════════════════════════════════════════════
# ev 사이트 — 하이브리드 전용 템플릿
# ════════════════════════════════════════════════════════════
def _ev_hev_vs(v):
    m = v['m']
    c = v['c']
    return [
        f"{m} vs {c} — 연비 대결, 3년 유지비 차이 {v['dep_diff']:,}만원",
        f"{m} 월 유지비 {v['maint_m']:,}만원 vs {c} — 어느 쪽이 경제적?",
        f"{m} 잔존가치 {v['r_pct']}% vs {c} {v['cr_pct']}% — 감가 비교",
        f"연비 {v['eff']}km/L {m} vs {c} — 3년 비용 비교",
        f"{m}{v['wa']} {c}, 유지비 현실 비교",
        f"{v['month_kr']} {m} vs {c} — 총비용 분석",
    ]

def _ev_hev_solo(v):
    m = v['m']
    h_tag = "" if "하이브리드" in m else " 하이브리드"
    return [
        f"{m} 연비 {v['eff']}km/L — 유지비 월 {v['maint_m']:,}만원의 현실",
        f"{v['p']:,}만원 {m},{h_tag} 내연기관보다 정말 이득일까",
        f"{m} 3년 총비용 {v['total']:,}만원 — 경제성 분석",
        f"{m} 자동차세 {v['tax']:,}만원, 보험 {v['ins']:,}만원 — 유지비 총정리",
        f"{m} 잔존가치 {v['r_pct']}% — 감가가 걱정된다면 이 숫자부터",
        f"연봉 대비 {m} 유지 가능할까 — 월 {v['maint_m']:,}만원 시뮬레이션",
        f"{v['month_kr']} {m} 구매 가이드 — 연비·세금·잔존가치",
    ]

# 메인 함수
# ════════════════════════════════════════════════════════════
SITE_VS = {
    "hotissue": _hotissue_vs,
    "tco": _tco_vs,
    "deal": _deal_vs,
    "compare": _compare_vs,
    "guide": _guide_vs,
    "ev": _ev_vs,
}

SITE_SOLO = {
    "hotissue": _hotissue_solo,
    "tco": _tco_solo,
    "deal": _deal_solo,
    "compare": _compare_solo,
    "guide": _guide_solo,
    "ev": _ev_solo,
}


def generate_title(data, site_id="hotissue"):
    v = _build_vars(data)
    has_comp = bool(v["c"])
    ftype = v.get("ftype", "")

    # ev 사이트: 하이브리드이면 전용 템플릿 사용
    if site_id == "ev" and "하이브리드" in ftype:
        if has_comp:
            pool = _common_vs(v) + _ev_hev_vs(v)
        else:
            pool = _common_solo(v) + _ev_hev_solo(v)
        return random.choice(pool)

    if site_id == "guide":
        # guide는 첫차/초보 전용 풀만 사용 (공용 풀 제외)
        if has_comp:
            pool = _guide_vs(v)
        else:
            pool = _guide_solo(v)
    elif has_comp:
        pool = _common_vs(v) + SITE_VS.get(site_id, _hotissue_vs)(v)
    else:
        pool = _common_solo(v) + SITE_SOLO.get(site_id, _hotissue_solo)(v)

    return random.choice(pool)
