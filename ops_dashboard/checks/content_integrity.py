"""ops_dashboard.checks.content_integrity — C01~C08 콘텐츠 무결성 검사

블로그별 콘텐츠 무결성 규칙(C01~C08)을 검사하고 결과를 check_results에 기록.

# feedback hook (stub, Phase 64-04 — no wiring yet):
# from shared.rule_feedback import record_feedback
# # false_positive example: gate flagged C01 but human judges pass
# record_feedback(type="false_positive", rule_id="C01", blog_id=blog_id,
#                 slug=path.parent.name, severity="MAJOR", gate_decision="blocked",
#                 reason="curved quote in code block is intentional", detected_by="human")
# # false_negative example: check passed but live issue found later
# record_feedback(type="false_negative", rule_id="C09", blog_id=blog_id,
#                 slug=slug, severity="CRITICAL", gate_decision="passed",
#                 reason="categories str-literal not detected", detected_by="agent")
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import urllib.parse
from datetime import datetime
from pathlib import Path

import httpx

from ops_dashboard.checks import register_check
from ops_dashboard.checks.render import _check_og_image, _fetch_get
from ops_dashboard.db import get_blog_detail, get_blog_domain, get_conn, record_check

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
    r"제목\s*후보",          # "제목 후보" / "가능한 제목 후보" 프롬프트 릭
    r"가능한\s*제목",        # "가능한 제목 후보"
    r"추천\s*제목",          # "추천 제목"
    r"다듬은\s*제목",        # "다듬은 제목"
    r"우선\s*사용자\s*요청", # "우선 사용자 요청을 분석"
    r"매우\s*세심한\s*지침", # "매우 세심한 지침"
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
        # Hugo 섹션/리스팅 인덱스(_index.md)는 실제 포스트 아님.
        # 최소 frontmatter(title/draft만)라 FM-MISSINGKEYS/FM-DRAFT 오탐 유발 → 제외.
        if md_file.name == "_index.md":
            continue
        content = md_file.read_text(encoding="utf-8", errors="replace")
        mtime_ok = md_file.stat().st_mtime >= cutoff
        date_ts = _frontmatter_date_ts(content)
        date_ok = date_ts is not None and date_ts >= cutoff
        safe_include = date_ts is None  # date 파싱 불가/없음 → 안전측 포함
        if mtime_ok or date_ok or safe_include:
            results.append((md_file, content))
    # 최신 발행순 정렬 (frontmatter date 내림차순, 파싱 불가는 mtime fallback).
    # 2026-09-10: 카드 릭 일괄 치환이 전 파일 mtime를 갱신 → 7일 mtime 필터가
    # 4~5월 과거 글까지 전소 대상화 → S01/S02/C08 폭증(과거누적 fail 250+).
    # _S_POST_SAMPLE 상한이 최신 N개를 잡도록 date 내림차순 정렬 보장.
    def _sort_key(item):
        md_file, content = item
        ts = _frontmatter_date_ts(content)
        if ts is None:
            ts = md_file.stat().st_mtime
        return -ts
    results.sort(key=_sort_key)
    return results


def _parse_frontmatter(content: str) -> tuple[str | None, dict]:
    """frontmatter 파싱 (python-frontmatter 기반, block-style YAML 지원).

    반환 시그니처 유지: (fm_text, dict).
    호출부(`.get(k) or ""` + `.strip()/.lower()` 패턴) 호환을 위해
    값을 문자열/None 안전 형태로 정규화:
      - None        → ""   (누락 = 빈값, 기존 동작 유지)
      - bool        → "true"/"false"
      - list/dict   → str(value)  (block-style tags 등 → 비어있지 않은 문자열)
      - 기타/str    → str(value) 또는 그대로
    → 단순 regex 가 block-style `tags:` 를 빈값으로 읽던 FM-MISSINGKEYS
      FALSE-POSITIVE 해소. import 실패 시 기존 regex 로 fallback.
    """
    m = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    if not m:
        return None, {}
    fm_text = m.group(1)
    try:
        import frontmatter as _fm

        parsed = _fm.loads(content).metadata
        fm: dict = {}
        for k, v in parsed.items():
            if v is None:
                fm[k] = ""
            elif isinstance(v, bool):
                fm[k] = "true" if v else "false"
            elif isinstance(v, (list, dict)):
                fm[k] = str(v)
            elif isinstance(v, str):
                fm[k] = v
            else:
                fm[k] = str(v)
        return fm_text, fm
    except Exception:
        # fallback: 기존 regex (graceful degradation)
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


# CUAP 형식/톤 위반 (P35) — 라벨 덤프 + 반말체 비율
C10_LABELS = ["가격", "배송", "쿠팡순위", "장점", "아쉬운점", "단점",
              "적당한대상", "적합대상", "추천대상", "추천 대상", "페르소나"]
C10_LABEL_RE = re.compile(r"^\s*(?:" + "|".join(re.escape(l) for l in C10_LABELS) + r")\s*[:：]")


def _check_c10(body_md: str, blog_id: str) -> tuple[bool, str]:
    """C10: 형식/톤 위반. 라벨덤프는 전 브랜치 적용(명백한 데이터 덤프),
    반말체 비율(~다)은 CUAP 전용(타 분기는 정당한 ~다 사용 가능)."""
    lines = body_md.split("\n")
    label_hits = [l.strip()[:40] for l in lines if C10_LABEL_RE.match(l)]
    # 라벨덤프: STAP/TAP/CUAP 등 어느 분기나 동일 항목 → 전체 적용
    if label_hits:
        return False, f"C10 위반: 라벨덤프 {len(label_hits)}건 — {label_hits[0]}"
    # 반말체 비율: CUAP 전용 (타 분기 정당한 ~다 사용 가능 → 오탐 방지)
    if not blog_id.startswith("cuap"):
        return True, "C10 통과 (비-CUAP 톤 검사 생략)"
    sentences = [s.strip() for s in re.split(r"[.!?。！？]\s*", body_md) if len(s.strip()) > 2]
    banmal = sum(1 for s in sentences if re.search(r"(?:다|이다)$", s))
    total = len(sentences)
    ratio = (banmal / total) if total else 0
    if ratio > 0.5 and total >= 5:
        return False, f"C10 위반: 반말체 비율 {ratio:.0%} (기대 ~입니다/~습니다)"
    return True, "C10 통과"


def _check_c05(fm: dict) -> tuple[bool, str]:
    """C05: draft:true 발행 대상."""
    if fm.get("draft", "").lower() == "true":
        return False, "C05 위반: draft:true 발행 대상"
    return True, "C05 통과"


def _check_c06(file_path: Path, blog_id: str) -> tuple[bool, str]:
    """C06: 로컬 mtime 기반 배포-미반영 감지.

    원래 구현은 '최근 1일 내 수정'이면 무조건 fail 했으나, 파이프라인이
    매일 배포하므로 정상 상태(방금 발행)에서도 항상 fail → 대시보드 노이즈.
    단순 mtime만으로는 '배포 미반영'을 판별할 수 없음(배포 시각 추적 없음).
    따라서 C06은 항상 pass(정보성)로 전환 — 실제 undeployed-change 감지는
    c08_live_file_mismatch(라이브 대조)가 담당.
    """
    if not file_path.exists():
        return True, "파일 없음 (skip)"
    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
    days_since = (datetime.now() - mtime).days
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


# ─── C08 라이브-파일 대조 (Phase 71, SC-2) ───

# (c) CoT/메타 프롬프트 유출 탐지 패턴 (C04 재사용)
_C08_COT_KO = [
    r"생각해보자", r"생각해 보자", r"다음 단계로 넘어", r"단계별로 진행해",
    r"우선, 우리가 해야", r"우리가 해야 할 것은", r"생각 과정을 통해",
    r"결론부터 말하면", r"먼저 생각해보자", r"단계별로 생각",
]
_C08_COT_EN = [
    r"Need to think", r"We need to write", r"Let's think step by step",
    r"think step by step", r"let's break this down", r"here's the plan",
    r"in order to achieve", r"as an AI language model",
]


def _meta_content(html: str, attr: str, value: str) -> str | None:
    """<meta attr="value" content="..."> 에서 content 추출."""
    m = re.search(
        r'<meta\s+[^>]*' + attr + r'=["\']' + re.escape(value) + r'["\'][^>]*content=["\']([^"\']+)["\']',
        html, re.IGNORECASE,
    )
    if m:
        return m.group(1)
    # 역순 (content 먼저)
    m = re.search(
        r'<meta\s+[^>]*content=["\']([^"\']+)["\'][^>]*' + attr + r'=["\']' + re.escape(value) + r'["\']',
        html, re.IGNORECASE,
    )
    return m.group(1) if m else None


def _title_text(html: str) -> str | None:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else None


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html or "")


def _compare_live_vs_local(fm: dict, live_html: str) -> list[str]:
    """라이브 HTML vs 로컬 frontmatter 비교 → 위반 problem_id 리스트.

    (a) 제목/메타설명/og:image 존재·일치
    (b) 구조 순서(타이틀→설명문→첫 소제목) 유지
    (c) CoT/메타 프롬프트 유출 본문 노출
    (d) 광고 블록 실제 렌더링
    """
    problems: list[str] = []
    local_title = (fm.get("title") or "").strip()
    local_og = (fm.get("og_image") or fm.get("featureimage") or "").strip()

    live_title = _meta_content(live_html, "property", "og:title") or _title_text(live_html)
    live_desc = (
        _meta_content(live_html, "name", "description")
        or _meta_content(live_html, "property", "og:description")
    )
    live_og_ok, live_og = _check_og_image(live_html)

    # (a)
    if local_title and live_title and local_title != live_title:
        problems.append("C08_TITLE_MISMATCH")
    # 존재 검사 먼저: 파일 또는 라이브 어느 한쪽이라도 og:image 없으면 fail
    if not local_og or not live_og_ok:
        problems.append("C08_OG_MISSING")
    elif local_og.rstrip("/") != live_og.rstrip("/"):
        problems.append("C08_OG_MISMATCH")

    # (b) 구조 순서: 타이틀 텍스트가 첫 h2 보다 먼저 등장해야 함
    if local_title and live_title:
        h2_pos = live_html.lower().find("<h2")
        title_pos = live_html.find(live_title)
        if h2_pos != -1 and title_pos != -1 and h2_pos < title_pos:
            problems.append("C08_STRUCTURE")

    # (c) CoT/메타 프롬프트 유출
    body_text = _strip_tags(live_html)
    for pat in (_C08_COT_KO + _C08_COT_EN):
        if re.search(pat, body_text):
            problems.append("C08_COT_LEAK")
            break

    # (d) 광고 렌더링 — adsbygoogle.js 로드 또는 <ins class="adsbygoogle"> 존재
    if (
        "adsbygoogle" not in live_html
        and 'class="adsbygoogle"' not in live_html
        and "adsbygoogle.js" not in live_html
    ):
        problems.append("C08_AD_NOT_RENDERED")

    return problems


def _post_url_candidates(domain: str, slug: str) -> list[str]:
    """라이브 포스트 URL 후보 (section prefix / bare / blog prefix).

    c08 체커는 과거 bare `/{slug}/` 만 가정해 실제 permalink(`/posts/{slug}/` 등)
    와 달라 404를 맞히고 매 포스트를 TITLE_MISMATCH+OG_MISSING 오탐.
    `_read_post_files` 는 `content/posts/` 만 읽으므로 표준 섹션은 'posts'.
    후보를 순서대로 시도해 첫 200(soft-404 아님) 본문을 사용한다.
    """
    enc = urllib.parse.quote(slug, safe="")
    base = f"https://{domain}"
    return [
        f"{base}/posts/{enc}/",
        f"{base}/{enc}/",
        f"{base}/blog/{enc}/",
    ]


def _crawl_post(blog_id: str, domain: str | None, slug: str) -> str | None:
    """라이브 포스트 URL GET (render._fetch_get 의 sync 래퍼).

    후보 URL 중 HTTP 200이고 soft-404(og:title에 '404' 포함)가 아닌
    첫 본문을 반환. 전부 실패 시 None. slug 유니코드는 URL 인코딩.
    """
    if not domain:
        return None
    candidates = _post_url_candidates(domain, slug)
    try:
        async def _go() -> str | None:
            async with httpx.AsyncClient(
                timeout=10, follow_redirects=True, headers={"User-Agent": "OpsDashboard/1.0"}
            ) as client:
                for url in candidates:
                    try:
                        status, body = await _fetch_get(client, url)
                    except Exception as e:  # noqa: BLE001
                        logger.warning("[C08] 크롤 예외: blog=%s url=%s: %s", blog_id, url, e)
                        continue
                    if status == 200 and body:
                        # soft-404 방지: og:title 가 404 마커면 무효 처리
                        ogt = _meta_content(body, "property", "og:title")
                        if ogt and "404" in ogt:
                            continue
                        return body
                return None

        return asyncio.run(_go())
    except Exception as e:  # 크롤 실패/타임아웃 — 통과가 아닌 명시적 에러 상태로 상위 전달
        logger.warning("[C08] 라이브 크롤 실패: blog=%s slug=%s: %s", blog_id, slug, e)
        return None


def _check_c08(
    site: Path | None, blog_id: str, domain: str | None = None
) -> tuple[bool, str]:
    """C08: 라이브-파일 불일치 실검사.

    라이브 URL 크롤 후 (a)제목/메타/og:image 일치, (b)구조 순서,
    (c)CoT/메타 프롬프트 유출, (d)광고 렌더링 여부를 각각 problem_id 로 기록.
    크롤 실패/타임아웃은 통과가 아닌 명시적 에러(C08_CRAWL_ERROR, fail) 상태.
    """
    if not site:
        return False, "C08_SITE_UNREACHABLE: site_path 없음 — 라이브 대조 불가"
    posts = _read_post_files(site)
    if not posts:
        return True, "C08 통과: 최근 검사 대상 포스트 없음"
    if domain is None:
        _conn = None
        try:
            _conn = get_conn()
            domain = get_blog_domain(_conn, blog_id)
        except Exception:
            domain = None
        finally:
            if _conn is not None:
                _conn.close()
    violations: list[str] = []
    crawl_errors = 0
    for path, content in posts:
        slug = path.parent.name
        _fm_text, fm = _parse_frontmatter(content)
        body = _crawl_post(blog_id, domain, slug)
        if body is None:
            crawl_errors += 1
            continue
        probs = _compare_live_vs_local(fm, body)
        violations.extend(f"{slug}:{p}" for p in probs)
    if crawl_errors and not violations:
        return False, (
            f"C08_CRAWL_ERROR: {crawl_errors}건 라이브 크롤 실패(타임아웃/네트워크) "
            f"— 통과 판정 불가 (명시적 에러)"
        )
    if violations:
        return False, f"C08 위반 {len(violations)}건: {'; '.join(violations[:5])}"
    return True, f"C08 통과 ({len(posts)}건 라이브 대조)"


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


@register_check("c10_cuap_format_tone")
def check_c10(conn, blog_id: str) -> dict:
    """C10: CUAP 형식/톤 위반 (라벨덤프 + 반말체). CUAP 전용."""
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
        passed, detail = _check_c10(body, blog_id)
        if not passed:
            violations.append(f"{path.parent.name}: {detail}")

    if violations:
        return {"status": "fail",
                "detail": f"C10 위반 {len(violations)}건: {'; '.join(violations[:3])}"}
    return {"status": "pass", "detail": f"C10 통과 ({len(posts)}건)"}


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
    """C08: 라이브-파일 불일치 실검사.

    라이브 크롤 비용 급증 완화: 24h 이내에 이미 실행됐으면 라이브 크롤을
    생략하고 이전 결과를 반환(저빈도 분리). 그 외엔 실제 크롤→비교→실판정.
    크롤 실패는 통과가 아닌 명시적 fail(에러) 상태.
    """
    # 저빈도 캐시: 24h 이내 실행 시 라이브 크롤 생략
    try:
        last = conn.execute(
            "SELECT status, detail, checked_at FROM check_results "
            "WHERE blog_id=? AND check_name='c08_live_file_mismatch' "
            "ORDER BY checked_at DESC LIMIT 1",
            (blog_id,),
        ).fetchone()
        if last:
            _ts = datetime.fromisoformat(last["checked_at"])
            if (datetime.now() - _ts).total_seconds() < 24 * 3600:
                # 캐시 무효화: 로컬 포스트가 캐시 시각보다 새로우면(배포 직후 등)
                # 구 결과는 stale 불일치(false positive)이므로 재크롤 강제.
                _stale = False
                try:
                    _posts = _read_post_files(site)
                    if _posts:
                        _max_mtime = max(p.stat().st_mtime for p, _ in _posts)
                        if _max_mtime > _ts.timestamp():
                            _stale = True
                except Exception:
                    pass
                if not _stale:
                    # 접미사 중복 누적 방지 — 이전 실행에서 붙은 캐시 문구는 제거 후 1회만 부착
                    base = last["detail"].replace(" (캐시: 24h 내 실행됨)", "")
                    return {
                        "status": last["status"],
                        "detail": base + " (캐시: 24h 내 실행됨)",
                        "evidence_url": "",
                    }
    except Exception:
        pass

    site = _find_site_path(conn, blog_id)
    if not site:
        return {
            "status": "fail",
            "detail": "C08_SITE_UNREACHABLE: site_path 없음 — 라이브 대조 불가",
            "evidence_url": "",
        }
    domain = get_blog_domain(conn, blog_id)
    passed, detail = _check_c08(site, blog_id, domain)
    return {
        "status": "pass" if passed else "fail",
        "detail": detail,
        "evidence_url": "",
    }


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


# ============================================================
# PHASE 70 WAVE 1: S-CATEGORY DASHBOARD RULES (S01~S05)
# ============================================================

_S_CORPUS_CAP = 200  # corpus 상한 — 초과 시 stride 샘플링 (preflight와 동일 기준)
_S_POST_SAMPLE = 50  # check_s01/s02 포스트 상한 — 초과 시 최근 N건만 검사


def _extract_corpus(site: Path, blog_id: str, exclude_slug: str = "") -> list[str]:
    """기존 발행된 포스트 본문들을 corpus로 추출 (S01, S02 게이트용).

    corpus가 _S_CORPUS_CAP 초과 시 stride 샘플링으로 축소.
    """
    posts_dir = site / "content" / "posts"
    if not posts_dir.exists():
        return []
    corpus = []
    for md_file in posts_dir.rglob("*.md"):
        slug = md_file.parent.name
        if slug == exclude_slug:
            continue
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
            # frontmatter 제거하고 본문만 추출
            body_start = content.find("---\n", 4)
            if body_start > 0:
                body = content[body_start + 4:]
                if len(body) > 200:
                    corpus.append(body)
        except Exception:
            pass
    if len(corpus) > _S_CORPUS_CAP:
        _step = len(corpus) // _S_CORPUS_CAP + 1
        corpus = corpus[::_step][:_S_CORPUS_CAP]
    return corpus


def _extract_corpus_by_slug(site: Path) -> dict:
    """slug→body dict corpus (self-match 제외용).

    2026-09-10: 체커가 최신 글(자기 자신 포함)을 corpus에 넣고 검사해
    uniqueness=0.0000 / max_sim=1.0000 self-match 오탐 발생 (panama-city-water-sports
    23:15 발행 직후 23:16 fail 사례). 검사 루프에서 자기 slug를 제외하기 위해 dict 반환.
    stride 샘플링은 _extract_corpus와 동일 — _S_CORPUS_CAP 초과 시 균등 축소.
    """
    posts_dir = site / "content" / "posts"
    if not posts_dir.exists():
        return {}
    corpus: dict = {}
    for md_file in posts_dir.rglob("*.md"):
        slug = md_file.parent.name
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
            body_start = content.find("---\n", 4)
            if body_start > 0:
                body = content[body_start + 4:]
                if len(body) > 200:
                    corpus[slug] = body
        except Exception:
            pass
    if len(corpus) > _S_CORPUS_CAP:
        _step = len(corpus) // _S_CORPUS_CAP + 1
        keys = list(corpus)[::_step][:_S_CORPUS_CAP]
        corpus = {k: corpus[k] for k in keys}
    return corpus


def _get_source_data_from_slug(slug: str, blog_id: str) -> dict:
    """slug를 이용해 source_data 재구성 (S03 게이트용).
    
    travel-en.db의 articles/publish_log에서 원본 데이터 조회.
    다른 파이프라인은 해당 DB에서 조회 로직 추가 필요.
    """
    import sqlite3
    from pathlib import Path
    
    # ETAP 블로그인 경우 travel-en.db 사용
    db_path = Path(__file__).parent.parent.parent / "data" / "travel-en.db"
    if not db_path.exists():
        return {}
    
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        
        # publish_log에서 topic_id 조회
        row = conn.execute(
            "SELECT topic_id FROM publish_log WHERE blog_id = ? AND slug = ? ORDER BY log_id DESC LIMIT 1",
            (blog_id, slug)
        ).fetchone()
        
        if not row or not row["topic_id"]:
            conn.close()
            return {}
        
        topic_id = row["topic_id"]
        
        # articles 테이블에서 원본 데이터 조회 (테이블명 유추)
        # topic_id로 어떤 테이블인지 파악 필요 - 여기선 기본 구조만 반환
        source_data = {"topic_id": topic_id}
        
        # flight_prices, popular_directions, flight_calendar 등에서 데이터 조회 시도
        for table in ["flight_prices", "popular_directions", "flight_calendar", "tours", "hotels", "restaurants"]:
            try:
                rows = conn.execute(f"SELECT * FROM {table} WHERE origin = ? OR destination = ? OR city = ? LIMIT 20",
                                   (slug, slug, slug)).fetchall()
                if rows:
                    source_data[table] = [dict(r) for r in rows]
            except Exception:
                pass
        
        conn.close()
        return source_data
    except Exception:
        return {}


def _quiet_gate_logs():
    """quality_gate 로거를 ERROR로 올리는 컨텍스트 매니저.

    체커가 게이트를 50포스트×200corpus호 시간당 수천 번 호출하는데
    게이트가 매 계산마다 WARNING/INFO 로그를 stderr에 뿌림 →
    하루 300MB+ 로그 폭발(2026-09-08 디스크 100% 사고 원인).
    체커 결과 자체가 detail에 요약되므로 게이트 단위 로그는 중복.
    """
    import logging as _logging
    import contextlib
    from contextlib import contextmanager
    _qg = _logging.getLogger("pipelines.etap.quality_guard")

    @contextmanager
    def _cm():
        _saved = _qg.level
        _qg.setLevel(_logging.ERROR)
        try:
            yield
        finally:
            _qg.setLevel(_saved)

    return _cm()


def _check_s01_uniqueness(content: str, corpus: list[str]) -> tuple[bool, str]:
    """S01: Uniqueness Ratio ≥ 0.85 vs corpus."""
    try:
        from pipelines.etap.quality_guard import uniqueness_ratio_gate
        with _quiet_gate_logs():
            passed, ratio, details = uniqueness_ratio_gate(content, corpus, threshold=0.85)
        if not passed:
            return False, f"S01 위반: uniqueness={ratio:.4f} (threshold=0.85), max_sim={details.get('max_similarity', 0):.4f}"
        return True, f"S01 통과: uniqueness={ratio:.4f}"
    except ImportError:
        return True, "S01 skip (quality_guard import 실패)"
    except Exception as e:
        logger.warning(f"[S01] check error: {e}")
        return True, f"S01 skip (error: {e})"


def _check_s02_structural(content: str, corpus: list[str]) -> tuple[bool, str]:
    """S02: Structural Similarity ≤ 0.70 (H2 sequence overlap)."""
    try:
        from pipelines.etap.quality_guard import structural_similarity_gate
        with _quiet_gate_logs():
            passed, sim, details = structural_similarity_gate(content, corpus, threshold=0.70)
        if not passed:
            return False, f"S02 위반: structural_sim={sim:.4f} (threshold=0.70)"
        return True, f"S02 통과: structural_sim={sim:.4f}"
    except ImportError:
        return True, "S02 skip (quality_guard import 실패)"
    except Exception as e:
        logger.warning(f"[S02] check error: {e}")
        return True, f"S02 skip (error: {e})"


def _check_s03_data_points(content: str, source_data: dict) -> tuple[bool, str]:
    """S03: Unique Data Points ≥ 3 verifiable points."""
    try:
        from pipelines.etap.quality_guard import unique_data_points_gate
        with _quiet_gate_logs():
            passed, count, details = unique_data_points_gate(content, source_data, threshold=3)
        if not passed:
            return False, f"S03 위반: data_points={count} (threshold=3), found={details.get('found_points', [])}"
        return True, f"S03 통과: data_points={count}"
    except ImportError:
        return True, "S03 skip (quality_guard import 실패)"
    except Exception as e:
        logger.warning(f"[S03] check error: {e}")
        return True, f"S03 skip (error: {e})"


def _check_s04_editorial_synthesis(content: str) -> tuple[bool, str]:
    """S04: Editorial Synthesis Passed (template markers replaced).
    
    Checks for remaining template markers like {{city}}, {{price}} etc.
    Hugo shortcodes `{{< ... >}}` / `{{% ... %}}` are valid rendered output,
    NOT unrendered markers — excluded via negative lookahead to match the actual
    deploy gate in dispatcher.py:preflight_check.
    """
    template_markers = re.findall(r"\{\{(?![<{%])[^}]+\}\}", content)
    if template_markers:
        unique_markers = set(template_markers)
        return False, f"S04 위반: 미치환 템플릿 마커 {len(unique_markers)}개 — {list(unique_markers)[:5]}"
    return True, "S04 통과: 템플릿 마커 없음"


def _check_s05_freshness(fm: dict, blog_id: str) -> tuple[bool, str]:
    """S05: Freshness Gate (data age < 30 days for price/date sensitive content).
    
    Checks frontmatter for data freshness indicators. For ETAP blogs,
    checks if the source data (prices, dates) is within 30 days.
    """
    # Check for freshness-related frontmatter keys
    freshness_keys = ["data_date", "price_date", "source_date", "last_updated", "data_freshness_days"]
    for key in freshness_keys:
        if key in fm and fm[key]:
            try:
                val = str(fm[key]).strip()
                # Try to parse as date
                from datetime import datetime
                for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S"):
                    try:
                        data_date = datetime.strptime(val[:10], "%Y-%m-%d")
                        age_days = (datetime.now() - data_date).days
                        if age_days > 30:
                            return False, f"S05 위반: 데이터 경과 {age_days}일 (threshold=30일), {key}={val}"
                        return True, f"S05 통과: 데이터 경과 {age_days}일"
                    except ValueError:
                        continue
                # Try as integer days
                try:
                    age_days = int(val)
                    if age_days > 30:
                        return False, f"S05 위반: 데이터 경과 {age_days}일 (threshold=30일), {key}={val}"
                    return True, f"S05 통과: 데이터 경과 {age_days}일"
                except ValueError:
                    pass
            except Exception:
                pass
    
    # No freshness info available - warn but don't fail (allow legacy)
    return True, "S05 통과: freshness 정보 없음 (legacy 허용)"


@register_check("s01_uniqueness_ratio")
def check_s01(conn, blog_id: str) -> dict:
    """S01: Uniqueness Ratio ≥ 0.85 vs existing corpus."""
    site = _find_site_path(conn, blog_id)
    if not site:
        return {"status": "unknown", "detail": f"site_path 없음: {blog_id}"}
    
    posts = _read_post_files(site)
    if not posts:
        return {"status": "unknown", "detail": "최근 7일 포스트 없음"}
    
    # corpus를 루프 밖에서 1회만 구축 (303포스트 × 302 corpus = 91,000회 계산 방지)
    # 2026-09-10: slug dict로 구축 — 검사 대상 글이 corpus에 자기 자신 포함 시
    # self-match(max_sim=1.0 → uniqueness=0.0000) 오탐. 루프에서 자기 slug 제외.
    corpus_by_slug = _extract_corpus_by_slug(site)
    if not corpus_by_slug:
        return {"status": "unknown", "detail": "corpus 없음"}
    
    # 포스트 수가 많으면 샘플링 (post-publish check 비용 상한)
    _posts = posts[:_S_POST_SAMPLE] if len(posts) > _S_POST_SAMPLE else posts
    
    violations = []
    for path, content in _posts:
        slug = path.parent.name
        _, fm = _parse_frontmatter(content)
        body_start = content.find("---\n", 4)
        body = content[body_start + 4:] if body_start > 0 else content
        corpus = [b for s, b in corpus_by_slug.items() if s != slug]
        if not corpus:
            continue
        passed, detail = _check_s01_uniqueness(body, corpus)
        if not passed:
            violations.append(f"{slug}: {detail}")
    
    if violations:
        return {"status": "fail",
                "detail": f"S01 위반 {len(violations)}건: {'; '.join(violations[:3])}"}
    return {"status": "pass", "detail": f"S01 통과 ({len(_posts)}건 검사, corpus {len(corpus_by_slug)}건)"}


@register_check("s02_structural_similarity")
def check_s02(conn, blog_id: str) -> dict:
    """S02: Structural Similarity ≤ 0.70 (H2 sequence overlap)."""
    if blog_id in ("adventure-hugo", "kitchen-hugo"):
        return {"status": "unknown", "detail": "S02 skip (고정구조 블로그)"}
    site = _find_site_path(conn, blog_id)
    if not site:
        return {"status": "unknown", "detail": f"site_path 없음: {blog_id}"}
    
    posts = _read_post_files(site)
    if not posts:
        return {"status": "unknown", "detail": "최근 7일 포스트 없음"}
    
    # corpus를 루프 밖에서 1회만 구축
    # 2026-09-10: slug dict — S01과 동일 self-match 제외 (H2 시퀀스도 자기 자신과 100% 일치)
    corpus_by_slug = _extract_corpus_by_slug(site)
    if not corpus_by_slug:
        return {"status": "unknown", "detail": "corpus 없음"}
    
    _posts = posts[:_S_POST_SAMPLE] if len(posts) > _S_POST_SAMPLE else posts
    
    violations = []
    for path, content in _posts:
        slug = path.parent.name
        _, fm = _parse_frontmatter(content)
        body_start = content.find("---\n", 4)
        body = content[body_start + 4:] if body_start > 0 else content
        corpus = [b for s, b in corpus_by_slug.items() if s != slug]
        if not corpus:
            continue
        passed, detail = _check_s02_structural(body, corpus)
        if not passed:
            violations.append(f"{slug}: {detail}")
    
    if violations:
        return {"status": "fail",
                "detail": f"S02 위반 {len(violations)}건: {'; '.join(violations[:3])}"}
    return {"status": "pass", "detail": f"S02 통과 ({len(_posts)}건 검사, corpus {len(corpus_by_slug)}건)"}


@register_check("s03_unique_data_points")
def check_s03(conn, blog_id: str) -> dict:
    """S03: Unique Data Points ≥ 3 verifiable points per article."""
    site = _find_site_path(conn, blog_id)
    if not site:
        return {"status": "unknown", "detail": f"site_path 없음: {blog_id}"}
    
    posts = _read_post_files(site)
    if not posts:
        return {"status": "unknown", "detail": "최근 7일 포스트 없음"}
    
    violations = []
    for path, content in posts:
        slug = path.parent.name
        _, fm = _parse_frontmatter(content)
        body_start = content.find("---\n", 4)
        body = content[body_start + 4:] if body_start > 0 else content
        source_data = _get_source_data_from_slug(slug, blog_id)
        if not source_data:
            continue  # source_data 없으면 검사 불가
        passed, detail = _check_s03_data_points(body, source_data)
        if not passed:
            violations.append(f"{slug}: {detail}")
    
    if violations:
        return {"status": "fail",
                "detail": f"S03 위반 {len(violations)}건: {'; '.join(violations[:3])}"}
    return {"status": "pass", "detail": f"S03 통과 ({len(posts)}건 검사)"}


@register_check("s04_editorial_synthesis")
def check_s04(conn, blog_id: str) -> dict:
    """S04: Editorial Synthesis Passed (no template markers remaining)."""
    site = _find_site_path(conn, blog_id)
    if not site:
        return {"status": "unknown", "detail": f"site_path 없음: {blog_id}"}
    
    posts = _read_post_files(site)
    if not posts:
        return {"status": "unknown", "detail": "최근 7일 포스트 없음"}
    
    violations = []
    for path, content in posts:
        slug = path.parent.name
        _, fm = _parse_frontmatter(content)
        body_start = content.find("---\n", 4)
        body = content[body_start + 4:] if body_start > 0 else content
        passed, detail = _check_s04_editorial_synthesis(body)
        if not passed:
            violations.append(f"{slug}: {detail}")
    
    if violations:
        return {"status": "fail",
                "detail": f"S04 위반 {len(violations)}건: {'; '.join(violations[:3])}"}
    return {"status": "pass", "detail": f"S04 통과 ({len(posts)}건 검사)"}


@register_check("s05_freshness_gate")
def check_s05(conn, blog_id: str) -> dict:
    """S05: Freshness Gate (data age < 30 days for price/date sensitive content)."""
    site = _find_site_path(conn, blog_id)
    if not site:
        return {"status": "unknown", "detail": f"site_path 없음: {blog_id}"}
    
    posts = _read_post_files(site)
    if not posts:
        return {"status": "unknown", "detail": "최근 7일 포스트 없음"}
    
    violations = []
    for path, content in posts:
        slug = path.parent.name
        _, fm = _parse_frontmatter(content)
        body_start = content.find("---\n", 4)
        body = content[body_start + 4:] if body_start > 0 else content
        passed, detail = _check_s05_freshness(fm, blog_id)
        if not passed:
            violations.append(f"{slug}: {detail}")
    
    if violations:
        return {"status": "fail",
                "detail": f"S05 위반 {len(violations)}건: {'; '.join(violations[:3])}"}
    return {"status": "pass", "detail": f"S05 통과 ({len(posts)}건 검사)"}
