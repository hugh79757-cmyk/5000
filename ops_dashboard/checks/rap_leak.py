"""ops_dashboard.checks.rap_leak — RAP C03 프론트매터 키→본문 누수(leak) 탐지.

Phase 73 SC-7. 탐지만 수행 (파일 수정/배포 금지).

누수 패턴: 게시물 본문(body)에 프론트매터 블록이 그대로 유입되어
`slug:`/`title:`/`date:` 등 키 행이 렌더링된 본문에 노출되는 현상.
실제 사례(하남시-미사강변-골든): 파일 상단 FM 블록 종료 후 본문에
두 번째 `---title: ...` + `date:`/`draft:`/`slug:`/`categories:`/`tags:`/
`cover:`/`featureimage:` 블록이 그대로 노출됨.

의심 근원 (Phase 73 감사 결과, 실제 fix는 이후 단계):
  - pipelines/rap/writer.py:906  _parse_article() — 첫 `---...---` 블록만
    re.search 로 추출(non-greedy). LLM이 본문 내에 두 번째 `---...---`
    FM 블록을 출력하면 그 블록이 body_md 에 잔류.
  - shared/publisher.py:585  content = fm + body_md — body_md 에 남은
    FM 블록을 그대로 파일에 기록 → 본문 노출.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from ops_dashboard.checks import register_check
from ops_dashboard.checks.content_integrity import (
    _find_site_path,
    _read_post_files,
)

logger = logging.getLogger(__name__)

# 본문에 노출되면 누수로 간주할 프론트매터 키
_LEAK_KEYS = (
    "slug", "title", "date", "draft", "author", "categories", "tags",
    "description", "featureimage", "cover", "image", "pubDate", "og_image",
)
_KEY_RE = re.compile(r"^(?:" + "|".join(_LEAK_KEYS) + r")\s*:", re.IGNORECASE)
# `---title:` 처럼 구분자와 키가 한 줄에 합쳐진 패턴 (이번 누수의 시그니처)
_MERGED_DELIM_RE = re.compile(r"^---\s*\w", re.IGNORECASE)
# 본문 내 연속 키 행 최소 길이 (HR `---`/우연 매칭 배제)
_MIN_RUN = 3


def _body_has_leak(content: str) -> tuple[bool, list[str]]:
    """본문에 임베드된 프론트매터 블록이 있는지 판정.

    선행 FM 블록(`^---\n...\n---\n`)을 제외한 본문만 검사.
    반환: (누수여부, 증거 라인 리스트).
    """
    m = re.match(r"^---\n.*?\n---\n?", content, re.DOTALL)
    body = content[m.end():] if m else content
    lines = body.split("\n")

    # 1) `---title:` 스타일 합쳐진 구분자 — 강력한 시그니처
    merged = [f"{i}: {ln}" for i, ln in enumerate(lines, 1) if _MERGED_DELIM_RE.match(ln)]
    if merged:
        return True, merged[:3]

    # 2) 본문 내 연속 키 행 런(run) ≥ _MIN_RUN
    run: list[str] = []
    evidence: list[str] = []
    for i, ln in enumerate(lines, 1):
        if _KEY_RE.match(ln):
            run.append(f"{i}: {ln}")
        else:
            if len(run) >= _MIN_RUN:
                evidence.append("; ".join(run[:_MIN_RUN]))
            run = []
    if len(run) >= _MIN_RUN:
        evidence.append("; ".join(run[:_MIN_RUN]))
    return (len(evidence) > 0, evidence[:3])


@register_check("rap_leak")
def check_rap_leak(conn, blog_id: str) -> dict:
    """RAP C03 프론트매터 키→본문 누수 탐지 (DETECT-ONLY).

    rap* 블로그에 한정 스캔. 누수 포스트 발견 시 fail + 증거(file:line) 기록.
    """
    if not blog_id.startswith("rap"):
        return {"status": "pass", "detail": f"non-rap 스킵: {blog_id}"}

    site = _find_site_path(conn, blog_id)
    if not site:
        return {"status": "unknown", "detail": f"site_path 없음: {blog_id}"}

    posts = _read_post_files(site)
    if not posts:
        return {"status": "unknown", "detail": "최근 포스트 없음"}

    hits: list[str] = []
    for path, content in posts:
        try:
            leak, ev = _body_has_leak(content)
        except Exception as e:  # 단건 파싱 실패는 스킵
            logger.warning("[rap_leak] 스킵 %s: %s", path, e)
            continue
        if leak:
            name = Path(path).parent.name
            hits.append(f"{name}: {ev[0]}")

    if not hits:
        return {"status": "pass", "detail": f"누수 없음 ({len(posts)}건)"}

    return {
        "status": "fail",
        "detail": "C03 FM키 본문 누수 " + "; ".join(hits[:5]) +
                  (f" (+{len(hits)-5}건)" if len(hits) > 5 else ""),
        "evidence_url": "",
    }
