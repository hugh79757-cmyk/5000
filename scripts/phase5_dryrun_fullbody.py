#!/usr/bin/env python3
"""
Phase5 dry-run 재생성 + 전체본문 스캔
13개 블로그 × 2건 → 본문 저장 → 전체본문 스캔 → pass/fail 판정
출력: JSON (data/phase5_dryrun/result.json) + 터미널 리포트
"""
import sys
import os
import re
import json
import time
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv("/Users/twinssn/Projects/5000/.env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── 블로그 정의 (phase5_verify.py와 동일) ────────────────────
CAP_BLOGS = [
    {"id": "compare-hugo", "pipeline": "car", "post_type": "ranking_compare",
     "prompt_file": "compare/ranking_compare.md"},
    {"id": "deal-hugo", "pipeline": "car", "post_type": "promo_deal",
     "prompt_file": "deal/promo_deal.md"},
    {"id": "ev-hugo", "pipeline": "car", "post_type": "ev_analysis",
     "prompt_file": "ev/ev_analysis.md"},
    {"id": "guide-hugo", "pipeline": "car", "post_type": "beginner_guide",
     "prompt_file": "guide/beginner_guide.md"},
    {"id": "hotissue-hugo", "pipeline": "car", "post_type": "resale_compare",
     "prompt_file": "hotissue/resale_compare.md"},
    {"id": "tco-hugo", "pipeline": "car", "post_type": "tco_analysis",
     "prompt_file": "tco/tco_analysis.md"},
    {"id": "rank-hugo", "pipeline": "car", "post_type": "top5_rank",
     "prompt_file": "rank/top5_rank.md"},
    {"id": "pick-hugo", "pipeline": "car", "post_type": "persona_pick",
     "prompt_file": "pick/persona_pick.md"},
]

TAP_BLOGS = [
    {"id": "travel-hugo", "pipeline": "travel", "source_type": "camping",
     "prompt_id": "tour1_camping"},
    {"id": "travel1-hugo", "pipeline": "travel", "source_type": "festival",
     "prompt_id": "travel1_festival"},
    {"id": "travel2-hugo", "pipeline": "travel", "source_type": "heritage",
     "prompt_id": "travel2_heritage"},
    {"id": "travel3-hugo", "pipeline": "travel", "source_type": "food",
     "prompt_id": "tour2_food"},
    {"id": "travel4-hugo", "pipeline": "travel", "source_type": "course",
     "prompt_id": "tour3_course"},
]

ALL_BLOGS = CAP_BLOGS + TAP_BLOGS

# ── 전체본문 스캔 시그니처 ──────────────────────────────────
SCAN_PATTERNS = {
    "ko_thinking": re.compile(
        r"사용자가 제공한 데이터|절대\s+.*\s+말라고 했습니다|초안:|이제\s+.*\s+작성|H2-\d|문장 수:|(?:^|\n)\s*주의:|(?:^|\n)\s*규칙|~해야 합니다\."
    ),
    "en_thinking": re.compile(
        r"(?:^|\n)\s*(?:The user has provided|Let me re-?[Rr]ead|Wait,|we need to|Let me|I should|Actually,|First,)\b"
    ),
    "cjk_leak_keywords": re.compile(
        r"(?:我们|需要|根据|注意|规则|禁止|应当|必须|以上|以下|关于|分析|考虑|但是|所以|因为|如果|虽然|并且|或者|因此|然而|目前|现在|对于|通过|使用|包括|属于|作为|已经)"
    ),
    "prompt_instruction_leak": re.compile(
        r"(?:^|\n)\s*(?:bold-list로 정리|테이블 금지|1~2문장으로 소개|H2 없이|최소 \d+문장|~를 명시해야|금지 표현|체크포인트|구조:|도입부 \()"
    ),
    "forbidden_grammar_break": re.compile(
        r"확인해 보시기 필요합니다|보시기 필요합니다"
    ),
    "forbidden_word_reverse": re.compile(
        r"바랍니다|되시길|있으시|마무리하며|마치며|정리하며|알아보겠습니다|과연|놀랍게도|충격적으로"
    ),
    "thinking_tag_remain": re.compile(
        r"<think(?:ing)?>|</think(?:ing)?>|<reasoning>|</reasoning>|<chain[- ]of[- ]thought>"
    ),
    "cjk_line_leak": re.compile(
        r"(?:^[^\n]*[\u4e00-\u9fff]{3,}[^\n]*$)"
    ),
}


def scan_full_body(title, body):
    """전체본문 스캔 — 500자 제한 없음"""
    findings = []
    full_text = (title or "") + "\n" + (body or "")

    for pname, regex in SCAN_PATTERNS.items():
        if pname == "cjk_line_leak":
            for line in (body or "").split("\n"):
                if regex.search(line):
                    findings.append({"pattern": pname, "context": line.strip()[:100]})
                    break
        elif pname in ("thinking_tag_remain", "ko_thinking"):
            # 전체 본문 검사
            m = regex.search(full_text)
            if m:
                findings.append({"pattern": pname, "context": m.group()[:100]})
        else:
            # 기타 패턴도 전체 본문 검사 (500자 제한 없음)
            m = regex.search(full_text)
            if m:
                findings.append({"pattern": pname, "context": m.group()[:100]})

    return findings


def build_car_test_data(blog_cfg):
    """CAP 블로그용 테스트 데이터"""
    post_type = blog_cfg["post_type"]
    if post_type in ("top5_rank", "persona_pick"):
        return {
            "type": post_type,
            "rank_type": "resale",
            "persona_type": "commuter",
            "site_id": blog_cfg["id"],
            "model": "현대 아반떼",
            "brand": "현대",
            "year": "2025",
            "trim": "스마트",
            "base_price": "2,520만원",
        }
    elif post_type == "ev_analysis":
        return {
            "type": post_type,
            "model": "현대 아이오닉6",
            "brand": "현대",
            "year": "2025",
            "fuel_type": "전기",
            "ev_range_km": "524km",
            "ev_efficiency": "6.2km/kWh",
            "battery_capacity_kwh": "77.4kWh",
            "ev_charge_monthly_home": "약 5만원",
            "ev_charge_monthly_fast": "약 12만원",
            "site_id": blog_cfg["id"],
        }
    else:
        return {
            "type": post_type,
            "model": "현대 그랜저",
            "brand": "현대",
            "year": "2025",
            "trim": "프리미엄",
            "base_price": "3,860만원",
            "engine": "2.5 가솔린",
            "fuel_type": "가솔린",
            "fuel_efficiency": "12.3km/L",
            "displacement": "2497cc",
            "seats": "5인승",
            "discount": "200만원",
            "discount_conditions": "출고 시",
            "annual_km": "15,000km",
            "tax_annual": "약 52만원",
            "insurance_estimate": "약 100만원",
            "annual_fuel_cost": "약 183만원",
            "resale_1yr": "78%",
            "resale_2yr": "65%",
            "resale_3yr": "54%",
            "resale_rate_percent": "54%",
            "three_year_depreciation": "약 1,200만원",
            "three_year_maintenance": "약 300만원",
            "three_year_total_cost": "약 1,683만원",
            "final_price": "약 3,660만원",
            "site_id": blog_cfg["id"],
        }


def build_travel_test_data(blog_cfg):
    """TAP 블로그용 테스트 데이터"""
    source_type = blog_cfg["source_type"]
    test_items = {
        "camping": {
            "title": "충남 태안 바다뷰 캠핑장 추천 5곳",
            "content": "태안 해안국립공원 근처 캠핑장들을 소개합니다.",
            "addr": "충남 태안군",
            "sigungu": "태안군",
            "region": "충남",
            "type": "camping",
        },
        "festival": {
            "title": "여름 축제 추천 — 보령 머드축제 완벽 가이드",
            "content": "보령 머드축제의 핵심 프로그램과 방문 팁을 정리했습니다.",
            "addr": "충남 보령시",
            "sigungu": "보령시",
            "region": "충남",
            "type": "festival",
        },
        "heritage": {
            "title": "경주 역사유적 탐방 — 신라 천년의 숨결",
            "content": "경주의 핵심 역사유산과 탐방 코스를 안내합니다.",
            "addr": "경북 경주시",
            "sigungu": "경주시",
            "region": "경북",
            "type": "heritage",
        },
        "food": {
            "title": "전주 한옥마을 맛집 베스트 7",
            "content": "전주 한옥마을 주변 인기 맛집을 소개합니다.",
            "addr": "전북 전주시",
            "sigungu": "전주시",
            "region": "전북",
            "type": "food",
        },
        "course": {
            "title": "제주 올레길 코스 추천 — 3일 코스 완성",
            "content": "제주 올레길 중 인기 있는 코스들을 연결한 3일 코스입니다.",
            "addr": "제주 제주시",
            "sigungu": "제주시",
            "region": "제주",
            "type": "course",
        },
    }
    return test_items.get(source_type, test_items["camping"])


def load_prompt_file(filename):
    """프롬프트 파일 로드"""
    prompt_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts"
    )
    path = os.path.join(prompt_dir, filename)
    if not os.path.exists(path):
        for root, dirs, files in os.walk(prompt_dir):
            for f in files:
                if f == filename or f == os.path.basename(filename):
                    path = os.path.join(root, f)
                    break
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return f"당신은 {filename} 주제의 블로그 에디터입니다. 한국어로 작성하세요."


def run_dryrun(blogs, count_per_blog=2, save_dir=None):
    """메인 dry-run 루프 — 생성 + 저장 + 스캔"""
    results = {}
    total_api_calls = 0

    if save_dir:
        os.makedirs(save_dir, exist_ok=True)

    for blog in blogs:
        blog_id = blog["id"]
        pipeline = blog["pipeline"]
        logger.info(f"=== {blog_id} ({pipeline}) dry-run 시작 ===")

        blog_dir = os.path.join(save_dir, blog_id) if save_dir else None
        if blog_dir:
            os.makedirs(blog_dir, exist_ok=True)

        blog_results = []
        for i in range(count_per_blog):
            logger.info(f"  [{i+1}/{count_per_blog}] 생성 중...")
            try:
                title = None
                body = None

                if pipeline == "car":
                    prompt_text = load_prompt_file(blog.get("prompt_file", ""))
                    data = build_car_test_data(blog)
                    from shared.ai_writer import generate_car
                    raw_content = generate_car(prompt_text, data)
                    body = raw_content
                    if raw_content:
                        for line in raw_content.split("\n"):
                            if line.strip().startswith("# "):
                                title = line[2:].strip()
                                break

                elif pipeline == "travel":
                    item_data = build_travel_test_data(blog)
                    from pipelines.travel.writer import generate_content
                    result = generate_content(item_data, blog_id=blog_id)
                    if isinstance(result, dict):
                        title = result.get("title", "")
                        body = result.get("body_md", "") or result.get("body", "") or result.get("content", "")
                    elif isinstance(result, str):
                        body = result
                    else:
                        body = str(result) if result else ""

                total_api_calls += 1

                if not body:
                    logger.warning(f"  [{i+1}] 본문 없음")
                    blog_results.append({
                        "post": i + 1, "title": "", "body_len": 0,
                        "passed": False, "findings": [],
                        "error": "empty body",
                    })
                    continue

                # 전체본문 스캔 (500자 제한 없음)
                findings = scan_full_body(title, body)
                body_len = len(body)

                # 판정 항목
                strong_pats = {"ko_thinking", "test_dummy", "prompt_instruction_leak",
                               "thinking_tag_remain", "forbidden_grammar_break"}
                has_strong = any(f["pattern"] in strong_pats for f in findings)
                has_cjk = any(f["pattern"] == "cjk_line_leak" for f in findings)
                has_style = any(f["pattern"] == "forbidden_word_reverse" for f in findings)
                has_valid = body_len > 500

                # 통과: strong 0 + 본문 500자 초과
                passed = not has_strong and has_valid

                post_result = {
                    "post": i + 1,
                    "title": title[:80] if title else "(제목 없음)",
                    "body_len": body_len,
                    "passed": passed,
                    "findings": findings,
                    "checks": {
                        "strong_leak": not has_strong,
                        "valid_structure": has_valid,
                    },
                }
                blog_results.append(post_result)

                # 본문 저장
                if blog_dir:
                    fname = f"{i+1}.md"
                    fpath = os.path.join(blog_dir, fname)
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(f"---\ntitle: \"{title or '(제목 없음)'}\"\nblog: {blog_id}\ndraft: true\n---\n\n{body}")
                    logger.info(f"  [{i+1}] 저장: {fpath}")

                status = "PASS" if passed else "FAIL"
                logger.info(f"  [{i+1}] {status} — {body_len}자")
                if findings:
                    for f in findings:
                        logger.info(f"    감지: {f['pattern']} — {f['context'][:60]}")

            except Exception as e:
                logger.error(f"  [{i+1}] 오류: {e}")
                blog_results.append({
                    "post": i + 1, "title": "", "body_len": 0,
                    "passed": False, "findings": [{"pattern": "error", "context": str(e)[:80]}],
                    "error": str(e),
                })

            if i < count_per_blog - 1:
                time.sleep(3)
        time.sleep(5)

        all_passed = all(p["passed"] for p in blog_results)
        results[blog_id] = {
            "pipeline": pipeline,
            "posts": blog_results,
            "all_passed": all_passed,
        }

    return results, total_api_calls


def print_report(results, total_api_calls):
    """리포트 출력"""
    print("\n" + "=" * 80)
    print("Phase5 dry-run 전체본문 재판정")
    print("=" * 80)
    print(f"총 API 호출: {total_api_calls}회")
    print()

    total_posts = sum(len(r["posts"]) for r in results.values())
    passed_posts = sum(
        sum(1 for p in r["posts"] if p["passed"])
        for r in results.values()
    )
    print(f"전체: {passed_posts}/{total_posts} PASS")
    print()

    print(f"{'블로그':<20} {'결과':<8} {'통과':<6} {'상세'}")
    print("-" * 80)
    for blog_id, r in sorted(results.items()):
        status = "PASS" if r["all_passed"] else "FAIL"
        pass_count = sum(1 for p in r["posts"] if p["passed"])
        total = len(r["posts"])
        detail_parts = []
        for p in r["posts"]:
            if not p["passed"]:
                failed = [f["pattern"] for f in p.get("findings", [])
                          if f["pattern"] in ("ko_thinking", "test_dummy", "prompt_instruction_leak",
                                               "thinking_tag_remain", "forbidden_grammar_break")]
                detail_parts.append(f"Post{p['post']}:{','.join(failed)}")
        detail = "; ".join(detail_parts) if detail_parts else "all clean"
        print(f"{blog_id:<20} {status:<8} {pass_count}/{total}   {detail}")
    print()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--blogs", help="쉼표 구분 블로그 ID (없으면 전체)")
    parser.add_argument("--count", type=int, default=2, help="블로그당 생성 건수")
    parser.add_argument("--save-dir", default="/Users/twinssn/Projects/5000/data/phase5_dryrun",
                        help="본문 저장 디렉터리")
    args = parser.parse_args()

    if args.blogs:
        selected_ids = args.blogs.split(",")
        blogs = [b for b in ALL_BLOGS if b["id"] in selected_ids]
    else:
        blogs = ALL_BLOGS

    results, total_api_calls = run_dryrun(blogs, count_per_blog=args.count, save_dir=args.save_dir)
    print_report(results, total_api_calls)

    # JSON 저장
    json_path = os.path.join(args.save_dir, "result.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"결과 저장: {json_path}")
    print(f"본문 저장: {args.save_dir}/{{blog}}/{{1,2}}.md")
