"""ops_dashboard.checks.content_quality — 발행 글 구조 품질 검사

라이브 최신 글 HTML을 가져와, 후처리(_normalize_product_blocks)가 놓친
구조 결함이 남아있는지 검사한다.
  - 값 없는 빈 불릿 (- 배송:, - 이미지:, - 단독)
  - 쪼개진 CTA 버튼 (<div ...>\n 뒤 <a> 분리)
  - 제휴문구 개수 이상 (정상: 1~2회)
  - 상품 이미지 누락 (본문 <img> 0개)
"""
from __future__ import annotations

import logging
import re
import urllib.parse
import urllib.request

from ops_dashboard.checks import register_check
from ops_dashboard.db import get_blog_config_status, get_blog_domain

logger = logging.getLogger(__name__)

DISCLOSURE = "쿠팡 파트너스 활동의 일환"
_UA = "Mozilla/5.0 (ops-dashboard content_quality check)"


def _fetch(url: str, timeout: int = 12) -> str | None:
    try:
        # 한글 등 비ASCII 경로 퍼센트 인코딩 (스킴/호스트는 보존)
        sp = urllib.parse.urlsplit(url)
        path = urllib.parse.quote(sp.path, safe="/%")
        url = urllib.parse.urlunsplit((sp.scheme, sp.netloc, path, sp.query, sp.fragment))
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning(f"content_quality fetch 실패 {url}: {e}")
        return None


def _latest_post_url(domain: str) -> str | None:
    """sitemap 또는 /posts/ 목록에서 최신 글 URL 1건 추출."""
    base = f"https://{domain}"
    # sitemap 우선 (lastmod 최신)
    sm = _fetch(f"{base}/sitemap.xml")
    if sm:
        locs = re.findall(r"<loc>([^<]*/posts/[^<]+)</loc>", sm)
        if locs:
            return locs[-1]
    # fallback: 목록 페이지 첫 글 링크
    lst = _fetch(f"{base}/posts/")
    if lst:
        m = re.search(r'href=["\']?([^"\'>\s]*/posts/[^"\'>\s]+/)["\']?', lst)
        if m:
            link = m.group(1)
            return link if link.startswith("http") else base + link
    return None


def _analyze(html: str) -> list[str]:
    """렌더된 라이브 HTML 기준 구조 결함 목록 (빈 리스트면 정상)."""
    issues = []

    # 1) 빈 리스트 항목 (라벨만 / 완전 빈 <li>)
    if re.search(r"<li>\s*(배송|이미지|쿠팡순위)\s*:\s*</li>", html):
        issues.append("[CQ01] 빈 불릿(라벨만)")
    if re.search(r"<li>\s*</li>", html):
        issues.append("[CQ01] 빈 리스트 항목")

    # 2) CTA 버튼이 <li> 안에 갇힘 (독립 블록화 실패)
    if re.search(r"<li>[^<]*<[^>]*btn-price-check", html):
        issues.append("[CQ02] CTA가 리스트 항목에 갇힘")

    # 3) 제휴문구 개수 (정상 1~2회)
    n = html.count(DISCLOSURE)
    if n == 0:
        issues.append("[CQ03] 제휴문구 누락")
    elif n > 2:
        issues.append(f"[CQ03] 제휴문구 과다({n}회)")

    # 4) 상품/썸네일 이미지 누락 (r2 썸네일 또는 쿠팡 상품 이미지)
    if not re.search(r"curation-images|r2\.dev|ads-partners\.coupang\.com|coupangcdn\.com", html):
        issues.append("[CQ05] 상품/썸네일 이미지 없음")


    # 5) '상품별 상세 비교'가 h2가 아님 (strong/bold/작은 글씨로 렌더)
    if "상품별 상세 비교" in html:
        if not re.search(r"<h2[^>]*>\s*상품별 상세 비교", html):
            issues.append("[CQ04] 상품별 상세 비교 h2 아님")

    # 6) 상품 개수 대비 이미지 부족 — '상품별 상세 비교' h2 ~ 다음 h2 구간만 대상
    m2 = re.search(r"상품별 상세 비교", html)
    if m2:
        seg = html[m2.start():]
        nxt = re.search(r"<h2", seg[10:])            # 다음 h2 전까지가 상품 섹션
        if nxt:
            seg = seg[:nxt.start()+10]
        prod_h3 = len(re.findall(r"<h3[^>]*>", seg))
        prod_img = len(re.findall(r"<img\b", seg))  # 섹션 내 모든 이미지
        if prod_h3 >= 2 and prod_img < prod_h3:
            issues.append(f"[CQ05] 상품 이미지 부족(상품 {prod_h3} vs 이미지 {prod_img})")

    # 7) 상품 설명 문단 소실 — 상품 섹션(룰6과 동일 범위) 내 각 h3 블록에 설명 텍스트가 없는 경우
    #    (이미지·CTA만 있고 설명 문장(CJK)이 없으면 위반. figure가 <p>에 래핑된 구조라
    #     태그 유무가 아닌 텍스트 기준으로 판정)
    m2 = re.search(r"상품별 상세 비교", html)
    if m2:
        seg = html[m2.start():]
        nxt = re.search(r"<h2", seg[10:])            # 다음 h2 전까지가 상품 섹션
        if nxt:
            seg = seg[:nxt.start()+10]
        h3s = list(re.finditer(r"<h3[^>]*>.*?</h3>", seg, re.S))   # h3 전체 요소(제목 포함)
        missing_desc = 0
        for _i, _hm in enumerate(h3s):
            _end = h3s[_i+1].start() if _i+1 < len(h3s) else len(seg)
            _blk = seg[_hm.end():_end]               # </h3> 다음 ~ 다음 h3(또는 섹션 끝) 구간
            # 오탐 방지: <img>/<figure>/CTA 없는 빈·부제목 블록은 대상 외 (FAQ h3는 섹션 밖이라 제외됨)
            if not re.search(r"<img\b|<figure\b|btn-price-check", _blk):
                continue
            _txt = re.sub(r"<a\b[^>]*btn-price-check[^>]*>.*?</a>", "", _blk, flags=re.S)  # CTA 링크 텍스트 제외
            _txt = re.sub(r"<[^>]+>", "", _txt)
            _txt = re.sub(r"\s+", "", _txt)
            if not re.search(r"[\uac00-\ud7a3\u4e00-\u9fff]", _txt):   # 설명 문장(CJK) 0자
                missing_desc += 1
        if missing_desc:
            issues.append(f"[CQ07] 상품 설명 문단 소실({missing_desc}개)")

    # 8) 상품당 이미지 1장 규격 — 상품 섹션(룰6과 동일 범위) 내 각 h3 블록에 이미지가 2장 이상이면 위반
    #    (figure 숏코드는 <figure><img>로 렌더되므로 <img> 개수 = 실제 이미지 수. gallery는
    #     figure 나열로 렌더되어 자연히 2장 이상으로 잡힘. FAQ h3는 섹션 밖이라 대상 외)
    m2 = re.search(r"상품별 상세 비교", html)
    if m2:
        seg = html[m2.start():]
        nxt = re.search(r"<h2", seg[10:])            # 다음 h2 전까지가 상품 섹션
        if nxt:
            seg = seg[:nxt.start()+10]
        h3s = list(re.finditer(r"<h3[^>]*>.*?</h3>", seg, re.S))   # h3 전체 요소(제목 포함)
        max_imgs = 0
        for _i, _hm in enumerate(h3s):
            _end = h3s[_i+1].start() if _i+1 < len(h3s) else len(seg)
            _blk = seg[_hm.end():_end]               # </h3> 다음 ~ 다음 h3(또는 섹션 끝) 구간
            _cnt = len(re.findall(r"<img\b", _blk))
            if _cnt > max_imgs:
                max_imgs = _cnt
        if max_imgs > 1:
            issues.append(f"[CQ08] 상품 이미지 중복(상품당 {max_imgs}장, 규격 1장)")

    return issues



@register_check("content_quality")
def check_content_quality(conn, blog_id: str) -> dict:
    config_status = get_blog_config_status(conn, blog_id)
    if not config_status:
        return {"status": "unknown", "detail": f"Blog {blog_id} not found", "evidence_url": ""}
    if config_status in ("inactive", "disabled"):
        return {"status": "pass", "detail": f"Blog is {config_status} — skip", "evidence_url": ""}

    domain = get_blog_domain(conn, blog_id)
    if not domain:
        return {"status": "unknown", "detail": "domain not found", "evidence_url": ""}

    post_url = _latest_post_url(domain)
    if not post_url:
        return {"status": "unknown", "detail": "최신 글 URL을 찾지 못함", "evidence_url": f"https://{domain}/posts/"}

    html = _fetch(post_url)
    if html is None:
        return {"status": "unknown", "detail": "글 HTML fetch 실패", "evidence_url": post_url}

    issues = _analyze(html)
    if issues:
        return {"status": "fail", "detail": "구조 결함: " + ", ".join(issues), "evidence_url": post_url}
    return {"status": "pass", "detail": "발행 글 구조 정상(빈불릿/CTA/제휴문구/이미지)", "evidence_url": post_url}
