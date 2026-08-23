"""ops_dashboard.rollback — BLK-5 ROLLBACK_CHAIN.

fixer 적용 전 롤백 지점 생성 + 실행(복원).
git commit 수행 안 함 (파일 복원만, commit은 호출자 책임).
원본 외 다른 파일 접근 금지. 실패 시 예외 raise (silent fail 금지).
"""
from __future__ import annotations

import hashlib
import logging
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

BACKUP_ROOT = Path(__file__).parent / "backups"


@dataclass
class RollbackPoint:
    blog_id: str
    post_path: str
    original_content_hash: str
    backup_path: str
    created_at: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RollbackResult:
    success: bool
    restored_hash: str
    matches_original: bool
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def create_rollback_point(blog_id: str, post_path: str) -> RollbackPoint:
    """적용 전 롤백 지점: 현재 내용 해시 + timestamp 백업 복사."""
    path = Path(post_path)
    content = path.read_text(encoding="utf-8")
    h = _sha256(content)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    dest_dir = BACKUP_ROOT / blog_id / ts
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / path.name
    shutil.copy2(path, dest)
    return RollbackPoint(
        blog_id=blog_id, post_path=str(path),
        original_content_hash=h, backup_path=str(dest),
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def execute_rollback(rollback_point: RollbackPoint) -> RollbackResult:
    """백업에서 원본 복원 후 해시 대조. 불일치 시 success=False + 경고."""
    path = Path(rollback_point.post_path)
    backup = Path(rollback_point.backup_path)
    if not backup.exists():
        raise FileNotFoundError(f"백업 없음: {backup}")  # silent fail 금지

    shutil.copy2(backup, path)  # 복원
    restored = path.read_text(encoding="utf-8")
    restored_h = _sha256(restored)
    matches = restored_h == rollback_point.original_content_hash
    ts = datetime.now(timezone.utc).isoformat()
    if not matches:
        logger.warning(
            "[rollback] 해시 불일치: %s (restored=%s, original=%s)",
            path, restored_h[:8], rollback_point.original_content_hash[:8],
        )
    return RollbackResult(
        success=matches, restored_hash=restored_h,
        matches_original=matches, timestamp=ts,
    )
