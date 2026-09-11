"""car_images 미검증 → webp → R2 업로드 → verified=1 (verify_ev_images_20260911.py 일반화).
사용: python3 scripts/verify_car_images.py <car_id> [<car_id> ...]  (차량당 상위 5장)
"""
import sys, sqlite3, hashlib, logging
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.publishers.hugo_writer import _download_image_bytes, _convert_to_webp
from shared.r2_uploader import upload_bytes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("verify_car_images")
DB = Path(__file__).resolve().parents[1] / "data" / "car.db"
MAX_PER_CAR = 5

def main():
    cars = sys.argv[1:] or ["kona_hev_2027", "k8_hev_2027"]
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row; c = conn.cursor()
    updated, failed = 0, []
    for car_id in cars:
        rows = c.execute(
            "SELECT id, image_url FROM car_images WHERE car_id=? AND verified=0 ORDER BY id LIMIT ?",
            (car_id, MAX_PER_CAR)).fetchall()
        logger.info(f"{car_id}: 미검증 {len(rows)}장 대상")
        for r in rows:
            img_id, url = r["id"], r["image_url"]
            try:
                result = _download_image_bytes(url)
                if result is None: failed.append((img_id, "download_fail")); continue
                data, _ = result
                webp = _convert_to_webp(data, quality=75) or data
                digest = hashlib.sha256(url.encode()).hexdigest()[:8]
                r2_key = f"car-images/{datetime.now():%Y/%m/%d}/{digest}.webp"
                r2_url = upload_bytes(webp, r2_key, content_type="image/webp")
                if not r2_url: failed.append((img_id, "upload_fail")); continue
                c.execute("UPDATE car_images SET verified=1, r2_url=? WHERE id=?", (r2_url, img_id))
                updated += 1; logger.info(f"  OK id={img_id} -> {r2_url}")
            except Exception as e:
                failed.append((img_id, str(e)[:80])); logger.warning(f"  FAIL id={img_id}: {e}")
    conn.commit()
    logger.info(f"완료: updated={updated}, failed={len(failed)}")
    for f in failed: logger.info(f"  실패 목록: {f}")
    for car_id in cars:
        n = c.execute("SELECT COUNT(*) FROM car_images WHERE car_id=? AND verified=1 AND r2_url != ''",
                      (car_id,)).fetchone()[0]
        logger.info(f"사후대조 {car_id}: verified=1 {n}장")
    conn.close()

if __name__ == "__main__":
    main()
