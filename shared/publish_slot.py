"""공유 모듈: publish 동시성 제한 (crash-safe 슬롯 기반 전역 게이트)

적용: scheduler.py run_publish() + dispatcher.py dispatch()
두 게이트 모두 동일 슬롯 파일(/tmp/publish_slots/slot_{i}.lock) 사용.
env var로 슬롯 ID 상속하여 이중 acquire 방지.

설계:
- MAX_CONCURRENT_PUBLISH=3 개 슬롯, O_CREAT|O_EXCL 원자 확보
- 각 슬롯은 {pid, timestamp, blog_id} 기록
- acquire 시: 빈 슬롯 원자 생성 / 기존 슬롯 pid 생존+TTL 검사 → 회수 가능하면 reclaim
- release 시: 본인 pid+ blog_id 일치 슬롯만 제거 (타인 보호)
- crash-safe: pid 사망/TTL 만료 시 자동 회수
- env var PUBLISH_SLOT_ID로 자식 프로세스에 슬롯 상속 (이중 acquire 방지)
"""

import os
import json
import time

# ── 설정 ──────────────────────────────────────────────────────
PUBLISH_SLOT_DIR = "/tmp/publish_slots"
MAX_CONCURRENT_PUBLISH = 3       # 전역 동시 발행 한도 (관측 기반 조정 가능)
PUB_SLOT_TTL_SEC = 1200          # 20분 — 정상 발행 소요(마진 포함)보다 넉넉히


def _slot_path(slot_id: int) -> str:
    return os.path.join(PUBLISH_SLOT_DIR, f"slot_{slot_id}.lock")


def _now() -> float:
    return time.time()


def _pid_alive(pid: int) -> bool:
    """pid가 살아있는 프로세스인지 확인. alive=True면 kill(0) 성공."""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _read_slot(slot_path: str) -> dict | None:
    """슬롯 파일 읽기. 깨지거나 없거나 하면 None."""
    try:
        with open(slot_path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _write_slot_atomic(slot_path: str, data: dict) -> None:
    """슬롯 파일 원자적 기록 (tmp+os.replace)."""
    tmp_path = slot_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp_path, slot_path)


def _remove_slot(slot_path: str) -> bool:
    """슬롯 제거. 없으면 False."""
    try:
        os.remove(slot_path)
        return True
    except FileNotFoundError:
        return False


def _try_acquire_empty_slot(slot_path: str, data: dict) -> bool:
    """빈 슬롯 원자적 확보 시도. O_CREAT|O_EXCL → 이미 있으면 False."""
    try:
        fd = os.open(slot_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except BaseException:
            try:
                os.close(fd)
            except OSError:
                pass
            os.remove(slot_path)
            raise
        return True
    except FileExistsError:
        return False


def _reclaim_slot(slot_path: str, data: dict) -> bool:
    """기존 슬롯이 회수 가능하면 제거하고 새 슬롯 원자 생성.

    회수 조건:
      - pid 사망 (os.kill(pid,0) 실패)
      - TTL 만료 (now - timestamp > PUB_SLOT_TTL_SEC)
      - 슬롯 파일이 깨짐 (invalid json)

    제거 직후 O_CREAT|O_EXCL로 새 슬롯 생성 시도 → 실패(다른 프로세스가
    동시에 회수했으면)하면 False → caller가 다음 슬롯으로 진행.
    """
    # 1. 제거
    if not _remove_slot(slot_path):
        # 이미 없음 → 빈 슬롯 확보 재도전
        return _try_acquire_empty_slot(slot_path, data)
    # 2. 제거 직후 원자 생성 (race window 최소화)
    return _try_acquire_empty_slot(slot_path, data)


def acquire_publish_slot(blog_id: str = "") -> int | None:
    """사용 가능한 publish 슬롯 확보. 없으면 None.

    각 슬롯을 순회하며:
      - 비어 있음 → 원자 생성로 확보
      - 기존 슬롯 존재 → pid 생존/TTL 검사 → 회수 가능하면 원자 reclaim
      - 둘 다 실패 → 다음 슬롯

    반환: 확보한 슬롯 ID (0..MAX_CONCURRENT-1), 풀 소진 시 None.
    """
    os.makedirs(PUBLISH_SLOT_DIR, exist_ok=True)
    now = _now()
    my_pid = os.getpid()
    data = {"pid": my_pid, "timestamp": now, "blog_id": blog_id}

    for i in range(MAX_CONCURRENT_PUBLISH):
        slot_path = _slot_path(i)

        # 빈 슬롯 원자 확보 시도
        if _try_acquire_empty_slot(slot_path, data):
            return i

        # 기존 슬롯 검사 → 회수 가능?
        existing = _read_slot(slot_path)
        reclaimable = False
        if existing is None:
            # 파일이 있었는데 읽을 때 사라졌거나 깨짐 → 빈 슬롯 확보 재도전
            if _try_acquire_empty_slot(slot_path, data):
                return i
            continue

        pid = existing.get("pid")
        ts = existing.get("timestamp")

        if pid is None or ts is None:
            reclaimable = True
        elif not _pid_alive(pid):
            reclaimable = True
        elif (now - ts) > PUB_SLOT_TTL_SEC:
            reclaimable = True

        if reclaimable:
            if _reclaim_slot(slot_path, data):
                return i
            # reclaim 실패(다른 프로세스가 동시에 회수) → 다음 슬롯
            continue

    return None  # 풀 소진


def release_publish_slot(slot_id: int | None, blog_id: str = "") -> bool:
    """본인 슬롯 반납. slot_id가 None이면 무시.

    자신의 pid와 blog_id가 일치하는 슬롯만 제거(타인 슬롯 보호).
    """
    if slot_id is None:
        return False
    slot_path = _slot_path(slot_id)
    existing = _read_slot(slot_path)
    if existing is None:
        return False
    if existing.get("pid") != os.getpid():
        # 남의 슬롯 — 제거 안 함
        return False
    if existing.get("blog_id") != blog_id:
        return False
    return _remove_slot(slot_path)


def get_active_slots() -> list[dict]:
    """현재 활성 슬롯 목록 반환 (모니터링용)."""
    slots = []
    if not os.path.isdir(PUBLISH_SLOT_DIR):
        return slots
    now = _now()
    for fname in sorted(os.listdir(PUBLISH_SLOT_DIR)):
        if not fname.startswith("slot_") or not fname.endswith(".lock"):
            continue
        fpath = os.path.join(PUBLISH_SLOT_DIR, fname)
        data = _read_slot(fpath)
        if data is None:
            continue
        pid = data.get("pid")
        ts = data.get("timestamp", 0)
        alive = pid is not None and _pid_alive(pid)
        expired = (now - ts) > PUB_SLOT_TTL_SEC if ts else True
        slots.append({
            "slot_id": int(fname.replace("slot_", "").replace(".lock", "")),
            "pid": pid,
            "blog_id": data.get("blog_id", ""),
            "timestamp": ts,
            "alive": alive,
            "expired": expired,
            "age_sec": now - ts if ts else None,
        })
    return slots


def cleanup_stale_slots() -> int:
    """startup 시 죽은/만료/깨진 슬롯 전량 정리. 제거한 슬롯 수 반환."""
    if not os.path.isdir(PUBLISH_SLOT_DIR):
        return 0
    now = _now()
    removed = 0
    for fname in os.listdir(PUBLISH_SLOT_DIR):
        if not fname.startswith("slot_") or not fname.endswith(".lock"):
            continue
        fpath = os.path.join(PUBLISH_SLOT_DIR, fname)
        data = _read_slot(fpath)
        if data is None:
            _remove_slot(fpath)
            removed += 1
            continue
        pid = data.get("pid")
        ts = data.get("timestamp")
        if pid is None or ts is None:
            _remove_slot(fpath)
            removed += 1
            continue
        if not _pid_alive(pid) or (now - ts) > PUB_SLOT_TTL_SEC:
            _remove_slot(fpath)
            removed += 1
    return removed


def get_my_slot_id() -> int | None:
    """env var에서 상속한 슬롯 ID 반환 (인수한 슬롯)."""
    val = os.environ.get("PUBLISH_SLOT_ID")
    if val is None:
        return None
    try:
        return int(val)
    except ValueError:
        return None


def get_inherited_slot_info() -> dict | None:
    """부모가 상속해준 슬롯 정보. 없으면 None."""
    slot_id = get_my_slot_id()
    if slot_id is None:
        return None
    blog_id = os.environ.get("PUBLISH_SLOT_BLOG_ID", "")
    return {"slot_id": slot_id, "blog_id": blog_id}


def slot_available_count() -> int:
    """현재 사용 가능한 슬롯 수 (풀 전체 - 활성 슬롯)."""
    total = MAX_CONCURRENT_PUBLISH
    active = 0
    if os.path.isdir(PUBLISH_SLOT_DIR):
        for fname in os.listdir(PUBLISH_SLOT_DIR):
            if not fname.startswith("slot_") or not fname.endswith(".lock"):
                continue
            fpath = os.path.join(PUBLISH_SLOT_DIR, fname)
            data = _read_slot(fpath)
            if data is None:
                continue
            pid = data.get("pid")
            ts = data.get("timestamp")
            if pid is not None and _pid_alive(pid) and ts is not None:
                if (_now() - ts) <= PUB_SLOT_TTL_SEC:
                    active += 1
    return max(0, total - active)
