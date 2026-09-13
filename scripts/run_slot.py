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


def _r2_key(local_path: str) -> str:
    """R2 객체 키 = basename (Phase 78 Task 3 put 규격 — bare name).
    probe #4 실패 수정: manifest 키(bare)와 STATE_FILES 경로(data/...)가 달라
    get은 repo 루트에 내려받고 put은 data/에서 못 찾는 불일치 발생."""
    return local_path.rsplit("/", 1)[-1]


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
    for key in STATE_FILES:
        # manifest 엔트리 2형식 허용: plain md5 문자열(run_slot put) 또는
        # {'path','md5','size'} dict (Phase 78 Task 3 Mac put) — probe #3 실패 수정
        entry = manifest.get(_r2_key(key), manifest.get(key))
        if entry is None:
            print(f"[run_slot] get 실패: manifest에 없음: {key}", file=sys.stderr)
            return False
        expect_md5 = entry.get("md5", "") if isinstance(entry, dict) else entry
        local = ROOT / key
        local.parent.mkdir(parents=True, exist_ok=True)
        try:
            s3.download_file(STATE_BUCKET, _r2_key(key), str(local))
        except Exception as e:
            print(f"[run_slot] get 실패: {key} — {e}", file=sys.stderr)
            return False
        actual = _md5(local)
        if actual != expect_md5:
            print(f"[run_slot] md5 불일치: {key} expect={expect_md5} actual={actual}", file=sys.stderr)
            return False
        ok += 1
    print(f"[run_slot] get_state: {ok}/{len(STATE_FILES)} 객체 복원+md5 OK")
    return True


def put_state(s3, skip_opsdb: bool) -> bool:
    """WAL 체크포인트 전수 → put → manifest 갱신 put.
    규약: 체크포인트 실패 시 해당 DB put 금지 (shared/runner_state.py:34-43).
    skip_opsdb 시: ops.db는 put하지 않되 기존 manifest 항목은 보존
    (get_state가 11파일 전부 manifest에서 찾으므로 항목 유실 시 다음 get 실패)."""
    keys = [k for k in PUT_KEYS if not (skip_opsdb and k == OPS_DB_KEY)] if skip_opsdb else PUT_KEYS
    # 기존 manifest 로드 — skip_opsdb 시 ops.db 항목 보존 (G-A 안 b)
    old_manifest = {}
    try:
        mp = ROOT / "data" / "manifest.json"
        s3.download_file(STATE_BUCKET, "manifest.json", str(mp))
        old_manifest = json.loads(mp.read_text())
    except Exception:
        pass
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
            s3.upload_file(str(local), STATE_BUCKET, _r2_key(key))
        except Exception as e:
            print(f"[run_slot] put 실패: {key} — {e}", file=sys.stderr)
            return False
        # manifest 규격 = Phase 78 Task 3 형식 (bare 키 → {path, md5, size})
        manifest[_r2_key(key)] = {"path": key, "md5": _md5(local), "size": local.stat().st_size}
    # skip_opsdb: 기존 manifest의 ops.db 항목 보존 (put하지 않지만 get_state에서 필요)
    if skip_opsdb and OPS_DB_KEY not in manifest:
        ops_r2 = _r2_key(OPS_DB_KEY)
        if ops_r2 in old_manifest:
            manifest[ops_r2] = old_manifest[ops_r2]
            print(f"[run_slot] manifest에 ops.db 항목 복원 (get-only 보존)", file=sys.stderr)
    if not manifest:
        # probe #4 교훈: 0객체 put 상태에서 manifest를 {}로 덮으면 R2 기준 무결성 파괴 — put 금지
        print("[run_slot] put 0객체 — manifest 갱신 거부 (R2 기준 보호)", file=sys.stderr)
        return False
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
