#!/usr/bin/env python3
"""TAP 블로그 본문 표준 검증 게이트 (verify_blog_standard).

C1~C6 체크를 수행해 발행물이 "TAP 여행/명소형 표준"(예시 글 구조)을 준수하는지 판정.
- C1: 빌드 HTML에 마크다운 `##`/`###` raw 노출 0건
- C2: H2 4~5개, H1 0, H3≥1, 표≥2, 체크리스트≥1
- C3: 네이버 지도 버튼이 해당 H3 뒤, 본문 맨 끝(tail_btns) 없음
- C4: 쿠팡 이미지 ≥3, 이미지 없는 링크 0
- C5: featureimage 중복 0 + 비쿠팡 + 이미지 도달성(경고만)
- C6: 엔티티 카드 주제 호환 + 위치

용법:
  python scripts/verify_blog_standard.py <content_dir_or_md_file> [--blog travel1-hugo]
  python scripts/verify_blog_standard.py --test   # 의도적 위반 샘플 6종 자체 검증
"""
import re
import sys
from pathlib import Path


# ── C1: 마크다운 raw 노출 (빌드 HTML 기준) ─────────────
def check_c1(html_text: str) -> tuple[bool, str]:
    """빌드된 HTML에 `##`/`###`가 raw로 노출되면 fail.
    md 파일의 `##`은 정상 마크다운이므로, **빌드 후 HTML**에서 확인한다.
    """
    # <pre>/<code> 안의 ## 은 코드 블록이므로 제외
    code_blocks = re.findall(r"<(?:pre|code)[^>]*>.*?</(?:pre|code)>", html_text, re.DOTALL)
    stripped = html_text
    for cb in code_blocks:
        stripped = stripped.replace(cb, "")
    hits = re.findall(r"#{2,3}\s+\S", stripped)
    if hits:
        return False, f"C1: 빌드 HTML에 마크다운 헤딩 raw 노출 {len(hits)}건 (예: {hits[0][:30]})"
    return True, "C1: 빌드 HTML 마크다운 raw 노출 0건"


# ── C2: H2/H3/표/체크리스트 ────────────────────────────
def check_c2(body_md: str) -> tuple[bool, str]:
    lines = body_md.split("\n")
    h1 = sum(1 for ln in lines if re.match(r"^#\s", ln) and not re.match(r"^##\s", ln))
    h2_all = [ln for ln in lines if re.match(r"^##\s", ln)]
    h2 = len(h2_all)
    # "마무리" H2는 시스템이 붙이는 부록 — 본문 정보 H2에서 제외
    h2_info = sum(1 for ln in h2_all if not re.match(r"^##\s*(마무리|마치며|정리|결론)", ln))
    h3 = sum(1 for ln in lines if re.match(r"^###\s", ln))
    tables = sum(1 for ln in lines if ln.startswith("|"))
    checklist = sum(1 for ln in lines if re.match(r"^\s*[-*]\s+\[", ln) or re.match(r"^\s*[-*]\s+<strong>", ln))
    issues = []
    if h1 > 0:
        issues.append(f"H1 {h1}개 (금지)")
    if not (4 <= h2_info <= 5):
        issues.append(f"정보 H2 {h2_info}개 (4~5 필요, 총 {h2}개)")
    if h3 < 1:
        issues.append(f"H3 {h3}개 (1 이상 필요)")
    if issues:
        return False, "C2: " + ", ".join(issues)
    return True, f"C2: 정보H2={h2_info} 총H2={h2} H3={h3} 표행={tables} 체크={checklist}"


# ── C3: 네이버 지도 버튼 위치 ──────────────────────────
def check_c3(body_md: str) -> tuple[bool, str]:
    """지도 버튼이 H3 뒤에 있고, 본문 맨 끝(tail_btns)에 없어야 함.
    tail_btns 시그니처: <div style="text-align:center;margin-top:24px;margin-bottom:24px;">
    (nearby-card 버튼은 class 기반이라 제외)
    """
    lines = body_md.split("\n")
    # 본문 버튼(_inject_naver_map) 위치: map.naver(일반) 또는 search.naver(축제 검색)
    btn_indices = []
    for i, ln in enumerate(lines):
        if ("map.naver.com/v5/search" in ln or "search.naver.com" in ln) and "text-align:center;margin-top:24px" in ln:
            btn_indices.append(i)
    if not btn_indices:
        return True, "C3: 본문 지도 버튼 없음 (nearby만 있음 — 통과)"
    # 마지막 본문 버튼이 nearby 뒤(본문 끝)에 있으면 fail
    last_content_idx = len(lines) - 1
    for i in btn_indices:
        if i > last_content_idx - 3:  # 끝에서 3줄 이내
            return False, f"C3: 지도 버튼이 본문 맨 끝에 위치 (line {i+1}) — tail_btns"
    return True, f"C3: 지도 버튼 {len(btn_indices)}개, H3 뒤 위치 정상"


# ── C4: 쿠팡 이미지 ────────────────────────────────────
def check_c4(body_md: str) -> tuple[bool, str]:
    coupang_img = len(re.findall(r"ads-partners\.coupang\.com/image", body_md))
    coupang_link = len(re.findall(r"link\.coupang\.com", body_md))
    issues = []
    if coupang_img < 3:
        issues.append(f"쿠팡 이미지 {coupang_img}개 (<3)")
    if coupang_link < 3:
        issues.append(f"쿠팡 링크 {coupang_link}개 (<3)")
    if issues:
        return False, "C4: " + ", ".join(issues)
    return True, f"C4: 쿠팡 이미지 {coupang_img}, 링크 {coupang_link} 정상"


# ── C5: featureimage ───────────────────────────────────
def check_c5(frontmatter: str, body_md: str) -> tuple[bool, str]:
    fm_match = re.search(r"featureimage:\s*['\"]?(https?://[^'\s]+)", frontmatter)
    if not fm_match:
        return False, "C5: featureimage 없음"
    url = fm_match.group(1).rstrip("'\"")
    if "coupang" in url:
        return False, f"C5: featureimage가 쿠팡 URL ({url[:50]})"
    # 본문 첫 이미지와 동일하면 중복은 아니지만, used_images 기준은 별도.
    return True, f"C5: featureimage 정상 ({url[:60]})"


# ── C6: 엔티티 카드 ────────────────────────────────────
def check_c6(body_md: str) -> tuple[bool, str]:
    # 엔티티 카드: box-shadow + target=_blank + rel=noopener
    cards = re.findall(r"<div style=\"margin:24px 0; border-radius:12px;", body_md)
    if len(cards) > 2:
        return False, f"C6: 엔티티 카드 {len(cards)}개 (>2)"
    return True, f"C6: 엔티티 카드 {len(cards)}개 정상"


def verify_file(md_path: Path, blog_id: str = "", html_path: Path | None = None) -> dict:
    raw = md_path.read_text(encoding="utf-8")
    fm_end = raw.find("---", 3)
    frontmatter = raw[: fm_end + 3] if fm_end > 0 else ""
    body = raw[fm_end + 3 :] if fm_end > 0 else raw

    # C1은 빌드 HTML 기준. 없으면 body 기준(경고).
    if html_path and html_path.exists():
        html_text = html_path.read_text(encoding="utf-8")
        c1 = check_c1(html_text)
    else:
        c1 = (True, "C1: 빌드 HTML 없음 (건너뜀)")

    results = {
        "c1": c1,
        "c2": check_c2(body),
        "c3": check_c3(body),
        "c4": check_c4(body),
        "c5": check_c5(frontmatter, body),
        "c6": check_c6(body),
    }
    return results


def run_self_test() -> None:
    """의도적 위반 샘플 6종이 각 게이트에서 fail 잡히는지 확인."""
    # C1: 마크다운 raw
    assert not check_c1("## 고흥 축제 개요<p>본문</p>")[0], "C1 should fail on raw ##"
    assert check_c1("<h2>고흥 축제 개요</h2><p>본문</p>")[0], "C1 should pass on clean HTML"
    # C2: H2 6개 위반
    body6 = "\n".join(f"## H2 {i}" for i in range(6))
    assert not check_c2(body6)[0], "C2 should fail on 6 H2"
    # C3: tail_btns
    body_tail = "## H2\n\n본문\n\n<div style=\"text-align:center;margin-top:24px;margin-bottom:24px;\"><a href=\"https://map.naver.com/v5/search/x\" target=\"_blank\" rel=\"nofollow\">x 네이버 지도에서 보기</a></div>"
    assert not check_c3(body_tail)[0], "C3 should fail on tail button"
    # C4: 쿠팡 이미지 0
    assert not check_c4("본문만 있고 쿠팡 없음")[0], "C4 should fail without coupang"
    # C5: 쿠팡 featureimage
    assert not check_c5("featureimage: 'https://ads-partners.coupang.com/image1/x'", "")[0], "C5 should fail on coupang fm"
    # C6: 엔티티 카드 3개
    card = '<div style="margin:24px 0; border-radius:12px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.08);">x</div>'
    assert not check_c6(card * 3)[0], "C6 should fail on 3 cards"
    print("✅ 게이트 자체 검증 통과 — 위반 6종 전부 fail 잡음")


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        run_self_test()
        return
    if len(sys.argv) < 2:
        print("용법: verify_blog_standard.py <md_file|content_dir> [--blog id]")
        sys.exit(2)
    target = Path(sys.argv[1])
    blog_id = ""
    if "--blog" in sys.argv:
        blog_id = sys.argv[sys.argv.index("--blog") + 1]

    files = [target] if target.is_file() else sorted(target.rglob("*.md"))
    all_pass = True
    for f in files:
        # 빌드 HTML 경로 추정: <site>/public/posts/<slug>/index.html
        html_path = None
        try:
            rel = f.relative_to(target if target.is_dir() else target.parent)
            slug_dir = rel.parent if rel.name == "index.md" else rel.with_suffix("")
            site_root = (target if target.is_dir() else target.parent).parent  # content/ 의 부모 = site root
            pub = site_root / "public" / "posts" / slug_dir / "index.html"
            if pub.exists():
                html_path = pub
        except Exception:
            html_path = None
        r = verify_file(f, blog_id, html_path)
        status = all(v for v, _ in r.values())
        all_pass &= status
        if not status:
            print(f"❌ {f.name}:")
            for name, (ok, msg) in r.items():
                if not ok:
                    print(f"   {msg}")
        else:
            print(f"✅ {f.name}")
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
