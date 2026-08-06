"""
scripts/render_inc_cl_fix.py

INC-CL-01~04: 기존 발행 74건 포스트의 크로스링크 카드/헤더 블록을
현재 linker(shared/cuap_entity_linker.build_cross_sell_card /
build_funnel_header, 커밋 7e2bd2312 CROSS_GRAPH 준수)로 재생성.

사용법:
    python scripts/render_inc_cl_fix.py              # dry-run (기본)
    python scripts/render_inc_cl_fix.py --execute    # 실제 적용

주의:
- 4블로그(git tag pre-inc-cl-<blog>) 백업 전제.
- 스케줄러 정지 상태 전제. 라이브 발행 중일 때 실행 금지.
- 적용 전 dry-run 출력 건수가 사전 카운트(74)와 일치해야 실행.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

# 이 스크립트는 프로젝트 루트에서 실행되는 것을 가정하지만,
# 임의의 venv에서 실행될 수 있으므로 프로젝트 루트를 명시적으로 넣는다.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# 대상 블로그 (4단계 프로토콜 대상)
TARGET_BLOGS = ("camping-hugo", "health-hugo", "laptop-hugo", "pet-hugo")

# 블로그 루트 (config/blogs.d/cuap.yaml에서 추출)
BLOG_ROOT = {
    "camping-hugo": Path("/Users/twinssn/Projects/cuap/camping-hugo"),
    "health-hugo": Path("/Users/twinssn/Projects/cuap/health-hugo"),
    "laptop-hugo": Path("/Users/twinssn/Projects/cuap/laptop-hugo"),
    "pet-hugo": Path("/Users/twinssn/Projects/cuap/pet-hugo"),
}

# CUAP 도메인 → 블로그 ID (ops_dashboard/checks/crosslink.py와 동일)
CUAP_DOMAIN_TO_BLOG_ID = {
    "appliance.informationhot.kr": "appliance-hugo",
    "baby.informationhot.kr": "baby-hugo",
    "beauty.informationhot.kr": "beauty-hugo",
    "camping.informationhot.kr": "camping-hugo",
    "fitness.informationhot.kr": "fitness-hugo",
    "health.informationhot.kr": "health-hugo",
    "interior.informationhot.kr": "interior-hugo",
    "kitchen.informationhot.kr": "kitchen-hugo",
    "laptop.informationhot.kr": "laptop-hugo",
    "pet.informationhot.kr": "pet-hugo",
}

# shared/cuap_entity_linker.py CROSS_GRAPH (동기화 대상: 코드 기준)
CROSS_GRAPH = {
    "beauty-hugo": {
        "primary": ["appliance-hugo", "camping-hugo"],
        "secondary": ["interior-hugo", "health-hugo"],
        "use_cases": ["kitchen-hugo", "baby-hugo"],
    },
    "appliance-hugo": {
        "primary": ["kitchen-hugo", "interior-hugo"],
        "secondary": ["laptop-hugo", "camping-hugo"],
        "use_cases": ["baby-hugo", "pet-hugo"],
    },
    "kitchen-hugo": {
        "primary": ["appliance-hugo", "interior-hugo"],
        "secondary": ["baby-hugo", "health-hugo"],
        "use_cases": ["pet-hugo", "camping-hugo"],
    },
    "interior-hugo": {
        "primary": ["appliance-hugo", "kitchen-hugo"],
        "secondary": ["camping-hugo", "baby-hugo"],
        "use_cases": ["fitness-hugo", "beauty-hugo"],
    },
    "laptop-hugo": {
        "primary": ["appliance-hugo", "fitness-hugo"],
        "secondary": ["camping-hugo", "health-hugo"],
        "use_cases": ["pet-hugo", "baby-hugo"],
    },
    "fitness-hugo": {
        "primary": ["health-hugo", "camping-hugo"],
        "secondary": ["baby-hugo", "interior-hugo"],
        "use_cases": ["beauty-hugo", "kitchen-hugo"],
    },
    "health-hugo": {
        "primary": ["fitness-hugo", "kitchen-hugo"],
        "secondary": ["baby-hugo", "beauty-hugo"],
        "use_cases": ["pet-hugo", "interior-hugo"],
    },
    "baby-hugo": {
        "primary": ["kitchen-hugo", "health-hugo"],
        "secondary": ["interior-hugo", "pet-hugo"],
        "use_cases": ["beauty-hugo", "appliance-hugo"],
    },
    "pet-hugo": {
        "primary": ["baby-hugo", "kitchen-hugo"],
        "secondary": ["interior-hugo", "health-hugo"],
        "use_cases": ["camping-hugo", "appliance-hugo"],
    },
    "camping-hugo": {
        "primary": ["appliance-hugo", "fitness-hugo"],
        "secondary": ["interior-hugo", "pet-hugo"],
        "use_cases": ["kitchen-hugo", "laptop-hugo"],
    },
}


def allowed_targets(blog_id: str) -> set[str]:
    """CROSS_GRAPH[blog_id]의 primary/secondary/use_cases 합집합."""
    graph = CROSS_GRAPH.get(blog_id, {})
    out: set[str] = set()
    for cat in ("primary", "secondary", "use_cases"):
        out.update(graph.get(cat, []))
    return out


def read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.warning("read 실패: %s :: %s", path, e)
        return ""


def write_file(path: Path, text: str, backup_ext: str = ".bak.inc-cl") -> None:
    if path.exists():
        bak = Path(str(path) + backup_ext)
        if not bak.exists():
            path.write_text(text, encoding="utf-8", errors="replace")
            path.rename(bak)
            logger.debug("백업 생성: %s", bak)
    path.write_text(text, encoding="utf-8", errors="replace")


def normalize_keyword_token(s: str) -> str:
    """포스트와 키워드 비교용 정규화: NFC + 전각→반각 + 공백 trimmed."""
    t = unicodedata.normalize("NFC", s)
    # 전각 ASCII → 반각
    t = t.translate(str.maketrans({
        "\u00a0": " ",
        "\uff01": "!", "\uff08": "(", "\uff09": ")",
        "\uff0c": ",", "\uff0e": ".", "\uff1a": ":",
        "\uff1b": ";", "\uff1f": "?", "\uff20": "@",
    }))
    return t.strip()


_HREF_RE = re.compile(r'<a\s+[^>]*href="(https://[^"]+)"', re.IGNORECASE)


def _extract_block_links(html_block: str) -> list[tuple[str, str]]:
    """블록 내 (url, target_blog_id or '') 목록."""
    out = []
    for m in _HREF_RE.finditer(html_block):
        url = m.group(1)
        parsed = urlparse(url)
        domain = parsed.netloc
        target = CUAP_DOMAIN_TO_BLOG_ID.get(domain, "")
        out.append((url, target))
    return out


def _block_violation_targets(html_block: str, allowed: set[str]) -> list[str]:
    """블록 내 허용집합 밖 대상 블로그 ID 목록(중복 제거)."""
    targets: list[str] = []
    seen: set[str] = set()
    for _, target in _extract_block_links(html_block):
        if target and target not in allowed and target not in seen:
            seen.add(target)
            targets.append(target)
    return targets


# 블록 경계: 파이프라인이 본문 상단과 하단에 부착하는 두 블록
FUNNEL_BLOCK_RE = re.compile(
    r"\n*<div class=\"funnel-header\">.*?</div>\s*",
    re.DOTALL,
)
CROSS_SELL_BLOCK_RE = re.compile(
    r"\n*<div class=\"cross-sell-card\">.*?</div>\s*",
    re.DOTALL,
)


def _find_blocks(text: str) -> tuple[str | None, str | None]:
    """본문 상단과 하단의 funnel-header/cross-sell-card 블록을 찾는다.

    반환: (funnel_block_or_None, cross_sell_block_or_None)
    """
    funnel = None
    cross = None

    # funnel-header는 통상 본문 최상단 근처에 있음
    m = FUNNEL_BLOCK_RE.search(text)
    if m:
        funnel = m.group(0)
    # cross-sell-card는 통상 본문 하단에 있음
    m = CROSS_SELL_BLOCK_RE.search(text)
    if m:
        cross = m.group(0)

    return funnel, cross


def _strip_blocks(text: str) -> str:
    """두 블록을 깔끔하게 제거(블록 주변 여백 포함)."""
    t = FUNNEL_BLOCK_RE.sub("", text)
    t = CROSS_SELL_BLOCK_RE.sub("", t)
    # 남은 이중 개행 정리
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip() + "\n"


_HAS_BAD_BLOCK = re.compile(
    r"<div class=\"(?:funnel-header|cross-sell-card)\">",
    re.IGNORECASE,
)


def _post_has_bad_block(text: str, allowed: set[str]) -> bool:
    """포스트 본문에 허용집합 밖 링크가 포함된 카드/헤더 블록이 있는지."""
    if not _HAS_BAD_BLOCK.search(text):
        return False
    funnel, cross = _find_blocks(text)
    if funnel and _block_violation_targets(funnel, allowed):
        return True
    if cross and _block_violation_targets(cross, allowed):
        return True
    return False


def collect_targets(dry_run: bool = True) -> list[dict]:
    """재렌더 대상 '블록' 목록 수집.

    M03은 위반 링크 블록 수로 카운트하므로, 대상 단위도 포스트가 아니라
    위반 링크가 포함된 카드/헤더 블록 하나하나로 잡아야 한다.
    한 포스트에 funnel-header + cross-sell-card가 모두 위반이면 2건으로 센다.

    반환: [ {blog_id, slug, path, block_type, block_html} ]
    """
    targets: list[dict] = []
    for blog_id in TARGET_BLOGS:
        root = BLOG_ROOT[blog_id]
        posts_dir = root / "content" / "posts"
        if not posts_dir.is_dir():
            logger.warning("[%s] posts_dir 없음: %s", blog_id, posts_dir)
            continue
        allowed = allowed_targets(blog_id)
        for pd in sorted(posts_dir.iterdir()):
            if not pd.is_dir():
                continue
            index_md = pd / "index.md"
            if not index_md.exists():
                continue
            text = read_file(index_md)
            if not text.strip():
                continue

            # funnel-header 블록들 (본문 상단 근처뿐 아니라 여러 개일 수 있음)
            for m in FUNNEL_BLOCK_RE.finditer(text):
                block = m.group(0)
                if _block_violation_targets(block, allowed):
                    targets.append({
                        "blog_id": blog_id,
                        "slug": pd.name,
                        "path": index_md,
                        "block_type": "funnel",
                        "block_html": block,
                    })

            # cross-sell-card 블록들
            for m in CROSS_SELL_BLOCK_RE.finditer(text):
                block = m.group(0)
                if _block_violation_targets(block, allowed):
                    targets.append({
                        "blog_id": blog_id,
                        "slug": pd.name,
                        "path": index_md,
                        "block_type": "cross_sell",
                        "block_html": block,
                    })
    return targets


def render_new_blocks(blog_id: str):
    """현재 linker로 신규 블록 2개 획득.

    실패 시 None 반환 (건너뛰기, 로그).
    """
    try:
        from shared.cuap_entity_linker import build_cross_sell_card, build_funnel_header
    except Exception as e:
        logger.error("shared.cuap_entity_linker import 실패: %s", e)
        sys.exit(2)

    funnel = build_funnel_header(blog_id)
    cross = build_cross_sell_card(blog_id, max_items=4)
    return funnel, cross


def execute(targets: list[dict]) -> dict:
    """실제 재렌더 적용 (블록 단위).

    동일 포스트가 여러 번 등장할 수 있으므로, 포스트별 누적 적용 횟수를
    추적해 마지막 적용 후 최종 write 한다(post 단위 1회 write로 I/O 최소화).
    반환: {applied_blocks: int, posts_touched: int, skipped_render_fail: int}
    """
    # blog_id → render 결과 캐시 (동일 블로그 포스트 여러 개일 때 재사용)
    render_cache: dict[str, tuple[str | None, str | None]] = {}

    def get_render(blog_id: str):
        if blog_id not in render_cache:
            render_cache[blog_id] = render_new_blocks(blog_id)
        return render_cache[blog_id]

    # post 단위 누적 적용 버퍼
    buf: dict[Path, dict] = {}

    for t in targets:
        blog_id = t["blog_id"]
        path = t["path"]
        if not path.exists():
            continue

        funnel_new, cross_new = get_render(blog_id)
        if funnel_new is None or cross_new is None:
            logger.warning("[%s] %s 재렌더 생성 실패 → 건너뜀", blog_id, t["slug"])
            continue

        entry = buf.setdefault(path, {
            "text": read_file(path),
            "blog_id": blog_id,
            "slug": t["slug"],
        })
        # 이미 읽은 상태면 다시 읽지 않음 (버퍼가 최신임을 전제)
        text = entry["text"]

        stripped = _strip_blocks(text)
        new_text = stripped
        if funnel_new:
            new_text = funnel_new + "\n\n" + new_text
        if cross_new:
            new_text = new_text + "\n\n" + cross_new
        new_text = new_text.rstrip() + "\n"
        entry["text"] = new_text

    stats = {"applied_blocks": len(targets), "posts_touched": 0, "skipped_render_fail": 0}
    for path, entry in buf.items():
        text = entry["text"]
        if text == read_file(path):
            logger.warning("[%s] %s 변경 없음(이상) → 건너뜀", entry["blog_id"], entry["slug"])
            continue
        write_file(path, text)
        stats["posts_touched"] += 1
        logger.info("[%s] %s 재렌더 완료 (백업: %s.bak.inc-cl)",
                    entry["blog_id"], entry["slug"], path.name)

    return stats


def summarize(targets: list[dict]) -> dict:
    """dry-run 요약 (블록 단위)."""
    by_blog: dict[str, dict] = {b: {"count": 0, "funnel": 0, "cross": 0} for b in TARGET_BLOGS}
    for t in targets:
        b = t["blog_id"]
        by_blog[b]["count"] += 1
        if t["block_type"] == "funnel":
            by_blog[b]["funnel"] += 1
        elif t["block_type"] == "cross_sell":
            by_blog[b]["cross"] += 1
    return by_blog


EXPECTED_TOTAL = 74


def main():
    ap = argparse.ArgumentParser(description="INC-CL-01~04 재렌더 도구 (dry-run 기본)")
    ap.add_argument("--execute", action="store_true", help="실제 적용 (dry-run 생략)")
    args = ap.parse_args()

    logger.info("타겟 블로그: %s", ", ".join(TARGET_BLOGS))
    targets = collect_targets(dry_run=not args.execute)

    summary = summarize(targets)
    print("\n===== 재렌더 대상 요약 (dry-run) =====")
    total = 0
    for b in TARGET_BLOGS:
        s = summary[b]
        total += s["count"]
        print(f"[{b}] 대상={s['count']}, funnel_violation={s['funnel']}, cross_violation={s['cross']}")
    print(f"===== 총합: {total}건 (기대: {EXPECTED_TOTAL}건) =====\n")

    if total != EXPECTED_TOTAL:
        logger.error("사전 카운트 불일치: 실제=%d 기대=%d → 중단 (실행 금지)", total, EXPECTED_TOTAL)
        sys.exit(3)

    if not args.execute:
        logger.info("dry-run 일치: %d건 == 기대 %d건. 실행하려면 --execute", total, EXPECTED_TOTAL)
        sys.exit(0)

    logger.info("--- 실제 적용 시작 (총 %d건/블록) ---", total)
    stats = execute(targets)
    logger.info("--- 적용 결과: applied_blocks=%d, posts_touched=%d, skipped_render_fail=%d ---",
                stats["applied_blocks"], stats["posts_touched"], stats["skipped_render_fail"])

    if stats["skipped_render_fail"] > 0:
        logger.warning("재렌더 생성 실패 %d건 존재 → 추후 수동 확인 필요", stats["skipped_render_fail"])

    # 최종 카운트 출력 (블록 단위)
    after = collect_targets(dry_run=True)
    after_summary = summarize(after)
    after_total = sum(s["count"] for s in after_summary.values())
    print("\n===== 재렌더 후 잔여 위반 (검증용, 블록 단위) =====")
    for b in TARGET_BLOGS:
        s = after_summary[b]
        print(f"[{b}] 잔여={s['count']} (funnel={s['funnel']}, cross={s['cross']})")
    print(f"===== 재렌더 후 총합: {after_total}건 =====\n")

    if after_total != 0:
        logger.error("재렌더 후 잔여 위반 %d건 존재 → 완전한 해결을 위해 추가 조치 필요", after_total)
        sys.exit(4)

    logger.info("재렌더 완료: 사전 74건 → 사후 0건 (rewrite 성공)")
    sys.exit(0)


if __name__ == "__main__":
    main()
