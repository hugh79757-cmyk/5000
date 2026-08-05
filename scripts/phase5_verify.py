#!/usr/bin/env python3
"""
Phase5 검증 — 수정된 writer가 깨끗한지 dry-run
13개 블로그 × 2건 생성 → 스캔 → 5개 항목 통과 여부 판정

Usage: python3 scripts/phase5_verify.py [--blogs blog1,blog2] [--count 2]
"""
import sys
import os
import re
import json
import time
import logging
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv("/Users/twinssn/Projects/5000/.env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── 블로그 정의 ──────────────────────────────────────────────
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

# ── 스캔 시그니처 (scan_multilingual_leak.py와 동일) ──────────
SCAN_PATTERNS = {
    "ko_thinking": re.compile(
        r"사용자가 제공한 데이터|절대\s+.*\s+말라고 했습니다|초안:|이제\s+.*\s+작성|H2-\d|문장 수:|주의:|규칙|~해야 합니다\."
    ),
    "en_thinking": re.compile(
        r"(?:^|\n)\s*(?:The user has provided|Let me re-?[Rr]ead|Wait,|we need to|Let me|I should|Actually,|First,)\b"
    ),
    "cjk_leak_keywords": re.compile(
        r"(?:我们|需要|根据|注意|规则|禁止|应当|必须|以上|以下|关于|分析|考虑|但是|所以|因为|如果|虽然|并且|或者|因此|然而|目前|现在|对于|通过|使用|包括|属于|作为|已经)"
    ),
    "prompt_instruction_leak": re.compile(
        r"bold-list로 정리|테이블 금지|1~2문장으로 소개|H2 없이|최소 \d+문장|~를 명시해야|금지 표현|체크포인트|구조:|도입부 \("
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


def scan_content(title, body):
    """콘텐츠 스캔 — 감지된 오염 패턴 목록 반환"""
    findings = []
    full_text = (title or "") + "\n" + (body or "")

    for pname, regex in SCAN_PATTERNS.items():
        if pname == "cjk_line_leak":
            # 라인별 검사
            for line in (body or "").split("\n"):
                if regex.search(line):
                    findings.append({"pattern": pname, "context": line.strip()[:80]})
                    break
        elif pname == "thinking_tag_remain":
            m = regex.search(full_text)
            if m:
                findings.append({"pattern": pname, "context": m.group()[:50]})
        else:
            m = regex.search(full_text[:500])
            if m:
                findings.append({"pattern": pname, "context": m.group()[:80]})

    return findings


def generate_car_post(blog_cfg, prompt_text, data):
    """CAP 블로그 — generate_car() 호출"""
    from shared.ai_writer import generate_car
    result = generate_car(prompt_text, data)
    return result


def generate_travel_post(blog_cfg, item_data):
    """TAP 블로그 — travel writer generate_content() 호출"""
    from pipelines.travel.writer import generate_content
    data = {
        "source_type": blog_cfg["source_type"],
        "items": [item_data],
    }
    result = generate_content(data, blog_id=blog_cfg["id"])
    return result


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
        # prompts/ 하위 디렉토리에서 검색
        for root, dirs, files in os.walk(prompt_dir):
            for f in files:
                if f == filename or f == os.path.basename(filename):
                    path = os.path.join(root, f)
                    break
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return f"당신은 {filename} 주제의 블로그 에디터입니다. 한국어로 작성하세요."


def run_verification(blogs, count_per_blog=2):
    """메인 검증 루프"""
    results = {}
    total_api_calls = 0

    for blog in blogs:
        blog_id = blog["id"]
        pipeline = blog["pipeline"]
        logger.info(f"=== {blog_id} ({pipeline}) 검증 시작 ===")

        blog_results = []
        for i in range(count_per_blog):
            logger.info(f"  [{i+1}/{count_per_blog}] 생성 중...")
            try:
                if pipeline == "car":
                    prompt_text = load_prompt_file(blog.get("prompt_file", ""))
                    data = build_car_test_data(blog)
                    raw_content = generate_car_post(blog, prompt_text, data)
                    # generate_car returns a string (body), not a dict
                    title = None
                    body = raw_content
                    if raw_content:
                        # H1에서 제목 추출 시도
                        for line in raw_content.split("\n"):
                            if line.strip().startswith("# "):
                                title = line[2:].strip()
                                break

                elif pipeline == "travel":
                    item_data = build_travel_test_data(blog)
                    result = generate_travel_post(blog, item_data)
                    if isinstance(result, dict):
                        title = result.get("title", "")
                        body = result.get("body_md", "") or result.get("body", "") or result.get("content", "")
                    elif isinstance(result, str):
                        body = result
                        title = None
                    else:
                        body = str(result) if result else ""
                        title = None
                else:
                    logger.warning(f"  알 수 없는 파이프라인: {pipeline}")
                    continue

                total_api_calls += 1

                # 스캔
                findings = scan_content(title, body)
                body_len = len(body) if body else 0

                # 5개 항목 검증
                has_thinking_leak = any(f["pattern"] in ("ko_thinking", "en_thinking", "cjk_leak_keywords", "cjk_line_leak") for f in findings)
                has_thinking_tag = any(f["pattern"] == "thinking_tag_remain" for f in findings)
                has_instruction_leak = any(f["pattern"] == "prompt_instruction_leak" for f in findings)
                has_grammar_break = any(f["pattern"] == "forbidden_grammar_break" for f in findings)
                has_valid_structure = (title is not None and body_len > 500) or (body_len > 500)

                # 판정 (forbidden_word_reverse는 스타일 이슈 — 통과 처리)
                passed = not (has_thinking_leak or has_thinking_tag or has_instruction_leak or has_grammar_break) and has_valid_structure

                post_result = {
                    "post": i + 1,
                    "title": title[:50] if title else "(제목 없음)",
                    "body_len": body_len,
                    "passed": passed,
                    "findings": findings,
                    "checks": {
                        "multilingual_leak": not has_thinking_leak,
                        "thinking_tag": not has_thinking_tag,
                        "instruction_leak": not has_instruction_leak,
                        "grammar_break": not has_grammar_break,
                        "valid_structure": has_valid_structure,
                    },
                }
                blog_results.append(post_result)

                status = "PASS" if passed else "FAIL"
                logger.info(f"  [{i+1}] {status} — {body_len}자, 제목: {title[:30] if title else '(없음)'}")
                if findings:
                    for f in findings:
                        logger.info(f"    감지: {f['pattern']} — {f['context'][:50]}")

            except Exception as e:
                logger.error(f"  [{i+1}] 오류: {e}")
                blog_results.append({
                    "post": i + 1,
                    "title": "",
                    "body_len": 0,
                    "passed": False,
                    "findings": [{"pattern": "error", "context": str(e)[:80]}],
                    "checks": {
                        "multilingual_leak": False,
                        "thinking_tag": False,
                        "instruction_leak": False,
                        "forbidden_reverse": False,
                        "valid_structure": False,
                    },
                })

            # API 호출 간 대기 (Gemini free tier 속도 제한 대기)
            if i < count_per_blog - 1:
                time.sleep(3)
        # 블로그 간 대기 (rate limit 대기)
        time.sleep(5)

        all_passed = all(p["passed"] for p in blog_results)
        results[blog_id] = {
            "pipeline": pipeline,
            "posts": blog_results,
            "all_passed": all_passed,
        }

    return results, total_api_calls


def print_report(results, total_api_calls):
    """최종 보고서 출력"""
    print("\n" + "=" * 80)
    print("Phase5 검증 결과 — 수정된 writer 오염 방어 테스트")
    print("=" * 80)
    print(f"총 API 호출: {total_api_calls}회")
    print()

    # 전체 요약
    total_posts = sum(len(r["posts"]) for r in results.values())
    passed_posts = sum(
        sum(1 for p in r["posts"] if p["passed"])
        for r in results.values()
    )
    print(f"전체: {passed_posts}/{total_posts} 통과")
    print()

    # 블로그별 상세
    print(f"{'블로그':<20} {'파이프라인':<10} {'결과':<8} {'통과':<6} {'상세'}")
    print("-" * 80)
    for blog_id, r in sorted(results.items()):
        status = "PASS" if r["all_passed"] else "FAIL"
        pass_count = sum(1 for p in r["posts"] if p["passed"])
        total = len(r["posts"])
        detail_parts = []
        for p in r["posts"]:
            if not p["passed"]:
                failed_checks = [k for k, v in p["checks"].items() if not v]
                detail_parts.append(f"Post{p['post']}:{','.join(failed_checks)}")
        detail = "; ".join(detail_parts) if detail_parts else "all clean"
        print(f"{blog_id:<20} {r['pipeline']:<10} {status:<8} {pass_count}/{total}   {detail}")

    print()
    print("검증 항목:")
    print("  (a) 다국어 누수 0건 (ko_thinking + en_thinking + cjk_leak + cjk_line_leak)")
    print("  (b) thinking/reasoning 태그 잔재 0건")
    print("  (c) 프롬프트 지시문 노출 0건 (라인 시작)")
    print("  (d) 문법 파괴형 역노출 0건 (forbidden_grammar_break)")
    print("  (e) 제목·본문 정상 구조 (body > 500자)")
    print("  (참고) forbidden_word_reverse(과연/바랍니다)는 스타일 이슈 — 판정에 미영향")
    print()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--blogs", help="쉼표 구분 블로그 ID (없으면 전체)")
    parser.add_argument("--count", type=int, default=2, help="블로그당 생성 건수")
    args = parser.parse_args()

    if args.blogs:
        selected_ids = args.blogs.split(",")
        blogs = [b for b in ALL_BLOGS if b["id"] in selected_ids]
    else:
        blogs = ALL_BLOGS

    results, total_api_calls = run_verification(blogs, count_per_blog=args.count)
    print_report(results, total_api_calls)

    # JSON 출력 (상세 분석용)
    json_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "phase5_verify_result.json"
    )
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"상세 결과: {json_path}")
