import logging
logger = logging.getLogger(__name__)
import sqlite3
import json
import random
import re
from pathlib import Path

# 모델명 매핑 (carisyou → public_fuel_data)
MODEL_NAME_MAP = {
    "모델 Y": "Model Y",
    "모델 3": "Model 3",
    "그랑 콜레오스": "콜레오스",
    "그랑 콜레오스 하이브리드": "콜레오스",
    "필랑트": "ARKANA",
    "일렉트리파이드 G80": "G80 전동화",
    "무쏘 스포츠": "무쏘 2.3",
    "1시리즈": "118",
    "2시리즈 액티브 투어러": "218",
    "2시리즈 그란 쿠페": "220",
    "2시리즈": "220",
    "3시리즈": "320",
    "5시리즈": "520",
    "7시리즈": "740",
    "8시리즈": "840",
    "C클래스": "C200",
    "프리우스": "Prius",
    "캠리": "Camry",
    "오딧세이": "ODYSSEY",
    "RSQ8": "Q8",
    "마이바흐 S클래스": "Maybach S",
    "마이바흐 GLS": "Maybach GLS",
    "마이바흐 EQS SUV": "Maybach EQS",
    "마이바흐 SL": "Maybach SL",
    "RS3": "RS 3",
    "무쏘": "무쏘 2.3",
    "G클래스": "G 450",
}



BRAND_URLS = {
    "현대": "https://www.hyundai.com/kr/ko/e/vehicles",
    "기아": "https://www.kia.com/kr/vehicles",
    "제네시스": "https://www.genesis.com/kr/ko/models",
    "테슬라": "https://www.tesla.com/ko_kr",
    "BMW": "https://www.bmw.co.kr/ko/models.html",
    "벤츠": "https://www.mercedes-benz.co.kr/passengercars.html",
    "아우디": "https://www.audi.co.kr/kr/web/ko/models.html",
    "볼보": "https://www.volvocars.com/kr/cars",
    "토요타": "https://www.toyota.co.kr/vehicles",
    "렉서스": "https://www.lexus.co.kr/models",
    "혼다": "https://www.honda.co.kr/auto",
    "르노코리아": "https://www.renaultkorea.com/vehicles",
    "KGM": "https://www.kgm.com/vehicles.html",
    "쉐보레": "https://www.chevrolet.co.kr/cars",
}

BRAND_MAP_API = {
    "현대": ["현대자동차(주)", "현대자동차", "현대"],
    "기아": ["기아(주)", "기아자동차(주)", "기아자동차", "기아"],
    "제네시스": ["제네시스", "(주)제네시스"],
    "르노코리아": ["르노코리아자동차(주)", "르노삼성자동차(주)"],
    "KGM": ["KG모빌리티(주)", "쌍용자동차(주)"],
    "쉐보레": ["한국지엠(주)", "쉐보레"],
    "테슬라": ["테슬라코리아(유)"],
    "BMW": ["비엠더블유코리아(주)"],
    "벤츠": ["메르세데스-벤츠코리아(주)", "벤츠"],
    "아우디": ["아우디폭스바겐코리아(주)"],
    "볼보": ["볼보자동차코리아(주)"],
    "토요타": ["한국토요타자동차(주)"],
    "렉서스": ["한국토요타자동차(주)"],
    "혼다": ["혼다코리아(주)"],
}

def lookup_fuel_efficiency(conn, brand, model, displacement=None):
    c = conn.cursor()
    model_clean = model
    is_ev = "전기" in str(model)
    is_hev = "하이브리드" in str(model)
    for suffix in [" 하이브리드", " 가솔린", " 디젤", " 터보", " LPi", " LPG", " 2.5", " 2.2", " 1.6"]:
        model_clean = model_clean.replace(suffix, "")
    # 모델명 매핑 적용
    if model_clean in MODEL_NAME_MAP:
        search_key = MODEL_NAME_MAP[model_clean]
    else:
        search_key = model_clean.split()[0] if model_clean.split() else model_clean
    brand_names = BRAND_MAP_API.get(brand, [brand])
    placeholders = ",".join(["?" for _ in brand_names])
    # 연료타입 기반 필터
    fuel_filter = ""
    if is_ev:
        fuel_filter = " AND fuel_nm = '전기'"
    elif is_hev:
        fuel_filter = " AND model_nm LIKE '%하이브리드%'"
    else:
        fuel_filter = " AND fuel_nm != '전기' AND model_nm NOT LIKE '%하이브리드%'"
    query = "SELECT display_eff, engine_displacement, fuel_nm FROM public_fuel_data WHERE source='CAREFF' AND model_nm LIKE ? AND comp_nm IN (" + placeholders + ")" + fuel_filter + " ORDER BY CAST(year AS INTEGER) DESC LIMIT 5"
    params = ["%" + search_key + "%"] + brand_names
    rows = c.execute(query, params).fetchall()
    if not rows:
        query2 = "SELECT display_eff, engine_displacement, fuel_nm FROM public_fuel_data WHERE source='CAREFF' AND model_nm LIKE ?" + fuel_filter + " ORDER BY CAST(year AS INTEGER) DESC LIMIT 5"
        rows = c.execute(query2, ["%" + search_key + "%"]).fetchall()
    if rows:
        for r in rows:
            eff = r["display_eff"]
            if eff and eff != "NULL":
                try:
                    val = float(eff)
                    # 비전기 차량인데 연비 5 미만이면 전기차 데이터 혼입 — 스킵
                    if not is_ev and val < 5:
                        continue
                    return val
                except (ValueError, TypeError):
                    pass
    return None



def lookup_ev_specs(conn, brand, model):
    """public_fuel_data에서 EV 추가 스펙 조회 (주행거리, 배터리 등)"""
    c = conn.cursor()
    model_clean = model
    for suffix in [" 하이브리드", " 가솔린", " 디젤", " 터보"]:
        model_clean = model_clean.replace(suffix, "")
    search_key = model_clean.split()[0] if model_clean.split() else model_clean
    
    rows = c.execute("""
        SELECT display_eff, range_per_charge, engine_displacement, fuel_nm, model_nm
        FROM public_fuel_data 
        WHERE source='CAREFF' AND fuel_nm='전기' AND model_nm LIKE ?
        ORDER BY CAST(year AS INTEGER) DESC LIMIT 1
    """, ["%" + search_key + "%"]).fetchall()
    
    if rows:
        r = rows[0]
        return {
            "ev_range_km": int(r["range_per_charge"]) if r["range_per_charge"] and r["range_per_charge"] != "NULL" else None,
            "ev_efficiency": float(r["display_eff"]) if r["display_eff"] and r["display_eff"] != "NULL" else None,
            "ev_model_match": r["model_nm"],
        }
    return {}

def build_engine_desc(car):
    ft = str(car["fuel_type"] or "")
    disp = car["displacement"] or 0
    if "전기" in ft:
        return "전기모터"
    desc = ""
    if disp:
        liter = round(disp / 1000, 1)
        desc = str(liter) + "L"
    if "하이브리드" in ft:
        desc += " 하이브리드"
    elif "디젤" in ft or "경유" in ft:
        desc += " 디젤"
    elif "LPG" in ft or "LPi" in ft:
        desc += " LPG"
    elif "터보" in ft:
        desc += " 터보"
    elif disp:
        desc += " 가솔린"
    return desc if desc else ft

def calc_tax(displacement, fuel_type):
    if not displacement:
        return 13 if "전기" in str(fuel_type) else 0
    if displacement > 1600:
        base = displacement * 200
    elif displacement > 1000:
        base = displacement * 140
    else:
        base = displacement * 80
    return round(base * 1.3 / 10000)

def fuel_type_to_code(fuel_type):
    ft = str(fuel_type)
    if "경유" in ft or "디젤" in ft:
        return "D047"
    elif "LPG" in ft or "부탄" in ft or "엘피지" in ft:
        return "K015"
    elif "고급" in ft:
        return "B034"
    return "B027"

def get_live_fuel_price(fuel_type, db_path):
    code = fuel_type_to_code(fuel_type)
    try:
        conn_tmp = sqlite3.connect(str(db_path))
        conn_tmp.row_factory = sqlite3.Row
        row = conn_tmp.execute(
            "SELECT price FROM fuel_price_cache WHERE fuel_code=? ORDER BY fetched_at DESC LIMIT 1",
            (code,)
        ).fetchone()
        conn_tmp.close()
        if row and row["price"]:
            return float(row["price"])
    except (sqlite3.Error, ValueError) as e:
        import logging
        logging.getLogger(__name__).debug(f"[DATA_BUILDER] Failed to get fuel price: {e}")
    defaults = {"B027": 1833, "D047": 1832, "K015": 1012, "B034": 2090}
    return defaults.get(code, 1833)

def calc_fuel_cost(annual_km, efficiency, fuel_type, db_path):
    if not efficiency or efficiency == 0:
        return 0
    if "전기" in str(fuel_type):
        kwh_price = 292
        return round((annual_km / efficiency) * kwh_price / 10000)
    price = get_live_fuel_price(fuel_type, db_path)
    return round((annual_km / efficiency) * price / 10000)

def calc_insurance(price):
    if price <= 2000: return 70
    if price <= 3000: return 90
    if price <= 4000: return 110
    if price <= 5000: return 130
    if price <= 7000: return 160
    return 200

def estimate_resale(base_price, brand, fuel_type, segment="", model=""):
    """브랜드/연료/세그먼트/모델별 3년 잔존가치 추정 (결정론적)"""

    # 브랜드별 3년 잔존가치 기본율 (%, 업계 평균 기반)
    brand_rates = {
        "현대": 55, "기아": 53, "제네시스": 61,
        "테슬라": 52,
        "BMW": 48, "벤츠": 50, "아우디": 46,
        "볼보": 47, "렉서스": 55, "토요타": 57,
        "쉐보레": 45, "르노코리아": 43, "KGM": 44,
        "포르쉐": 62, "랜드로버": 45,
    }
    base_rate = brand_rates.get(brand, 48)

    # 연료 타입 보정
    ft = str(fuel_type)
    if "하이브리드" in ft and "플러그인" not in ft:
        base_rate += 5  # HEV 인기 높음
    elif "플러그인" in ft:
        base_rate += 1
    elif "전기" in ft:
        base_rate -= 8  # EV 감가 큼
    elif "디젤" in ft or "경유" in ft:
        base_rate -= 4  # 디젤 수요 감소
    elif "LPG" in ft or "엘피지" in ft:
        base_rate -= 6

    # 세그먼트 보정
    seg = str(segment)
    if "SUV" in seg:
        base_rate += 3
    elif "경차" in seg or "경형" in seg:
        base_rate -= 2
    elif "대형" in seg:
        base_rate += 1

    # 가격대 보정 (고가차일수록 감가 큼)
    if base_price > 8000:
        base_rate -= 5
    elif base_price > 6000:
        base_rate -= 3
    elif base_price > 4000:
        base_rate -= 1
    elif base_price < 2000:
        base_rate += 2

    # 인기 모델 프리미엄 (수요 높아 잔존가치 유지)
    model_premium = {
        "그랜저 하이브리드": 5, "그랜저": 3, "그랜저 2.5": 3,
        "싼타페 하이브리드": 4, "쏘렌토 하이브리드": 4,
        "투싼 하이브리드": 3, "스포티지 하이브리드": 3,
        "아반떼 하이브리드": 3, "K5 하이브리드": 3,
        "아이오닉 5": 2, "아이오닉 6": 1,
        "모닝": 2, "캐스퍼": 2, "레이": 2,
        "GV80": 4, "GV70": 3, "G80": 3,
        "모델 Y": 3,
    }
    base_rate += model_premium.get(model, 0)

    # 범위 제한
    base_rate = max(30, min(72, base_rate))

    # 연차별 감가 커브 (결정론적: 해시 기반 미세 변동)
    seed = hash(str(brand) + str(model) + str(base_price)) % 100
    micro = (seed - 50) * 0.02  # -1.0 ~ +1.0 범위

    yr1_rate = round(100 - 18 + micro, 1)  # 1년 후 약 82%
    yr2_rate = round(yr1_rate - 10 + micro * 0.5, 1)  # 2년 후 약 72%
    yr3_rate = round(base_rate + micro, 1)  # 3년 후 = base_rate

    # 정합성 보장
    yr3_rate = max(30, min(72, yr3_rate))
    yr2_rate = max(yr3_rate + 4, min(80, yr2_rate))
    yr1_rate = max(yr2_rate + 4, min(88, yr1_rate))

    return {
        "resale_1yr": round(base_price * yr1_rate / 100),
        "resale_2yr": round(base_price * yr2_rate / 100),
        "resale_3yr": round(base_price * yr3_rate / 100),
        "resale_rate_percent": round(yr3_rate),
    }

# ── 상수 정의 ──
CAR_CONSTANTS = {
    "annual_km": 15000,
    "finance_rate": 3.9,
    "finance_terms": [48, 36, 60],
    "default_fuel_price": 1650,
    "ev_kwh_price": 292,
    "min_trim_price": 500,
}

ANNUAL_KM = CAR_CONSTANTS["annual_km"]
FINANCE_RATE = CAR_CONSTANTS["finance_rate"]
FINANCE_TERMS = CAR_CONSTANTS["finance_terms"]
DEFAULT_FUEL_PRICE = CAR_CONSTANTS["default_fuel_price"]
EV_KWH_PRICE = CAR_CONSTANTS["ev_kwh_price"]
MIN_TRIM_PRICE = CAR_CONSTANTS["min_trim_price"]


def calc_monthly_payment(price_manwon, annual_rate, months):
    """월 할부금 계산 (만원 단위 반환)"""
    r = annual_rate / 100 / 12
    return round(price_manwon * 10000 * r * (1 + r) ** months / ((1 + r) ** months - 1) / 10000)

def select_representative_trim(trims):
    if len(trims) == 1:
        return 0
    if len(trims) == 2:
        return 1
    return len(trims) // 2

def select_matching_trim(comp_trims, target_price):
    if len(comp_trims) == 1:
        return 0
    best_idx = 0
    best_diff = abs(comp_trims[0]["price"] - target_price)
    for i, t in enumerate(comp_trims):
        diff = abs(t["price"] - target_price)
        if diff < best_diff:
            best_diff = diff
            best_idx = i
    return best_idx

def build_input(conn, topic, db_path):
    c = conn.cursor()
    car_row = c.execute('SELECT * FROM cars WHERE car_id = ?', (topic['car_id'],)).fetchone()
    if not car_row:
        return None
    car = dict(car_row)
    trims_raw = c.execute(
        'SELECT * FROM trims WHERE car_id = ? AND status = "시판" ORDER BY price',
        (topic['car_id'],)
    ).fetchall()
    trims = [dict(t) for t in trims_raw]
    # === 데이터 품질 필터 ===
    trims = [t for t in trims if t["price"] and t["price"] >= 500]
    if not trims:
        logger.warning(f"[BLOCK] 유효 트림 없음 (가격 비정상) - 발행 차단: {car['model']}")
        return None
    # 배기량 0 + 비전기 차량 차단
    ft = str(car.get("fuel_type", ""))
    if (not car["displacement"] or car["displacement"] == 0) and "전기" not in ft:
        logger.warning(f"[BLOCK] 배기량 0 + 비전기 - 발행 차단: {car['brand']} {car['model']} ({ft})")
        return None
    idx = select_representative_trim(trims)
    main_trim = trims[idx]
    annual_km = ANNUAL_KM
    tax = calc_tax(car['displacement'], car['fuel_type'])
    insurance = calc_insurance(main_trim['price'])
    fuel_eff = main_trim['fuel_efficiency']
    # 연비 비정상 감지: 5 미만(비전기)이면 배기량이 연비로 잘못 저장된 케이스
    ft_check = str(car.get("fuel_type", ""))
    if fuel_eff and fuel_eff > 0 and fuel_eff < 5 and "전기" not in ft_check:
        logger.warning(f"[연비보정] {car['brand']} {car['model']} trims 연비 {fuel_eff} 비정상 → public_fuel_data 재조회")
        fuel_eff = None
    if not fuel_eff or fuel_eff == 0:
        fuel_eff = lookup_fuel_efficiency(conn, car['brand'], car['model'], car['displacement'])
    if not fuel_eff or fuel_eff == 0:
        logger.warning("[BLOCK] 연비 데이터 없음 - 발행 차단: " + car['model'])
        return None
    fuel_cost = calc_fuel_cost(annual_km, fuel_eff, car['fuel_type'], db_path)
    resale = estimate_resale(main_trim['price'], car['brand'], car['fuel_type'], car.get('segment', ''), car.get('model', ''))
    dep_3yr = main_trim['price'] - resale["resale_3yr"]
    maint_3yr = (tax + insurance + fuel_cost) * 3
    total_3yr = dep_3yr + maint_3yr
    data = {
        "type": topic['post_type'],
        "model": car["model"],
        "brand": car['brand'],
        "year": car['year'],
        "trim": main_trim['trim_name'],
        "seats": "5인승",
        "base_price": main_trim['price'],
        "base_price_display": f"{main_trim['price'] / 10000:.1f}억원" if main_trim['price'] >= 10000 else f"{main_trim['price']:,}만원",
        "engine": build_engine_desc(car),
        "fuel_type": car['fuel_type'],
        "segment": car.get('segment', ''),
        "body_type": car.get('body_type', ''),
        "drive_type": car.get('drive_type', ''),
        "fuel_efficiency": fuel_eff,
        "displacement": car['displacement'],
        "discount": 0, "discount_conditions": "",
        "finance_rate": FINANCE_RATE, "finance_term_months": FINANCE_TERMS[0],
        "monthly_payment_48": calc_monthly_payment(main_trim['price'], FINANCE_RATE, 48),
        "monthly_payment_36": calc_monthly_payment(main_trim['price'], FINANCE_RATE, 36),
        "monthly_payment_60": calc_monthly_payment(main_trim['price'], FINANCE_RATE, 60),
        "annual_km": annual_km, "fuel_price_source": "opinet", "tax_annual": tax, "tax_annual_3yr": tax * 3,
        "insurance_estimate": insurance, "fuel_price": DEFAULT_FUEL_PRICE,
        "annual_fuel_cost": fuel_cost,
        **resale,
        "three_year_depreciation": dep_3yr,
        "three_year_maintenance": maint_3yr,
        "three_year_total_cost": total_3yr,
        "final_price": main_trim['price'],
        "trim_lineup": [{"name": t['trim_name'], "price": t['price'], "price_display": f"{t['price'] / 10000:.1f}억원" if t['price'] >= 10000 else f"{t['price']:,}만원", "fuel_eff": fuel_eff if (t.get('fuel_efficiency') and t['fuel_efficiency'] < 5 and "전기" not in ft_check) else (t.get('fuel_efficiency') or fuel_eff), "fuel": t.get('fuel', car['fuel_type'])} for t in trims],
    }
    if topic['competitor_car_id']:
        comp_row = c.execute('SELECT * FROM cars WHERE car_id = ?', (topic['competitor_car_id'],)).fetchone()
        comp = dict(comp_row) if comp_row else None
        comp_trims_raw = c.execute(
            'SELECT * FROM trims WHERE car_id = ? AND status = "시판" ORDER BY price',
            (topic['competitor_car_id'],)
        ).fetchall()
        comp_trims = [dict(t) for t in comp_trims_raw]
        comp_trims = [t for t in comp_trims if t["price"] and t["price"] >= 500]
        if comp and comp_trims:
            cidx = select_matching_trim(comp_trims, main_trim['price'])
            ct = comp_trims[cidx]
            c_tax = calc_tax(comp['displacement'], comp['fuel_type'])
            c_ins = calc_insurance(ct['price'])
            c_eff = ct['fuel_efficiency']
            if not c_eff or c_eff == 0:
                c_eff = lookup_fuel_efficiency(conn, comp['brand'], comp['model'], comp['displacement'])
            if not c_eff or c_eff == 0:
                c_eff = 12.0
            c_fuel = calc_fuel_cost(annual_km, c_eff, comp['fuel_type'], db_path)
            c_resale = estimate_resale(ct['price'], comp['brand'], comp['fuel_type'], comp.get('segment', ''), comp.get('model', ''))
            c_dep = ct['price'] - c_resale["resale_3yr"]
            c_maint = (c_tax + c_ins + c_fuel) * 3
            c_total = c_dep + c_maint
            data.update({
                "competitor": comp["model"],
                "competitor_trim": ct['trim_name'],
                "competitor_price": ct['price'],
                "competitor_engine": build_engine_desc(comp),
                "competitor_fuel_efficiency": c_eff,
                "competitor_displacement": comp['displacement'],
                "competitor_resale_1yr": c_resale["resale_1yr"],
                "competitor_resale_2yr": c_resale["resale_2yr"],
                "competitor_resale_3yr": c_resale["resale_3yr"],
                "competitor_resale_rate_percent": c_resale["resale_rate_percent"],
                "competitor_tax_annual": c_tax,
                "competitor_insurance_estimate": c_ins,
                "competitor_annual_fuel_cost": c_fuel,
                "competitor_three_year_depreciation": c_dep,
                "competitor_three_year_maintenance": c_maint,
                "competitor_three_year_total_cost": c_total,
                "competitor_final_price": ct['price'],
                "competitor_trim_lineup": " / ".join(f"{t['trim_name']} {t['price']:,}" for t in comp_trims),
            })
    data.update({
        "notes": "",
        "sources": [f"https://m.carisyou.com/car/{car['carisyou_id']}"],
        "cta_links": {"kb_chacha": "https://www.kbchachacha.com", "carisyou": "https://www.carisyou.com"},
        "thumbnail_url": "",
    })
    # EV 추가 데이터 보강 (배터리 용량, 주행거리 등)
    if car["fuel_type"] == "전기":
        ev_specs = lookup_ev_specs(conn, car["brand"], car["model"])
        if ev_specs:
            data["ev_range_km"] = ev_specs.get("ev_range_km")
            data["ev_efficiency"] = ev_specs.get("ev_efficiency")
            data["ev_model_match"] = ev_specs.get("ev_model_match")
        if car["battery_capacity_kwh"]:
            data["battery_capacity_kwh"] = car["battery_capacity_kwh"]

    # ── 데이터 Sanity Check (발행 전 최종 검증) ──
    _issues = []
    _ft = str(data.get("fuel_type", ""))
    _price = data.get("base_price", 0)
    _eff = data.get("fuel_efficiency", 0)
    _tax = data.get("tax_annual", 0)
    _ins = data.get("insurance_estimate", 0)
    _fuel = data.get("annual_fuel_cost", 0)
    _dep = data.get("three_year_depreciation", 0)
    _total = data.get("three_year_total_cost", 0)
    _resale_rate = data.get("resale_rate_percent", 0)

    # 연비 범위 (전기차: 2~8 km/kWh, 내연기관: 5~30 km/L)
    if "전기" in _ft:
        if _eff < 2 or _eff > 8:
            _issues.append(f"연비 비정상(전기): {_eff} km/kWh")
    else:
        if _eff < 5 or _eff > 30:
            _issues.append(f"연비 비정상(내연): {_eff} km/L")

    # 가격 범위 (최소 500만원, 최대 50000만원=5억)
    if _price < 500 or _price > 50000:
        _issues.append(f"가격 비정상: {_price}만원")

    # 브랜드별 가격 최소값 (수입차 1000만원 이상)
    _import_brands = ["BMW", "벤츠", "아우디", "볼보", "렉서스", "포르쉐", "테슬라"]
    if data.get("brand") in _import_brands and _price < 3000:
        _issues.append(f"수입차 가격 비정상: {data['brand']} {_price}만원")

    # 세금 범위 (0~200만원)
    if _tax < 0 or _tax > 200:
        _issues.append(f"자동차세 비정상: {_tax}만원")

    # 보험 범위 (30~300만원)
    if _ins < 30 or _ins > 300:
        _issues.append(f"보험료 비정상: {_ins}만원")

    # 연간 유류비 범위 (전기 0~50, 내연 50~500만원)
    if "전기" in _ft:
        if _fuel > 50:
            _issues.append(f"전기차 유류비 비정상: {_fuel}만원")
    else:
        if _fuel > 500:
            _issues.append(f"유류비 비정상: {_fuel}만원")

    # 잔존가치율 범위 (30~72%)
    if _resale_rate < 25 or _resale_rate > 80:
        _issues.append(f"잔존가치율 비정상: {_resale_rate}%")

    # 3년 감가 > 차량 가격이면 비정상
    if _dep > _price:
        _issues.append(f"감가 > 차량가: 감가 {_dep}만원 > 가격 {_price}만원")

    # 3년 총비용 상한 (차량가의 2배 초과 시 의심)
    if _total > _price * 2:
        _issues.append(f"3년 총비용 과다: {_total}만원 (차량가 {_price}만원의 {round(_total/_price*100)}%)")

    if _issues:
        logger.warning(f"[SANITY BLOCK] {data.get('brand')} {data.get('model')} — {_issues}")
        return None

    return data
