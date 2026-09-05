#!/usr/bin/env python3
"""RAP desc 오염 백필 — related 블록 조각이 된 description을 본문 첫 문단으로 재생성.
오염 원인: 과거 파이프라인 후처리가 body 하단 related 블록을 desc 위치에 복사(8/1 종료).
재발 방지는 5000 A2 게이트(validators _check_rap)가 담당. 본 스크립트는 라이브 SEO 회복용 1회 실행.
사용법: python3 fix_rap_desc_pollution.py [--apply]  (기본 dry-run)
"""
import glob
import re
import sys

SITES = {
    "rap-hugo": "/Users/twinssn/Projects/RAP/rap-hugo/content/posts",
    "rap2-hugo": "/Users/twinssn/Projects/RAP/rap2-hugo/content/posts",
    "rap3-hugo": "/Users/twinssn/Projects/RAP/rap3-hugo/content/posts",
    "rap4-hugo": "/Users/twinssn/Projects/RAP/rap4-hugo/content/posts",
    "rap5-hugo": "/Users/twinssn/Projects/RAP/rap5-hugo/content/posts",
}

POLLUTION_MARKERS = ("함께 읽으면", "<strong>", "](/posts/")


def is_polluted(desc: str) -> bool:
    return any(m in desc for m in POLLUTION_MARKERS)


def make_desc_from_lead(body: str, limit: int = 120) -> str:
    """본문 첫 문단(리드)에서 120자 내외 desc 생성."""
    # 헤더/광고 마커 제외한 첫 일반 문단
    for para in re.split(r"\n\s*\n", body):
        p = para.strip()
        if not p or p.startswith(("#", "!", "|", "<", "---", "[", "{{")) or "함께 읽으면" in p:
            continue
        # 인라인 마크다운 제거
        p = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", p)
        p = re.sub(r"[*_`<strong>]</strong>|[*_`]", "", p)
        p = p.replace("<strong>", "").replace("</strong>", "")
        p = re.sub(r"\s+", " ", p).strip()
        if len(p) >= 40:  # 최소 길이
            if len(p) > limit:
                p = p[:limit].rsplit(" ", 1)[0] + "…"
            return p
    return ""


def main() -> int:
    apply_mode = "--apply" in sys.argv
    fixed, skipped_nolead, total_polluted = 0, 0, 0
    for site, d in SITES.items():
        for md in sorted(glob.glob(f"{d}/*/index.md")):
            src = open(md).read()
            parts = src.split("---\n", 2)
            if len(parts) < 3:
                continue
            fm, body = parts[1], parts[2]
            dm = re.search(r"description: (.*?)(?=\n(?:[ \t]+\S)|\n[a-zA-Z_]+:|\Z)", fm, re.DOTALL)
            if not dm or not is_polluted(dm.group(1)):
                continue
            # YAML folded/list 연속 라인(들여쓰기 후속)도 desc 교체 범위에 포함됨 — 위 lookahead가 처리
            total_polluted += 1
            new_desc = make_desc_from_lead(body)
            if not new_desc:
                skipped_nolead += 1
                continue
            if apply_mode:
                new_fm = fm[:dm.start(1)] + new_desc + fm[dm.end(1):]
                open(md, "w").write("---\n" + new_fm + "---\n" + body)
            fixed += 1
            if total_polluted <= 3 or not apply_mode:
                print(f"{'FIX' if apply_mode else 'DRY'} {md.split('/posts/')[1][:50]}: {new_desc[:60]}")
    print(f"\n오염 {total_polluted}건 중 교체 {'완료' if apply_mode else '예정'} {fixed}건, 리드 없음 skip {skipped_nolead}건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
