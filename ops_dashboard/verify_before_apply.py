"""ops_dashboard.verify_before_apply — BLK-6 NONDESTRUCTIVE_VERIFY.

fixer 실제 적용 전, 메모리 시뮬레이션으로 부작용 검증. 통과해야만 적용 허용.
원본 파일은 절대 수정하지 않음 (읽기만). 기존 fixer 코드 수정 금지 — wrapper 호출.
"""
from __future__ import annotations

import difflib
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

# side_effect 임계값 상수
FILE_SIZE_DELTA_THRESHOLD = 0.5   # 원본 대비 ±50% 초과 시 의심
MAX_DIFF_LINES = 30              # diff 라인 수 상한 초과 시 excessive_changes

# 의도적 키 제거 allowlist (FM-DRAFT의 draft 제거 등)
# 이 키를 fixer가 제거해도 부작용으로 판단하지 않음 (안전망 오탐 방지)
INTENTIONAL_REMOVAL_KEYS = {"draft"}


@dataclass
class VerifyResult:
    safe_to_apply: bool
    original_hash: str
    simulated_hash: str
    diff_lines: list[str]
    side_effects: list[str]
    detail: str

    def to_dict(self) -> dict:
        return asdict(self)


def _hash(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _nonascii_count(text: str) -> int:
    return sum(1 for c in text if ord(c) > 127)


def dry_apply(
    blog_id: str, post_path: str, check_name: str, fixer_fn
) -> VerifyResult:
    """fixer_fn(content: str) -> str 를 메모리 버퍼에 적용, 부작용 검사.

    - 원본은 읽기만 (수정 안 함).
    - fixer_fn은 문자열을 받아 문자열을 반환해야 함 (파일 I/O 금지, 계약 기반).
    """
    path = Path(post_path)
    original = path.read_text(encoding="utf-8")
    original_hash = _hash(original)

    # 메모리 시뮬레이션 — 파일 시스템 미접근
    simulated = fixer_fn(original)
    simulated_hash = _hash(simulated)

    orig_lines = original.splitlines(keepends=True)
    sim_lines = simulated.splitlines(keepends=True)
    diff = list(
        difflib.unified_diff(orig_lines, sim_lines, fromfile="original", tofile="simulated", n=3)
    )

    side_effects: list[str] = []

    # a. 예상치 못한 필드 제거 (frontmatter key 사라짐)
    removed = _detect_removed_frontmatter_keys(original, simulated)
    removed = [k for k in removed if k not in INTENTIONAL_REMOVAL_KEYS]
    if removed:
        side_effects.append(f"unexpected_field_removed:{','.join(removed)}")

    # b. 파일 크기 변동 >50%
    if original:
        delta = abs(len(simulated) - len(original)) / len(original)
        if delta > FILE_SIZE_DELTA_THRESHOLD:
            side_effects.append(f"file_size_delta_>{int(FILE_SIZE_DELTA_THRESHOLD*100)}%")

    # c. 비ASCII 인코딩 변경 (원본 비ASCII가 사라짐)
    if _nonascii_count(original) > 0 and _nonascii_count(simulated) == 0:
        side_effects.append("encoding_changed")

    # d. diff 라인 과다
    if len(diff) > MAX_DIFF_LINES:
        side_effects.append(f"excessive_changes(>{MAX_DIFF_LINES})")

    safe = len(side_effects) == 0
    return VerifyResult(
        safe_to_apply=safe,
        original_hash=original_hash,
        simulated_hash=simulated_hash,
        diff_lines=diff,
        side_effects=side_effects,
        detail="안전" if safe else f"부작용: {side_effects}",
    )


def _detect_removed_frontmatter_keys(original: str, simulated: str) -> list[str]:
    """원본 frontmatter 키 중 시뮬레이션에서 사라진 키 탐지."""
    def keys_of(text: str) -> set[str]:
        if not text.startswith("---"):
            return set()
        end = text.find("\n---", 3)
        if end == -1:
            return set()
        block = text[3:end]
        ks = set()
        for line in block.splitlines():
            if ":" in line and not line.startswith(" "):
                ks.add(line.split(":", 1)[0].strip())
        return ks

    orig_keys = keys_of(original)
    sim_keys = keys_of(simulated)
    return sorted(orig_keys - sim_keys)
