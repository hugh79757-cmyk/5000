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
    "G클래스": "G 580",
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
    "벤츠": ["메르세데스-벤츠코리아(주)"],
    "아우디": ["아우디폭스바겐코리아(주)"],
    "볼보": ["볼보자동차코리아(주)"],
    "토요타": ["한국토요타자동차(주)"],
    "렉서스": ["한국토요타자동차(주)"],
    "혼다": ["혼다코리아(주)"],
}

def lookup_fuel_efficiency(conn, brand, model, displacement=None):
    c = conn.cursor()
    model_clean = model
    for suffix in [" 하이브리드", " 가솔린", " 디젤", " 터보", " LPi", " LPG", " 2.5", " 2.2", " 1.6"]:
        model_clean = model_clean.replace(suffix, "")
    # 모델명 매핑 적용
    if model_clean in MODEL_NAME_MAP:
        search_key = MODEL_NAME_MAP[model_clean]
    else:
        search_key = model_clean.split()[0] if model_clean.split() else model_clean
    brand_names = BRAND_MAP_API.get(brand, [brand])
    placeholders = ",".join(["?" for _ in brand_names])
    query = "SELECT display_eff, engine_displacement, fuel_nm FROM public_fuel_data WHERE source='CAREFF' AND model_nm LIKE ? AND comp_nm IN (" + placeholders + ") ORDER BY CAST(year AS INTEGER) DESC LIMIT 5"
    params = ["%" + search_key + "%"] + brand_names
    rows = c.execute(query, params).fetchall()
    if not rows:
        query2 = "SELECT display_eff, engine_displacement, fuel_nm FROM public_fuel_data WHERE source='CAREFF' AND model_nm LIKE ? ORDER BY CAST(year AS INTEGER) DESC LIMIT 5"
        rows = c.execute(query2, ["%" + search_key + "%"]).fetchall()
    if rows:
        for r in rows:
            eff = r["display_eff"]
            if eff and eff != "NULL":
                try:
                    return float(eff)
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
        "engine": build_engine_desc(car),
        "fuel_type": car['fuel_type'],
        "segment": car.get('segment', ''),
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
        "trim_lineup": [{"name": t['trim_name'], "price": t['price'], "fuel_eff": t.get('fuel_efficiency') or fuel_eff, "fuel": t.get('fuel', car['fuel_type'])} for t in trims],
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

    return data


def build_top5_rank_input(conn, topic, db_path):
    """세그먼트별 TOP5 랭킹 데이터 빌드"""
    c = conn.cursor()

    # 메인 차량으로 세그먼트 확정
    car_row = c.execute("SELECT * FROM cars WHERE car_id = ?", (topic["car_id"],)).fetchone()
    if not car_row:
        return None
    car = dict(car_row)
    segment = car.get("segment", "")
    if not segment:
        return None

    rank_type = topic.get("rank_type", "resale")

    # 같은 세그먼트 차량 전체 조회
    seg_cars = c.execute("""
        SELECT c.* FROM cars c
        WHERE c.segment = ? AND c.car_id != ?
        ORDER BY c.is_popular DESC, RANDOM()
        LIMIT 20
    """, (segment, car["car_id"])).fetchall()
    seg_cars = [dict(r) for r in seg_cars]

    candidates = [car] + seg_cars

    # 각 차량 대표 트림 데이터 수집
    ranked = []
    for cand in candidates:
        trims_raw = c.execute(
            "SELECT * FROM trims WHERE car_id = ? AND status = '시판' ORDER BY price",
            (cand["car_id"],)
        ).fetchall()
        trims = [dict(t) for t in trims_raw if t["price"] and t["price"] >= 500]
        if not trims:
            continue
        idx = select_representative_trim(trims)
        trim = trims[idx]

        fuel_eff = trim.get("fuel_efficiency")
        if not fuel_eff or fuel_eff == 0:
            fuel_eff = lookup_fuel_efficiency(conn, cand["brand"], cand["model"], cand["displacement"])
        if not fuel_eff or fuel_eff == 0:
            # 연비 없으면 연료 타입별 기본값 사용 (탈락 방지)
            ft = str(cand.get("fuel_type", ""))
            if "전기" in ft:
                fuel_eff = 4.5
            elif "하이브리드" in ft:
                fuel_eff = 16.0
            elif "디젤" in ft:
                fuel_eff = 14.0
            else:
                fuel_eff = 12.0

        tax = calc_tax(cand["displacement"], cand["fuel_type"])
        ins = calc_insurance(trim["price"])
        fuel_cost = calc_fuel_cost(ANNUAL_KM, fuel_eff, cand["fuel_type"], db_path)
        resale = estimate_resale(trim["price"], cand["brand"], cand["fuel_type"],
                                 cand.get("segment", ""), cand.get("model", ""))
        dep_3yr = trim["price"] - resale["resale_3yr"]
        maint_3yr = (tax + ins + fuel_cost) * 3
        total_3yr = dep_3yr + maint_3yr
        monthly = calc_monthly_payment(trim["price"], FINANCE_RATE, 48) + round((tax + ins + fuel_cost) / 12)

        ranked.append({
            "car_id": cand["car_id"],
            "model": cand["model"],
            "brand": cand["brand"],
            "trim": trim["trim_name"],
            "base_price": trim["price"],
            "fuel_efficiency": fuel_eff,
            "fuel_type": cand["fuel_type"],
            "displacement": cand["displacement"],
            "engine": build_engine_desc(cand),
            "tax_annual": tax,
            "insurance_estimate": ins,
            "annual_fuel_cost": fuel_cost,
            "resale_rate_percent": resale["resale_rate_percent"],
            "resale_3yr": resale["resale_3yr"],
            "three_year_depreciation": dep_3yr,
            "three_year_maintenance": maint_3yr,
            "three_year_total_cost": total_3yr,
            "monthly_total": monthly,
        })

    if len(ranked) < 3:
        return None

    # 랭킹 정렬
    if rank_type == "resale":
        ranked.sort(key=lambda x: x["resale_rate_percent"], reverse=True)
    elif rank_type == "maintenance":
        ranked.sort(key=lambda x: x["tax_annual"] + x["insurance_estimate"] + x["annual_fuel_cost"])
    elif rank_type == "monthly_cost":
        ranked.sort(key=lambda x: x["monthly_total"])
    else:  # value
        ranked.sort(key=lambda x: (x["resale_rate_percent"] + x["fuel_efficiency"]) / x["base_price"], reverse=True)

    top5 = ranked[:5]

    return {
        "type": "top5_rank",
        "segment": segment,
        "rank_type": rank_type,
        "rank_type_label": {
            "resale": "잔존가치",
            "maintenance": "연간 유지비",
            "monthly_cost": "월 총비용",
            "value": "가성비",
        }.get(rank_type, rank_type),
        "model": top5[0]["model"],
        "brand": top5[0]["brand"],
        "base_price": top5[0]["base_price"],
        "top5": top5,
        "total_candidates": len(ranked),
    }


PERSONA_CONFIGS = {
    "commuter": {
        "label": "출퇴근 40km 직장인",
        "annual_km": 18000,
        "finance_term": 48,
        "salary": 4000,
        "priority": "연비·유지비 최우선",
    },
    "newlywed": {
        "label": "신혼부부 첫 차",
        "annual_km": 15000,
        "finance_term": 48,
        "salary": 5000,
        "priority": "가격·잔존가치·실용성 균형",
    },
    "first_car": {
        "label": "사회초년생 첫 차",
        "annual_km": 12000,
        "finance_term": 60,
        "salary": 3000,
        "priority": "저예산·보험료·유지비 최소화",
        "insurance_surcharge": 1.4,
    },
    "family": {
        "label": "자녀 있는 가족",
        "annual_km": 20000,
        "finance_term": 60,
        "salary": 6000,
        "priority": "공간·안전·유지비",
    },
    "premium": {
        "label": "연봉 8,000만원+ 직장인",
        "annual_km": 15000,
        "finance_term": 36,
        "salary": 8000,
        "priority": "브랜드·잔존가치·승차감",
    },
}


def build_persona_pick_input(conn, topic, db_path):
    """페르소나 기반 차량 추천 데이터 빌드"""
    c = conn.cursor()

    car_row = c.execute("SELECT * FROM cars WHERE car_id = ?", (topic["car_id"],)).fetchone()
    if not car_row:
        return None
    car = dict(car_row)

    persona_type = topic.get("persona_type", "commuter")
    pcfg = PERSONA_CONFIGS.get(persona_type, PERSONA_CONFIGS["commuter"])

    trims_raw = c.execute(
        "SELECT * FROM trims WHERE car_id = ? AND status = '시판' ORDER BY price",
        (car["car_id"],)
    ).fetchall()
    trims = [dict(t) for t in trims_raw if t["price"] and t["price"] >= 500]
    if not trims:
        return None

    idx = select_representative_trim(trims)
    main_trim = trims[idx]

    annual_km = pcfg["annual_km"]
    finance_term = pcfg["finance_term"]

    fuel_eff = main_trim.get("fuel_efficiency")
    if not fuel_eff or fuel_eff == 0:
        fuel_eff = lookup_fuel_efficiency(conn, car["brand"], car["model"], car["displacement"])
    if not fuel_eff or fuel_eff == 0:
        return None

    tax = calc_tax(car["displacement"], car["fuel_type"])
    ins = calc_insurance(main_trim["price"])
    # 초보 할증 적용
    ins_surcharge = pcfg.get("insurance_surcharge", 1.0)
    ins_actual = round(ins * ins_surcharge)

    fuel_cost = calc_fuel_cost(annual_km, fuel_eff, car["fuel_type"], db_path)
    resale = estimate_resale(main_trim["price"], car["brand"], car["fuel_type"],
                             car.get("segment", ""), car.get("model", ""))
    dep_3yr = main_trim["price"] - resale["resale_3yr"]
    maint_3yr = (tax + ins_actual + fuel_cost) * 3
    total_3yr = dep_3yr + maint_3yr
    monthly_payment = calc_monthly_payment(main_trim["price"], FINANCE_RATE, finance_term)
    monthly_maintain = round((tax + ins_actual + fuel_cost) / 12)
    monthly_total = monthly_payment + monthly_maintain

    # 세후 월급 계산 (연봉의 72% / 12)
    salary = pcfg["salary"]
    monthly_net = round(salary * 0.72 / 12)
    monthly_ratio = round(monthly_total / monthly_net * 100, 1)

    data = {
        "type": "persona_pick",
        "persona_type": persona_type,
        "persona_label": pcfg["label"],
        "persona_priority": pcfg["priority"],
        "persona_annual_km": annual_km,
        "persona_finance_term": finance_term,
        "persona_salary": salary,
        "persona_monthly_net": monthly_net,
        "persona_monthly_ratio": monthly_ratio,
        "model": car["model"],
        "brand": car["brand"],
        "year": car["year"],
        "trim": main_trim["trim_name"],
        "base_price": main_trim["price"],
        "engine": build_engine_desc(car),
        "fuel_type": car["fuel_type"],
        "segment": car.get("segment", ""),
        "fuel_efficiency": fuel_eff,
        "displacement": car["displacement"],
        "finance_rate": FINANCE_RATE,
        "finance_term_months": finance_term,
        "monthly_payment_main": monthly_payment,
        "monthly_payment_36": calc_monthly_payment(main_trim["price"], FINANCE_RATE, 36),
        "monthly_payment_48": calc_monthly_payment(main_trim["price"], FINANCE_RATE, 48),
        "monthly_payment_60": calc_monthly_payment(main_trim["price"], FINANCE_RATE, 60),
        "annual_km": annual_km,
        "tax_annual": tax,
        "insurance_estimate": ins,
        "insurance_actual": ins_actual,
        "annual_fuel_cost": fuel_cost,
        "monthly_maintain": monthly_maintain,
        "monthly_total": monthly_total,
        **resale,
        "three_year_depreciation": dep_3yr,
        "three_year_maintenance": maint_3yr,
        "three_year_total_cost": total_3yr,
        "trim_lineup": [{"name": t["trim_name"], "price": t["price"]} for t in trims],
    }

    # 경쟁 모델
    if topic.get("competitor_car_id"):
        comp_row = c.execute("SELECT * FROM cars WHERE car_id = ?", (topic["competitor_car_id"],)).fetchone()
        comp = dict(comp_row) if comp_row else None
        comp_trims_raw = c.execute(
            "SELECT * FROM trims WHERE car_id = ? AND status = '시판' ORDER BY price",
            (topic["competitor_car_id"],)
        ).fetchall()
        comp_trims = [dict(t) for t in comp_trims_raw if t["price"] and t["price"] >= 500]
        if comp and comp_trims:
            cidx = select_matching_trim(comp_trims, main_trim["price"])
            ct = comp_trims[cidx]
            c_eff = ct.get("fuel_efficiency")
            if not c_eff or c_eff == 0:
                c_eff = lookup_fuel_efficiency(conn, comp["brand"], comp["model"], comp["displacement"]) or 12.0
            c_tax = calc_tax(comp["displacement"], comp["fuel_type"])
            c_ins = calc_insurance(ct["price"])
            c_fuel = calc_fuel_cost(annual_km, c_eff, comp["fuel_type"], db_path)
            c_resale = estimate_resale(ct["price"], comp["brand"], comp["fuel_type"],
                                       comp.get("segment", ""), comp.get("model", ""))
            c_dep = ct["price"] - c_resale["resale_3yr"]
            c_maint = (c_tax + c_ins + c_fuel) * 3
            c_total = c_dep + c_maint
            c_monthly = calc_monthly_payment(ct["price"], FINANCE_RATE, finance_term) + round((c_tax + c_ins + c_fuel) / 12)
            data.update({
                "competitor": comp["model"],
                "competitor_trim": ct["trim_name"],
                "competitor_price": ct["price"],
                "competitor_fuel_efficiency": c_eff,
                "competitor_tax_annual": c_tax,
                "competitor_insurance_estimate": c_ins,
                "competitor_annual_fuel_cost": c_fuel,
                "competitor_resale_rate_percent": c_resale["resale_rate_percent"],
                "competitor_three_year_depreciation": c_dep,
                "competitor_three_year_maintenance": c_maint,
                "competitor_three_year_total_cost": c_total,
                "competitor_monthly_total": c_monthly,
                "persona_saving_3yr": c_total - total_3yr,
            })

    return data

