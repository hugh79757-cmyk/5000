"""Omio popular routes collector – parses local CSV.gz files."""
import os, sys, csv, gzip, sqlite3, logging, glob
from datetime import datetime

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DB_PATH = os.path.join(BASE_DIR, "data", "travel-en.db")
ARCHIVE_DIR = os.path.join(BASE_DIR, "data", "Archive")

def _get_db():
    return sqlite3.connect(DB_PATH)

def _safe_float(val):
    if not val or val.strip() == "":
        return None
    try:
        return float(val.strip())
    except (ValueError, TypeError):
        return None

def _safe_int(val):
    if not val or val.strip() == "":
        return None
    try:
        return int(float(val.strip()))
    except (ValueError, TypeError):
        return None

def collect_from_csv(csv_path):
    """단일 CSV 파일에서 Omio 루트 수집"""
    db = _get_db()
    count = 0

    try:
        if csv_path.endswith(".gz"):
            f = gzip.open(csv_path, "rt", encoding="utf-8", errors="replace")
        else:
            f = open(csv_path, "r", encoding="utf-8", errors="replace")

        reader = csv.DictReader(f)
        for row in reader:
            try:
                route_id = row.get("route_id", "").strip()
                if not route_id:
                    continue

                db.execute("""
                    INSERT OR REPLACE INTO omio_routes
                    (route_id, title, image_url, description, travel_mode, top_seller_rank,
                     origin_name, origin_country, origin_station, origin_lat, origin_lon,
                     destination_name, destination_country, destination_station, dest_lat, dest_lon,
                     train_min_price, bus_min_price, flight_min_price, ferry_min_price,
                     train_min_duration, bus_min_duration, flight_min_duration, ferry_min_duration,
                     currency, link_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    route_id,
                    row.get("title", ""),
                    row.get("image_url", ""),
                    row.get("description", ""),
                    row.get("travel_mode", ""),
                    _safe_float(row.get("Top_Seller_Rank")),
                    row.get("origin_name", ""),
                    row.get("origin_country_code", ""),
                    row.get("origin_station_code", ""),
                    _safe_float(row.get("origin_latitude")),
                    _safe_float(row.get("origin_longitude")),
                    row.get("destination_name", ""),
                    row.get("destination_country_code", ""),
                    row.get("destination_station_code", ""),
                    _safe_float(row.get("destination_latitude")),
                    _safe_float(row.get("destination_longitude")),
                    _safe_float(row.get("train_min_price")),
                    _safe_float(row.get("bus_min_price")),
                    _safe_float(row.get("flight_min_price")),
                    _safe_float(row.get("ferry_min_price")),
                    _safe_int(row.get("train_min_duration")),
                    _safe_int(row.get("bus_min_duration")),
                    _safe_int(row.get("flight_min_duration")),
                    _safe_int(row.get("ferry_min_duration")),
                    row.get("domain_currency", "USD"),
                    row.get("link_URL", "")
                ))
                count += 1
            except Exception as e:
                logger.warning(f"[Omio] row 파싱 오류: {e}")
                continue

        f.close()
    except Exception as e:
        logger.error(f"[Omio] 파일 읽기 오류 {csv_path}: {e}")

    db.commit()
    db.close()
    return count

def collect_all_archive():
    """Archive 폴더의 모든 CSV.gz 파일 수집 (영어 우선)"""
    if not os.path.isdir(ARCHIVE_DIR):
        logger.error(f"[Omio] Archive 폴더 없음: {ARCHIVE_DIR}")
        return 0

    # 영어 파일 우선
    en_files = glob.glob(os.path.join(ARCHIVE_DIR, "English*CUSTOM*.csv.gz"))
    if not en_files:
        en_files = glob.glob(os.path.join(ARCHIVE_DIR, "English*CUSTOM*.csv"))
    if not en_files:
        # 모든 파일
        en_files = glob.glob(os.path.join(ARCHIVE_DIR, "*.csv.gz")) + glob.glob(os.path.join(ARCHIVE_DIR, "*.csv"))

    total = 0
    for fpath in sorted(en_files):
        fname = os.path.basename(fpath)
        cnt = collect_from_csv(fpath)
        logger.info(f"[Omio] {fname}: {cnt}건")
        total += cnt

    logger.info(f"[Omio] 전체 수집: {total}건")
    return total

def run_full_collection():
    return collect_all_archive()

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    total = run_full_collection()
    print(f"Omio routes: {total}건")
