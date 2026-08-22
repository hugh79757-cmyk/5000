"""ops_dashboard.fix_history — BLK-3 UPSERT_HISTORY (Sidecar).

fixer 적용/롤백 이력을 JSON sidecar로 보존. DB 스키마 변경 없음.
상태머신 전이 기록용. 블로그 소스 파일은 미접근 (경로 문자열 파싱만).
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# 저장 루트 — 테스트에서 tmp로 교체 가능
ROOT = Path(__file__).parent / "fix_history"

VALID_ACTIONS = {
    "PATCH_PROPOSED",
    "APPLIED",
    "RECHECK_PASS",
    "RECHECK_FAIL",
    "ROLLED_BACK",
    "VERIFIED",
    "ABSTAINED",
}


@dataclass
class HistoryEntry:
    blog_id: str
    post_path: str
    check_name: str
    action: str
    detail: str
    timestamp: str
    actor: str = "agent"

    def to_dict(self) -> dict:
        return asdict(self)


def _slug_from_post_path(post_path: str) -> str:
    # {slug}/index.md 경로에서 slug는 부모 디렉토리명 (stem은 'index'가 됨)
    # 단일 파일 경로(테스트 등)는 파일명 stem 사용
    p = Path(post_path)
    if p.name == "index.md":
        return p.parent.name
    return p.stem


def _sidecar_path(blog_id: str, post_path: str) -> Path:
    return ROOT / blog_id / f"{_slug_from_post_path(post_path)}.json"


def _load(blog_id: str, post_path: str) -> list[dict]:
    p = _sidecar_path(blog_id, post_path)
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def _atomic_write(p: Path, data: list[dict]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.parent / f".{p.name}.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)  # atomic rename — partial write 방지


def record_fix(
    blog_id: str, post_path: str, check_name: str, action: str, detail: str = ""
) -> HistoryEntry:
    """이력 1건 기록 (append). action이 VALID_ACTIONS 외면 ValueError."""
    if action not in VALID_ACTIONS:
        raise ValueError(f"지원 안 되는 action: {action}. 지원: {sorted(VALID_ACTIONS)}")
    entry = HistoryEntry(
        blog_id=blog_id, post_path=post_path, check_name=check_name,
        action=action, detail=detail,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    data = _load(blog_id, post_path)
    data.append(entry.to_dict())
    _atomic_write(_sidecar_path(blog_id, post_path), data)
    return entry


def get_history(blog_id: str, post_path: str) -> list[HistoryEntry]:
    """전체 이력 (오래된 순). 파일 미존재 시 빈 리스트."""
    return [HistoryEntry(**d) for d in _load(blog_id, post_path)]


def get_latest(
    blog_id: str, post_path: str, check_name: str
) -> Optional[HistoryEntry]:
    """해당 check_name 최신 1건. 없으면 None."""
    matches = [e for e in get_history(blog_id, post_path) if e.check_name == check_name]
    return matches[-1] if matches else None
