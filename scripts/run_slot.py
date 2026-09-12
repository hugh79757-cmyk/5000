#!/usr/bin/env python3
"""GH Actions 러너 슬롯 어댑터 — R2 상태 round-trip + dispatcher 실행.
Phase 79 P2 파일럿 (G0 tco-hugo). WAL put 금지 규약 코드화 (MASTER-PLAN §2).

환경변수 (publish.yml env 주입 — GH Secrets와 동일명):
  R2_ENDPOINT / R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY  (r2_uploader.py:11-13와 동일 3키)
  R2_STATE_BUCKET (기본 5000-state)

동작:
  1. get_state()   — R2 → 로컬 data/ 복원 + manifest md5 대조 (불일치 시 exit 2)
  2. dispatcher    — python dispatcher.py {blog_id} (timeout 600s — scheduler.py:405 동일)
  3. put_state()   — WAL 체크포인트 전수 → R2 put (안 b: ops.db 제외) → manifest 갱신 put
"""
import argparse, hashlib, json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.runner_state import STATE_FILES, wal_checkpoint, snapshot_paths  # Phase 78 0d3ee8349

STATE_BUCKET = os.getenv("R2_STATE_BUCKET", "5000-state")
# G-A 안 b (확정): ops.db는 get-only — put 목록에서 제외 (I2-EXCEPTION.md §1)
OPS_DB_KEY = "ops_dashboard/ops.db"
PUT_KEYS = [k for k in STATE_FILES if k != OPS_DB_KEY]


def _s3():
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("R2_ENDPOINT"),
        aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
    )


def _md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def get_state(s3) -> bool:
    """R2 → 로컬 복원 + manifest 대조. 불일치/부재 시 False (exit 2)."""
    manifest_path = ROOT / "data" / "manifest.json"
    try:
        s3.download_file(STATE_BUCKET, "manifest.json", str(manifest_path))
    except Exception:
        print("[run_slot] manifest.json 다운로드 실패 — R2 상태 버킷 접근 불가", file=sys.stderr)
        return False
    manifest = json.loads(manifest_path.read_text())
    ok = 0
    for key, expect in manifest.items():
        if key == "manifest.json":
            continue
        local = ROOT / key
        local.parent.mkdir(parents=True, exist_ok=True)
        try:
            s3.download_file(STATE_BUCKET, key, str(local))
        except Exception as e:
            print(f"[run_slot] get 실패: {key} — {e}", file=sys.stderr)
            return False
        actual = _md5(local)
        if actual != expect:
            print(f"[run_slot] md5 불일치: {key} expect={expect} actual={actual}", file=sys.stderr)
            return False
        ok += 1
    print(f"[run_slot] get_state: {ok}/{len(manifest)-1} 객체 복원+md5 OK")
    return True


def put_state(s3, skip_opsdb: bool) -> bool:
    """WAL 체크포인트 전수 → put → manifest 갱신 put.
    규약: 체크포인트 실패 시 해당 DB put 금지 (shared/runner_state.py:34-43)."""
    keys = [k for k in PUT_KEYS if not (skip_opsdb and k == OPS_DB_KEY)] if skip_opsdb else PUT_KEYS
    manifest = {}
    for key in keys:
        local = ROOT / key
        if not local.exists():
            print(f"[run_slot] put 스킵 (파일 부재): {key}", file=sys.stderr)
            continue
        if local.suffix == ".db":
            # WAL DB: put 직전 체크포인트 — 실패 시 put 금지 (규약 코드화)
            if not wal_checkpoint(str(local)):
                print(f"[run_slot] WAL 체크포인트 실패 — put 금지: {key}", file=sys.stderr)
                return False
        try:
            s3.upload_file(str(local), STATE_BUCKET, key)
        except Exception as e:
            print(f"[run_slot] put 실패: {key} — {e}", file=sys.stderr)
            return False
        manifest[key] = _md5(local)
    s3.put_object(Bucket=STATE_BUCKET, Key="manifest.json",
                  Body=json.dumps(manifest, indent=2, sort_keys=True).encode())
    print(f"[run_slot] put_state: {len(manifest)} 객체 put + manifest 갱신 OK (ops.db 제외: {skip_opsdb})")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("blog_id")
    ap.add_argument("--dry-run", action="store_true", help="dispatcher 스킵 (probe)")
    ap.add_argument("--skip-opsdb", action="store_true",
                    help="ops.db put 제외 (G-A 안 b — 기본 동작, 명시용 플래그)")
    args = ap.parse_args()

    missing = [k for k in STATE_FILES if not (ROOT / k).exists()]
    if missing:
        # ops.db는 get으로 복원될 것 — snapshot_paths 재확인
        pre = snapshot_paths()
        missing = [k for k in missing if k in pre]

    s3 = _s3()
    if not get_state(s3):
        return 2

    if args.dry_run:
        print("[run_slot] dry-run — dispatcher 스킵, put_state만 수행")
    else:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "dispatcher.py"), args.blog_id],
            cwd=ROOT, timeout=600, capture_output=True, text=True,
        )
        print(proc.stdout, end="")
        if proc.stderr:
            print(proc.stderr, end="", file=sys.stderr)
        if proc.returncode != 0:
            print(f"[run_slot] dispatcher exit={proc.returncode}", file=sys.stderr)
            return proc.returncode

    # put은 발행 성공/실패 무관 상태 반납 (실패 시에도 실패 기록 카운터가 갱신돼야 함)
    if not put_state(s3, skip_opsdb=True):
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
