#!/usr/bin/env python3
"""
c01_c08_reverse_validation.py — C01~C08 역검증 스크립트

실제 검증 데이터(dead_links, contamination, ETAP 영문 샘플, 정상글)에 대해
C01~C08 규칙을 적용하여 "전건 탐지 + 오탐 0"을 확인한다.

Usage:
    python3 scripts/c01_c08_reverse_validation.py \
        --dead-links scripts/c01_c08_validation_data/dead_links.json \
        --contamination scripts/c01_c08_validation_data/contamination.json \
        --dongnam scripts/c01_c08_validation_data/dongnam_npmb.json \
        --etap-samples scripts/c01_c08_validation_data/etap_english_samples.json \
        --normal-samples scripts/c01_c08_validation_data/normal_samples.json

    python3 scripts/c01_c08_reverse_validation.py --test-functions  # 단위 테스트
"""

import argparse
import json
import re
import sys
from pathlib import Path

import yaml as _yaml
import re
import sys
from pathlib import Path

# ── C01: 프론트매터 내 곡선따옴표 ──────────────────────────────────────────

CURVED_SINGLE = {'\u2018', '\u2019'}  # ' '
CURVED_DOUBLE = {'\u201c', '\u201d'}  # " "


def check_c01_frontmatter(frontmatter: str) -> tuple[bool, str]:
    """C01: frontmatter에 곡선따옴표(U+2018/2019/201C/201D)가 있으면 fail"""
    fm_check = frontmatter
    found = []
    if any(c in fm_check for c in CURVED_SINGLE):
        found.append("곡선따옴표(' ')")
    if any(c in fm_check for c in CURVED_DOUBLE):
        found.append('곡선따옴표(" ")')
    if found:
        return False, f"C01 위반: {', '.join(found)}"
    return True, "C01 통과"


# ── C02: 프론트매터 미종료 (첫 --- 이후 두 번째 --- 존재 여부로만 판정) ──


def check_c02_frontmatter(full_content: str) -> tuple[bool, str]:
    """C02: 첫 --- 이후 두 번째 ---가 없으면 fail.
    전체 --- 홀수 카운트 금지 (본문 내 --- 수평선과 혼동)."""
    lines = full_content.split('\n')
    first_dash_idx = None
    second_dash_idx = None
    for i, line in enumerate(lines):
        if line.strip() == '---':
            if first_dash_idx is None:
                first_dash_idx = i
            elif second_dash_idx is None and i > first_dash_idx:
                second_dash_idx = i
                break  # 두 번째 찾았으면 중단 (첫 --- 이후만 봄)
    if first_dash_idx is None:
        return False, "C02 위반: 첫 --- 없음"
    if second_dash_idx is None:
        return False, "C02 위반: 첫 --- 이후 두 번째 --- 없음"
    return True, "C02 통과"


# ── C03: 본문에 프론트매터 키 라인 유출 ──────────────────────────────────


FM_KEY_PATTERN = re.compile(
    r'^\s*(title|og_image|featureimage|date|slug|categories|tags|'
    r'description|draft|image|pubDate|author|cover):'
)


def check_c03_body(body_md: str) -> tuple[bool, str]:
    """C03: 본문에 프론트매터 키 라인(title:, slug: 등)이 있으면 fail"""
    leaked = []
    for line in body_md.split('\n'):
        if FM_KEY_PATTERN.match(line):
            leaked.append(line.strip()[:80])
    if leaked:
        return False, f"C03 위반: 프론트매터 키 유출 {len(leaked)}건 — {leaked[0]}"
    return True, "C03 통과"


# ── C04: 본문 LLM 프롬프트/사고문 누수 (국문 + 영문 패턴 분리) ──────────

KO_PATTERNS = [
    re.compile(r'먼저\s*생각', re.I),
    re.compile(r'생각해보자|생각해\s*보자', re.I),
    re.compile(r'다음\s*단계', re.I),
    re.compile(r'단계별로', re.I),
    re.compile(r'우선\s*', re.I),
    re.compile(r'우리가\s*해야\s*할', re.I),
    re.compile(r'필요한\s*것', re.I),
    re.compile(r'생각\s*해보자', re.I),
    # 프롬프트 지시문이 "주의: ..." 형태로 본문에 누수된 경우
    re.compile(r'(?:^|\n)\s*주의:', re.M),
]

EN_PATTERNS = [
    re.compile(r'\bNeed\s+think\b', re.I),
    re.compile(r'\bWe\s+need\s+to\s+write\b', re.I),
    re.compile(r"Let\.?s\s+think\s+step\s+by\s+step", re.I),
    re.compile(r'think\s+step\s+by\s+step', re.I),
    re.compile(r"let\.?s\s+break\s+this\s+down", re.I),
    re.compile(r"here\.?s?\s+the\s+plan", re.I),
    re.compile(r'firstly,?\s+', re.I),
    re.compile(r'secondly,?\s+', re.I),
    re.compile(r'in\s+order\s+to\s+achieve', re.I),
    re.compile(r'The\s+user\s+(?:has\s+provided|wants\s+me|said|is\s+asking)', re.I),
    re.compile(r'Let\s+me\s+(?:re-?[Rr]ead|write|check|look|verify|start|create)', re.I),
    re.compile(r'I\s+should\s+(?:write|check|note|add)', re.I),
    re.compile(r'Actually,?\s+', re.I),
    re.compile(r'First,?\s+', re.I),
    re.compile(r'Wait,?\s+', re.I),
    re.compile(r'we\s+need\s+to', re.I),
]


def check_c04_body(body_md: str, locale: str = 'ko') -> tuple[bool, str]:
    """C04: 본문에 프롬프트·CoT 패턴이 있으면 fail. locale=en 시 영문 패턴 사용."""
    patterns = EN_PATTERNS if locale == 'en' else KO_PATTERNS
    found = []
    for pat in patterns:
        m = pat.search(body_md)
        if m:
            found.append(m.group()[:50])
    if found:
        return False, f"C04 위반({locale}): 프롬프트 누수 패턴 {len(found)}건 — {found[0]}"
    return True, f"C04 통과({locale})"


# ── C05: draft:true 발행 대상 ─────────────────────────────────────────


def check_c05_frontmatter(frontmatter_dict: dict) -> tuple[bool, str]:
    """C05: frontmatter에 draft: true가 설정되어 있으면 fail.
    boolean True와 문자열 'true' (대소문자 무관) 모두 탐지."""
    draft_val = frontmatter_dict.get('draft', None)
    if draft_val is None:
        return True, "C05 통과 (draft 키 없음)"
    if draft_val is True:
        return False, "C05 위반: draft:true 발행 대상 (boolean)"
    if isinstance(draft_val, str) and draft_val.strip().lower() == 'true':
        return False, "C05 위반: draft:true 발행 대상 (문자열)"
    return True, "C05 통과"


# ── C06: 로컬 mtime > 배포 시각 (역검증에서는 skip) ─────────────────────


def check_c06_file(file_path: str, last_deploy_at: str) -> tuple[bool, str]:
    """C06: 로컬 파일 mtime이 마지막 배포 시각보다 최신이면 fail.
    역검증에서는 항상 True 반환 (배포 시각 정보 없음)."""
    return True, "C06 skip (역검증 범위 외)"


# ── C07: 죽은 크로스셀 링크 ────────────────────────────────────────────

# 일반 따옴표와 이스케이프 따옴표(\\") 모두 지원
# URL 내 공백 포함 허용: 텐트방수 스프레이 추천-... 등 한글 슬러그 전체 캡처
# 따옴표 형식: 일반 " 와 이스케이프 \" (backslash+quote) 모두 매칭
# raw string r'\\"' = 3 chars (\, \, ") → regex \\" = literal backslash + quote ✓
C07_SLUG_PATTERN = re.compile(
    r'href=(?:"|\\")https://([\w-]+)\.informationhot\.kr/posts/(.+?)/(?:"|\\")'
)


def check_c07_body(body_md: str, known_dead_slugs: set[str]) -> tuple[bool, str]:
    """C07: 크로스셀 카드가 dead_slugs에 있는 target을 가리키면 fail"""
    dead_found = []
    for m in C07_SLUG_PATTERN.finditer(body_md):
        target_slug = m.group(2)
        if target_slug in known_dead_slugs:
            dead_found.append(target_slug)
    if dead_found:
        return False, f"C07 위반: 죽은 크로스셀 링크 {len(dead_found)}건 — {dead_found[0]}"
    return True, "C07 통과"


# ── C08: 라이브-파일 불일치 (역검증에서는 placeholder) ─────────────────


def check_c08_placeholder(*args, **kwargs) -> tuple[bool, str]:
    """C08: 라이브 비교 API 필요 — 역검증에서는 skip."""
    return True, "C08 skip (라이브 비교 API 필요, placeholder)"


# ── C09: categories/tags 문자열화 탐지 ──────────────────────────────────
# YAML 배열이 문자열화된 형태: categories: "['추천']" → type=str, 값이 "[...]" 형태
# 정상: categories: ["추천"] → type=list
# Hugo range .Params.categories 실패 원인 → severity=CRITICAL, 배포차단
#
# 발생 원인:
#   - YAML 파서(yaml.safe_load)가 ["추천"]을 Python list로 정상 파싱
#   - 하지만 일부 생성 파이프라인이 문자열 리터럴 "['추천']"을 그대로 기록
#   - 이 경우 YAML 파싱 결과 type이 str이 되고, 값이 "['...']" 형태
#
# 탐지 방식:
#   1. fm_dict.get('categories')의 type 확인
#   2. type이 list → 정상 (통과)
#   3. type이 str이고 C09_STR_LIST_PATTERN 매칭 → 문자열화 (fail)
#   4. type이 str이지만 패턴 불일치 → 다른 문자열 값 (C09 대상 아님)
#
# 참고: phases/phase-62-content-leak-prevention/CONTEXT.md §C09 규칙 정의
# 참고: ops_dashboard/db.py SEED_STANDARD_RULES에 C09 INSERT 예정 (63-02)

C09_STR_LIST_PATTERN = re.compile(r'^\[\s*[\'"].*[\'"]\s*\]$')  # "['...']" 또는 '["..."]' 형태


def check_c09_frontmatter(fm_dict: dict) -> tuple[bool, str]:
    """C09: categories 또는 tags가 문자열화된 리스트이면 fail.

    정상 YAML 배열(type=list)은 통과, "['추천']" 형태(type=str, [...] 패턴)는 fail.

    Args:
        fm_dict: YAML 파싱 결과 딕셔너리 (parse_frontmatter의 두 번째 반환값)

    Returns:
        (통과여부, 메시지): fail 시 (False, "C09 위반: ..."), 통과 시 (True, "C09 통과")

    예시:
        >>> check_c09_frontmatter({'categories': ['추천'], 'tags': ['노트북']})
        (True, "C09 통과")
        >>> check_c09_frontmatter({'categories': "['추천']", 'tags': "['노트북']"})
        (False, "C09 위반: categories='['추천']' (문자열화된 리스트), ...")
    """
    issues = []
    for field in ('categories', 'tags'):
        val = fm_dict.get(field)
        if val is None:
            continue  # 필드가 없으면 skip
        if isinstance(val, list):
            continue  # 정상 YAML 배열 → 통과
        if isinstance(val, str) and C09_STR_LIST_PATTERN.match(val.strip()):
            issues.append(f"{field}='{val}' (문자열화된 리스트)")
    if issues:
        return False, f"C09 위반: {', '.join(issues)}"
    return True, "C09 통과"


# ── 통합 검사 ──────────────────────────────────────────────────────────


def parse_frontmatter(content: str) -> tuple[str, dict, str]:
    """콘텐츠에서 프론트매터와 본문을 분리.

    핵심: description 값에 '---'가 포함되어 있어도 정확히 분리한다.
    방법: ^---$\\n 패턴(매 줄에 단독 ---)으로 frontmatter 종료 지점을 찾는다.
    단순 str.index('---')는 description 내 '---'를 잘못 찾으므로 사용 금지.

    반환: (frontmatter_str, frontmatter_dict, body_md)
    """
    if not content.startswith('---'):
        return '', {}, content

    # ---로 시작하고 ---로 끝나는 YAML 블록의 끝 위치 찾기
    # 조건: ---가 라인 시작에 단독으로 존재하고, 그 다음 줄이 본문 시작
    # (description 내 ---는 ' --- ' 형태로 주변 문자가 있으므로 구별됨)
    lines = content.split('\n')
    fm_end_line = None
    for i in range(1, len(lines)):
        # 첫 --- 이후 두 번째 '---' 단독 라인 찾기
        if lines[i].strip() == '---':
            fm_end_line = i
            break

    if fm_end_line is None:
        # 두 번째 --- 없음 → 전체 YAML으로 시도
        try:
            fm_dict = _yaml.safe_load(content) or {}
        except _yaml.YAMLError:
            fm_dict = {}
        if not isinstance(fm_dict, dict):
            fm_dict = {}
        return content, fm_dict, ''

    # fm_end_line까지의 내용을 YAML로 파싱 (첫 --- 라인 제외, 종료 --- 라인 제외)
    fm_lines = lines[1:fm_end_line]
    fm_str = '\n'.join(fm_lines)
    body_lines = lines[fm_end_line + 1:]
    body = '\n'.join(body_lines).lstrip('\n')

    # YAML 파싱
    try:
        fm_dict = _yaml.safe_load(fm_str) or {}
    except _yaml.YAMLError:
        fm_dict = {}
    if not isinstance(fm_dict, dict):
        fm_dict = {}

    return fm_str, fm_dict, body


def run_validation(
    dead_links_path: str,
    contamination_path: str,
    dongnam_path: str,
    etap_samples_path: str,
    normal_samples_path: str,
) -> dict:
    """C01~C08 역검증 실행. 결과를 dict로 반환."""

    # 검증 데이터 로드
    with open(dead_links_path) as f:
        dead_links = json.load(f)
    with open(contamination_path) as f:
        contamination = json.load(f)
    with open(dongnam_path) as f:
        dongnam = json.load(f)
    with open(etap_samples_path) as f:
        etap_samples = json.load(f)
    with open(normal_samples_path) as f:
        normal_samples = json.load(f)

    # dead slug 집합 구성 (C07 검사용)
    dead_slugs = set()
    # dead_links: cross_sell_target_slug 기준
    for item in dead_links:
        ts = item.get('cross_sell_target_slug', '')
        if ts:
            dead_slugs.add(ts)
    # contamination에서 추출한 slug (source_file 기반)
    for item in contamination:
        sf = item.get('source_file', '')
        if sf:
            dead_slugs.add(sf.split('/')[-2])
    # dongnam에서 cross_sell_target_slug 기준
    for item in dongnam:
        ts = item.get('target_slug', '')
        if ts:
            dead_slugs.add(ts)

    results = {
        'summary': {},
        'details': {
            'c07_dead_links': [],
            'c07_dongnam': [],
            'c04_contamination': [],
            'c04_etap': [],
            'c01_c02_c03_c05_normal': [],
        },
        'counts': {
            'dead_links_total': len(dead_links),
            'dead_links_detected': 0,
            'contamination_total': len(contamination),
            'contamination_detected': 0,
            'dongnam_total': len(dongnam),
            'dongnam_detected': 0,
            'etap_total': len(etap_samples),
            'etap_false_positives': 0,
            'normal_total': len(normal_samples),
            'normal_false_positives': 0,
        },
    }

    # ── C07: dead_links 검사 ──────────────────────────────────────────
    for item in dead_links:
        sf = item.get('source_file', '')
        try:
            content = open(sf, encoding='utf-8').read()
        except Exception:
            continue
        _, fm_dict, body = parse_frontmatter(content)
        ok, msg = check_c07_body(body, dead_slugs)
        results['details']['c07_dead_links'].append({
            'post_slug': item.get('post_slug', ''),
            'target': item.get('cross_sell_target_slug', ''),
            'expected': 'fail',
            'actual': 'fail' if not ok else 'pass (예상외)',
            'check': msg,
        })
        if not ok:
            results['counts']['dead_links_detected'] += 1

    # ── C07: dongnam 검사 ─────────────────────────────────────────────
    for item in dongnam:
        sf = item.get('source_file', '')
        try:
            content = open(sf, encoding='utf-8').read()
        except Exception:
            continue
        _, fm_dict, body = parse_frontmatter(content)
        ok, msg = check_c07_body(body, dead_slugs)
        results['details']['c07_dongnam'].append({
            'post_slug': item.get('post_slug', ''),
            'target': item.get('target_slug', ''),
            'expected': 'fail',
            'actual': 'fail' if not ok else 'pass (예상외)',
            'check': msg,
        })
        if not ok:
            results['counts']['dongnam_detected'] += 1

    # ── C04: contamination 검사 ───────────────────────────────────────
    for item in contamination:
        sf = item.get('source_file', '')
        try:
            content = open(sf, encoding='utf-8').read()
        except Exception:
            continue
        _, fm_dict, body = parse_frontmatter(content)
        # locale 판단: 영문 패턴 매칭 시도
        ok_en, _ = check_c04_body(body, locale='en')
        ok_ko, _ = check_c04_body(body, locale='ko')
        ok = not (ok_en and ok_ko)  # True = contamination 발견 (둘 중 하나라도 fail)
        results['details']['c04_contamination'].append({
            'post_slug': item.get('post_slug', ''),
            'blog_id': item.get('blog_id', ''),
            'signature': item.get('signature', ''),
            'expected': 'fail',
            'actual': 'fail' if ok else 'pass (예상외)',
            'check': f"C04(en): {'fail' if not ok_en else 'pass'} / C04(ko): {'fail' if not ok_ko else 'pass'}",
        })
        if ok:
            results['counts']['contamination_detected'] += 1

    # ── C04: ETAP 영문 샘플 검사 (오탐 0 기대) ────────────────────────
    for item in etap_samples:
        body = item.get('body_md', '')
        ok, msg = check_c04_body(body, locale='en')
        results['details']['c04_etap'].append({
            'post_slug': item.get('post_slug', ''),
            'blog_id': item.get('blog_id', ''),
            'expected': 'pass',
            'actual': 'pass' if ok else 'fail (오탐)',
            'check': msg,
        })
        if not ok:
            results['counts']['etap_false_positives'] += 1

    # ── C01/C02/C03/C05: 정상글 검사 (오탐 0 기대) ───────────────────
    for item in normal_samples:
        sf = item.get('source_file', '')
        try:
            content = open(sf, encoding='utf-8').read()
        except Exception:
            continue
        fm_str, fm_dict, body = parse_frontmatter(content)

        c01_ok, c01_msg = check_c01_frontmatter(fm_str)
        c02_ok, c02_msg = check_c02_frontmatter(content)
        c03_ok, c03_msg = check_c03_body(body)
        c05_ok, c05_msg = check_c05_frontmatter(fm_dict)

        all_ok = c01_ok and c02_ok and c03_ok and c05_ok
        results['details']['c01_c02_c03_c05_normal'].append({
            'post_slug': item.get('post_slug', ''),
            'blog_id': item.get('blog_id', ''),
            'expected': 'all pass',
            'actual': 'all pass' if all_ok else 'fail (오탐)',
            'c01': c01_msg,
            'c02': c02_msg,
            'c03': c03_msg,
            'c05': c05_msg,
        })
        if not all_ok:
            results['counts']['normal_false_positives'] += 1

    # ── 요약 ──────────────────────────────────────────────────────────
    dl = results['counts']
    results['summary'] = {
        'dead_links_detection_rate': (
            f"{dl['dead_links_detected']}/{dl['dead_links_total']}"
            if dl['dead_links_total'] > 0 else "N/A"
        ),
        'dongnam_detection_rate': (
            f"{dl['dongnam_detected']}/{dl['dongnam_total']}"
            if dl['dongnam_total'] > 0 else "N/A"
        ),
        'contamination_detection_rate': (
            f"{dl['contamination_detected']}/{dl['contamination_total']}"
            if dl['contamination_total'] > 0 else "N/A"
        ),
        'etap_false_positive_rate': (
            f"{dl['etap_false_positives']}/{dl['etap_total']}"
            if dl['etap_total'] > 0 else "N/A"
        ),
        'normal_false_positive_rate': (
            f"{dl['normal_false_positives']}/{dl['normal_total']}"
            if dl['normal_total'] > 0 else "N/A"
        ),
    }

    return results


# ── 단위 테스트 ──────────────────────────────────────────────────────────


def test_functions():
    """판정 함수 단위 테스트"""
    tests_passed = 0
    tests_failed = 0

    def check(name, actual, expected):
        nonlocal tests_passed, tests_failed
        if actual == expected:
            tests_passed += 1
            print(f"  ✅ {name}")
        else:
            tests_failed += 1
            print(f"  ❌ {name}: 기대={expected}, 실제={actual}")

    # C01: 곡선따옴표
    ok, msg = check_c01_frontmatter("title: '정상제목'")
    check("C01 직선따옴표 통과", ok, True)
    ok, msg = check_c01_frontmatter("title: '\u2018곡선\u2019'")
    check("C01 곡선따옴표 fail", ok, False)

    # C02: 프론트매터 미종료
    ok, msg = check_c02_frontmatter("---\ntitle: 홍길동\n---\n본문")
    check("C02 정상 통과", ok, True)
    ok, msg = check_c02_frontmatter("---\ntitle: 홍길동\n본문")
    check("C02 미종료 fail", ok, False)
    # 본문 내 --- 수평선 있어도 통과해야 함
    ok, msg = check_c02_frontmatter("---\ntitle: 홍길동\n---\n본문\n---\n수평선")
    check("C02 본문 --- 있어도 통과", ok, True)

    # C03: 프론트매터 키 유출
    ok, msg = check_c03_body("본문 내용입니다")
    check("C03 정상 통과", ok, True)
    ok, msg = check_c03_body("title: 유출된제목\n본문")
    check("C03 키 유출 fail", ok, False)

    # C04: 프롬프트 누수
    ok, msg = check_c04_body("이것은 정상 본문입니다", locale='ko')
    check("C04 국문 정상 통과", ok, True)
    ok, msg = check_c04_body("먼저 생각해보겠습니다", locale='ko')
    check("C04 국문 누수 fail", ok, False)
    ok, msg = check_c04_body("This is normal English body.", locale='en')
    check("C04 영문 정상 통과", ok, True)
    ok, msg = check_c04_body("We need to write the content", locale='en')
    check("C04 영문 누수 fail", ok, False)

    # C05: draft:true
    ok, msg = check_c05_frontmatter({'draft': False})
    check("C05 draft:false 통과", ok, True)
    ok, msg = check_c05_frontmatter({'draft': True})
    check("C05 draft:true fail", ok, False)

    # C07: 죽은 크로스셀 링크
    ok, msg = check_c07_body('<a href="https://kitchen.informationhot.kr/posts/죽은-slug/">링크</a>',
                              known_dead_slugs={'죽은-slug'})
    check("C07 죽은 링크 fail", ok, False)
    ok, msg = check_c07_body('<a href="https://kitchen.informationhot.kr/posts/살아있는-slug/">링크</a>',
                              known_dead_slugs={'죽은-slug'})
    check("C07 정상 링크 통과", ok, True)

    print(f"\n단위 테스트: {tests_passed} 통과 / {tests_failed} 실패")
    return tests_failed == 0


# ── CLI ──────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description='C01~C08 역검증 스크립트')
    parser.add_argument('--dead-links', default='scripts/c01_c08_validation_data/dead_links.json')
    parser.add_argument('--contamination', default='scripts/c01_c08_validation_data/contamination.json')
    parser.add_argument('--dongnam', default='scripts/c01_c08_validation_data/dongnam_npmb.json')
    parser.add_argument('--etap-samples', default='scripts/c01_c08_validation_data/etap_english_samples.json')
    parser.add_argument('--normal-samples', default='scripts/c01_c08_validation_data/normal_samples.json')
    parser.add_argument('--test-functions', action='store_true', help='단위 테스트 실행')
    args = parser.parse_args()

    if args.test_functions:
        success = test_functions()
        sys.exit(0 if success else 1)

    # 파일 존재 확인
    for path, name in [
        (args.dead_links, 'dead_links'),
        (args.contamination, 'contamination'),
        (args.dongnam, 'dongnam'),
        (args.etap_samples, 'etap_samples'),
        (args.normal_samples, 'normal_samples'),
    ]:
        if not Path(path).exists():
            print(f"❌ {name} 파일 없음: {path}")
            sys.exit(1)

    print("=" * 60)
    print("  C01~C08 역검증 실행")
    print("=" * 60)
    print()

    results = run_validation(
        args.dead_links,
        args.contamination,
        args.dongnam,
        args.etap_samples,
        args.normal_samples,
    )

    s = results['summary']
    c = results['counts']

    print(f"  📋 검증 데이터")
    print(f"     dead_links:    {c['dead_links_total']}건")
    print(f"     contamination: {c['contamination_total']}건")
    print(f"     dongnam:       {c['dongnam_total']}건")
    print(f"     ETAP 영문:     {c['etap_total']}건")
    print(f"     정상글:        {c['normal_total']}건")
    print()
    print(f"  🔍 판정 결과")
    print(f"     C07 dead_links 검출:    {s['dead_links_detection_rate']} "
          f"{'✅' if c['dead_links_detected'] == c['dead_links_total'] and c['dead_links_total'] > 0 else '❌'}")
    print(f"     C07 dongnam 검출:       {s['dongnam_detection_rate']} "
          f"{'✅' if c['dongnam_detected'] == c['dongnam_total'] and c['dongnam_total'] > 0 else '❌'}")
    print(f"     C04 contamination 검출: {s['contamination_detection_rate']} "
          f"{'✅' if c['contamination_detected'] == c['contamination_total'] and c['contamination_total'] > 0 else '❌'}")
    print(f"     C04 ETAP 오탐:          {s['etap_false_positive_rate']} "
          f"{'✅ 오탐 0' if c['etap_false_positives'] == 0 else '❌ 오탐 있음'}")
    print(f"     C01/C02/C03/C05 정상글 오탐: {s['normal_false_positive_rate']} "
          f"{'✅ 오탐 0' if c['normal_false_positives'] == 0 else '❌ 오탐 있음'}")
    print()

    # 상세 실패 목록
    if results['details']['c07_dead_links']:
        failed_dl = [d for d in results['details']['c07_dead_links'] if d['actual'] != 'fail']
        if failed_dl:
            print(f"  ⚠️  dead_links 미탐지 (예상: fail, 실제: pass): {len(failed_dl)}건")
            for d in failed_dl[:5]:
                print(f"     - {d['post_slug']} → {d['target']}")

    if results['details']['c07_dongnam']:
        failed_dn = [d for d in results['details']['c07_dongnam'] if d['actual'] != 'fail']
        if failed_dn:
            print(f"  ⚠️  dongnam 미탐지 (예상: fail, 실제: pass): {len(failed_dn)}건")
            for d in failed_dn[:5]:
                print(f"     - {d['post_slug']} → {d['target']}")

    if results['details']['c04_contamination']:
        failed_ct = [d for d in results['details']['c04_contamination'] if d['actual'] != 'fail']
        if failed_ct:
            print(f"  ⚠️  contamination 미탐지 (예상: fail, 실제: pass): {len(failed_ct)}건")
            for d in failed_ct[:5]:
                print(f"     - {d['blog_id']}/{d['post_slug']} ({d['signature']})")

    if results['details']['c04_etap']:
        failed_etap = [d for d in results['details']['c04_etap'] if d['actual'] != 'pass']
        if failed_etap:
            print(f"  ⚠️  ETAP 영문 오탐 (예상: pass, 실제: fail): {len(failed_etap)}건")
            for d in failed_etap[:5]:
                print(f"     - {d['blog_id']}/{d['post_slug']}: {d['check']}")

    if results['details']['c01_c02_c03_c05_normal']:
        failed_normal = [d for d in results['details']['c01_c02_c03_c05_normal'] if d['actual'] != 'all pass']
        if failed_normal:
            print(f"  ⚠️  정상글 오탐 (예상: all pass, 실제: fail): {len(failed_normal)}건")
            for d in failed_normal[:5]:
                print(f"     - {d['blog_id']}/{d['post_slug']}: {d['c01']}/{d['c02']}/{d['c03']}/{d['c05']}")

    print()
    print("=" * 60)

    # 최종 판정
    dl_ok = c['dead_links_detected'] == c['dead_links_total'] and c['dead_links_total'] > 0
    dn_ok = c['dongnam_detected'] == c['dongnam_total'] and c['dongnam_total'] > 0
    ct_ok = c['contamination_detected'] == c['contamination_total'] and c['contamination_total'] > 0
    etap_ok = c['etap_false_positives'] == 0
    normal_ok = c['normal_false_positives'] == 0

    all_ok = dl_ok and dn_ok and ct_ok and etap_ok and normal_ok

    if all_ok:
        print("  ✅ 결과: 전건 탐지 + 오탐 0 → 다음 단계(62-02 INSERT) 진행 가능")
    else:
        print("  ❌ 결과: 조건 미달 — INSERT 보류, 조건 수정 후 재검증 필요")
        if not dl_ok:
            print(f"     - dead_links: {c['dead_links_detected']}/{c['dead_links_total']} 검출")
        if not dn_ok:
            print(f"     - dongnam: {c['dongnam_detected']}/{c['dongnam_total']} 검출")
        if not ct_ok:
            print(f"     - contamination: {c['contamination_detected']}/{c['contamination_total']} 검출")
        if not etap_ok:
            print(f"     - ETAP 영문 오탐: {c['etap_false_positives']}/{c['etap_total']}")
        if not normal_ok:
            print(f"     - 정상글 오탐: {c['normal_false_positives']}/{c['normal_total']}")

    print("=" * 60)

    # JSON 결과 저장
    out_path = 'scripts/c01_c08_validation_data/validation_result.json'
    with open(out_path, 'w') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n  결과 저장: {out_path}")

    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
