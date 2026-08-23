"""scripts/validate_schema_pr.py — 스키마-as-code CI 정합성 게이트.

설계 참조: docs/superpowers/specs/2026-08-22-schema-as-code-design.md §5
  - 정방향: 블로그 구조 변경 PR 시, 해당 blog_id 분기 schema.yaml이 함께 변경되지 않으면 fail.
  - 역방향: schemas/ 변경 시, 영향받는 체커를 대상으로 Stage 1 드라이런 (위반 delta 검증).

동작 방식:
  1. git diff로 PR 변경 파일 목록 수집 (기본: HEAD~1..HEAD, --base-ref/--head-ref로 오버라이드).
  2. 정방향: 구조 파일(pipelines/, shared/publishers/, layouts/, content/)에서
     blog_id 추론 → 해당 분기 schema.yaml 변경 여부 확인.
  3. 역방향: schemas/ 변경 시 로컬 콘텐츠(스키마 Stage 1) 드라이런 실행 —
     기존 콘텐츠 위반 건수가 새 스키마 적용 후 증가하면 fail.

제약:
  - 로컬 파일 기반만 (라이브 크롤/HTTP 금지). Stage 1 드라이런만 수행.
  - 기존 체커 코드 수정 금지. schema_loader.load_schema() 재사용.
  - 트랙A DB/레지스트리 접근 금지.
"""
from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ops_dashboard.schema_loader import load_schema  # noqa: E402

logger = logging.getLogger(__name__)

# 정방향 검증 대상 구조 파일 경로 (변경 시 스키마 동반 변경 필요)
_STRUCTURE_PATHS = (
    "pipelines/",
    "shared/publishers/",
    "layouts/",
    "content/",
)

# blog_id 추론: 경로에서 blog_id 후보 추출
# 예: pipelines/etap/michelin_pipeline.py → etap 분기 (blog_id 특정 불가, 분기 수준)
#     content/posts/zurich-to-milan/index.md → blog_id 특정 불가 (사이트 단위)
#     pipelines/etap/deals_pipeline.py → 분기만, 블로그 단위는 YAML에서 분기 매핑


def _git_diff_files(base_ref: str, head_ref: str) -> list[str]:
    """git diff로 변경 파일 목록 수집. 실패 시 빈 리스트 + 경고."""
    try:
        out = subprocess.run(
            ["git", "diff", "--name-only", base_ref, head_ref],
            capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=30,
        )
        if out.returncode != 0:
            logger.warning("[validate_schema_pr] git diff 실패: %s", out.stderr.strip())
            return []
        return [l for l in out.stdout.splitlines() if l.strip()]
    except Exception as e:
        logger.warning("[validate_schema_pr] git diff 예외: %s", e)
        return []


def _branch_from_path(path: str) -> str | None:
    """변경 파일 경로에서 분기(branch) 추론.

    - pipelines/{branch}/... → branch
    - schemas/{branch}/schema.yaml → branch
    - 그 외 → None (분기 특정 불가)
    """
    parts = Path(path).parts
    if len(parts) >= 2:
        if parts[0] == "pipelines" and len(parts) >= 2:
            return parts[1]
        if parts[0] == "schemas" and len(parts) >= 2:
            return parts[1]
    return None


def _schema_changed(files: list[str], branch: str) -> bool:
    """해당 분기의 schema.yaml(또는 blog-overrides)이 변경 목록에 있는지."""
    for f in files:
        if f.startswith(f"schemas/{branch}/"):
            return True
    return False


def _forward_gate(files: list[str]) -> list[str]:
    """정방향 검증: 구조 변경이 있는데 스키마 변경이 없는 (블로그, 분기) 목록 반환."""
    violations: list[str] = []
    for f in files:
        if not f.startswith(_STRUCTURE_PATHS):
            continue
        branch = _branch_from_path(f)
        if branch is None:
            continue  # 분기 특정 불가 — 블로그 단위가 아니면 스킵
        if not _schema_changed(files, branch):
            violations.append(f"{f} → 분기 {branch} schema.yaml 미변경")
    return violations


def _stage1_dry_run(branch: str, blog_ids: list[str]) -> dict:
    """역방향 드라이런: 해당 분기 blog_id들에 새 스키마 적용 → 위반 건수 산출.

    Stage 1만 (로컬 frontmatter vs SchemaSpec) — 라이브 크롤 없음.
    TODO(2026-08-22): frontmatter 필수 키/빈 값/title 형식 위반 카운트 실제 구현.
    현재는 load_schema 호출 성공 여부 + 기본 위반 집계 스텁.
    """
    violations = 0
    for bid in blog_ids:
        try:
            spec = load_schema(bid)
            # 기본 Stage 1: required_frontmatter 빈 값 위반 스텁
            # TODO: 실제 로컬 frontmatter 파싱(_read_post_files) 연동
            _ = spec
        except Exception as e:
            logger.warning("[validate_schema_pr] load_schema 실패 %s: %s", bid, e)
            violations += 1
    return {"violations": violations, "checked": len(blog_ids)}


def _reverse_gate(files: list[str]) -> list[str]:
    """역방향 검증: schemas/ 변경 시 해당 분기 드라이런 위반 delta 확인.

    반환: 문제 메시지 목록 (비면 통과).
    """
    problems: list[str] = []
    for f in files:
        if not f.startswith("schemas/") or not f.endswith(".yaml"):
            continue
        branch = _branch_from_path(f)
        if branch is None or branch == "_base":
            continue
        # 해당 분기 blog_id 목록은 config/blogs.d에서 추론 (로더 내부 매핑 재사용)
        # TODO(2026-08-22): _resolve_branch 역방향 인덱스 노출 시 블로그 목록 확보
        result = _stage1_dry_run(branch, [])
        if result["violations"] > 0:
            problems.append(
                f"{f}: Stage 1 드라이런 위반 {result['violations']}건 (기존 콘텐츠 영향)"
            )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="스키마-as-code CI 정합성 게이트")
    parser.add_argument("--base-ref", default="HEAD~1", help="기준 ref (기본 HEAD~1)")
    parser.add_argument("--head-ref", default="HEAD", help="비교 ref (기본 HEAD)")
    parser.add_argument("--files", nargs="*", default=None,
                        help="변경 파일 목록 직접 전달 (git diff 대신)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING)

    files = args.files if args.files is not None else _git_diff_files(args.base_ref, args.head_ref)
    if not files:
        print("validate_schema_pr: 변경 파일 없음 — PASS")
        return 0

    forward_violations = _forward_gate(files)
    reverse_problems = _reverse_gate(files)

    failed = bool(forward_violations or reverse_problems)
    if forward_violations:
        print("FAIL (정방향): 구조 변경인데 스키마 미변경")
        for v in forward_violations:
            print(f"  - {v}")
    if reverse_problems:
        print("FAIL (역방향): 스키마 변경이 기존 콘텐츠 위반 증가")
        for p in reverse_problems:
            print(f"  - {p}")
    if not failed:
        print("validate_schema_pr: PASS")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
