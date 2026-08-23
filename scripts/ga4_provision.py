#!/usr/bin/env python3
"""GA4 속성 + 웹 데이터스트림 자동 생성 CLI.

Usage:
  # 계획만 출력 (API 호출 없음)
  python scripts/ga4_provision.py --account-id 321003076 --blogs car-hugo,golf-hugo --dry-run

  # 실제 생성
  python scripts/ga4_provision.py --account-id 321003076 --blogs car-hugo,golf-hugo,...

출력: /tmp/ga4_new_ids.json ({blog_id: "G-XXXXXXX"})

인증: blogdex OAuth 토큰 (token_2_informationhot.json, analytics.edit 스코프).
재사용: 향후 블로그 추가 시 동일 스크립트에 blog_id 나열.
"""
import argparse
import json
import sys
import time
from pathlib import Path

TOKEN_PATH = Path.home() / "Projects" / "blogdex/credentials/token_2_informationhot.json"
SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/analytics.edit",
]
OUTPUT_PATH = Path("/tmp/ga4_new_ids.json")

# blog_id → {sub}.informationhot.kr
BLOG_DOMAIN_SUFFIX = "informationhot.kr"


def _client():
    from google.oauth2.credentials import Credentials
    from google.analytics.admin import AnalyticsAdminServiceClient
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    return AnalyticsAdminServiceClient(credentials=creds)


def provision(blog_ids: list[str], account_id: str, dry_run: bool = False) -> dict:
    import google.analytics.admin as ga  # 타입은 클라이언트와 동일 네임스페이스 사용

    client = None if dry_run else _client()
    results: dict[str, str] = {}
    errors: dict[str, str] = {}

    for bid in blog_ids:
        domain = f"{bid.removesuffix('-hugo')}.{BLOG_DOMAIN_SUFFIX}"
        url = f"https://{domain}"
        print(f"[{bid}] target={domain} {'(dry-run)' if dry_run else ''}")

        if dry_run:
            continue
        try:
            # 1) 속성 생성
            created = client.create_property(property=ga.Property(
                display_name=domain,
                parent=f"accounts/{account_id}",
                time_zone="Asia/Seoul",
                currency_code="KRW",
            ))
            prop_name = created.name
            print(f"   property created: {prop_name}")

            # 2) 웹 데이터스트림 생성
            stream = ga.DataStream(
                type_=ga.DataStream.DataStreamType.WEB_DATA_STREAM,
                display_name=domain,
                web_stream_data=ga.DataStream.WebStreamData(default_uri=url),
            )
            created_stream = client.create_data_stream(parent=prop_name, data_stream=stream)
            mid = created_stream.web_stream_data.measurement_id
            print(f"   measurement_id: {mid}")
            results[bid] = mid
            time.sleep(2)
        except Exception as e:  # noqa: BLE001 — 개별 실패 skip, 나머지 계속
            errors[bid] = f"{type(e).__name__}: {e}"
            print(f"   ERROR: {errors[bid]}", file=sys.stderr)
            time.sleep(2)

    return {"created": results, "errors": errors}


def main() -> int:
    ap = argparse.ArgumentParser(description="GA4 property + web datastream provisioner")
    ap.add_argument("--account-id", required=True, help="GA4 account id (숫자)")
    ap.add_argument("--blogs", required=True, help="comma-separated blog ids")
    ap.add_argument("--dry-run", action="store_true", help="API 호출 없이 계획만 출력")
    args = ap.parse_args()

    blog_ids = [b.strip() for b in args.blogs.split(",") if b.strip()]
    out = provision(blog_ids, args.account_id, args.dry_run)

    if not args.dry_run and out["created"]:
        existing = json.loads(OUTPUT_PATH.read_text()) if OUTPUT_PATH.exists() else {}
        existing.update(out["created"])
        OUTPUT_PATH.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
        print(f"saved -> {OUTPUT_PATH}")
    if out.get("errors"):
        print("errors:", json.dumps(out["errors"], ensure_ascii=False), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
