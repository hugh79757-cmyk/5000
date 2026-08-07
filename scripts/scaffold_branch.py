#!/usr/bin/env python3
"""scripts/scaffold_branch.py — 표준 파이프라인 분기 생성 도구 (Phase 61, D-05).

새 파이프라인 분기를 표준 6-모듈 골격(PIPELINE-STANDARD.md §2.1)으로 즉시 생성한다.
수동 복제(ETAP 35쌍 같은)를 근절하기 위한 온보딩 도구이며, 생성은 전부 새 파일 추가
(additive) — 기존 분기·코드는 절대 수정하지 않는다 (D-08 / destructive-ops).

생성 내용:
- pipelines/{branch}/  — __init__.py + 표준 6모듈(pipeline/fetcher/topic_manager/writer/enrich/validator)
- config/blogs.d/{branch}.yaml — 표준 config 템플릿 (managed_by: pipeline)

분기명 검증: ^[a-z][a-z0-9_]*$ (경로/모듈 주입 방지, threat T-61-09-01/02).

DB 배선: 생성된 pipeline.py 는 `from shared.db import get_db_path` 로 분기 DB 경로를
`shared/db.py` 를 통해 해석한다 — 인라인 하드코딩 경로 없음. 신규 분기는 아직
`shared/db.py::_BRANCH_DB` 에 등록되지 않았을 수 있으므로, 경로 해석은 run() 안에서
lazy + 안전(fallback None)하게 수행해 import 를 깨지 않는다.

사용:
    python scripts/scaffold_branch.py --branch mybranch            # 실제 생성
    python scripts/scaffold_branch.py --branch mybranch --dry-run  # 생성 시뮬레이션
    python scripts/scaffold_branch.py --branch mybranch --base-dir /tmp/x --config-dir /tmp/x
"""

import argparse
import os
import re
from pathlib import Path

BRANCH_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")

STANDARD_MODULES = ("fetcher", "topic_manager", "writer", "enrich", "validator")

# 표준 config 템플릿 (PIPELINE-STANDARD.md §4.1 필수/표준 필드 + managed_by: pipeline)
CONFIG_TEMPLATE = """\
# {branch} 블로그 표준 config 템플릿 (Phase 61, D-05 scaffold 생성).
# placeholder 값 — 실제 도메인/스케줄/상태로 교체 후 활성화하세요.
id: {branch}-hugo
pipeline: {branch}
platform: hugo
name: {Branch}
domain: "{branch}.example.com"
daily_quota: 1
schedule:
  times: []
status: inactive
managed_by: pipeline
"""


def _project_root() -> Path:
    """스크립트(scripts/)의 부모 = 프로젝트 루트."""
    return Path(__file__).resolve().parent.parent


def validate_branch_name(branch_name: str) -> str:
    """분기명 검증 — ^[a-z][a-z0-9_]*$. 실패 시 ValueError.

    경로/모듈 주입 방지 (threat T-61-09-01): ../, 공백, 대문자, 점, 특수문자 거부.
    """
    if not isinstance(branch_name, str) or not BRANCH_NAME_RE.fullmatch(branch_name):
        raise ValueError(
            f"잘못된 분기명 {branch_name!r}: ^[a-z][a-z0-9_]*$ 패턴만 허용됩니다 "
            "(소문자 시작, 영소문자/숫자/언더스코어만). 경로/모듈 주입 방지."
        )
    return branch_name


def _module_bodies(branch: str) -> dict[str, str]:
    """표준 모듈별 전체 소스 (docstring + 함수 본문)."""
    return {
        "fetcher": (
            f'"""{branch} 파이프라인 표준 골격 — fetcher (Phase 61, D-05 scaffold).\n\n'
            f"표준 6-모듈 골격(pipeline/fetcher/topic_manager/writer/enrich/validator)의 일부.\n"
            f"데이터 수집(외부 API·DB·정적 소스)을 담당. 기본 구현은 빈 목록 placeholder.\n"
            f'실데이터 수집 로직은 여기서 구현하세요.\n"""\n'
            f"\n\ndef fetch_data(cfg):\n"
            f'    """데이터 수집 placeholder — 빈 목록 반환."""\n'
            f"    return []\n"
        ),
        "topic_manager": (
            f'"""{branch} 파이프라인 표준 골격 — topic_manager (Phase 61, D-05 scaffold).\n\n'
            f'토픽 선택/중복 가드/할당량을 담당. 기본 구현은 None placeholder.\n"""\n'
            f"\n\ndef select_topic(cfg):\n"
            f'    """토픽 선택 placeholder — None 반환."""\n'
            f"    return None\n"
        ),
        "writer": (
            f'"""{branch} 파이프라인 표준 골격 — writer (Phase 61, D-05 scaffold).\n\n'
            f'글 생성(AI 프롬프트·LLM 폴백 체인)을 담당. 기본 구현은 dict placeholder.\n"""\n'
            f"\n\ndef write_article(cfg, topic):\n"
            f'    """글 생성 placeholder — 빈 article dict 반환."""\n'
            f'    return {{"title": None, "body_md": None, "topic": topic}}\n'
        ),
        "enrich": (
            f'"""{branch} 파이프라인 표준 골격 — enrich (Phase 61, D-05 scaffold).\n\n'
            f'엔리치먼트(광고 삽입·내부 링크·이미지·크로스셀)를 담당.\n'
            f'기본 구현은 body_md 를 그대로 반환하는 passthrough placeholder.\n"""\n'
            f"\n\ndef enrich_content(cfg, body_md):\n"
            f'    """본문 엔리치먼트 passthrough placeholder — 원문 유지."""\n'
            f"    return body_md\n"
        ),
        "validator": (
            f'"""{branch} 파이프라인 표준 골격 — validator (Phase 61, D-05 scaffold).\n\n'
            f'발행 전/후 검증(품질 게이트·이미지 URL·CJK 누수)을 담당.\n'
            f'기본 구현은 (True, []) 를 반환하는 placeholder.\n"""\n'
            f"\n\ndef validate_post(cfg, article):\n"
            f'    """발행 전 검증 placeholder — 항상 통과 (True, [])."""\n'
            f"    return True, []\n"
        ),
    }


def _pipeline_source(branch: str) -> str:
    """생성되는 pipeline.py 소스.

    run(cfg) -> dict 표준 계약(PIPELINE-STANDARD.md §3) 충족. 분기 DB 경로는
    `from shared.db import get_db_path` 로 해석 — 인라인 하드코딩 경로 없음.
    신규 분기가 아직 shared/db.py::_BRANCH_DB 에 없어도 import 가 깨지지 않도록
    DB 경로는 run() 안에서 lazy + 안전하게 해석한다.
    """
    return (
        f'"""{branch} 파이프라인 표준 골격 — pipeline (Phase 61, D-05 scaffold).\n\n'
        f"표준 진입점 run(cfg) -> dict (PIPELINE-STANDARD.md §3). 표준 6-모듈 골격을\n"
        f"표준 순서(fetcher → topic_manager → writer → enrich → validator)로 오케스트레이션.\n"
        f"DB 경로는 shared/db.py::get_db_path 로 중앙 해석 — 인라인 경로 없음 (D-06).\n"
        f'"""\n\n'
        f"from shared.db import get_db_path\n\n\n"
        f"def _resolve_db_path():\n"
        f'    """분기 DB 경로를 shared/db.py 로 해석. 미등록 분기는 None 반환(안전)."""\n'
        f"    try:\n"
        f'        return get_db_path("{branch}")\n'
        f"    except ValueError:\n"
        f"        return None\n\n\n"
        f"def run(cfg):\n"
        f'    """표준 파이프라인 진입점 — dict 를 반환 (표준 계약).\n\n'
        f"    표준 순서로 골격 모듈을 호출한다. 새 분기의 실제 발행 로직은\n"
        f"    이 함수를 확장해 구현한다. 기본값은 no_topic placeholder.\n"
        f'    """\n'
        f"    from pipelines.{branch}.fetcher import fetch_data\n"
        f"    from pipelines.{branch}.topic_manager import select_topic\n"
        f"    from pipelines.{branch}.writer import write_article\n"
        f"    from pipelines.{branch}.enrich import enrich_content\n"
        f"    from pipelines.{branch}.validator import validate_post\n\n"
        f"    _db_path = _resolve_db_path()  # DB 경로 중앙 해석 (D-06)\n"
        f"    data = fetch_data(cfg)\n"
        f"    topic = select_topic(cfg)\n"
        f"    if not topic:\n"
        f'        return {{"success": False, "reason": "no_topic"}}\n'
        f"    article = write_article(cfg, topic)\n"
        f'    article["body_md"] = enrich_content(cfg, article.get("body_md"))\n'
        f"    ok, errors = validate_post(cfg, article)\n"
        f"    if not ok:\n"
        f'        return {{"success": False, "reason": "content_quality_gate", "errors": errors}}\n'
        f'    return {{"success": False, "reason": "no_topic"}}\n'
    )


def scaffold_branch(
    branch_name: str,
    base_dir: str | None = None,
    config_dir: str | None = None,
    dry_run: bool = False,
) -> Path:
    """새 파이프라인 분기 스캐폴드를 생성한다.

    Args:
        branch_name: 분기명 — ^[a-z][a-z0-9_]*$ 검증 (경로/모듈 주입 방지).
        base_dir: pipelines/ 부모 디렉터리 (기본: 프로젝트 루트).
        config_dir: blogs.d/ 부모 디렉터리 (기본: 프로젝트 config/).
        dry_run: True 면 실제 파일을 쓰지 않고 예상 생성 항목만 출력.

    Returns:
        생성된 pipelines/{branch}/ 디렉터리 Path.

    Raises:
        ValueError: 분기명이 규칙을 위반할 때 (T-61-09-01).
        FileExistsError: pipelines/{branch}/ 가 이미 존재할 때 (T-61-09-02, refuse-overwrite).
    """
    validate_branch_name(branch_name)

    root = _project_root()
    base_dir = Path(base_dir) if base_dir else root
    config_dir = Path(config_dir) if config_dir else root / "config"

    branch_dir = base_dir / "pipelines" / branch_name
    if branch_dir.exists():
        raise FileExistsError(
            f"분기 디렉터리 이미 존재 (overwrite 거부, T-61-09-02): {branch_dir}"
        )

    created: list[str] = []
    if dry_run:
        created.append(str(branch_dir / "__init__.py"))
        for mod in STANDARD_MODULES:
            created.append(str(branch_dir / f"{mod}.py"))
        created.append(str(branch_dir / "pipeline.py"))
        created.append(str(config_dir / "blogs.d" / f"{branch_name}.yaml"))
        for f in created:
            print(f"[dry-run] create {f}")
        return branch_dir

    branch_dir.mkdir(parents=True, exist_ok=False)
    created.append(str(branch_dir / "__init__.py"))
    (branch_dir / "__init__.py").write_text(
        f'"""{branch_name} 파이프라인 패키지 (Phase 61, D-05 scaffold)."""\n',
        encoding="utf-8",
    )

    bodies = _module_bodies(branch_name)
    for mod in STANDARD_MODULES:
        path = branch_dir / f"{mod}.py"
        path.write_text(bodies[mod], encoding="utf-8")
        created.append(str(path))

    pipeline_path = branch_dir / "pipeline.py"
    pipeline_path.write_text(_pipeline_source(branch_name), encoding="utf-8")
    created.append(str(pipeline_path))

    blogs_d = config_dir / "blogs.d"
    blogs_d.mkdir(parents=True, exist_ok=True)
    config_path = blogs_d / f"{branch_name}.yaml"
    config_path.write_text(
        CONFIG_TEMPLATE.format(
            branch=branch_name, Branch=branch_name.title()
        ),
        encoding="utf-8",
    )
    created.append(str(config_path))

    for f in created:
        print(f"created {f}")
    return branch_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="표준 파이프라인 분기 스캐폴드 생성기 (Phase 61, D-05)")
    parser.add_argument("--branch", required=True, help="새 분기명 (^[a-z][a-z0-9_]*$)")
    parser.add_argument("--base-dir", default=None, help="pipelines/ 부모 디렉터리 (기본: 프로젝트 루트)")
    parser.add_argument("--config-dir", default=None, help="config/ 부모 디렉터리 (기본: 프로젝트 config)")
    parser.add_argument("--dry-run", action="store_true", help="실제 생성 없이 예상 항목만 출력")
    args = parser.parse_args(argv)

    try:
        scaffold_branch(args.branch, base_dir=args.base_dir, config_dir=args.config_dir, dry_run=args.dry_run)
    except ValueError as e:
        print(f"오류: {e}", file=os.sys.stderr)
        return 1
    except FileExistsError as e:
        print(f"오류: {e}", file=os.sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
