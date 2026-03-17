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
                price_match = re.search(r'[\d,]+', raw_price.replace('만원', '').replace(',', ''))
                if not price_match:
                    continue
                price = int(price_match.group().replace(',', ''))

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
    }
    model_key = model_map.get(model, re.sub(r'[^a-zA-Z0-9]', '_', model.lower()))
    prefix = brand_map.get(brand, brand.lower())
    cid = f"{prefix}_{model_key}_{year}" if prefix else f"{model_key}_{year}"
    return cid.strip("_").replace("__", "_")


def guess_fuel_type(title):
    if "하이브리드" in title: return "가솔린/하이브리드"
    if "EV" in title or "일렉트릭" in title or "전기" in title: return "전기"
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
            body = "SUV" if "SUV" in segment else "세단" if "세단" in segment else "경차" if "경차" in segment else "기타"

            c.execute("""INSERT INTO cars (car_id, carisyou_id, brand, model, year, fuel_type, displacement, segment, body_type, drive_type, is_popular, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, 'FWD', 0, datetime('now'))""",
                (car_id, cid, brand, model, year, fuel, segment, body))

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
                except:
                    pass
            if added > 0:
                total_new += added
                logger.info(f"  [{car['brand']} {car['model']}] +{added}장")
        except:
            pass
        time.sleep(0.3)

    conn.commit()
    logger.info(f"이미지 보충: {total_new}장 (차단: {len(blocked)}개)")
    return total_new


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

    trims_updated = refresh_trims(conn)
    images_added = refresh_images(conn)
    new_cars = scan_new_cars(conn)
    price_changes = detect_price_changes(conn)

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

    logger.info(f"=== 갱신 완료: 차량 {total_cars}대, 트림 {total_trims}개, 이미지 {total_imgs}장, 대기토픽 {pending}개 ===")
    conn.close()


if __name__ == "__main__":
    run_refresh()
