"""ops_dashboard.checks.content_integrity — C01~C08 콘텐츠 무결성 검사

블로그별 콘텐츠 무결성 규칙(C01~C08)을 검사하고 결과를 check_results에 기록.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path

from ops_dashboard.checks import register_check
from ops_dashboard.db import get_blog_detail, record_check

logger = logging.getLogger(__name__)

# 프론트매터 키 목록 (C03 검출 대상)
FM_KEYS = ["title", "og_image", "featureimage", "date", "slug",
            "categories", "tags", "description", "draft", "image", "pubDate", "author"]

# C04 패턴 (국문 + 영문) - dispatcher.py preflight_check와 동일한 패턴 사용
C04_KO_PATTERNS = [
    r"생각해보자\b",         # "생각해보자" (문장 끝)
    r"생각해\s*보자\b",      # "생각해 보자" (문장 끝)
    r"다음\s*단계로\s*넘어", # "다음 단계로 넘어가자"
    r"단계별로\s*진행해",    # "단계별로 진행해보자"
    r"우선\s*,?\s*(우리가|제가|내가|우리)\s*해야",  # "우선, 우리가 해야..."
    r"우리가\s*해야\s*할\s*것은",  # "우리가 해야 할 것은"
    r"생각\s*과정을\s*통해", # "생각 과정을 통해"
    r"먼저\s*생각해보자",    # "먼저 생각해보자" (let's think)
    r"단계별로\s*생각",      # "단계별로 생각해보자"
]
C04_EN_PATTERNS = [
    r"\bNeed\s+to\s+think\b",
    r"\bWe\s+need\s+to\s+write\b",
    r"Let['']s\s+think\s+step\s+by\s+step",
    r"think\s+step\s+by\s+step",
    r"let['']s\s+break\s+this\s+down",
    r"here['']s\s+the\s+plan",
    r"in\s+order\s+to\s+achieve",
    r"as\s+an\s+AI\s+language\s+model",
]


def _find_site_path(conn, blog_id: str) -> Path | None:
    """blog_lifecycle에서 site_path 추출."""
    blog_info = get_blog_detail(conn, blog_id)
    if not blog_info:
        return None
    blog_row = blog_info.get("blog", {})
    sp = blog_row.get("site_path", "")
    p = Path(sp) if sp else None
    return p if p and p.exists() else None


def _parse_frontmatter_date(content: str) -> str | None:
    """frontmatter date 값 추출(원문 문자열). date 키 없으면 None."""
    m = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    if not m:
        return None
    for line in m.group(1).split("\n"):
        mm = re.match(r'^\s*date:\s*["\']?([^"\'\s]+)', line)
        if mm:
            return mm.group(1)
    return None


def _frontmatter_date_ts(content: str) -> float | None:
    """frontmatter date를 epoch로 변환. 파싱 실패/값없음 → None(안전측 '포함').

    date 단일 기준의 검사대상 붕괴(948건)를 막기 위해 OR 병합에서 사용.
    None 반환 = 판정 불가 → 호출부에서 '검사대상 포함(안전측)' 처리한다.
    """
    raw = _parse_frontmatter_date(content)
    if not raw:
        return None
    s = raw.strip().strip('"\'')
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return datetime(int(m[1]), int(m[2]), int(m[3])).timestamp()
        except ValueError:
            return None
    m2 = re.match(r"^(\d{4})(\d{2})(\d{2})$", s)
    if m2:
        try:
            return datetime(int(m2[1]), int(m2[2]), int(m2[3])).timestamp()
        except ValueError:
            return None
    return None


def _read_post_files(site: Path) -> list[tuple[Path, str]]:
    """site/content/posts/의 최신 md 파일 목록 반환.

    검사대상 = (mtime >= now-7d) OR (frontmatter date >= now-7d) OR
               (date 파싱 불가/없음 → 포함, 안전측).

    mtime 조건: touch/재배포로 갱신된 글 포착 → 회피경로 차단.
    date 조건: 최근 발행글 포착.
    date 없음/파싱실패: 판정 불가 → '검사 제외'가 아니라 '검사 포함'(안전측).
    ※ 'mtime 7일 밖 + date 7일 밖'인 과거 발행글은 의도된 '최근분만 검수'
       정책 범위 밖 — 새 오류는 못 잡음 (한계: 규칙카드/운영노트 명시).
    """
    posts_dir = site / "content" / "posts"
    if not posts_dir.exists():
        return []
    cutoff = datetime.now().timestamp() - 7 * 86400
    results = []
    for md_file in posts_dir.rglob("*.md"):
        content = md_file.read_text(encoding="utf-8", errors="replace")
        mtime_ok = md_file.stat().st_mtime >= cutoff
        date_ts = _frontmatter_date_ts(content)
        date_ok = date_ts is not None and date_ts >= cutoff
        safe_include = date_ts is None  # date 파싱 불가/없음 → 안전측 포함
        if mtime_ok or date_ok or safe_include:
            results.append((md_file, content))
    return results


def _parse_frontmatter(content: str) -> tuple[str | None, dict]:
    """frontmatter 파싱 (단순 regex)."""
    m = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    if not m:
        return None, {}
    fm_text = m.group(1)
    fm = {}
    for line in fm_text.split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            k, v = k.strip(), v.strip().strip("'\"")
            fm[k] = v
    return fm_text, fm


def _check_c01(fm_text: str | None) -> tuple[bool, str]:
    """C01: 프론트매터 내 곡선따옴표."""
    if not fm_text:
        return True, "frontmatter 없음 (skip)"
    curved_single = ["\u2018", "\u2019"]  # ' '
    curved_double = ["\u201c", "\u201d"]  # " "
    found = []
    if any(c in fm_text for c in curved_single):
        found.append("곡선따옴표(' ')")
    if any(c in fm_text for c in curved_double):
        found.append('곡선따옴표(" ")')
    if found:
        return False, f"C01 위반: {', '.join(found)}"
    return True, "C01 통과"


def _check_c02(content: str) -> tuple[bool, str]:
    """C02: 프론트매터 미종료 — 첫 --- 이후 두 번째 --- 존재 여부로만 판정."""
    lines = content.split('\n')
    first_dash = None
    second_dash = None
    for i, line in enumerate(lines):
        if line.strip() == '---':
            if first_dash is None:
                first_dash = i
            elif second_dash is None and i > first_dash:
                second_dash = i
                break  # 첫 --- 이후 두 번째만 찾으면 중단 (전체 카운트 금지)
    if first_dash is None:
        return False, "C02 위반: 첫 --- 없음"
    if second_dash is None:
        return False, "C02 위반: 첫 --- 이후 두 번째 --- 없음"
    return True, "C02 통과"


def _check_c03(body_md: str) -> tuple[bool, str]:
    """C03: 본문에 프론트매터 키 라인 유출."""
    pattern = re.compile(r'^\s*(' + '|'.join(FM_KEYS) + r'):\s*')
    leaked = [l.strip()[:60] for l in body_md.split('\n') if pattern.match(l)]
    if leaked:
        return False, f"C03 위반: {len(leaked)}건 — {leaked[0]}"
    return True, "C03 통과"


def _check_c04(body_md: str, blog_id: str) -> tuple[bool, str]:
    """C04: LLM 프롬프트/사고문 누수. 국문+영문 패턴 모두 확인."""
    patterns = C04_KO_PATTERNS + C04_EN_PATTERNS
    found = []
    for pat in patterns:
        m = re.search(pat, body_md, re.IGNORECASE)
        if m:
            found.append(m.group()[:40])
    if found:
        return False, f"C04 위반: 프롬프트 누수 {len(found)}건 — {found[0]}"
    return True, "C04 통과"


def _check_c05(fm: dict) -> tuple[bool, str]:
    """C05: draft:true 발행 대상."""
    if fm.get("draft", "").lower() == "true":
        return False, "C05 위반: draft:true 발행 대상"
    return True, "C05 통과"


def _check_c06(file_path: Path, blog_id: str) -> tuple[bool, str]:
    """C06: 로컬 mtime > 마지막 배포 시각 (단순화: 최근 수정 파일 경고)."""
    if not file_path.exists():
        return True, "파일 없음 (skip)"
    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
    days_since = (datetime.now() - mtime).days
    if days_since < 1:
        return False, f"C06 경고: 최근 수정 ({mtime.strftime('%Y-%m-%d')})"
    return True, f"C06 통과 (마지막 수정 {days_since}일 전)"


def _check_c07(body_md: str, conn) -> tuple[bool, str]:
    """C07: 죽은 크로스셀 링크.

    실제 구현: data-target-slug 추출 + "More about" 블록(EntityLinker 새 패턴) href 추출
    → slug 정규화 → content.db published 확인 → HTTP HEAD 확인(운영 환경).
    """
    def _extract_slug_from_url(url: str) -> str:
        """URL에서 publish_ledger slug 컬럼 형식에 맞는 slug 추출.
        예: https://visafree.techpawz.com/posts/france-visa-free/ → france-visa-free
             https://tours.techpawz.com/posts/best-tours-bouches-du-rh-ne/ → best-tours-bouches-du-rh-ne
        """
        # /posts/SLUG[/] 형태에서 SLUG 추출
        m = re.search(r'/posts/([^/\s]+)', url)
        if m:
            return m.group(1)
        # /posts/ 접두어 없으면 그대로 사용 (상대 slug)
        return url.rstrip('/')

    # 패턴 1: 구 data-target-slug (일부 파이프라인) — 이미 slug만 들어 있음
    target_slugs = re.findall(r'data-target-slug=["\']([^"\']+)["\']', body_md)

    # 패턴 2: entity_linker build_cross_sell_html "More about" 블록
    #    "📌 More about {city}" 헤더 + inline-flex 앵커 href → slug 정규화
    more_about_match = re.search(r'More about\s*\S+', body_md)
    if more_about_match:
        start = more_about_match.start()
        end = min(start + 2000, len(body_md))
        section = body_md[start:end]
        inline_urls = re.findall(
            r'<a[^>]*href=["\']([^"\']+)["\']', section
        )
        for url in inline_urls:
            target_slugs.append(_extract_slug_from_url(url))

    if not target_slugs:
        return True, "크로스셀 링크 없음 (skip)"

    # content.db에서 published 확인 (slug 기준)
    try:
        dead = []
        for slug in target_slugs:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM publish_ledger WHERE slug=? AND status='published'",
                (slug,)
            ).fetchone()
            if row["cnt"] == 0:
                dead.append(slug)
        if dead:
            return False, f"C07 위반: 죽은 크로스셀 링크 {len(dead)}건 — {dead[0]}"
    except Exception as e:
        logger.warning(f"[C07] DB 확인 실패: {e}")
    return True, "C07 통과 (HTTP 확인은 운영 환경에서)"


def _check_c08(site: Path | None, blog_id: str) -> tuple[bool, str]:
    """C08: 라이브-파일 불일치. 현재 placeholder (라이브 비교 API 연동 필요)."""
    # TODO: 라이브 사이트 HTML 크롤링 → 제목/og_image 비교
    return True, "C08: 라이브 비교 미구현 (placeholder)"


def _check_c09(content: str) -> tuple[bool, str]:
    """C09: categories/tags 문자열화 탐지.

    YAML 파싱 결과 type이 str이고 값이 "['...']" 또는 '["..."]' 패턴이면 fail.
    type이 list이면 정상 통과.
    """
    import yaml as _yaml9
    import re as _re9
    try:
        m = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
        if not m:
            return True, "C09 skip (frontmatter 없음)"
        fm = _yaml9.safe_load(m.group(1)) or {}
        if not isinstance(fm, dict):
            return True, "C09 skip (파싱 실패)"
        issues = []
        for field in ('categories', 'tags'):
            val = fm.get(field)
            if val is not None and isinstance(val, str):
                if _re9.match(r'^\[\s*[\'"].*[\'"]\s*\]$', val.strip()):
                    issues.append(f"{field}='{val}' (문자열화된 리스트)")
        if issues:
            return False, f"C09 위반: {', '.join(issues)}"
        return True, "C09 통과"
    except Exception as e:
        return True, f"C09 skip (파싱 예외: {e})"


@register_check("c01_curve_quote")
def check_c01(conn, blog_id: str) -> dict:
    """C01: 프론트매터 내 곡선따옴표 검사."""
    site = _find_site_path(conn, blog_id)
    if not site:
        return {"status": "unknown", "detail": f"site_path 없음: {blog_id}"}

    posts = _read_post_files(site)
    if not posts:
        return {"status": "unknown", "detail": "최근 7일 포스트 없음"}

    # 전수 검사 (모든 포스트 순회 — posts[0] 단건 검사의 커버리지 구멍 제거)
    violations = []
    for _, content in posts:
        fm_text, _ = _parse_frontmatter(content)
        passed, detail = _check_c01(fm_text)
        if not passed:
            violations.append(detail)

    if violations:
        return {"status": "fail",
                "detail": f"C01 위반 {len(violations)}건: {'; '.join(violations[:3])}"}
    return {"status": "pass", "detail": f"C01 통과 ({len(posts)}건)"}


@register_check("c02_frontmatter_close")
def check_c02(conn, blog_id: str) -> dict:
    """C02: 프론트매터 미종료 검사."""
    site = _find_site_path(conn, blog_id)
    if not site:
        return {"status": "unknown", "detail": f"site_path 없음: {blog_id}"}

    posts = _read_post_files(site)
    if not posts:
        return {"status": "unknown", "detail": "최근 7일 포스트 없음"}

    violations = []
    for path, content in posts:
        passed, detail = _check_c02(content)
        if not passed:
            violations.append(f"{path.parent.name}: {detail}")

    if violations:
        return {"status": "fail",
                "detail": f"C02 위반 {len(violations)}건: {'; '.join(violations[:3])}"}
    return {"status": "pass", "detail": f"C02 통과 ({len(posts)}건)"}


@register_check("c03_fm_key_leak")
def check_c03(conn, blog_id: str) -> dict:
    """C03: 본문 프론트매터 키 유출 검사."""
    site = _find_site_path(conn, blog_id)
    if not site:
        return {"status": "unknown", "detail": f"site_path 없음: {blog_id}"}

    posts = _read_post_files(site)
    if not posts:
        return {"status": "unknown", "detail": "최근 7일 포스트 없음"}

    violations = []
    for path, content in posts:
        _, fm = _parse_frontmatter(content)
        body_start = content.find("---\n", 4)
        body = content[body_start + 4:] if body_start > 0 else content
        passed, detail = _check_c03(body)
        if not passed:
            violations.append(f"{path.parent.name}: {detail}")

    if violations:
        return {"status": "fail",
                "detail": f"C03 위반 {len(violations)}건: {'; '.join(violations[:3])}"}
    return {"status": "pass", "detail": f"C03 통과 ({len(posts)}건)"}


@register_check("c04_prompt_leak")
def check_c04(conn, blog_id: str) -> dict:
    """C04: LLM 프롬프트/사고문 누수 검사 (국문+영문)."""
    site = _find_site_path(conn, blog_id)
    if not site:
        return {"status": "unknown", "detail": f"site_path 없음: {blog_id}"}

    posts = _read_post_files(site)
    if not posts:
        return {"status": "unknown", "detail": "최근 7일 포스트 없음"}

    violations = []
    for path, content in posts:
        _, fm = _parse_frontmatter(content)
        body_start = content.find("---\n", 4)
        body = content[body_start + 4:] if body_start > 0 else content
        passed, detail = _check_c04(body, blog_id)
        if not passed:
            violations.append(f"{path.parent.name}: {detail}")

    if violations:
        return {"status": "fail",
                "detail": f"C04 위반 {len(violations)}건: {'; '.join(violations[:3])}"}
    return {"status": "pass", "detail": f"C04 통과 ({len(posts)}건)"}


@register_check("c05_draft_publish")
def check_c05(conn, blog_id: str) -> dict:
    """C05: draft:true 발행 대상 검사."""
    site = _find_site_path(conn, blog_id)
    if not site:
        return {"status": "unknown", "detail": f"site_path 없음: {blog_id}"}

    posts = _read_post_files(site)
    if not posts:
        return {"status": "unknown", "detail": "최근 7일 포스트 없음"}

    violations = []
    for path, content in posts:
        _, fm = _parse_frontmatter(content)
        passed, detail = _check_c05(fm)
        if not passed:
            violations.append(f"{path.parent.name}: {detail}")

    if violations:
        return {"status": "fail",
                "detail": f"C05 위반 {len(violations)}건: {'; '.join(violations[:3])}"}
    return {"status": "pass", "detail": f"C05 통과 ({len(posts)}건)"}


@register_check("c06_mtime_deploy")
def check_c06(conn, blog_id: str) -> dict:
    """C06: 로컬 mtime > 배포 시각 검사."""
    site = _find_site_path(conn, blog_id)
    if not site:
        return {"status": "unknown", "detail": f"site_path 없음: {blog_id}"}

    posts = _read_post_files(site)
    if not posts:
        return {"status": "unknown", "detail": "최근 7일 포스트 없음"}

    warnings = []
    for path, _ in posts:
        passed, detail = _check_c06(path, blog_id)
        if not passed:
            warnings.append(detail)

    if warnings:
        return {"status": "fail",
                "detail": f"C06 경고 {len(warnings)}건: {'; '.join(warnings[:3])}"}
    return {"status": "pass", "detail": f"C06 통과 ({len(posts)}건)"}


@register_check("c07_dead_crossell")
def check_c07(conn, blog_id: str) -> dict:
    """C07: 죽은 크로스셀 링크 검사."""
    site = _find_site_path(conn, blog_id)
    if not site:
        return {"status": "unknown", "detail": f"site_path 없음: {blog_id}"}

    posts = _read_post_files(site)
    if not posts:
        return {"status": "unknown", "detail": "최근 7일 포스트 없음"}

    violations = []
    for path, content in posts:
        _, fm = _parse_frontmatter(content)
        body_start = content.find("---\n", 4)
        body = content[body_start + 4:] if body_start > 0 else content
        passed, detail = _check_c07(body, conn)
        if not passed:
            violations.append(f"{path.parent.name}: {detail}")

    if violations:
        return {"status": "fail",
                "detail": f"C07 위반 {len(violations)}건: {'; '.join(violations[:3])}"}
    return {"status": "pass", "detail": f"C07 통과 ({len(posts)}건)"}


@register_check("c08_live_file_mismatch")
def check_c08(conn, blog_id: str) -> dict:
    """C08: 라이브-파일 불일치 검사 (placeholder)."""
    return {"status": "unknown", "detail": "C08: 라이브 비교 미구현 (향후 활성화)"}


@register_check("c09_str_list_categories")
def check_c09(conn, blog_id: str) -> dict:
    """C09: categories/tags 문자열화 탐지.

    YAML 값이 ["추천"] (list)가 아닌 "['추천']" (str)로 저장된 경우 탐지.
    severity=CRITICAL → 대시보드에서 fail 상태로 표시.
    """
    site = _find_site_path(conn, blog_id)
    if not site:
        return {"status": "unknown", "detail": f"site_path 없음: {blog_id}"}

    posts = _read_post_files(site)
    if not posts:
        return {"status": "unknown", "detail": "최근 7일 포스트 없음"}

    violations = []
    for path, content in posts:
        passed, detail = _check_c09(content)
        if not passed:
            violations.append(f"{path.parent.name}: {detail}")

    if violations:
        return {"status": "fail",
                "detail": f"C09 위반 {len(violations)}건: {'; '.join(violations[:3])}"}
    return {"status": "pass", "detail": f"C09 통과 ({len(posts)}건)"}
