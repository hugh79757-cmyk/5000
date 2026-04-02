#!/usr/bin/env python3
"""CAP 데이터 자동 갱신 모듈
- 기존 차량 트림/가격 업데이트
- 카이즈유 신규 차량 탐색
- 이미지 부족 차량 보충
- publish.py 실행 전 호출됨
"""
import sqlite3
import requests
from bs4 import BeautifulSoup
import time
import re
import logging
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "car.db"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def refresh_trims(conn):
    """기존 차량의 트림/가격 업데이트 + 가격 변동 기록"""
    c = conn.cursor()
    cars = c.execute('SELECT car_id, carisyou_id, brand, model FROM cars WHERE carisyou_id > 0').fetchall()
    updated = 0
    price_changed = 0

    for car in cars:
        cid = car['carisyou_id']
        try:
            resp = requests.get(f"https://m.carisyou.com/car/{cid}", headers=HEADERS, timeout=10)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            table = soup.select_one("table")
            if not table:
                continue

            rows = table.select("tr")
            for row in rows:
                cells = row.select("td")
                if len(cells) < 2:
                    continue
                raw_name = cells[-2].get_text(strip=True) if len(cells) >= 3 else cells[0].get_text(strip=True)
                raw_price = cells[-1].get_text(strip=True)

                trim_name = re.sub(r'(A/T|M/T|DCT)', '', raw_name).strip()
                # 가격 파싱: "1억 2,345만원" → 12345, "5,745만원" → 5745
                raw_p = raw_price.replace(',', '').strip()
                eok_match = re.search(r'(\d+)억\s*(\d*)', raw_p)
                man_match = re.search(r'(\d+)만', raw_p)
                if eok_match:
                    eok = int(eok_match.group(1)) * 10000
                    rest = int(eok_match.group(2)) if eok_match.group(2) else 0
                    price = eok + rest
                elif man_match:
                    price = int(man_match.group(1))
                else:
                    price_match = re.search(r'\d+', raw_p)
                    if not price_match:
                        continue
                    price = int(price_match.group())
                if price < 500:
                    continue  # 비정상 가격 스킵

                status = "시판"
                first_cell = cells[0].get_text(strip=True) if len(cells) >= 3 else ""
                if "단종" in first_cell:
                    status = "단종"

                existing_trim = c.execute('SELECT price FROM trims WHERE car_id=? AND trim_name=?',
                    (car['car_id'], trim_name)).fetchone()
                if existing_trim and existing_trim['price'] and existing_trim['price'] != price:
                    old_p = existing_trim['price']
                    change_pct = round((price - old_p) / old_p * 100, 1)
                    c.execute("""INSERT INTO price_history (car_id, trim_name, old_price, new_price, change_amount, change_percent, detected_at)
                        VALUES (?,?,?,?,?,?,datetime('now'))""",
                        (car['car_id'], trim_name, old_p, price, price - old_p, change_pct))
                    price_changed += 1
                c.execute('''INSERT OR REPLACE INTO trims (car_id, trim_name, price, status, updated_at)
                    VALUES (?, ?, ?, ?, ?)''',
                    (car['car_id'], trim_name, price, status, datetime.now().isoformat()))
                updated += 1

        except Exception as e:
            logger.warning(f"트림 업데이트 실패 [{car['model']}]: {e}")
        time.sleep(0.3)

    conn.commit()
    logger.info(f"트림 업데이트: {updated}건, 가격변동: {price_changed}건")
    return updated


AUTO_REGISTER_BRANDS = {"현대", "기아", "제네시스", "테슬라", "벤츠", "BMW", "아우디", "볼보", "토요타", "혼다", "렉서스", "르노코리아", "KGM", "쉐보레"}

def parse_car_info(title):
    """카이즈유 타이틀에서 연도, 브랜드, 모델명 추출"""
    title = re.sub(r'\(.*?\)', '', title).strip()
    parts = title.split(" ", 2)
    if len(parts) < 3:
        return None, None, None
    year = int(parts[0]) if parts[0].isdigit() else None
    brand = parts[1]
    model = parts[2].replace("뉴 ", "")
    return year, brand, model


def make_car_id(brand, model, year):
    """car_id 자동 생성"""
    brand_map = {"현대": "", "기아": "", "제네시스": "genesis", "테슬라": "tesla", "벤츠": "benz",
                 "BMW": "bmw", "아우디": "audi", "볼보": "volvo", "토요타": "toyota",
                 "혼다": "honda", "렉서스": "lexus", "르노코리아": "renault", "KGM": "kgm", "쉐보레": "chevy"}
    model_map = {
        "쏘나타 하이브리드": "sonata_hev", "쏘나타": "sonata", "그랜저 하이브리드": "grandeur_hev",
        "그랜저": "grandeur", "아반떼 하이브리드": "avante_hev", "아반떼": "avante",
        "투싼 하이브리드": "tucson_hev", "투싼": "tucson", "싼타페 하이브리드": "santafe_hev",
        "싼타페": "santafe", "코나 하이브리드": "kona_hev", "코나": "kona",
        "아이오닉 5 N": "ioniq5n", "아이오닉 5": "ioniq5", "아이오닉 6 N": "ioniq6n",
        "아이오닉 6": "ioniq6", "캐스퍼": "casper", "K8 하이브리드": "k8_hev", "K8": "k8",
        "K5 하이브리드": "k5_hev", "K5": "k5", "K9": "k9", "EV6": "ev6", "EV5": "ev5",
        "쏘렌토 하이브리드": "sorento_hev", "쏘렌토": "sorento",
        "스포티지 하이브리드": "sportage_hev", "스포티지": "sportage",
        "모닝": "morning", "레이 EV": "ray_ev", "레이": "ray", "모델 Y": "model_y",
        "GV80 쿠페": "gv80_coupe", "GV80": "gv80",
        "GV60 마그마": "gv60_magma", "G70 슈팅 브레이크": "g70_shooting_brake",
        "일렉트리파이드 G80": "electrified_g80",
        "마이바흐 EQS SUV": "maybach_eqs_suv", "마이바흐 GLS": "maybach_gls",
        "마이바흐 S클래스": "maybach_s_class", "마이바흐 SL": "maybach_sl",
        "C클래스": "c_class", "G클래스": "g_class",
        "1시리즈": "1_series", "2시리즈 그란 쿠페": "2_series_gran_coupe",
        "2시리즈 액티브 투어러": "2_series_active_tourer",
        "2시리즈": "2_series", "3시리즈": "3_series",
        "5시리즈": "5_series", "7시리즈": "7_series", "8시리즈": "8_series",
        "오딧세이": "odyssey", "무쏘 스포츠": "musso_sports", "무쏘": "musso",
        "렉스턴": "rexton", "토레스 EVX": "torres_evx",
        "그랑 콜레오스 하이브리드": "grand_koleos_hev", "그랑 콜레오스": "grand_koleos",
        "필랑트": "philant", "모델 3": "model_3",
        "캠리": "camry", "프리우스": "prius",
        "Q4 e-트론": "q4_etron", "Q6 e-트론": "q6_etron",
        "RS e-트론 GT": "rs_etron_gt", "S e-트론 GT": "s_etron_gt",
        "EX30 크로스 컨트리": "ex30_cross_country", "V60 크로스 컨트리": "v60_cross_country",
        "포터2 일렉트릭": "porter2_electric", "아이오닉 9": "ioniq9",
    }
    model_key = model_map.get(model, re.sub(r'[^a-zA-Z0-9]', '_', model.lower()))
    prefix = brand_map.get(brand, brand.lower())
    cid = f"{prefix}_{model_key}_{year}" if prefix else f"{model_key}_{year}"
    return re.sub(r'_+', '_', cid).strip('_')


def guess_fuel_type(title):
    t = title.upper()
    if "하이브리드" in title: return "가솔린/하이브리드"
    # 전기차 모델명 패턴
    ev_keywords = ["EV", "일렉트릭", "전기", "E-트론", "이트론", "IONIQ", "아이오닉",
                   "모델 Y", "모델 3", "MODEL", "TESLA", "테슬라", "볼트", "BOLT",
                   "ID.", "EQE", "EQS", "EQA", "EQB", "I4", "I5", "I7", "IX",
                   "GV60", "일렉트리파이드", "EX30", "EX90", "EC6", "ET5"]
    for kw in ev_keywords:
        if kw.upper() in t or kw in title:
            return "전기"
    return "가솔린"


def guess_segment(title):
    if any(k in title for k in ["K9", "마이바흐", "팬텀"]): return "대형세단"
    if any(k in title for k in ["그랜저", "K8"]): return "준대형세단"
    if any(k in title for k in ["쏘나타", "K5", "어코드"]): return "중형세단"
    if any(k in title for k in ["아반떼"]): return "준중형세단"
    if any(k in title for k in ["싼타페", "쏘렌토", "GV80", "GLE", "GLS"]): return "중형SUV"
    if any(k in title for k in ["투싼", "스포티지", "아이오닉 5", "EV6", "EV5"]): return "준중형SUV"
    if any(k in title for k in ["코나", "셀토스"]): return "소형SUV"
    if any(k in title for k in ["캐스퍼", "모닝", "레이"]): return "경차"
    return "기타"


def scan_new_cars(conn):
    """카이즈유에서 최신 차량 탐색 + 자동 등록"""
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    already = c.execute('SELECT id FROM scan_log WHERE scan_date=?', (today,)).fetchone()
    if already:
        logger.info("오늘 이미 탐색 완료 - 스킵")
        return []
    
    max_id = c.execute('SELECT MAX(carisyou_id) FROM cars').fetchone()[0] or 7650
    last_scan = c.execute('SELECT max_scanned_id FROM scan_log ORDER BY id DESC LIMIT 1').fetchone()
    if last_scan and last_scan[0] > max_id:
        max_id = last_scan[0]
    scan_start = max_id + 1
    scan_end = scan_start + 30

    found = []
    auto_added = 0
    logger.info(f"신규 차량 탐색: {scan_start}~{scan_end}")

    for cid in range(scan_start, scan_end + 1):
        try:
            resp = requests.get(f"https://m.carisyou.com/car/{cid}", headers=HEADERS, timeout=5)
            if resp.status_code != 200 or len(resp.text) < 50000:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            title_tag = soup.select_one("title")
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True).replace(" - 카이즈유 자동차 정보", "")

            imgs = soup.select("img[src*='file.carisyou.com/upload']")
            img_count = len(imgs)

            if img_count < 5:
                continue

            found.append((cid, title, img_count))
            logger.info(f"  신규 발견: {cid} {title} ({img_count}장)")

            year, brand, model = parse_car_info(title)
            if not brand or brand not in AUTO_REGISTER_BRANDS:
                continue

            existing = c.execute('SELECT car_id FROM cars WHERE carisyou_id=?', (cid,)).fetchone()
            if existing:
                continue

            car_id = make_car_id(brand, model, year)
            existing2 = c.execute('SELECT car_id FROM cars WHERE car_id=?', (car_id,)).fetchone()
            if existing2:
                continue

            fuel = guess_fuel_type(title)
            segment = guess_segment(model)
            # 배기량 추출 시도 (페이지 테이블에서)
            disp = 0
            try:
                spec_cells = soup.select("td")
                for sc in spec_cells:
                    txt = sc.get_text(strip=True)
                    dm = re.search(r"([\d,]+)\s*cc", txt)
                    if dm:
                        disp = int(dm.group(1).replace(",", ""))
                        break
            except (AttributeError, ValueError):
                pass
            body = "SUV" if "SUV" in segment else "세단" if "세단" in segment else "경차" if "경차" in segment else "기타"

            c.execute("""INSERT INTO cars (car_id, carisyou_id, brand, model, year, fuel_type, displacement, segment, body_type, drive_type, is_popular, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'FWD', 0, datetime('now'))""",
                (car_id, cid, brand, model, year, fuel, disp, segment, body))

            for img in imgs:
                src = img.get("src", "")
                if not src: continue
                if src.startswith("//"): src = "https:" + src
                elif not src.startswith("http"): continue
                src = src.replace("/thumb/", "/")
                c.execute('INSERT OR IGNORE INTO car_images (car_id, image_url, source) VALUES (?, ?, ?)',
                          (car_id, src, "carisyou"))

            auto_added += 1
            logger.info(f"  자동 등록: {car_id} ({brand} {model} {year})")

        except Exception as e:
            logger.warning(f"  탐색 실패 {cid}: {e}")
        time.sleep(0.2)

    conn.commit()
    c.execute('INSERT OR REPLACE INTO scan_log (scan_date, max_scanned_id, cars_found, cars_registered) VALUES (?,?,?,?)',
              (today, scan_end, len(found), auto_added))
    conn.commit()
    logger.info(f"신규 차량 {len(found)}대 발견, {auto_added}대 자동 등록 (탐색범위: {scan_start}~{scan_end})")
    return found



def validate_ingested_data(conn):
    """데이터 수집 직후 이상값 검출 — 자동 보정 또는 플래그"""
    import logging
    logger = logging.getLogger(__name__)
    c = conn.cursor()
    fixed = 0
    flagged = 0

    # ── 1. 가격 이상값: 500만원 미만 또는 50,000만원(5억) 초과 ──
    bad_prices = c.execute("""
        SELECT t.rowid, c.brand, c.model, t.trim_name, t.price
        FROM trims t JOIN cars c ON c.car_id=t.car_id
        WHERE t.price IS NOT NULL AND (t.price < 500 OR t.price > 50000)
    """).fetchall()
    for r in bad_prices:
        logger.warning(f"[INGEST CHECK] 가격 이상: {r['brand']} {r['model']} {r['trim_name']} = {r['price']}만원")
        flagged += 1

    # ── 2. 연비와 배기량 혼입: 비전기차인데 연비가 배기량/1000과 동일 ──
    disp_mix = c.execute("""
        SELECT t.rowid AS rid, c.brand, c.model, t.trim_name, t.fuel_efficiency, c.displacement
        FROM trims t JOIN cars c ON c.car_id=t.car_id
        WHERE c.fuel_type NOT LIKE '%전기%'
          AND t.fuel_efficiency IS NOT NULL AND t.fuel_efficiency > 0
          AND c.displacement > 0
          AND ABS(t.fuel_efficiency - CAST(c.displacement AS REAL)/1000) < 0.1
    """).fetchall()
    if disp_mix:
        from pipelines.car.data_builder import lookup_fuel_efficiency
        for r in disp_mix:
            correct = lookup_fuel_efficiency(conn, r["brand"], r["model"], r["displacement"])
            if correct and correct > 4:
                c.execute("UPDATE trims SET fuel_efficiency=? WHERE rowid=?", (correct, r["rid"]))
                logger.info(f"[INGEST FIX] 배기량 혼입 수정: {r['brand']} {r['model']} {r['trim_name']} {r['fuel_efficiency']} → {correct}")
                fixed += 1
            else:
                logger.warning(f"[INGEST FLAG] 배기량 혼입 의심 (보정 실패): {r['brand']} {r['model']} {r['trim_name']} = {r['fuel_efficiency']}")
                flagged += 1

    # ── 3. 비전기차 연비 5미만: 이상값 ──
    low_eff = c.execute("""
        SELECT t.rowid AS rid, c.brand, c.model, t.trim_name, t.fuel_efficiency, c.displacement
        FROM trims t JOIN cars c ON c.car_id=t.car_id
        WHERE c.fuel_type NOT LIKE '%전기%'
          AND t.fuel_efficiency > 0 AND t.fuel_efficiency < 5
    """).fetchall()
    if low_eff:
        from pipelines.car.data_builder import lookup_fuel_efficiency
        for r in low_eff:
            correct = lookup_fuel_efficiency(conn, r["brand"], r["model"], r["displacement"])
            if correct and correct >= 5:
                c.execute("UPDATE trims SET fuel_efficiency=? WHERE rowid=?", (correct, r["rid"]))
                logger.info(f"[INGEST FIX] 저연비 수정: {r['brand']} {r['model']} {r['trim_name']} {r['fuel_efficiency']} → {correct}")
                fixed += 1
            else:
                logger.warning(f"[INGEST FLAG] 저연비 보정 실패: {r['brand']} {r['model']} {r['trim_name']} = {r['fuel_efficiency']}")
                flagged += 1

    # ── 4. 수입차 최소 가격 위반 ──
    import_brands = ["BMW", "벤츠", "아우디", "볼보", "렉서스", "포르쉐", "테슬라", "토요타", "혼다"]
    placeholders = ",".join(["?"] * len(import_brands))
    cheap_imports = c.execute(f"""
        SELECT c.brand, c.model, t.trim_name, t.price
        FROM trims t JOIN cars c ON c.car_id=t.car_id
        WHERE c.brand IN ({placeholders}) AND t.price > 0 AND t.price < 2000
    """, import_brands).fetchall()
    for r in cheap_imports:
        logger.warning(f"[INGEST FLAG] 수입차 저가: {r['brand']} {r['model']} {r['trim_name']} = {r['price']}만원")
        flagged += 1

    conn.commit()
    if fixed or flagged:
        logger.info(f"[INGEST CHECK] 완료 — 자동수정: {fixed}건, 플래그: {flagged}건")
    return fixed, flagged

def fill_trim_efficiency(conn):
    """trims 테이블의 fuel_efficiency가 NULL인 항목을 public_fuel_data에서 보충"""
    import sys
    if "/Users/twinssn/Projects/5000" not in sys.path:
        sys.path.insert(0, "/Users/twinssn/Projects/5000")
    from pipelines.car.data_builder import lookup_fuel_efficiency

    c = conn.cursor()
    rows = c.execute("""
        SELECT t.rowid AS rid, t.car_id, t.trim_name, c.brand, c.model, c.displacement
        FROM trims t JOIN cars c ON t.car_id = c.car_id
        WHERE (t.fuel_efficiency IS NULL OR t.fuel_efficiency = 0)
    """).fetchall()

    filled = 0
    for r in rows:
        eff = lookup_fuel_efficiency(conn, r["brand"], r["model"], r["displacement"])
        if eff and eff > 0:
            c.execute("UPDATE trims SET fuel_efficiency=? WHERE rowid=?", (eff, r["rid"]))
            filled += 1

    conn.commit()
    if filled > 0:
        logger.info(f"  [연비보충] {filled}/{len(rows)}건 매칭 완료")
    return filled


def refresh_images(conn):
    """이미지 부족 차량 보충 (차단 목록 제외)"""
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS blocked_images (id INTEGER PRIMARY KEY, image_url TEXT UNIQUE, blocked_at TEXT DEFAULT (datetime('now')))")
    blocked = {r[0] for r in c.execute("SELECT image_url FROM blocked_images").fetchall()}
    cars = c.execute('SELECT car_id, carisyou_id, brand, model FROM cars WHERE carisyou_id > 0').fetchall()
    total_new = 0

    for car in cars:
        cnt = c.execute('SELECT COUNT(*) FROM car_images WHERE car_id=?', (car['car_id'],)).fetchone()[0]
        if cnt >= 8:
            continue

        try:
            resp = requests.get(f"https://m.carisyou.com/car/{car['carisyou_id']}", headers=HEADERS, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            imgs = soup.select("img[src*='file.carisyou.com/upload']")
            added = 0
            for img in imgs:
                src = img.get("src", "")
                if not src:
                    continue
                if src.startswith("//"):
                    src = "https:" + src
                elif not src.startswith("http"):
                    continue
                src = src.replace("/thumb/", "/")
                if src in blocked:
                    continue
                try:
                    c.execute('INSERT OR IGNORE INTO car_images (car_id, image_url, source) VALUES (?, ?, ?)',
                              (car['car_id'], src, "carisyou"))
                    if c.rowcount > 0:
                        added += 1
                except (AttributeError, ValueError):
                    pass
            if added > 0:
                total_new += added
                logger.info(f"  [{car['brand']} {car['model']}] +{added}장")
        except (AttributeError, ValueError):
            logger.debug(f"[DAILY_REFRESH] Image fetch failed: {e}")
        time.sleep(0.3)

    conn.commit()
    logger.info(f"이미지 보충: {total_new}장 (차단: {len(blocked)}개)")
    return total_new


def replenish_topics(conn, min_pending=50):
    """사이트별 post_type 토픽이 min_pending 미만이면 자동 보충"""
    c = conn.cursor()

    SITE_POST_TYPE = {
        "hotissue": "resale_compare",
        "tco": "tco_analysis",
        "deal": "promo_deal",
        "compare": "ranking_compare",
        "guide": "beginner_guide",
        "ev": "ev_analysis",
    }

    # 인기차 목록
    popular = c.execute(
        "SELECT car_id, brand, model, segment, fuel_type FROM cars WHERE is_popular=1"
    ).fetchall()

    # 비인기차 목록 (롱테일 트래픽용)
    unpopular = c.execute(
        "SELECT car_id, brand, model, segment, fuel_type FROM cars WHERE is_popular=0 AND segment!='상용차' ORDER BY RANDOM()"
    ).fetchall()

    # 세그먼트별 그룹핑
    seg_map = {}
    for car in popular:
        seg = car["segment"]
        if seg not in seg_map:
            seg_map[seg] = []
        seg_map[seg].append(car)

    # 경쟁차 조합 생성: 같은 세그먼트 내 다른 차량
    pairs = []
    for seg, cars in seg_map.items():
        for i, a in enumerate(cars):
            for b in cars[i+1:]:
                pairs.append((a["car_id"], b["car_id"]))
                pairs.append((b["car_id"], a["car_id"]))

    # 비인기차 세그먼트별 비교 조합
    unpop_seg_map = {}
    for car in unpopular:
        seg = car["segment"]
        if seg not in unpop_seg_map:
            unpop_seg_map[seg] = []
        unpop_seg_map[seg].append(car)

    unpop_pairs = []
    for seg, ucars in unpop_seg_map.items():
        for i, a in enumerate(ucars):
            for b in ucars[i+1:]:
                unpop_pairs.append((a["car_id"], b["car_id"]))
                unpop_pairs.append((b["car_id"], a["car_id"]))

    # 단독 토픽 (경쟁차 없음): tco, deal, guide, ev
    solos = [car["car_id"] for car in popular]

    # EV 전용 필터
    ev_cars = [car["car_id"] for car in popular if car["fuel_type"] in ("전기", "가솔린/하이브리드")]

    total_created = 0

    for site_id, post_type in SITE_POST_TYPE.items():
        # 현재 pending 수
        row = c.execute(
            "SELECT COUNT(*) FROM topics WHERE site_id=? AND post_type=? AND status='pending'",
            (site_id, post_type)
        ).fetchone()
        current = row[0]

        if current >= min_pending:
            continue

        # 인기차/비인기차 비율: 전체의 2/3는 인기차, 1/3은 비인기차
        pop_pending = c.execute(
            "SELECT COUNT(*) FROM topics t JOIN cars c ON t.car_id=c.car_id WHERE t.site_id=? AND t.post_type=? AND t.status='pending' AND c.is_popular=1",
            (site_id, post_type)
        ).fetchone()[0]
        unpop_pending = current - pop_pending
        min_popular = min_pending * 2 // 3      # 20
        min_unpopular = min_pending - min_popular  # 10
        need_popular = max(0, min_popular - pop_pending)
        need_unpopular = max(0, min_unpopular - unpop_pending)
        need = need_popular + need_unpopular
        if need == 0:
            continue
        created = 0

        if post_type == "resale_compare" or post_type == "ranking_compare":
            # 비교 글: 경쟁차 조합 필요
            for car_a, car_b in pairs:
                if created >= need:
                    break
                exists = c.execute(
                    "SELECT 1 FROM topics WHERE car_id=? AND competitor_car_id=? AND post_type=? AND site_id=? AND status IN ('pending','skip_no_data','published')",
                    (car_a, car_b, post_type, site_id)
                ).fetchone()
                if not exists:
                    pri = 7
                    c.execute(
                        "INSERT INTO topics (car_id, competitor_car_id, post_type, priority, status, created_at, site_id) VALUES (?,?,?,?,?,datetime('now'),?)",
                        (car_a, car_b, post_type, pri, "pending", site_id)
                    )
                    created += 1

            # 인기차 소진 시 비인기차 비교 조합 추가
            if created < need:
                unpop_created = 0
                for car_a, car_b in unpop_pairs:
                    if unpop_created >= need_unpopular or created >= need:
                        break
                    exists = c.execute(
                        "SELECT 1 FROM topics WHERE car_id=? AND competitor_car_id=? AND post_type=? AND site_id=? AND status IN ('pending','skip_no_data','published')",
                        (car_a, car_b, post_type, site_id)
                    ).fetchone()
                    if not exists:
                        c.execute(
                            "INSERT INTO topics (car_id, competitor_car_id, post_type, priority, status, created_at, site_id) VALUES (?,?,?,5,'pending',datetime('now'),?)",
                            (car_a, car_b, post_type, site_id)
                        )
                        created += 1
                        unpop_created += 1

        elif post_type == "ev_analysis":
            # EV 전용
            for car_id in ev_cars:
                if created >= need:
                    break
                exists = c.execute(
                    "SELECT 1 FROM topics WHERE car_id=? AND post_type=? AND site_id=? AND status IN ('pending','skip_no_data','published')",
                    (car_id, post_type, site_id)
                ).fetchone()
                if not exists:
                    c.execute(
                        "INSERT INTO topics (car_id, competitor_car_id, post_type, priority, status, created_at, site_id) VALUES (?,NULL,?,7,'pending',datetime('now'),?)",
                        (car_id, post_type, site_id)
                    )
                    created += 1
            # EV 비교 조합도 추가
            for i, a in enumerate(ev_cars):
                for b in ev_cars[i+1:]:
                    if created >= need:
                        break
                    exists = c.execute(
                        "SELECT 1 FROM topics WHERE car_id=? AND competitor_car_id=? AND post_type=? AND site_id=? AND status IN ('pending','skip_no_data','published')",
                        (a, b, post_type, site_id)
                    ).fetchone()
                    if not exists:
                        c.execute(
                            "INSERT INTO topics (car_id, competitor_car_id, post_type, priority, status, created_at, site_id) VALUES (?,?,?,7,'pending',datetime('now'),?)",
                            (a, b, post_type, site_id)
                        )
                        created += 1

            # 인기 EV 소진 시 비인기 전기차/하이브리드 추가
            if created < need:
                unpop_ev = [car["car_id"] for car in unpopular if car["fuel_type"] in ("전기", "가솔린/하이브리드")]
                for car_id in unpop_ev:
                    if created >= need:
                        break
                    exists = c.execute(
                        "SELECT 1 FROM topics WHERE car_id=? AND post_type=? AND site_id=? AND status IN ('pending','skip_no_data','published')",
                        (car_id, post_type, site_id)
                    ).fetchone()
                    if not exists:
                        c.execute(
                            "INSERT INTO topics (car_id, competitor_car_id, post_type, priority, status, created_at, site_id) VALUES (?,NULL,?,9,'pending',datetime('now'),?)",
                            (car_id, post_type, site_id)
                        )
                        created += 1

        else:
            # tco_analysis, promo_deal, beginner_guide: 단독 토픽
            # 인기차 (priority 7)
            for car_id in solos:
                if created >= need_popular:
                    break
                exists = c.execute(
                    "SELECT 1 FROM topics WHERE car_id=? AND post_type=? AND site_id=? AND status IN ('pending','skip_no_data','published')",
                    (car_id, post_type, site_id)
                ).fetchone()
                if not exists:
                    c.execute(
                        "INSERT INTO topics (car_id, competitor_car_id, post_type, priority, status, created_at, site_id) VALUES (?,NULL,?,7,'pending',datetime('now'),?)",
                        (car_id, post_type, site_id)
                    )
                    created += 1
            # 비인기차 (priority 5)
            unpop_created = 0
            for car in unpopular:
                if unpop_created >= need_unpopular:
                    break
                exists = c.execute(
                    "SELECT 1 FROM topics WHERE car_id=? AND post_type=? AND site_id=? AND status IN ('pending','skip_no_data','published')",
                    (car["car_id"], post_type, site_id)
                ).fetchone()
                if not exists:
                    c.execute(
                        "INSERT INTO topics (car_id, competitor_car_id, post_type, priority, status, created_at, site_id) VALUES (?,NULL,?,5,'pending',datetime('now'),?)",
                        (car["car_id"], post_type, site_id)
                    )
                    created += 1
                    unpop_created += 1

            # 인기차 소진 시 비인기차 추가
            if created < need:
                for car in unpopular:
                    if created >= need:
                        break
                    exists = c.execute(
                        "SELECT 1 FROM topics WHERE car_id=? AND post_type=? AND site_id=? AND status IN ('pending','skip_no_data','published')",
                        (car["car_id"], post_type, site_id)
                    ).fetchone()
                    if not exists:
                        c.execute(
                            "INSERT INTO topics (car_id, competitor_car_id, post_type, priority, status, created_at, site_id) VALUES (?,NULL,?,9,'pending',datetime('now'),?)",
                            (car["car_id"], post_type, site_id)
                        )
                        created += 1

        if created > 0:
            logger.info(f"  [토픽보충] {site_id}/{post_type}: {created}건 추가 (기존 {current} → {current+created})")
        total_created += created

    conn.commit()
    return total_created


def detect_price_changes(conn):
    """트림 가격 변동 감지 → 이벤트 토픽 자동 생성"""
    c = conn.cursor()
    changes = c.execute("""
        SELECT id, car_id, trim_name, old_price, new_price, change_amount, change_percent
        FROM price_history
        WHERE event_created = 0 AND ABS(change_percent) >= 2.0
        ORDER BY ABS(change_percent) DESC
    """).fetchall()

    events_created = 0
    for ch in changes:
        car = c.execute('SELECT brand, model FROM cars WHERE car_id=?', (ch[1],)).fetchone()
        if not car:
            continue
        direction = "인하" if ch[5] < 0 else "인상"
        logger.info(f"  [가격변동] {car['brand']} {car['model']} {ch[2]}: {ch[3]:,} -> {ch[4]:,}만원 ({direction} {abs(ch[5])}만원, {abs(ch[6]):.1f}%)")

        existing = c.execute(
            "SELECT id FROM topics WHERE car_id=? AND post_type='promo_deal' AND status='pending'",
            (ch[1],)
        ).fetchone()
        if not existing:
            c.execute("""INSERT INTO topics (car_id, competitor_car_id, post_type, priority, status, created_at)
                VALUES (?, NULL, 'promo_deal', 15, 'pending', datetime('now'))""",
                (ch[1],))
            events_created += 1

        c.execute("UPDATE price_history SET event_created=1 WHERE id=?", (ch[0],))

    conn.commit()
    if events_created:
        logger.info(f"  가격변동 이벤트 {events_created}개 토픽 생성 (우선순위 15)")
    return events_created


def run_refresh():
    """전체 갱신 실행 (하루 1회)"""
    conn = get_conn()
    c = conn.cursor()

    today = datetime.now().strftime('%Y-%m-%d')
    already = c.execute('SELECT id FROM refresh_log WHERE refresh_date=?', (today,)).fetchone()
    if already:
        logger.info("오늘 이미 데이터 갱신 완료 - 스킵")
        conn.close()
        return

    logger.info("=== CAP 데이터 갱신 시작 ===")

    trims_updated = 0
    images_added = 0
    new_cars = []
    price_changes = 0
    topics_created = 0

    try:
        trims_updated = refresh_trims(conn)
    except Exception as e:
        logger.error(f"refresh_trims 실패: {e}")

    try:
        fill_trim_efficiency(conn)
    except Exception as e:
        logger.error(f"fill_trim_efficiency 실패: {e}")

    try:
        validate_ingested_data(conn)
    except Exception as e:
        logger.error(f"validate_ingested_data 실패: {e}")

    try:
        images_added = refresh_images(conn)
    except Exception as e:
        logger.error(f"refresh_images 실패: {e}")

    try:
        new_cars = scan_new_cars(conn)
    except Exception as e:
        logger.error(f"scan_new_cars 실패: {e}")

    try:
        price_changes = detect_price_changes(conn)
    except Exception as e:
        logger.error(f"detect_price_changes 실패: {e}")

    try:
        topics_created = replenish_topics(conn)
    except Exception as e:
        logger.error(f"replenish_topics 실패: {e}")

    if new_cars:
        logger.info(f"신규 차량 {len(new_cars)}대 발견 (수동 등록 필요)")
        for cid, title, ic in new_cars:
            logger.info(f"  {cid}: {title} ({ic}장)")

    c.execute("INSERT INTO refresh_log (refresh_date, trims_updated, images_added, price_changes, cars_scanned) VALUES (?,?,?,?,?)",
              (today, trims_updated, images_added, price_changes, len(new_cars) if new_cars else 0))
    conn.commit()

    total_cars = conn.execute('SELECT COUNT(*) FROM cars WHERE carisyou_id > 0').fetchone()[0]
    total_imgs = conn.execute('SELECT COUNT(*) FROM car_images').fetchone()[0]
    total_trims = conn.execute('SELECT COUNT(*) FROM trims').fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM topics WHERE status=\'pending\'").fetchone()[0]

    logger.info(f"=== 갱신 완료: 차량 {total_cars}대, 트림 {total_trims}개, 이미지 {total_imgs}장, 대기토픽 {pending}개, 신규토픽 {topics_created}개 ===")
    conn.close()


if __name__ == "__main__":
    run_refresh()
