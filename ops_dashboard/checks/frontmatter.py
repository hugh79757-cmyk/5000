"""ops_dashboard.checks.frontmatter — FM-* 프론트매터 안전등급 자동수정 라우팅 탐지.

Phase 72 (Wave 2b SC-3) 갭 종료: 신규 등록된 안전등급 fixer
(fix_draft_true / fix_frontmatter_missing_keys / fix_featureimage_url_sanitize)가
실제로 발화하려면, 실패를 rule_id(FM-DRAFT / FM-MISSINGKEYS / FM-FEATUREIMAGE)로
기록하는 탐지 체크가 필요했다. 본 모듈이 그 탐지 루프다.

탐지만 수행한다 (자동수정/배포 호출 금지). 발화는 dispatcher._auto_fix_on_fail 가
check_results.rule_id 를 소비해 수행 (dual-write 패턴은 standard.py 와 동일).
"""
from __future__ import annotations

import logging
import re

from ops_dashboard.checks import register_check
from ops_dashboard.checks.content_integrity import (
    _find_site_path,
    _parse_frontmatter,
    _read_post_files,
)

logger = logging.getLogger(__name__)

# 누락 시 보강 대상 필수 프론트매터 키
REQUIRED_KEYS = ["title", "description", "date", "slug", "tags"]

# featureimage 토큰 반복(LLM 아티팩트: gLozv0gLozv0...) 탐지
_TOKEN_REPEAT = re.compile(r"(.{4,})\1{2,}")


def _featureimage_bad(url: str) -> tuple[bool, str | None]:
    """featureimage URL이 IMAGE-GUARD 정화 기준을 벗어하는지 판정.

    위반: 길이 > 200 / 토큰 반복 / 비정상 문자(공백·백슬래시).
    비어있으면 위반 아님(누락은 FM-MISSINGKEYS 영역).
    """
    if not url:
        return False, None
    if len(url) > 200:
        return True, f"featureimage URL 길이 {len(url)}>200"
    if _TOKEN_REPEAT.search(url):
        return True, "featureimage URL 토큰 반복(LLM 아티팩트)"
    if re.search(r"[\s\\]", url):
        return True, "featureimage URL 비정상 문자(공백/백슬래시)"
    return False, None


@register_check("frontmatter")
def check_frontmatter(conn, blog_id: str) -> dict:
    """FM-* 프론트매터 위반 탐지 → rule_id 기록(자동수정 폐루프 라우팅).

    최근 포스트(_read_post_files)를 순회:
      - draft:true → FM-DRAFT
      - title/description/date/slug/tags 누락 → FM-MISSINGKEYS
      - featureimage 가 IMAGE-GUARD 기준 위반 → FM-FEATUREIMAGE
    단건 포스트 파싱/검사 오류는 스킵(로그) — RecheckAll 전체를 죽이지 않는다.
    """
    site = _find_site_path(conn, blog_id)
    if not site:
        return {"status": "unknown", "detail": f"site_path 없음: {blog_id}"}

    posts = _read_post_files(site)
    if not posts:
        return {"status": "unknown", "detail": "최근 7일 포스트 없음"}

    triggered: dict[str, str] = {}
    for path, content in posts:
        try:
            _, fm = _parse_frontmatter(content)
        except Exception as e:
            logger.warning("[frontmatter] 파싱 스킵: %s: %s", path, e)
            continue
        try:
            draft = (fm.get("draft") or "").strip().lower()
            if draft == "true":
                triggered.setdefault("FM-DRAFT", f"{path.parent.name}: draft:true")

            missing = [k for k in REQUIRED_KEYS if not (fm.get(k) or "").strip()]
            if missing:
                triggered.setdefault(
                    "FM-MISSINGKEYS", f"{path.parent.name}: 누락 {missing}"
                )

            feat = (fm.get("featureimage") or "").strip()
            if feat:
                bad, why = _featureimage_bad(feat)
                if bad:
                    triggered.setdefault(
                        "FM-FEATUREIMAGE", f"{path.parent.name}: {why}"
                    )
        except Exception as e:
            logger.warning("[frontmatter] 검사 스킵: %s: %s", path, e)
            continue

    if not triggered:
        return {"status": "pass", "detail": f"FM 통과 ({len(posts)}건)"}

    # dual-write: rule_id 별 개별 행 기록 → _auto_fix_on_fail 가 rule_id 로 라우팅
    from ops_dashboard.db import record_check_rule
    from ops_dashboard.registry import get_entry

    for rule_id, detail in triggered.items():
        entry = get_entry(rule_id)
        severity = (entry.severity if entry else "MINOR") or "MINOR"
        action = entry.action if entry else ""
        try:
            conn.execute(
                "DELETE FROM check_results WHERE blog_id=? AND check_name=?",
                (blog_id, rule_id),
            )
            record_check_rule(
                conn, blog_id, rule_id=rule_id, status="fail",
                severity=severity, action=action, detail=f"FM 위반: {detail}",
            )
        except Exception as e:
            logger.warning("[frontmatter] 기록 실패 %s %s: %s", blog_id, rule_id, e)

    return {
        "status": "fail",
        "detail": "FM 위반 " + "; ".join(f"{rid}:{d}" for rid, d in triggered.items()),
    }
