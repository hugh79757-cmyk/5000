"""키워드 풀 유지보수 스크립트 — 자동 검증 + 정리 + 확장

기능:
  --audit          : 모든 블로그 키워드의 평균 relevance 검사 후 보고
  --purge          : relevance가 threshold 미만인 키워드를 KEYWORD_MAP에서 제거 (--auto 없이 미리보기)
  --purge --auto   : 제거를 실제로 적용 (삭제 전 미리보기 먼저 권장)
  --expand         : allowed 키워드 기반으로 새로운 키워드 후보 생성
  --report         : 간소화된 리포트 출력 (기본값)

사용 예:
  python3 scripts/maintain_keyword_pool.py --audit
  python3 scripts/maintain_keyword_pool.py --purge --auto
  python3 scripts/maintain_keyword_pool.py --expand
"""
import sys, os, re, sqlite3, random, argparse
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipelines.curation.keywords import get_keywords
from pipelines.curation.collector import get_products
from shared.relevance_scorer import score_products, get_threshold
from dotenv import load_dotenv
load_dotenv(os.path.expanduser("~/.env.common"))
load_dotenv(os.path.expanduser("~/Projects/5000/.env"))

PYPROJ = Path(__file__).resolve().parent.parent
KEYWORDS_PATH = PYPROJ / "pipelines/curation/keywords.py"
DB_PATH = PYPROJ / "data/curation.db"

BLOGS = sorted([
    "appliance-hugo", "baby-hugo", "beauty-hugo", "camping-hugo",
    "fitness-hugo", "health-hugo", "interior-hugo", "kitchen-hugo",
    "laptop-hugo", "pet-hugo",
])

# Allowed list cache (loaded once from pipeline)
ALLOWED_CACHE: dict[str, list[str]] = {}


def _load_pipeline_filters():
    """pipeline.py에서 CATEGORY_FILTERS의 allowed 목록을 로드"""
    if ALLOWED_CACHE:
        return ALLOWED_CACHE
    # Parse pipeline.py for CATEGORY_FILTERS
    path = PYPROJ / "pipelines/curation/pipeline.py"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    import ast
    # Extract CATEGORY_FILTERS assignment by finding the variable name
    start = content.find("CATEGORY_FILTERS = {")
    if start == -1:
        return {}
    end = content.find("\n\n", start)
    if end == -1:
        end = content.find("}\n\n", start) + 2
    # Parse the dict literal safely
    try:
        filters = ast.literal_eval(content[start:end].split("=", 1)[1].strip())
    except Exception as e:
        print(f"  [WARN] CATEGORY_FILTERS 파싱 실패: {e}")
        return {}
    for blog_id, cfg in filters.items():
        if "allowed" in cfg:
            ALLOWED_CACHE[blog_id] = cfg["allowed"]
    return ALLOWED_CACHE


def get_allowed(blog_id):
    return _load_pipeline_filters().get(blog_id, [])


def audit_keywords(blog_id, threshold=None):
    """주어진 블로그의 모든 키워드별 평균 relevance 계산"""
    keywords = get_keywords(blog_id)
    if not keywords:
        return []
    allowed = get_allowed(blog_id)
    if not allowed:
        return []

    th = threshold or get_threshold(blog_id)
    results = []

    for kw in keywords:
        products = get_products(kw, limit=10)
        if not products:
            results.append((kw, 0.0, "NO_PRODUCTS"))
            continue
        scores = score_products(products, blog_id)
        avg = scores["avg"]
        if avg < th:
            results.append((kw, avg, "BELOW_THRESHOLD"))
        else:
            results.append((kw, avg, "OK"))

    return results


def write_keyword_map(keyword_map):
    """keywords.py에 KEYWORD_MAP 쓰기"""
    with open(KEYWORDS_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    start = content.find("KEYWORD_MAP = {")
    end = content.find("\n}\n", start) + 2

    new_map_lines = ["KEYWORD_MAP = {"]
    for blog, kws in keyword_map.items():
        new_map_lines.append(f'    "{blog}": [')
        line_parts = []
        for kw in kws:
            line_parts.append(f'"{kw}"')
            if len(line_parts) >= 10:
                new_map_lines.append("        " + ", ".join(line_parts) + ",")
                line_parts = []
        if line_parts:
            new_map_lines.append("        " + ", ".join(line_parts) + ",")
        new_map_lines.append("    ],")
    new_map_lines.append("}\n")

    new_content = content[:start] + "\n".join(new_map_lines) + content[end:]
    with open(KEYWORDS_PATH, "w", encoding="utf-8") as f:
        f.write(new_content)


def cmd_audit(args):
    """--audit: 모든 블로그의 키워드 relevance 보고"""
    total_below = 0
    total_keywords = 0
    for blog_id in BLOGS:
        results = audit_keywords(blog_id)
        allowed = get_allowed(blog_id)
        keywords = get_keywords(blog_id)
        total_keywords += len(keywords)

        below = [r for r in results if r[2] != "OK"]
        total_below += len(below)

        print(f"\n{'='*50}")
        print(f"  {blog_id} ({len(keywords)} 키워드)")
        print(f"{'='*50}")
        if not allowed:
            print(f"  [WARN] allowed 목록 없음 — 건너뜀")
            continue
        if not below:
            print(f"  ✅ 모든 키워드 OK (threshold={get_threshold(blog_id)})")
        else:
            for kw, avg, status in below:
                print(f"  ⚠️  {kw:<25} avg={avg:.2f}  {status}")
            print(f"  → {len(below)}/{len(keywords)} 키워드가 threshold({get_threshold(blog_id)}) 미만")

    print(f"\n{'='*50}")
    print(f"종합: {total_below}/{total_keywords} 키워드가 threshold 미만 "
          f"({total_below/max(total_keywords,1)*100:.1f}%)")


def cmd_purge(args):
    """--purge: threshold 미만 키워드를 KEYWORD_MAP에서 제거"""
    from pipelines.curation.keywords import KEYWORD_MAP
    import copy

    updated = copy.deepcopy(KEYWORD_MAP)
    total_removed = 0

    for blog_id in BLOGS:
        if blog_id not in updated:
            continue
        results = audit_keywords(blog_id)
        to_remove = [r[0] for r in results if r[2] != "OK"]

        if not to_remove:
            continue

        before = len(updated[blog_id])
        updated[blog_id] = [k for k in updated[blog_id] if k not in to_remove]
        removed = before - len(updated[blog_id])
        total_removed += removed

        if removed:
            print(f"  {blog_id}: {removed}개 키워드 제거 ({before}→{len(updated[blog_id])})")
            for kw in to_remove[:5]:
                print(f"    - {kw}")
            if len(to_remove) > 5:
                print(f"    ... 외 {len(to_remove)-5}개")

    if args.auto:
        write_keyword_map(updated)
        print(f"\n✅ KEYWORD_MAP 업데이트 완료: 총 {total_removed}개 키워드 제거")
    else:
        print(f"\n⚠️  --auto 없음: 실제 적용 안 됨. 확인 후 --auto로 재실행하세요.")
        print(f"  제거 예정: 총 {total_removed}개 키워드")


def _generate_expansions(blog_id, base_keywords, max_expansions=30):
    """allowed 키워드를 기반으로 연관 키워드 확장 (규칙 기반)"""
    allowed = get_allowed(blog_id)
    if not allowed:
        return []

    expansions = []
    targets = allowed[:5]  # 상위 5개 allowed로 한정

    for target in targets:
        # 패턴: {target} 추천, {target} 가격, {target} 순위 등
        if len(target) >= 2:
            expansions.append(f"{target} 추천")
            expansions.append(f"{target} 가격")
            expansions.append(f"{target} 순위")
            expansions.append(f"{target} 비교")
            expansions.append(f"{target} 후기")
            expansions.append(f"{target} 할인")
            expansions.append(f"{target} 브랜드")

    # 중복 제거 및 base_keywords에 없는 것만
    existing = set(base_keywords)
    expansions = [e for e in expansions if e not in existing][:max_expansions]
    return expansions


def cmd_expand(args):
    """--expand: allowed 기반 키워드 확장 후 KEYWORD_MAP에 추가"""
    from pipelines.curation.keywords import KEYWORD_MAP
    import copy

    updated = copy.deepcopy(KEYWORD_MAP)
    total_added = 0

    for blog_id in BLOGS:
        if blog_id not in updated:
            continue
        allowed = get_allowed(blog_id)
        if not allowed:
            continue

        new_keywords = _generate_expansions(blog_id, updated[blog_id])
        if not new_keywords:
            continue

        before = len(updated[blog_id])
        updated[blog_id] = list(dict.fromkeys(updated[blog_id] + new_keywords))  # 중복 제거 + 순서 유지
        added = len(updated[blog_id]) - before
        total_added += added

        if added:
            print(f"  {blog_id}: {added}개 키워드 추가 ({before}→{len(updated[blog_id])})")
            for kw in new_keywords[:3]:
                print(f"    + {kw}")

    if total_added > 0:
        write_keyword_map(updated)
        print(f"\n✅ KEYWORD_MAP 업데이트 완료: 총 {total_added}개 키워드 추가")
    else:
        print("추가할 새 키워드 없음")


def cmd_report(args):
    """--report: 간소화된 상태 리포트"""
    print(f"\n{'='*50}")
    print("CUAP 키워드 풀 상태 리포트")
    print(f"{'='*50}")

    for blog_id in BLOGS:
        results = audit_keywords(blog_id)
        keywords = get_keywords(blog_id)
        below = [r for r in results if r[2] != "OK"]
        no_prod = [r for r in results if r[2] == "NO_PRODUCTS"]
        status = "✅" if len(below) == 0 else f"⚠️  {len(below)}개"
        print(f"  {blog_id:<18} {len(keywords):>3} 키워드  {status}")
        if no_prod and len(no_prod) <= 3:
            for kw, _, _ in no_prod:
                print(f"    NO_PRODUCTS: {kw}")

    # 격리 상태
    try:
        from pipelines.curation.keyword_health import KeywordHealthStore
        hs = KeywordHealthStore()
        quarantined = hs.get_all_quarantined()
        if quarantined:
            print(f"\n  🔒 격리됨: {len(quarantined)}개 키워드")
            for blog_id, kws in quarantined.items():
                print(f"    {blog_id}: {len(kws)}개")
                for kw, info in list(kws.items())[:3]:
                    print(f"      - {kw} (남은 시간: {info.get('remaining_hours', '?')}h)")
        else:
            print(f"\n  ✅ 격리된 키워드 없음")
    except Exception as e:
        print(f"\n  [WARN] 격리 확인 실패: {e}")


def main():
    parser = argparse.ArgumentParser(description="키워드 풀 유지보수 도구")
    parser.add_argument("--audit", action="store_true", help="모든 블로그 키워드 relevance 검사")
    parser.add_argument("--purge", action="store_true", help="threshold 미만 키워드 제거 (--auto 없이 미리보기)")
    parser.add_argument("--expand", action="store_true", help="allowed 기반 키워드 확장")
    parser.add_argument("--report", action="store_true", help="상태 리포트 (기본값)")
    parser.add_argument("--auto", action="store_true", help="실제 적용 (삭제/추가)")
    parser.add_argument("--threshold", type=float, default=None, help="relevance threshold (기본값: 블로그별 설정)")

    args = parser.parse_args()

    if args.audit:
        cmd_audit(args)
    elif args.purge:
        cmd_purge(args)
    elif args.expand:
        cmd_expand(args)
    else:
        cmd_report(args)


if __name__ == "__main__":
    main()
