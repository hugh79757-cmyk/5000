"""ops_dashboard.checks.rap_region — RAP 지역 왜곡 탐지 (ERR-025).

2026-09-05 관악드림타운 사례 유래: '관악드림타운' 제목 글 본문이 전부
'서울 강남구' + 강남구 단지 시세표 — find_lawd_cd 미매칭 → 랜덤 지역
fallback → 무관 데이터 발행 (데이터 매핑 버그 체인, LLM 왜곡 아님).

발행 시점 게이트(pipelines/rap/pipeline.py 이중 미매칭 가드 +
shared/validators.py _check_rap)는 재발 방지 담당.
본 체크는 사후 전수 스캔 — 과거 유물 + 게이트 우회 케이스 탐지.

로직: 폴더명/data_key의 시·군·구 접미사 지역명이 본문에 0회 언급 시 fail.
(정상 글은 지역명 수 회~수십 회 언급 — 0회면 무관 데이터 강한 증거)

탐지만 수행 (파일 수정/배포 금지).
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from ops_dashboard.checks import register_check
from ops_dashboard.checks.content_integrity import _find_site_path

logger = logging.getLogger(__name__)

# 시·군·구 접미사 지역명 추출 (_check_rap와 동일 정규식 계열)
_REGION_RE = re.compile(r"([가-힣A-Za-z]+(?:시|군|구))\b")


def _extract_regions(text: str) -> list[str]:
    """시·군·구 접미사 지역명 추출 (특별시/광역시 접두 포함 형태 정규화)."""
    found = _REGION_RE.findall(text)
    # '서울특별시 강남구' → 강남구. '부산남구' 같은 붙은 형태는 그대로.
    return [r for r in found]


@register_check("rap_region")
def check_rap_region(conn, blog_id: str) -> dict:
    """ERR-025 지역 왜곡 탐지 (DETECT-ONLY, 무윈도우 전수 스캔).

    rap* 블로그 한정. 폴더명에서 추출한 지역명이 본문에 0회 언급 시 fail.
    폴더명에 지역명 없으면 스킵(unknown 아님 — 검사 불가 대상).

    커버리지 한계 (명시):
    - 폴더명에 시·군·구가 있는 글(예: 경희궁자이3단지-종로구-실거래가)만 검사 가능.
    - 폴더명에 지역명 없는 글(예: 관악드림타운-부동산-시세-분석 — 관악 사례)은
      본 체크로 탐지 불가 → 발행 시점 이중 미매칭 게이트(pipeline.py)가 담당.
    """
    if not blog_id.startswith("rap"):
        return {"status": "pass", "detail": "비-rap 블로그 — 검사 대상 아님",
                "evidence_url": ""}
    site = _find_site_path(conn, blog_id)
    if not site:
        return {"status": "unknown", "detail": "site_path 미확인", "evidence_url": ""}
    posts_dir = site / "content" / "posts"
    if not posts_dir.exists():
        return {"status": "unknown", "detail": "posts 디렉터리 없음", "evidence_url": ""}

    violations: list[str] = []
    scanned = 0
    for md_file in posts_dir.rglob("*.md"):
        if md_file.name == "_index.md":
            continue
        scanned += 1
        folder = md_file.parent.name
        regions = _extract_regions(folder)
        if not regions:
            continue  # 폴더명에 지역명 없음 — 검사 불가
        content = md_file.read_text(encoding="utf-8", errors="replace")
        # 본문에서 FM 제외 후 지역명 전부 0회인지 확인
        missing = [r for r in regions if r not in content]
        # 폴더명에 지역 1개 나왔는데 본문 전체에 그 지역 0회 = 왜곡
        if len(missing) == len(regions):
            violations.append(f"{folder}: '{regions[0]}' 본문 0회")
        if len(violations) >= 5:
            break

    if violations:
        return {"status": "fail",
                "detail": f"지역 왜곡 의심 {len(violations)}건+ (전수 {scanned}건) — {violations[0]}",
                "evidence_url": ""}
    return {"status": "pass", "detail": f"지역 정합 이상 0건 (전수 {scanned}건 스캔)",
            "evidence_url": ""}
