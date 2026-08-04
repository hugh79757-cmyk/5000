#!/usr/bin/env python3
"""Q1/Q3 규칙 기반 스캐너 v2 — read-only scan

검증 이력:
  v1: 오탐 25% (효과적/도움/FAQ 헤더 미분리), 미탐 다수
  v2: 건강 전용 맥락 필터, FAQ 제외, 1인칭 주어 확장

사용법:
    python3 q3_scanner.py validate  # 오탐/미탐 검증
    python3 q3_scanner.py scan      # 전량 스캔
"""
import csv
import json
import os
import re
import sys
from pathlib import Path

CUAP = Path("/Users/twinssn/Projects/CUAP")
OUT_DIR = Path(__file__).parent / "samples"

# ──────────────────────────────────────────────
# 공통: FAQ/H2 헤더 제외 영역
# ──────────────────────────────────────────────
FAQ_HEADER = re.compile(r"(?:^|\n)\s*#{1,3}\s+.*(?:실제\s*사용|사용해보|써보|경험|후기)", re.I)

def strip_faq_headers(text):
    """FAQ/H2 헤더 라인을 제거해 오탐 방지"""
    return FAQ_HEADER.sub("", text)

# ──────────────────────────────────────────────
# Q3: 건강/뷰티 효능 단정 (건강 전용 맥락 필수)
# ──────────────────────────────────────────────

# 건강/뷰티/신체 관련 키워드 (이 맥락에서만 Q3 적용)
HEALTH_CONTEXT = re.compile(
    r"(피부|모발|탈모|여드름|비타민|영양제|보충제|건강기능식품|식약처|기능성|혈액|혈행|"
    r"면역|소화|수면|스트레스|눈|관절|뼈|근육|체지방|다이어트|체중|칼슘|철분|오메가|"
    r"유산균|프로바이오|콜라겐|히알루론산|레티놀|비타민A|비타민B|비타민C|비타민D|비타민E|"
    r"엽산|아연|마그네슘|칼륨|프로틴|단백질|칼로리|영양|섭취|복용|제품의\s*효과|제품이\s*도움)",
    re.I
)

# Tier 1 — 직접적 효능 단정 (건강 맥락에서만 위반)
Q3_VIOLATION_PATTERNS = [
    # 직접적 효능 단정
    (re.compile(r"개선[된된다됩니다]+", re.I), "효능단정: 개선"),
    (re.compile(r"향상[된된다됩니다]+", re.I), "효능단정: 향상"),
    (re.compile(r"효과[가이가 ]{0,2}(있습니다|있다|있는|明显的)", re.I), "효능단정: 효과"),
    (re.compile(r"피부가\s*좋아[집니다지다]+", re.I), "효능단정: 피부개선"),
    (re.compile(r"피부를?\s*(환하게|맑게|깨끗하게|깨끗이|개선)", re.I), "효능단정: 피부효과"),
    # 탄력 + 신체 맥락
    (re.compile(r"탄력[을을이가 ]{0,2}(더해|생기|있|좋|강화)", re.I), "효능단정: 탄력"),
    # 활력 + 신체 맥락
    (re.compile(r"활력[을을이가 ]{0,2}(더하|주|있|줄|생기)", re.I), "효능단정: 활력"),
    # 도움 — direct (건강 전용 맥락에서만 위반)
    # "도움이 됩니다"는 제품 기능 설명에서 흔하므로 건강 키워드와 결합될 때만 위반
    (re.compile(r"(?:피부|건강|호흡기|면역|혈액|혈행|영양|다이어트|체중|체지방|소화|수면|스트레스|눈|관절|뼈|근육|칼로리|체온|신진대사|피로|원기|활력)[^\.]{0,20}도움[을이가 ]{0,2}(줍니다|됩니다|된다|줘요|드립니다|큰 도움)", re.I), "효능단정: 도움(건강맥락)"),
    # 면역/혈액/기억력/집중력
    (re.compile(r"면역[을을이가 ]{0,2}(강화|향상|增强|좋|나쁨|개선|튼튼|增强)", re.I), "효능단정: 면역"),
    (re.compile(r"혈액\s*순환[을을이가 ]{0,2}(개선|향상|도움|촉진|원활|좋|나쁨)", re.I), "효능단정: 혈액순환"),
    (re.compile(r"혈행[을을이가 ]{0,2}(개선|향상|도움|촉진|원활|좋|나쁨)", re.I), "효능단정: 혈행"),
    (re.compile(r"기억력[을을이가 ]{0,2}(개선|향상|增强|좋|나쁨|도움)", re.I), "효능단정: 기억력"),
    (re.compile(r"집중력[을을이가 ]{0,2}(개선|향상|增强|좋|나쁨|도움)", re.I), "효능단정: 집중력"),
    # 치료/예방/완화 (건강 맥락에서)
    (re.compile(r"치료[한다됩니다]+", re.I), "효능단정: 치료"),
    (re.compile(r"예방[한다됩니다]+", re.I), "효능단정: 예방"),
    (re.compile(r"완화[한다됩니다]+", re.I), "효능단정: 완화"),
    # 환해 (건강/뷰티 맥락에서)
    (re.compile(r"환해[집니다지다]+", re.I), "효능단정: 환해"),
]

# Tier 2 — 정상 표현 (위반에서 제외)
Q3_SAFE_PATTERNS = [
    re.compile(r"도움[이가 ]{0,2}(될\s*수\s*있|될지도|될\s*가능성)", re.I),  # hedged
    re.compile(r"알려져\s*있", re.I),     # attribution
    re.compile(r"알려진\s*\S+", re.I),    # attribution
    re.compile(r"관심\s*있는\s*분들에게\s*적합", re.I),  # preference
    re.compile(r"성분표를?\s*확인", re.I),
    re.compile(r"본인에게?\s*맞는\s*제품을?\s*선택", re.I),
    re.compile(r"식약처\s*(인증|고시|등록)", re.I),
    re.compile(r"기능성\s*원료", re.I),
    re.compile(r"도움[이가 ]{0,2}되는\s*\S+", re.I),  # "도움이 되는 성분" — 묘사
]

# 비건강 맥락 필터 — 이것들이으면 Q3 위반에서 제외
NON_HEALTH_PRODUCTS = re.compile(
    r"(공기청정기|청소기|로봇청소기|세탁기|건조기|에어컨|제습기|가습기|"
    r"밥솥|전기밥솥|냄비|프라이팬|믹서기|블렌더|토스터|전자레인지|"
    r"카메라|노트북|모니터|키보드|마우스|태블릿|스피커|이어폰|"
    r"매트리스|침대|소파|책장|수납장|의자|테이블|행거|"
    r"히터|전기히터|카본히터|온풍기|에어컨|선풍기|서큘레이터|"
    r"캠핑|텐트|침낭|매트|랜턴|그릴|코펠|체어|테이블|"
    r"반려동물|강아지|고양이|어항|케이지|이동장)",
    re.I
)


def scan_q3(text):
    """Q3 위반 탐지 — 건강 맥락 + safe 패턴 필터링"""
    hits = []
    clean_text = strip_faq_headers(text)

    for pat, label in Q3_VIOLATION_PATTERNS:
        for m in pat.finditer(clean_text):
            matched = m.group()
            start = max(0, m.start() - 40)
            end = min(len(clean_text), m.end() + 40)
            context = clean_text[start:end].replace("\n", " ").strip()

            # 1) safe 패턴과 겹치면 제외
            if any(sp.search(context) for sp in Q3_SAFE_PATTERNS):
                continue

            # 2) 건강 맥락 필수 — "효과적입니다" 등은 건강 제품에서만 위반
            #    non-health 제품이면 제외
            if NON_HEALTH_PRODUCTS.search(context):
                continue

            # 3) 건강 맥락 확인 (텍스트 전체에서 health 컨텍스트 존재 여부)
            #    "효과적입니다" 등 일반 표현은 건강 맥락이 있을 때만 위반
            has_health = bool(HEALTH_CONTEXT.search(clean_text))
            if not has_health:
                # 건강 맥락이 없는 글 → 효과적/도움은 일반 표현으로 간주
                # 단, 탄력/환해/면역/혈액/기억력/집중력은 건강 맥락 없어도 위반
                if label.startswith("효능단정:") and label.split(":")[1].strip() in ("탄력", "활력", "환해", "면역", "혈액순환", "혈행", "기억력", "집중력"):
                    pass  # 건강 전용 단어 → 계속 위반
                else:
                    continue  # 일반 표현 → 제외

            hits.append({"match": matched, "context": context, "label": label})
    return hits


# ──────────────────────────────────────────────
# Q1: 1인칭 경험 주장
# ──────────────────────────────────────────────

Q1_1PERSON_SUBJECTS = re.compile(r"(?<![가-힣])(저도|저는|내가|나도|나는|제가|저희가)(?=[\s,.:!?]|$)")
Q1_EXPERIENCE_VERBS = re.compile(
    r"(사용[해하]|써[보보니]|경험[했습]|느꼈[다습]|만족[스러웠]|체험[했습])",
    re.I,
)

Q1_DIRECT_PATTERNS = [
    (re.compile(r"실제\s*사용[해하]", re.I), "실제 사용 경험"),
    (re.compile(r"실사용\s*(후기|느낌|리뷰|경험|평)", re.I), "실사용 후기"),
    (re.compile(r"직접\s*써[보보니]", re.I), "직접 써보니"),
    (re.compile(r"직접\s*사용[해하]", re.I), "직접 사용"),
    (re.compile(r"써보니", re.I), "써보니"),
    (re.compile(r"사용해보니", re.I), "사용해보니"),
    (re.compile(r"사용해본\s*결과", re.I), "사용해본 결과"),
    (re.compile(r"써본\s*결과", re.I), "써본 결과"),
    (re.compile(r"경험했[다습]", re.I), "경험했"),
    (re.compile(r"느꼈[다습]", re.I), "느꼈"),
    (re.compile(r"만족스러웠[다습]", re.I), "만족스러웠"),
    (re.compile(r"체험했[다습]", re.I), "체험했"),
]

Q1_SAFE_PATTERNS = [
    re.compile(r"실제\s*사용\s*(무게|크기|면적|환경|온도|습도|소음)", re.I),
    re.compile(r"사용자[들이가]\s*(만족|평가|선호|선택|리뷰)", re.I),
    re.compile(r"평가[받받은]", re.I),
    re.compile(r"리뷰[에서가]", re.I),
    re.compile(r"후기[에서가]", re.I),
    re.compile(r"판매량", re.I),
    re.compile(r"리뷰\s*\d", re.I),     # "리뷰 4.8점"
    re.compile(r"판매\s*\d", re.I),     # "판매 1만건"
]


def scan_q1(text):
    """Q1 위반 탐지 — 라이브 가시 본문+FAQ헤더+타이틀 스캔
    
    정의: 독자에게 실제로 렌더링되어 보이는 위치의 위반만 카운트
    - 본문 텍스트 ✅ (독자에게 보임)
    - FAQ 헤더 ✅ (h2/h3으로 렌더링되어 보임)
    - 타이틀 ✅ (h1으로 렌더링되어 보임)
    - JSON-LD ❌ (script 태그, 독자에게 보이지 않음)
    - 관련글 링크 ❌ (다른 글 제목, 이중계산 방지)
    - frontmatter YAML ❌ (Hugo가 파싱 후 제거)
    
    FAQ 질문/주장 구분:
    - 질문형 ("### 실제 사용해보니 어떤가요?") → 위반 아님
    - 주장형 ("### 실제 사용해보니 좋았습니다") → 위반
    """
    hits = []
    lines = text.split("\n")

    # 1인칭 주어 + 경험 동사 조합
    for subj_m in Q1_1PERSON_SUBJECTS.finditer(text):
        after = text[subj_m.end():subj_m.end() + 60]
        if Q1_EXPERIENCE_VERBS.search(after):
            context = text[max(0, subj_m.start() - 10):min(len(text), subj_m.end() + 60)].replace("\n", " ").strip()
            is_safe = any(sp.search(context) for sp in Q1_SAFE_PATTERNS)
            # FAQ 질문형 필터: 헤더 라인이 "?"를 포함하면 질문 → 제외
            match_line = _find_line(lines, subj_m.start())
            is_faq_question = _is_faq_question_line(match_line) if match_line else False
            if not is_safe and not is_faq_question:
                hits.append({"match": subj_m.group(), "context": context, "label": "1인칭+경험동사"})

    # 단독 패턴
    for pat, label in Q1_DIRECT_PATTERNS:
        for m in pat.finditer(text):
            matched = m.group()
            start = max(0, m.start() - 30)
            end = min(len(text), m.end() + 30)
            context = text[start:end].replace("\n", " ").strip()
            is_safe = any(sp.search(context) for sp in Q1_SAFE_PATTERNS)
            match_line = _find_line(lines, m.start())
            is_faq_question = _is_faq_question_line(match_line) if match_line else False
            if not is_safe and not is_faq_question:
                hits.append({"match": matched, "context": context, "label": label})
    return hits


def _find_line(lines, pos):
    """텍스트 내 offset이 어떤 줄에 속하는지 반환"""
    current = 0
    for line in lines:
        current += len(line) + 1  # +1 for \n
        if pos < current:
            return line
    return None


def _is_faq_question_line(line):
    """FAQ 헤더 라인이 '질문형'인지 판정
    
    질문형: "### 실제 사용해보니 어떤가요?" → Q1 위반 아님
    주장형: "### 실제 사용해보니 좋았습니다" → Q1 위반
    """
    stripped = line.strip()
    if not stripped.startswith("#"):
        return False  # 헤더가 아님
    # 헤더 라인에서 "?"가 있으면 질문형
    if "?" in stripped or "؟" in stripped:
        return True
    return False


def read_post(filepath):
    """index.md에서 full_text 반환 (타이틀+FAQ헤더+본문, JSON/script 제거)"""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    text = re.sub(r'\{[^{}]*"(?:name|url|date|description|keyword)"[^{}]*\}', '', content)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
    text = re.sub(r'<(?!#{1,3}\s)[^>]+>', ' ', text)
    return text


def read_body(filepath):
    """index.md에서 body만 반환 (frontmatter 제거, JSON/script 제거)"""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            body = parts[2].strip()
    body = re.sub(r'\{[^{}]*"(?:name|url|date|description|keyword)"[^{}]*\}', '', body)
    body = re.sub(r'<script[^>]*>.*?</script>', '', body, flags=re.DOTALL)
    body = re.sub(r'<[^>]+>', ' ', body)
    return body


def get_posts(blog_id, limit=None):
    posts_dir = CUAP / blog_id / "content" / "posts"
    if not posts_dir.is_dir():
        return []
    results = []
    for slug in sorted(posts_dir.iterdir()):
        idx = slug / "index.md"
        if not idx.is_file():
            continue
        with open(idx, "r", encoding="utf-8") as f:
            head = f.read(600)
        if "draft: true" in head:
            continue
        full_text = read_post(str(idx))    # Q1용: 타이틀+FAQ+본문
        body = read_body(str(idx))         # Q3용: 본문만
        results.append({"blog_id": blog_id, "slug": slug.name, "full_text": full_text, "body": body, "path": str(idx)})
        if limit and len(results) >= limit:
            break
    return results


def find_post_by_keyword(blog_id, keyword_fragment):
    """특정 키워드가 포함된 slug의 포스트를 찾음"""
    posts = get_posts(blog_id)
    for p in posts:
        if keyword_fragment in p["slug"]:
            return p
    # 없으면 첫 번째
    return posts[0] if posts else None


# ──────────────────────────────────────────────
# 검증 모드
# ──────────────────────────────────────────────

def validate():
    print("=" * 60)
    print("규칙 검증 시작 (v2)")
    print("=" * 60)

    # ── 오탐 검증 ──
    clean_blogs = ["appliance-hugo", "interior-hugo", "kitchen-hugo"]
    fp_total = 0
    fp_posts = 0
    all_clean_posts = 0

    print("\n[오탐 검증] appliance/interior/kitchen에서 20건씩")
    for blog in clean_blogs:
        posts = get_posts(blog, limit=20)
        blog_fp = 0
        for p in posts:
            q1 = scan_q1(p["full_text"])
            q3 = scan_q3(p["body"])
            if q1 or q3:
                blog_fp += 1
                fp_posts += 1
                fp_total += len(q1) + len(q3)
                print(f"  ⚠️ 오탐 {blog}/{p['slug'][:40]}… Q1={len(q1)} Q3={len(q3)}")
                for h in (q1 + q3)[:3]:
                    print(f"     → [{h.get('label','')}] '{h['match']}' in …{h['context'][:60]}…")
        all_clean_posts += len(posts)
        print(f"  {blog}: {len(posts)}건 중 {blog_fp}건 오탐")

    print(f"\n오탐 요약: {fp_posts}/{all_clean_posts}건 ({fp_posts/all_clean_posts*100:.1f}%), 위반 문구 {fp_total}개")

    # ── 미탐 검증 ──
    print("\n[미탐 검증] before 베이스라인 대조")
    human_counts = {
        "beauty-hugo": {"Q1": 4, "Q3": 12, "slug_frag": "비타민c-세럼"},
        "fitness-hugo": {"Q1": 6, "Q3": 0, "slug_frag": "워킹머신-실사용"},
        "laptop-hugo": {"Q1": 3, "Q3": 0, "slug_frag": "lg전자-그램"},
        "kitchen-hugo": {"Q1": 2, "Q3": 2, "slug_frag": "쿠첸-브레인"},
        "interior-hugo": {"Q1": 1, "Q3": 0, "slug_frag": "리버-책장"},
        "health-hugo": {"Q1": 0, "Q3": 0, "slug_frag": "피부-영양제"},
    }

    match_summary = {"Q1": {"match": 0, "mismatch": 0}, "Q3": {"match": 0, "mismatch": 0}}

    for blog, expected in human_counts.items():
        p = find_post_by_keyword(blog, expected["slug_frag"])
        if not p:
            print(f"  {blog}: 포스트 없음")
            continue
        q1 = scan_q1(p["full_text"])
        q3 = scan_q3(p["body"])
        q1_ok = len(q1) == expected["Q1"]
        q3_ok = len(q3) == expected["Q3"]
        q1_mark = "✅" if q1_ok else "❌"
        q3_mark = "✅" if q3_ok else "❌"

        if q1_ok: match_summary["Q1"]["match"] += 1
        else: match_summary["Q1"]["mismatch"] += 1
        if q3_ok: match_summary["Q3"]["match"] += 1
        else: match_summary["Q3"]["mismatch"] += 1

        print(f"  {blog}/{p['slug'][:40]}…")
        print(f"    Q1: 스캐너={len(q1)} vs 사람={expected['Q1']} {q1_mark}")
        for h in q1[:3]:
            print(f"      → [{h.get('label','')}] '{h['match']}' …{h['context'][:50]}…")
        print(f"    Q3: 스캐너={len(q3)} vs 사람={expected['Q3']} {q3_mark}")
        for h in q3[:3]:
            print(f"      → [{h.get('label','')}] '{h['match']}' …{h['context'][:50]}…")

    q1_rate = match_summary["Q1"]["match"] / (match_summary["Q1"]["match"] + match_summary["Q1"]["mismatch"]) * 100 if (match_summary["Q1"]["match"] + match_summary["Q1"]["mismatch"]) > 0 else 0
    q3_rate = match_summary["Q3"]["match"] / (match_summary["Q3"]["match"] + match_summary["Q3"]["mismatch"]) * 100 if (match_summary["Q3"]["match"] + match_summary["Q3"]["mismatch"]) > 0 else 0

    print(f"\n{'='*60}")
    print(f"검증 결과 요약")
    print(f"{'='*60}")
    print(f"오탐률: {fp_posts}/{all_clean_posts} ({fp_posts/all_clean_posts*100:.1f}%)")
    print(f"Q1 일치율: {match_summary['Q1']['match']}/{match_summary['Q1']['match']+match_summary['Q1']['mismatch']} ({q1_rate:.0f}%)")
    print(f"Q3 일치율: {match_summary['Q3']['match']}/{match_summary['Q3']['match']+match_summary['Q3']['mismatch']} ({q3_rate:.0f}%)")
    print(f"{'='*60}")


def _classify_location(text, match_start, match_end):
    """위반 위치 분류: body / faq_header / title"""
    lines = text.split("\n")
    line = _find_line(lines, match_start)
    if not line:
        return "body"
    stripped = line.strip()
    # title: frontmatter의 title 필드 (YAML)
    if stripped.startswith("title:") and match_start < sum(len(l) + 1 for l in lines[:2]):
        return "title"
    # faq_header: #으로 시작하는 헤더 라인
    if stripped.startswith("#"):
        return "faq_header"
    return "body"


def full_scan():
    all_blogs = sorted([d.name for d in CUAP.iterdir() if d.is_dir() and d.name.endswith("-hugo")])
    results = []
    summary = {}

    for blog in all_blogs:
        posts = get_posts(blog)
        blog_results = []
        for p in posts:
            q1 = scan_q1(p["full_text"])  # Q1: full_text (타이틀+FAQ+본문)
            q3 = scan_q3(p["body"])        # Q3: body만 (건강 맥락 필터)
            if q1 or q3:
                # 위치 분류
                q1_locations = []
                for h in q1:
                    loc = _classify_location(p["full_text"], 
                                             p["full_text"].find(h["match"]),
                                             p["full_text"].find(h["match"]) + len(h["match"]))
                    q1_locations.append(loc)
                
                blog_results.append({
                    "blog_id": blog,
                    "slug": p["slug"],
                    "q1_count": len(q1),
                    "q3_count": len(q3),
                    "q1_matches": [h["match"] for h in q1],
                    "q3_matches": [h["match"] for h in q3],
                    "q1_contexts": [h["context"][:100] for h in q1],
                    "q3_contexts": [h["context"][:100] for h in q3],
                    "q1_labels": [h["label"] for h in q1],
                    "q3_labels": [h["label"] for h in q3],
                    "q1_locations": q1_locations,
                    "live_url": f"https://{blog.replace('-hugo', '')}.rotcha.kr/{p['slug']}",
                })
        results.extend(blog_results)
        summary[blog] = {
            "total_posts": len(posts),
            "violations": len(blog_results),
            "q1_total": sum(r["q1_count"] for r in blog_results),
            "q3_total": sum(r["q3_count"] for r in blog_results),
        }

    # CSV 저장
    csv_path = OUT_DIR / "full_scan_results.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "blog_id", "slug", "q1_count", "q3_count",
            "q1_matches", "q3_matches", "q1_contexts", "q3_contexts",
            "q1_labels", "q3_labels", "q1_locations", "live_url"
        ])
        w.writeheader()
        w.writerows(results)

    # JSON 저장
    json_path = OUT_DIR / "full_scan_results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": results}, f, ensure_ascii=False, indent=2)

    total_posts = sum(s["total_posts"] for s in summary.values())
    total_violations = sum(s["violations"] for s in summary.values())
    total_q1 = sum(s["q1_total"] for s in summary.values())
    total_q3 = sum(s["q3_total"] for s in summary.values())

    # 콘솔 출력
    print(f"\n{'='*60}")
    print(f"전량 스캔 결과 (라이브 가시 위반 기준)")
    print(f"{'='*60}")
    print(f"| Blog | Posts | 위반 | Q1 | Q3 |")
    print(f"|------|------:|-----:|---:|---:|")
    for blog in all_blogs:
        s = summary.get(blog, {})
        v = s.get("violations", 0)
        marker = " ⚠️" if v > 0 else ""
        print(f"| {blog} | {s.get('total_posts',0)} | {v} | {s.get('q1_total',0)} | {s.get('q3_total',0)}{marker} |")
    print(f"| **합계** | **{total_posts}** | **{total_violations}** | **{total_q1}** | **{total_q3}** |")
    print(f"\n저장: {csv_path}")
    print(f"저장: {json_path}")

    return summary, results


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "validate"
    if mode == "validate":
        validate()
    elif mode == "scan":
        full_scan()
    else:
        print(f"사용법: python3 {sys.argv[0]} [validate|scan]")
