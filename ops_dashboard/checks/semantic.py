"""ops_dashboard.checks.semantic — 의미품질 heuristic 탐지 (detect-only)

건강효능·경험허위·수치무근 주장을 보수적 키워드 휴리스틱으로 스캔한다.
본 check는 **탐지만** 하며 자동수정하지 않는다. 사람 리뷰 대상.

휴리스틱 (보수적 — 오탐 최소화):
  SEM-Q3 health_efficacy (금지패턴):
    - 완치
    - 100% 효과 / 백퍼센트 효과
    - 부작용 없음 / 전혀 없음 / 0개
    - 치료 효과 / 치료에 효과 / 치료에 도움
    - 효능 확실 / 효능 완벽 / 효능 100
  SEM-Q2 unsource_number (수치주장 인접 소스 없음):
    - 2~3자리 퍼센트(\\d{2,3}%) 또는 N배(\\d+배) 가 인접(±40자)에
      소스 키워드(연구/논문/보고서/임상/조사 결과/통계) 없이 등장
  SEM-Q1 experience_claim (1인칭 경험 주장):
    - 내가 ~해봤 / 경험상 / 직접 써본 / 내 경험(에 따르면)

임계값: 각 항목 매칭 건수 >= 1 이면 fail (최소 1건). 단 패턴은 금지어
위주로 엄격히 제한해 정상 콘텐츠 오탐을 막는다. 최신 1개 글 본문만 스캔.
"""
from __future__ import annotations

import logging
import re
import urllib.parse
import urllib.request

from ops_dashboard.checks import register_check
from ops_dashboard.db import get_blog_config_status, get_blog_domain

logger = logging.getLogger(__name__)

_UA = "Mozilla/5.0 (ops-dashboard semantic check)"
_SOURCE_KW = re.compile(r"연구|논문|보고서|임상|조사\s*결과|통계")
_Q3 = [
    r"완치",
    r"100\s*%\s*효과",
    r"백퍼센트\s*효과",
    r"부작용\s*(없음|전혀|0개|없는)",
    r"치료\s*효과",
    r"치료에\s*효과",
    r"치료에\s*도움",
    r"효능\s*(확실|완벽|100)",
]
_Q3_RE = [re.compile(p) for p in _Q3]
_Q2_PCT = re.compile(r"(\d{2,3})\s*%")
_Q2_MULT = re.compile(r"(\d+)\s*배")
_Q1 = re.compile(r"내가\s*.{0,12}해봤|경험상|직접\s*써본|내\s*경험(?:\에\s*따르면|상)")


def _fetch(url: str, timeout: int = 12) -> str | None:
    try:
        sp = urllib.parse.urlsplit(url)
        path = urllib.parse.quote(sp.path, safe="/%")
        url = urllib.parse.urlunsplit((sp.scheme, sp.netloc, path, sp.query, sp.fragment))
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning("semantic fetch 실패 %s: %s", url, e)
        return None


def _latest_post_url(domain: str) -> str | None:
    base = f"https://{domain}"
    sm = _fetch(f"{base}/sitemap.xml")
    if sm:
        locs = re.findall(r"<loc>([^<]*/posts/[^<]+)</loc>", sm)
        if locs:
            return locs[-1]
    lst = _fetch(f"{base}/posts/")
    if lst:
        m = re.search(r'href=["\']?([^"\'>\s]*/posts/[^"\'>\s]+/)["\']?', lst)
        if m:
            link = m.group(1)
            return link if link.startswith("http") else base + link
    return None


def _text(html: str) -> str:
    """HTML → 순수 텍스트 (태그/스크립트/스타일/엔티티 제거)."""
    t = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"&[a-z]+;", " ", t)
    return t


def _check_q3(text: str) -> str | None:
    for rx in _Q3_RE:
        m = rx.search(text)
        if m:
            return m.group(0)
    return None


def _check_q2(text: str) -> str | None:
    for rx in (_Q2_PCT, _Q2_MULT):
        for m in rx.finditer(text):
            start = max(0, m.start() - 40)
            ctx = text[start:m.end() + 10]
            if not _SOURCE_KW.search(ctx):
                return m.group(0)
    return None


def _scan(text: str) -> list[str]:
    hits: list[str] = []
    q3 = _check_q3(text)
    if q3:
        hits.append(f"SEM-Q3:{q3}")
    q2 = _check_q2(text)
    if q2:
        hits.append(f"SEM-Q2:{q2}")
    q1 = _Q1.search(text)
    if q1:
        hits.append(f"SEM-Q1:{q1.group(0)}")
    return hits


@register_check("semantic")
def check_semantic(conn, blog_id: str) -> dict:
    """최신 글 본문 스캔 → 건강효능/수치무근/경험허위 의심 탐지 (detect-only)."""
    config_status = get_blog_config_status(conn, blog_id)
    if not config_status:
        return {"status": "unknown", "detail": f"Blog {blog_id} not found"}
    if config_status in ("inactive", "disabled"):
        return {"status": "pass", "detail": f"Blog is {config_status} — skip"}

    domain = get_blog_domain(conn, blog_id)
    if not domain:
        return {"status": "unknown", "detail": "domain not found"}

    post_url = _latest_post_url(domain)
    if not post_url:
        return {"status": "unknown", "detail": "최신 글 URL 찾지 못함", "evidence_url": f"https://{domain}/posts/"}

    html = _fetch(post_url)
    if html is None:
        return {"status": "unknown", "detail": "글 HTML fetch 실패", "evidence_url": post_url}

    hits = _scan(_text(html))
    if hits:
        return {
            "status": "fail",
            "detail": "의미품질 의심: " + "; ".join(hits[:5]),
            "evidence_url": post_url,
        }
    return {
        "status": "pass",
        "detail": "의미품질 휴리스틱 통과(건강효능/수치무근/경험허위)",
        "evidence_url": post_url,
    }
