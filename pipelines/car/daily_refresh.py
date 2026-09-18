#!/usr/bin/env python3
"""CAP 데이터 자동 갱신 모듈
- 기존 차량 트림/가격 업데이트
- 카이즈유 신규 차량 탐색
- 이미지 부족 차량 보충
- publish.py 실행 전 호출됨
"""
import logging
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# scheduler가 subprocess로 실행할 때 sys.path[0]이 스크립트 디렉토리
# (pipelines/car/)로 설정되어 프로젝트 루트의 shared가 import되지 않는다.
# cwd는 sys.path에 자동 추가되지 않으므로 명시적으로 루트를 삽입한다.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.db_paths import ARTICLES_DB

DB_PATH = Path(__file__).parent.parent.parent / "data" / "car.db"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _articles_exists(blog_id, source_id, prompt_id, cutoff):
    """stap_content.db articles에 해당 콘텐츠 존재 여부 확인 (publish_log 대체)"""
    conn = sqlite3.connect(ARTICLES_DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT 1 FROM articles WHERE blog_id=? AND source_id=? AND prompt_id=? AND published_at > ?",
        (blog_id, source_id, prompt_id, cutoff)
    ).fetchone()
    conn.close()
    return row is not None


def refresh_trims(conn):
    """기존 차량의 트림/가격 업데이트 + 가격 변동 기록"""
    c = conn.cursor()
    cars = c.execute("SELECT car_id, carisyou_id, brand, model FROM cars WHERE carisyou_id > 0").fetchall()
    updated = 0
    price_changed = 0

    for car in cars:
        cid = car["carisyou_id"]
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

                trim_name = re.sub(r"(A/T|M/T|DCT)", "", raw_name).strip()
                # 가격 파싱: "1억 2,345만원" → 12345, "5,745만원" → 5745
                raw_p = raw_price.replace(",", "").strip()
                eok_match = re.search(r"(\d+)억\s*(\d*)", raw_p)
                man_match = re.search(r"(\d+)만", raw_p)
                if eok_match:
                    eok = int(eok_match.group(1)) * 10000
                    rest = int(eok_match.group(2)) if eok_match.group(2) else 0
                    price = eok + rest
                elif man_match:
                    price = int(man_match.group(1))
                else:
                    price_match = re.search(r"\d+", raw_p)
                    if not price_match:
                        continue
                    price = int(price_match.group())
                if price < 500:
                    continue  # 비정상 가격 스킵

                status = "시판"
                first_cell = cells[0].get_text(strip=True) if len(cells) >= 3 else ""
                if "단종" in first_cell:
                    status = "단종"

                existing_trim = c.execute("SELECT price FROM trims WHERE car_id=? AND trim_name=?",
                    (car["car_id"], trim_name)).fetchone()
                if existing_trim and existing_trim["price"] and existing_trim["price"] != price:
                    old_p = existing_trim["price"]
                    change_pct = round((price - old_p) / old_p * 100, 1)
                    c.execute("""INSERT INTO price_history (car_id, trim_name, old_price, new_price, change_amount, change_percent, detected_at)
                        VALUES (?,?,?,?,?,?,datetime('now'))""",
                        (car["car_id"], trim_name, old_p, price, price - old_p, change_pct))
                    price_changed += 1
                c.execute("""INSERT OR REPLACE INTO trims (car_id, trim_name, price, status, updated_at)
                    VALUES (?, ?, ?, ?, ?)""",
                    (car["car_id"], trim_name, price, status, datetime.now().isoformat()))
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
    title = re.sub(r"\(.*?\)", "", title).strip()
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
    model_key = model_map.get(model, re.sub(r"[^a-zA-Z0-9]", "_", model.lower()))
    prefix = brand_map.get(brand, brand.lower())
    cid = f"{prefix}_{model_key}_{year}" if prefix else f"{model_key}_{year}"
    return cid.strip("_").replace("__", "_")


def guess_fuel_type(title) -> str:
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


def guess_segment(title) -> str:
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
    """카이즈유에서 최신 차량 탐색 + 자동 등록

    커서 기준: cars.MAX(carisyou_id) — 등록된 마지막 차량 다음부터 스캔.
    scan_log.max_scanned_id를 우선하지 않음: carisyou가 빈 쓰레기 id
    (len<50000) 대역을 앞당겨 발급해도, 실제 모델은 낮은 id 대역에
    늦게 등록되는 경우가 있어 지나친 구간을 다시 봐야 하기 때문.
    (실측: cars.MAX=7830, scan_log=12293 — 7831+에 18개 실모델 미스캔)
    """
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    already = c.execute("SELECT id FROM scan_log WHERE scan_date=?", (today,)).fetchone()
    if already:
        logger.info("오늘 이미 탐색 완료 - 스킵")
        return []

    max_id = c.execute("SELECT MAX(carisyou_id) FROM cars").fetchone()[0] or 7650
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

            existing = c.execute("SELECT car_id FROM cars WHERE carisyou_id=?", (cid,)).fetchone()
            if existing:
                continue

            car_id = make_car_id(brand, model, year)
            existing2 = c.execute("SELECT car_id FROM cars WHERE car_id=?", (car_id,)).fetchone()
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
                c.execute("INSERT OR IGNORE INTO car_images (car_id, image_url, source) VALUES (?, ?, ?)",
                          (car_id, src, "carisyou"))

            auto_added += 1
            logger.info(f"  자동 등록: {car_id} ({brand} {model} {year})")

        except Exception as e:
            logger.warning(f"  탐색 실패 {cid}: {e}")
        time.sleep(0.2)

    conn.commit()
    c.execute("INSERT OR REPLACE INTO scan_log (scan_date, max_scanned_id, cars_found, cars_registered) VALUES (?,?,?,?)",
              (today, scan_end, len(found), auto_added))
    conn.commit()
    logger.info(f"신규 차량 {len(found)}대 발견, {auto_added}대 자동 등록 (탐색범위: {scan_start}~{scan_end})")
    return found


def fill_trim_efficiency(conn):
    """Trims 테이블의 fuel_efficiency가 NULL인 항목을 public_fuel_data에서 보충"""
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
    cars = c.execute("SELECT car_id, carisyou_id, brand, model FROM cars WHERE carisyou_id > 0").fetchall()
    total_new = 0

    for car in cars:
        cnt = c.execute("SELECT COUNT(*) FROM car_images WHERE car_id=?", (car["car_id"],)).fetchone()[0]
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
                    c.execute("INSERT OR IGNORE INTO car_images (car_id, image_url, source) VALUES (?, ?, ?)",
                              (car["car_id"], src, "carisyou"))
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


def reset_skip_no_data(conn, days=7):
    """N일+ 경과한 skip_no_data 토픽을 pending으로 복귀 — 데이터가 보충되었을 수 있으므로 재시도.
    최근 skip_no_data는 유지(직전 실패 원인 재현 방지).
    본체/경쟁차량이 여전히 시판 trims 없으면 복귀하지 않음(영구 블록 무한 순환 방지)."""
    c = conn.cursor()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    cur = c.execute(
        """
        UPDATE topics SET status='pending'
        WHERE status='skip_no_data' AND created_at < ?
        AND EXISTS (SELECT 1 FROM trims WHERE car_id=topics.car_id AND status='시판' AND price>=500)
        AND (
            competitor_car_id IS NULL OR competitor_car_id = ''
            OR EXISTS (SELECT 1 FROM trims WHERE car_id=topics.competitor_car_id AND status='시판' AND price>=500)
        )
        """,
        (cutoff,)
    )
    conn.commit()
    if cur.rowcount:
        logger.info(f"  [skip_no_data 리셋] {cur.rowcount}건 pending 복귀 (기준 {days}일)")
    return cur.rowcount


def replenish_topics(conn, min_pending=50):
    """사이트별 post_type 토픽이 min_pending 미만이면 자동 보충"""
    c = conn.cursor()

    SITE_POST_TYPE = {
        "hotissue": "resale_compare",
        "tco": "tco_analysis",
        "rank": "top5_rank",
        "pick": "persona_pick",
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

    # FIX C: 시판 trim 보유 차량만 보충 풀에 포함 (displ=0·단종 재삽입 무한순환 방지)
    market_ok = {r[0] for r in c.execute("SELECT DISTINCT car_id FROM trims WHERE status='시판'").fetchall()}
    # FIX C-2: 연비 데이터 게이트 — lookup_fuel_efficiency 통과 차량만 (skip_no_data 재순환 방지)
    from pipelines.car.data_builder import lookup_fuel_efficiency
    def _fuel_ok(car_row):
        try:
            return lookup_fuel_efficiency(conn, car_row["brand"], car_row["model"]) is not None
        except Exception:
            return False
    # EV 전용 필터
    ev_cars = [car["car_id"] for car in popular if car["fuel_type"] in ("전기", "가솔린/하이브리드") and car["car_id"] in market_ok and _fuel_ok(car)]

    def _count_eligible_topics(conn, site_id, post_type, days_window=14):
        """select_topic과 동일한 가드 세트 + 연비 데이터 게이트로 실제 발행 가능 토픽 수 계산.
        
        가드:
        1. Market filter: trims.status='시판' 존재
        2. Combo block 90-day: articles(stap_content.db) data_source='car_db' 90일 내 발행
        3. Combo block 30-day (any post_type): articles 30일 내 발행 (post_type 무관)
        4. Reuse filter: publish_log 7일 내 동일 topic_id 발행
        5. Recent keys: publish_log 14일 내 car_id:competitor_key 발행 (select_topic과 일치)
        6. Fuel efficiency gate: lookup_fuel_efficiency 통과 (build_input과 일치)
        """
        from shared.db_paths import ARTICLES_DB
        from pipelines.car.data_builder import lookup_fuel_efficiency
        c = conn.cursor()
        cutoff = (datetime.now() - timedelta(days=days_window)).isoformat()
        
        # 1. Recent keys (days_window from publish_log)
        recent = c.execute("""
            SELECT DISTINCT t.car_id || ':' || COALESCE(t.competitor_car_id,'')
            FROM topics t JOIN publish_log p ON t.id = p.topic_id
            WHERE p.published_at > ? AND p.site = ?
        """, (cutoff, site_id)).fetchall()
        recent_keys = {r[0] for r in recent}
        
        # 2. Combo blocks from articles (stap_content.db)
        _blog_id = site_id + "-hugo"
        _cconn = sqlite3.connect(ARTICLES_DB)
        _blocked = _cconn.execute(
            "SELECT DISTINCT source_id FROM articles WHERE blog_id = ? AND data_source = 'car_db' AND published_at > datetime('now', '-90 days') AND prompt_id = ?",
            (_blog_id, post_type)
        ).fetchall()
        _blocked_30 = _cconn.execute(
            "SELECT DISTINCT source_id FROM articles WHERE blog_id = ? AND data_source = 'car_db' AND published_at > datetime('now', '-30 days')",
            (_blog_id,)
        ).fetchall()
        _cconn.close()
        _combo_blocked = {r[0] for r in _blocked} | {r[0] for r in _blocked_30}
        
        # 3. Build query with all guards
        _combo_filter = ""
        _combo_params = []
        if _combo_blocked:
            _ph = ",".join("?" * len(_combo_blocked))
            _combo_filter = f" AND t.car_id NOT IN ({_ph})"
            _combo_params = list(_combo_blocked)
        
        reuse_sql = "AND t.id NOT IN (SELECT topic_id FROM publish_log WHERE published_at > ?)"
        market_sql = "AND t.car_id IN (SELECT car_id FROM trims WHERE status = '시판')"
        post_filter = " AND t.post_type = ?"
        
        sql = f"""
            SELECT t.*, c.brand, c.model, c.fuel_type, c.displacement, c.year
            FROM topics t JOIN cars c ON t.car_id = c.car_id
            WHERE (t.status = 'pending' OR t.status = 'published') 
            {reuse_sql} {market_sql} AND t.site_id = ? 
            {_combo_filter}{post_filter}
        """
        params = (cutoff, site_id) + tuple(_combo_params) + (post_type,)
        topics = c.execute(sql, params).fetchall()
        
        # 4. Apply recent_keys filter + fuel efficiency gate
        count = 0
        for t in topics:
            key = f"{t['car_id']}:{t['competitor_car_id'] or ''}"
            if key not in recent_keys:
                # Fuel efficiency check (matches build_input:396-401)
                try:
                    fuel_eff = lookup_fuel_efficiency(conn, t['brand'], t['model'], t['displacement'])
                    if fuel_eff and fuel_eff > 0:
                        count += 1
                except Exception:
                    pass
        return count

    def _count_eligible_topics_popular(conn, site_id, post_type, days_window=14):
        """select_topic 가드 + 연비 게이트 적용 후 인기차(is_popular=1) 토픽 수만 계산.
        
        recent_keys 윈도우: 14일 (select_topic과 일치)
        """
        from shared.db_paths import ARTICLES_DB
        from pipelines.car.data_builder import lookup_fuel_efficiency
        c = conn.cursor()
        cutoff = (datetime.now() - timedelta(days=days_window)).isoformat()
        
        # 1. Recent keys
        recent = c.execute("""
            SELECT DISTINCT t.car_id || ':' || COALESCE(t.competitor_car_id,'')
            FROM topics t JOIN publish_log p ON t.id = p.topic_id
            WHERE p.published_at > ? AND p.site = ?
        """, (cutoff, site_id)).fetchall()
        recent_keys = {r[0] for r in recent}
        
        # 2. Combo blocks
        _blog_id = site_id + "-hugo"
        _cconn = sqlite3.connect(ARTICLES_DB)
        _blocked = _cconn.execute(
            "SELECT DISTINCT source_id FROM articles WHERE blog_id = ? AND data_source = 'car_db' AND published_at > datetime('now', '-90 days') AND prompt_id = ?",
            (_blog_id, post_type)
        ).fetchall()
        _blocked_30 = _cconn.execute(
            "SELECT DISTINCT source_id FROM articles WHERE blog_id = ? AND data_source = 'car_db' AND published_at > datetime('now', '-30 days')",
            (_blog_id,)
        ).fetchall()
        _cconn.close()
        _combo_blocked = {r[0] for r in _blocked} | {r[0] for r in _blocked_30}
        
        _combo_filter = ""
        _combo_params = []
        if _combo_blocked:
            _ph = ",".join("?" * len(_combo_blocked))
            _combo_filter = f" AND t.car_id NOT IN ({_ph})"
            _combo_params = list(_combo_blocked)
        
        reuse_sql = "AND t.id NOT IN (SELECT topic_id FROM publish_log WHERE published_at > ?)"
        market_sql = "AND t.car_id IN (SELECT car_id FROM trims WHERE status = '시판')"
        post_filter = " AND t.post_type = ?"
        
        sql = f"""
            SELECT t.*, c.brand, c.model, c.fuel_type, c.displacement, c.year, c.is_popular
            FROM topics t JOIN cars c ON t.car_id = c.car_id
            WHERE (t.status = 'pending' OR t.status = 'published') 
            {reuse_sql} {market_sql} AND t.site_id = ? 
            {_combo_filter}{post_filter} AND c.is_popular=1
        """
        params = (cutoff, site_id) + tuple(_combo_params) + (post_type,)
        topics = c.execute(sql, params).fetchall()
        
        # 3. Apply recent_keys filter + fuel efficiency gate
        count = 0
        for t in topics:
            key = f"{t['car_id']}:{t['competitor_car_id'] or ''}"
            if key not in recent_keys:
                # Fuel efficiency check (matches build_input:396-401)
                try:
                    fuel_eff = lookup_fuel_efficiency(conn, t['brand'], t['model'], t['displacement'])
                    if fuel_eff and fuel_eff > 0:
                        count += 1
                except Exception:
                    pass
        return count

    total_created = 0

    for site_id, post_type in SITE_POST_TYPE.items():
        # FIX C (2026-09-11): raw pending이 아니라 '시판 trim 보유 차량의 pending'만 계산.
        # 단종/미시판 pending이 raw-count를 오염시켜 신차 보충(need)이 0으로 잡히는 결함 해소.
        # 유효 = trims.status='시판' 존재 (market guard와 동일 기준), 단 ev_analysis는
        # 연비 데이터 게이트(fuel NULL·90일 콤보 가드)도 통과해야 실제 발행 가능.
        # FIX C-3 (2026-09-18): select_topic과 동일한 가드 세트(combo 90/30일, reuse 7일, recent_keys 7일)
        # 적용해 실제 발행 가능 토픽만 계산 → replenish 트리거 정합성 확보.
        current = _count_eligible_topics(conn, site_id, post_type, days_window=14)

        if current >= min_pending:
            continue

        # 인기차/비인기차 비율: 전체의 2/3는 인기차, 1/3은 비인기차 (동일 기준 적용)
        # select_topic 가드 적용된 인기차 수 별도 계산 필요
        pop_pending = _count_eligible_topics_popular(conn, site_id, post_type, days_window=14)
        unpop_pending = current - pop_pending

        # FIX C-2: ev_analysis는 연비 게이트까지 통과한 pending만 유효으로 계산
        if post_type == "ev_analysis":
            _rows = c.execute(
                "SELECT c.car_id, c.brand, c.model, c.is_popular FROM topics t JOIN cars c ON t.car_id=c.car_id "
                "WHERE t.site_id=? AND t.post_type=? AND t.status='pending' "
                "AND EXISTS (SELECT 1 FROM trims tr WHERE tr.car_id=t.car_id AND tr.status='시판')",
                (site_id, post_type)
            ).fetchall()
            _ok = [r for r in _rows if _fuel_ok(r)]
            current = len(_ok)
            if current >= min_pending:
                continue
            pop_pending = sum(1 for r in _ok if r["is_popular"])
            unpop_pending = current - pop_pending
        min_popular = min_pending * 2 // 3      # 20
        min_unpopular = min_pending - min_popular  # 10
        need_popular = max(0, min_popular - pop_pending)
        need_unpopular = max(0, min_unpopular - unpop_pending)
        need = need_popular + need_unpopular
        if need == 0:
            continue
        created = 0

        if post_type in {"resale_compare", "ranking_compare"}:
            # 비교 글: 경쟁차 조합 필요
            for car_a, car_b in pairs:
                if created >= need:
                    break
                exists = c.execute(
                    "SELECT 1 FROM topics WHERE car_id=? AND competitor_car_id=? AND post_type=? AND site_id=? AND status IN ('pending','published')",
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
                        "SELECT 1 FROM topics WHERE car_id=? AND competitor_car_id=? AND post_type=? AND site_id=? AND status IN ('pending','published')",
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
                # 존재 체크: publish_log → articles(stap_content.db) 기반
                cutoff = (datetime.now() - timedelta(days=30)).isoformat()
                articles_exists = _articles_exists(f"{site_id}-hugo", car_id, post_type, cutoff)
                if not articles_exists:
                    pending_row = c.execute(
                        "SELECT 1 FROM topics WHERE car_id=? AND post_type=? AND site_id=? AND status='pending'",
                        (car_id, post_type, site_id)
                    ).fetchone()
                    exists = pending_row
                else:
                    exists = True
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
                        "SELECT 1 FROM topics WHERE car_id=? AND competitor_car_id=? AND post_type=? AND site_id=? AND status IN ('pending','published')",
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
                unpop_ev = [car["car_id"] for car in unpopular if car["fuel_type"] in ("전기", "가솔린/하이브리드") and car["car_id"] in market_ok and _fuel_ok(car)]
                for car_id in unpop_ev:
                    if created >= need:
                        break
                    exists = c.execute(
                        "SELECT 1 FROM topics WHERE car_id=? AND post_type=? AND site_id=? AND status IN ('pending','published')",
                        (car_id, post_type, site_id)
                    ).fetchone()
                    if not exists:
                        c.execute(
                            "INSERT INTO topics (car_id, competitor_car_id, post_type, priority, status, created_at, site_id) VALUES (?,NULL,?,9,'pending',datetime('now'),?)",
                            (car_id, post_type, site_id)
                        )
                        created += 1

        elif post_type == "persona_pick":
            # persona_pick: 인기차 + 같은 세그먼트 경쟁차 쌍으로 삽입
            import random
            pop_with_seg = [
                (car["car_id"], car["segment"]) for car in
                conn.execute(
                    "SELECT car_id, segment FROM cars WHERE is_popular=1 AND segment IS NOT NULL"
                ).fetchall()
            ]
            for car_id, segment in pop_with_seg:
                if created >= need:
                    break
                # 같은 세그먼트 경쟁차 랜덤 선택
                rivals = [
                    r["car_id"] for r in conn.execute(
                        "SELECT car_id FROM cars WHERE segment=? AND car_id!=? AND is_popular=1",
                        (segment, car_id)
                    ).fetchall()
                ]
                competitor_id = random.choice(rivals) if rivals else None
                # 존재 체크: publish_log → articles(stap_content.db) 기반
                cutoff = (datetime.now() - timedelta(days=30)).isoformat()
                articles_exists = _articles_exists(f"{site_id}-hugo", car_id, post_type, cutoff)
                if not articles_exists:
                    pending_row = c.execute(
                        "SELECT 1 FROM topics WHERE car_id=? AND post_type=? AND site_id=? AND status='pending'",
                        (car_id, post_type, site_id)
                    ).fetchone()
                    exists = pending_row
                else:
                    exists = True
                if not exists:
                    c.execute(
                        "INSERT INTO topics (car_id, competitor_car_id, post_type, priority, status, created_at, site_id) VALUES (?,?,?,7,'pending',datetime('now'),?)",
                        (car_id, competitor_id, post_type, site_id)
                    )
                    created += 1
            # 비인기차도 추가
            if created < need:
                unpop_with_seg = [
                    (car["car_id"], car["segment"]) for car in
                    conn.execute(
                        "SELECT car_id, segment FROM cars WHERE is_popular=0 AND segment IS NOT NULL"
                    ).fetchall()
                ]
                for car_id, segment in unpop_with_seg:
                    if created >= need:
                        break
                    rivals = [
                        r["car_id"] for r in conn.execute(
                            "SELECT car_id FROM cars WHERE segment=? AND car_id!=?",
                            (segment, car_id)
                        ).fetchall()
                    ]
                    competitor_id = random.choice(rivals) if rivals else None
                    exists = c.execute(
                        "SELECT 1 FROM topics WHERE car_id=? AND post_type=? AND site_id=? AND status IN ('pending','published')",
                        (car_id, post_type, site_id)
                    ).fetchone()
                    if not exists:
                        c.execute(
                            "INSERT INTO topics (car_id, competitor_car_id, post_type, priority, status, created_at, site_id) VALUES (?,?,?,5,'pending',datetime('now'),?)",
                            (car_id, competitor_id, post_type, site_id)
                        )
                        created += 1

        else:
            # tco_analysis, promo_deal, beginner_guide: 단독 토픽
            # 인기차 (priority 7)
            for car_id in solos:
                if created >= need_popular:
                    break
                # 존재 체크: publish_log → articles(stap_content.db) 기반
                cutoff = (datetime.now() - timedelta(days=30)).isoformat()
                articles_exists = _articles_exists(f"{site_id}-hugo", car_id, post_type, cutoff)
                if not articles_exists:
                    pending_row = c.execute(
                        "SELECT 1 FROM topics WHERE car_id=? AND post_type=? AND site_id=? AND status='pending'",
                        (car_id, post_type, site_id)
                    ).fetchone()
                    exists = pending_row
                else:
                    exists = True
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
                # 존재 체크: publish_log → articles(stap_content.db) 기반
                cutoff = (datetime.now() - timedelta(days=30)).isoformat()
                articles_exists = _articles_exists(f"{site_id}-hugo", car["car_id"], post_type, cutoff)
                if not articles_exists:
                    pending_row = c.execute(
                        "SELECT 1 FROM topics WHERE car_id=? AND post_type=? AND site_id=? AND status='pending'",
                        (car["car_id"], post_type, site_id)
                    ).fetchone()
                    exists = pending_row
                else:
                    exists = True
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
                        "SELECT 1 FROM topics WHERE car_id=? AND post_type=? AND site_id=? AND status IN ('pending','published')",
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
        car = c.execute("SELECT brand, model FROM cars WHERE car_id=?", (ch[1],)).fetchone()
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


def run_refresh() -> dict:
    """전체 갱신 실행 (하루 1회).

    반환: {"success": bool, "rows_inserted": int(신규 토픽 수), "completed_at": str, "reason": str}
    rows_inserted=0 은 데이터 소스에 신규 후보가 없는 정상 상태일 수 있다.
    """
    conn = get_conn()
    c = conn.cursor()

    today = datetime.now().strftime("%Y-%m-%d")
    already = c.execute("SELECT id FROM refresh_log WHERE refresh_date=?", (today,)).fetchone()
    if already:
        logger.info("오늘 이미 데이터 갱신 완료 - 스킵")
        conn.close()
        return {"success": True, "rows_inserted": 0, "completed_at": datetime.now().isoformat(), "reason": "already_done"}

    logger.info("=== CAP 데이터 갱신 시작 ===")

    trims_updated = 0
    images_added = 0
    new_cars = []
    price_changes = 0
    topics_created = 0

    try:
        trims_updated = refresh_trims(conn)
    except Exception as e:
        logger.exception(f"refresh_trims 실패: {e}")

    try:
        fill_trim_efficiency(conn)
    except Exception as e:
        logger.exception(f"fill_trim_efficiency 실패: {e}")

    try:
        images_added = refresh_images(conn)
    except Exception as e:
        logger.exception(f"refresh_images 실패: {e}")

    try:
        new_cars = scan_new_cars(conn)
    except Exception as e:
        logger.exception(f"scan_new_cars 실패: {e}")

    try:
        price_changes = detect_price_changes(conn)
    except Exception as e:
        logger.exception(f"detect_price_changes 실패: {e}")

    try:
        reset_skip_no_data(conn)
    except Exception as e:
        logger.exception(f"reset_skip_no_data 실패: {e}")

    try:
        topics_created = replenish_topics(conn)
    except Exception as e:
        logger.exception(f"replenish_topics 실패: {e}")

    if new_cars:
        logger.info(f"신규 차량 {len(new_cars)}대 발견 (수동 등록 필요)")
        for cid, title, ic in new_cars:
            logger.info(f"  {cid}: {title} ({ic}장)")

    c.execute("INSERT INTO refresh_log (refresh_date, trims_updated, images_added, price_changes, cars_scanned) VALUES (?,?,?,?,?)",
              (today, trims_updated, images_added, price_changes, len(new_cars) if new_cars else 0))
    conn.commit()

    total_cars = conn.execute("SELECT COUNT(*) FROM cars WHERE carisyou_id > 0").fetchone()[0]
    total_imgs = conn.execute("SELECT COUNT(*) FROM car_images").fetchone()[0]
    total_trims = conn.execute("SELECT COUNT(*) FROM trims").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM topics WHERE status='pending'").fetchone()[0]

    logger.info(f"=== 갱신 완료: 차량 {total_cars}대, 트림 {total_trims}개, 이미지 {total_imgs}장, 대기토픽 {pending}개, 신규토픽 {topics_created}개 ===")
    conn.close()

    return {"success": True, "rows_inserted": topics_created, "completed_at": datetime.now().isoformat(), "reason": ""}


if __name__ == "__main__":
    run_refresh()
