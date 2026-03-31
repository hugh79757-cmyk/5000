"""ETAP image fetcher — Unsplash → R2 업로드 → public URL 반환."""
import os
import sys
import requests
from pathlib import Path
from io import BytesIO

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shared.r2_uploader import upload_bytes, file_exists


def fetch_city_image(city: str, country: str, slug: str) -> dict:
    """도시명으로 Unsplash 검색 → R2 업로드 → URL과 credit 반환.

    Returns:
        {"url": "https://...", "credit": "Photo by ..."} 또는 빈 dict.
    """
    access_key = os.getenv("UNSPLASH_ACCESS_KEY")
    if not access_key:
        print("[ETAP] UNSPLASH_ACCESS_KEY 없음")
        return {}

    r2_key = f"etap/{slug}/cover.jpg"
    if file_exists(r2_key):
        from shared.r2_uploader import R2_PUBLIC_BASE
        print(f"[ETAP] R2에 이미 존재: {r2_key}")
        return {"url": f"{R2_PUBLIC_BASE}/{r2_key}", "credit": ""}

    query = f"{city} {country} travel landmark"

    try:
        resp = requests.get(
            "https://api.unsplash.com/search/photos",
            headers={"Authorization": f"Client-ID {access_key}"},
            params={
                "query": query,
                "per_page": 1,
                "orientation": "landscape",
                "content_filter": "high",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("results"):
            print(f"[ETAP] Unsplash 검색 결과 없음: {query}")
            return {}

        photo = data["results"][0]
        image_url = photo["urls"]["regular"]
        photographer = photo["user"]["name"]
        photo_link = photo["links"]["html"]

        img_resp = requests.get(image_url, timeout=20)
        img_resp.raise_for_status()

        public_url = upload_bytes(img_resp.content, r2_key, content_type="image/jpeg")
        if not public_url:
            print("[ETAP] R2 업로드 실패")
            return {}

        credit = f"Photo by [{photographer}]({photo_link}) on [Unsplash](https://unsplash.com)"
        print(f"[ETAP] 이미지 R2 업로드: {public_url} ({photographer})")

        # Unsplash API 필수: 다운로드 트리거
        dl_link = photo.get("links", {}).get("download_location", "")
        if dl_link:
            try:
                requests.get(dl_link, headers={"Authorization": f"Client-ID {access_key}"}, timeout=5)
            except Exception:
                pass

        return {"url": public_url, "credit": credit}

    except Exception as e:
        print(f"[ETAP] Unsplash 이미지 실패: {e}")
        return {}
