#!/usr/bin/env python3
"""
rule_reverse_validate.py — 범용 규칙 역검증 스크립트

기존 `scripts/c01_c08_reverse_validation.py`를 일반화:
- 특정 규칙(C01~C09) 하드코딩 제거
- `--rule-id`로 대상 규칙 지정
- `--positive-dir` (위반 샘플 디렉토리) / `--negative-dir` (정상 샘플 디렉토리)로 검증 데이터 입력
- 게이트: 양성 전건 탐지(100%) + 음성 오탐 0건 → exit 0, 그 외 → exit 1 + 리포트 테이블

사용 예시:
    # C01 데모 데이터로 검증
    python scripts/rule_reverse_validate.py \
        --rule-id C01 \
        --positive-dir scripts/c01_c08_validation_data/c01_demo_positive \
        --negative-dir scripts/c01_c08_validation_data/c01_demo_negative

    # 신규 규칙 S01 검증
    python scripts/rule_reverse_validate.py \
        --rule-id S01 \
        --positive-dir scripts/validation_data/S01/positive \
        --negative-dir scripts/validation_data/S01/negative
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Callable

import yaml as _yaml

# ─────────────────────────────────────────────────────────────────────────────
# 규칙별 판정 함수 레지스트리 (기존 c01_c08_reverse_validation.py에서 추출)
# ─────────────────────────────────────────────────────────────────────────────

# C01: 프론트매터 내 곡선따옴표
CURVED_SINGLE = {'\u2018', '\u2019'}
CURVED_DOUBLE = {'\u201c', '\u201d'}


def check_c01_frontmatter(frontmatter: str) -> tuple[bool, str]:
    fm_check = frontmatter
    found = []
    if any(c in fm_check for c in CURVED_SINGLE):
        found.append("곡선따옴표(' ')")
    if any(c in fm_check for c in CURVED_DOUBLE):
        found.append('곡선따옴표(" ")')
    if found:
        return False, f"C01 위반: {', '.join(found)}"
    return True, "C01 통과"


# C02: 프론트매터 미종료 (첫 --- 이후 두 번째 --- 존재 여부)
def check_c02_frontmatter(full_content: str) -> tuple[bool, str]:
    lines = full_content.split('\n')
    first_dash_idx = None
    second_dash_idx = None
    for i, line in enumerate(lines):
        if line.strip() == '---':
            if first_dash_idx is None:
                first_dash_idx = i
            elif second_dash_idx is None and i > first_dash_idx:
                second_dash_idx = i
                break
    if first_dash_idx is None:
        return False, "C02 위반: 첫 --- 없음"
    if second_dash_idx is None:
        return False, "C02 위반: 첫 --- 이후 두 번째 --- 없음"
    return True, "C02 통과"


# C03: 본문에 프론트매터 키 라인 유출
FM_KEY_PATTERN = re.compile(
    r'^\s*(title|og_image|featureimage|date|slug|categories|tags|'
    r'description|draft|image|pubDate|author|cover):'
)


def check_c03_body(body_md: str) -> tuple[bool, str]:
    leaked = []
    for line in body_md.split('\n'):
        if FM_KEY_PATTERN.match(line):
            leaked.append(line.strip()[:80])
    if leaked:
        return False, f"C03 위반: 프론트매터 키 유출 {len(leaked)}건 — {leaked[0]}"
    return True, "C03 통과"


# C04: 본문 LLM 프롬프트/사고문 누수 (국문 + 영문)
KO_PATTERNS = [
    re.compile(r'먼저\s*생각', re.I),
    re.compile(r'생각해보자|생각해\s*보자', re.I),
    re.compile(r'다음\s*단계', re.I),
    re.compile(r'단계별로', re.I),
    re.compile(r'우선\s*', re.I),
    re.compile(r'우리가\s*해야\s*할', re.I),
    re.compile(r'필요한\s*것', re.I),
    re.compile(r'생각\s*해보자', re.I),
    re.compile(r'(?:^|\n)\s*주의:', re.M),
]

EN_PATTERNS = [
    re.compile(r'\bNeed\s+think\b', re.I),
    re.compile(r'\bWe\s+need\s+to\s+write\b', re.I),
    re.compile(r"Let\.?s\s+think\s+step\s+by\s+step", re.I),
    re.compile(r'think\s+step\s+by\s+step', re.I),
    re.compile(r"let\.?s\s+break\s+this\s+down", re.I),
    re.compile(r"here\.?s?\s+the\s+plan", re.I),
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
    patterns = EN_PATTERNS if locale == 'en' else KO_PATTERNS
    found = []
    for pat in patterns:
        m = pat.search(body_md)
        if m:
            found.append(m.group()[:50])
    if found:
        return False, f"C04 위반({locale}): 프롬프트 누수 패턴 {len(found)}건 — {found[0]}"
    return True, f"C04 통과({locale})"


# C05: draft:true 발행 대상
def check_c05_frontmatter(frontmatter_dict: dict) -> tuple[bool, str]:
    draft_val = frontmatter_dict.get('draft', None)
    if draft_val is None:
        return True, "C05 통과 (draft 키 없음)"
    if draft_val is True:
        return False, "C05 위반: draft:true 발행 대상 (boolean)"
    if isinstance(draft_val, str) and draft_val.strip().lower() == 'true':
        return False, "C05 위반: draft:true 발행 대상 (문자열)"
    return True, "C05 통과"


# C06: 로컬 mtime > 배포 시각 (역검증에서는 skip)
def check_c06_file(file_path: str, last_deploy_at: str) -> tuple[bool, str]:
    return True, "C06 skip (역검증 범위 외)"


# C07: 죽은 크로스셀 링크
C07_SLUG_PATTERN = re.compile(
    r'href=(?:"|\\")https://([\w-]+)\.informationhot\.kr/posts/(.+?)/(?:"|\\")'
)


def check_c07_body(body_md: str, known_dead_slugs: set[str]) -> tuple[bool, str]:
    dead_found = []
    for m in C07_SLUG_PATTERN.finditer(body_md):
        target_slug = m.group(2)
        if target_slug in known_dead_slugs:
            dead_found.append(target_slug)
    if dead_found:
        return False, f"C07 위반: 죽은 크로스셀 링크 {len(dead_found)}건 — {dead_found[0]}"
    return True, "C07 통과"


# C08: 라이브-파일 불일치 (placeholder)
def check_c08_placeholder(*args, **kwargs) -> tuple[bool, str]:
    return True, "C08 skip (라이브 비교 API 필요, placeholder)"


# C09: categories/tags 문자열화 탐지
C09_STR_LIST_PATTERN = re.compile(r'^\[\s*[\'"].*[\'"]\s*\]$')


def check_c09_frontmatter(fm_dict: dict) -> tuple[bool, str]:
    issues = []
    for field in ('categories', 'tags'):
        val = fm_dict.get(field)
        if val is None:
            continue
        if isinstance(val, list):
            continue
        if isinstance(val, str) and C09_STR_LIST_PATTERN.match(val.strip()):
            issues.append(f"{field}='{val}' (문자열화된 리스트)")
    if issues:
        return False, f"C09 위반: {', '.join(issues)}"
    return True, "C09 통과"


# ─────────────────────────────────────────────────────────────────────────────
# 프론트매터 파싱 (기존 코드 재사용)
# ─────────────────────────────────────────────────────────────────────────────

def parse_frontmatter(content: str) -> tuple[str, dict, str]:
    """콘텐츠에서 프론트매터와 본문 분리. description 내 --- 처리 안전."""
    if not content.startswith('---'):
        return '', {}, content

    lines = content.split('\n')
    fm_end_line = None
    for i in range(1, len(lines)):
        if lines[i].strip() == '---':
            fm_end_line = i
            break

    if fm_end_line is None:
        try:
            fm_dict = _yaml.safe_load(content) or {}
        except _yaml.YAMLError:
            fm_dict = {}
        if not isinstance(fm_dict, dict):
            fm_dict = {}
        return content, fm_dict, ''

    fm_lines = lines[1:fm_end_line]
    fm_str = '\n'.join(fm_lines)
    body_lines = lines[fm_end_line + 1:]
    body = '\n'.join(body_lines).lstrip('\n')

    try:
        fm_dict = _yaml.safe_load(fm_str) or {}
    except _yaml.YAMLError:
        fm_dict = {}
    if not isinstance(fm_dict, dict):
        fm_dict = {}

    return fm_str, fm_dict, body


# ─────────────────────────────────────────────────────────────────────────────
# 규칙별 검증 함수 매핑
# ─────────────────────────────────────────────────────────────────────────────

RULE_CHECKERS: dict[str, Callable] = {
    'C01': lambda fm_str, fm_dict, body, **kw: check_c01_frontmatter(fm_str),
    'C02': lambda fm_str, fm_dict, body, **kw: check_c02_frontmatter(fm_str + '\n---\n' + body),
    'C03': lambda fm_str, fm_dict, body, **kw: check_c03_body(body),
    'C04': lambda fm_str, fm_dict, body, **kw: check_c04_body(body, kw.get('locale', 'ko')),
    'C05': lambda fm_str, fm_dict, body, **kw: check_c05_frontmatter(fm_dict),
    'C06': lambda fm_str, fm_dict, body, **kw: check_c06_file('', ''),
    'C07': lambda fm_str, fm_dict, body, **kw: check_c07_body(body, kw.get('dead_slugs', set())),
    'C08': lambda fm_str, fm_dict, body, **kw: check_c08_placeholder(),
    'C09': lambda fm_str, fm_dict, body, **kw: check_c09_frontmatter(fm_dict),
}


def get_checker(rule_id: str) -> Callable:
    """규칙 ID로 판정 함수 조회. 미구현 규칙은 통과 반환 placeholder."""
    if rule_id in RULE_CHECKERS:
        return RULE_CHECKERS[rule_id]
    # 신규 규칙(S01, L01 등)은 사용자 구현 필요 — 여기선 통과 반환하며 경고
    def placeholder(fm_str, fm_dict, body, **kw):
        return True, f"{rule_id} 미구현 (placeholder 통과)"
    return placeholder


# ─────────────────────────────────────────────────────────────────────────────
# 검증 실행
# ─────────────────────────────────────────────────────────────────────────────

def load_samples(dir_path: Path) -> list[dict]:
    """디렉토리 내 모든 .md/.json 파일을 샘플로 로드."""
    samples = []
    for ext in ('.md', '.json'):
        for f in dir_path.glob(f'*{ext}'):
            try:
                if ext == '.json':
                    with open(f, encoding='utf-8') as fp:
                        data = json.load(fp)
                        if isinstance(data, list):
                            samples.extend(data)
                        else:
                            samples.append(data)
                else:
                    content = f.read_text(encoding='utf-8')
                    samples.append({'source_file': str(f), 'content': content, 'post_slug': f.stem})
            except Exception as e:
                print(f"  ⚠️  로드 실패: {f} — {e}", file=sys.stderr)
    return samples


def run_validation(
    rule_id: str,
    positive_dir: Path,
    negative_dir: Path,
    **checker_kwargs
) -> dict:
    """단일 규칙에 대한 역검증 실행."""

    checker = get_checker(rule_id)

    pos_samples = load_samples(positive_dir)
    neg_samples = load_samples(negative_dir)

    results = {
        'rule_id': rule_id,
        'summary': {},
        'details': {'positive': [], 'negative': []},
        'counts': {
            'positive_total': len(pos_samples),
            'positive_detected': 0,
            'negative_total': len(neg_samples),
            'negative_false_positives': 0,
        },
    }

    # ── 양성 샘플: 전건 탐지 기대 (fail 반환 = 탐지 성공) ──────────────────
    for sample in pos_samples:
        content = sample.get('content', '')
        fm_str, fm_dict, body = parse_frontmatter(content)
        ok, msg = checker(fm_str, fm_dict, body, **checker_kwargs)
        detected = not ok  # fail = 위반 탐지 = 성공
        results['details']['positive'].append({
            'source': sample.get('source_file', sample.get('post_slug', 'unknown')),
            'expected': 'fail (탐지)',
            'actual': 'fail (탐지됨)' if detected else 'pass (미탐지 ❌)',
            'check': msg,
        })
        if detected:
            results['counts']['positive_detected'] += 1

    # ── 음성 샘플: 오탐 0 기대 (pass 반환 = 정상 = 성공) ──────────────────
    for sample in neg_samples:
        content = sample.get('content', '')
        fm_str, fm_dict, body = parse_frontmatter(content)
        ok, msg = checker(fm_str, fm_dict, body, **checker_kwargs)
        false_positive = not ok  # fail = 오탐
        results['details']['negative'].append({
            'source': sample.get('source_file', sample.get('post_slug', 'unknown')),
            'expected': 'pass (정상)',
            'actual': 'pass (정상)' if ok else 'fail (오탐 ❌)',
            'check': msg,
        })
        if false_positive:
            results['counts']['negative_false_positives'] += 1

    # ── 요약 ──────────────────────────────────────────────────────────────
    c = results['counts']
    pos_rate = f"{c['positive_detected']}/{c['positive_total']}" if c['positive_total'] > 0 else "N/A"
    neg_rate = f"{c['negative_false_positives']}/{c['negative_total']}" if c['negative_total'] > 0 else "N/A"

    results['summary'] = {
        'positive_detection_rate': pos_rate,
        'negative_false_positive_rate': neg_rate,
        'gate_passed': (
            c['positive_detected'] == c['positive_total'] and c['positive_total'] > 0
            and c['negative_false_positives'] == 0
        ),
    }

    return results


def print_report(results: dict) -> None:
    """검증 결과 콘솔 출력."""
    r = results
    c = r['counts']
    s = r['summary']

    print("=" * 60)
    print(f"  {r['rule_id']} 역검증 결과")
    print("=" * 60)
    print()
    print(f"  📋 검증 데이터")
    print(f"     양성(위반) 샘플:  {c['positive_total']}건")
    print(f"     음성(정상) 샘플:  {c['negative_total']}건")
    print()
    print(f"  🔍 판정 결과")
    print(f"     양성 탐지율:       {s['positive_detection_rate']} "
          f"{'✅' if c['positive_detected'] == c['positive_total'] and c['positive_total'] > 0 else '❌'}")
    print(f"     음성 오탐율:       {s['negative_false_positive_rate']} "
          f"{'✅ 오탐 0' if c['negative_false_positives'] == 0 else '❌ 오탐 있음'}")
    print()

    # 실패 상세
    if r['details']['positive']:
        missed = [d for d in r['details']['positive'] if d['actual'] != 'fail (탐지됨)']
        if missed:
            print(f"  ⚠️  양성 미탐지 (예상: fail, 실제: pass): {len(missed)}건")
            for d in missed[:5]:
                print(f"     - {d['source']}: {d['check']}")

    if r['details']['negative']:
        false_pos = [d for d in r['details']['negative'] if d['actual'] != 'pass (정상)']
        if false_pos:
            print(f"  ⚠️  음성 오탐 (예상: pass, 실제: fail): {len(false_pos)}건")
            for d in false_pos[:5]:
                print(f"     - {d['source']}: {d['check']}")

    print()
    print("=" * 60)

    if s['gate_passed']:
        print("  ✅ 결과: 전건 탐지 + 오탐 0 → 게이트 통과")
    else:
        print("  ❌ 결과: 게이트 미달 — 규칙 로직 수정 또는 검증 데이터 보강 필요")
        if c['positive_detected'] != c['positive_total'] or c['positive_total'] == 0:
            print(f"     - 양성 탐지: {c['positive_detected']}/{c['positive_total']} (100% 필요)")
        if c['negative_false_positives'] != 0:
            print(f"     - 음성 오탐: {c['negative_false_positives']}건 (0건 필요)")

    print("=" * 60)


def save_result(results: dict, rule_id: str) -> Path:
    """결과 JSON 저장."""
    out_dir = Path(f'scripts/validation_data/{rule_id}')
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / 'validation_result.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    return out_path


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='범용 규칙 역검증: 양성 전건탐지 + 음성 오탐0 게이트')
    parser.add_argument('--rule-id', required=True, help='검증 대상 규칙 ID (예: C01, S01, L01)')
    parser.add_argument('--positive-dir', required=True, type=Path, help='양성(위반) 샘플 디렉토리')
    parser.add_argument('--negative-dir', required=True, type=Path, help='음성(정상) 샘플 디렉토리')
    parser.add_argument('--locale', default='ko', choices=['ko', 'en'], help='C04 등 로케일 의존 규칙용')
    parser.add_argument('--dead-slugs', help='C07용 dead slug 목록 (쉼표 구분)', default='')
    args = parser.parse_args()

    # 디렉토리 존재 확인
    for path, name in [(args.positive_dir, 'positive-dir'), (args.negative_dir, 'negative-dir')]:
        if not path.exists():
            print(f"❌ {name} 디렉토리 없음: {path}")
            sys.exit(1)
        if not path.is_dir():
            print(f"❌ {name}이 디렉토리가 아님: {path}")
            sys.exit(1)

    checker_kwargs = {}
    if args.rule_id == 'C04':
        checker_kwargs['locale'] = args.locale
    if args.rule_id == 'C07' and args.dead_slugs:
        checker_kwargs['dead_slugs'] = set(s.strip() for s in args.dead_slugs.split(',') if s.strip())

    print("=" * 60)
    print(f"  {args.rule_id} 역검증 실행")
    print("=" * 60)
    print()

    results = run_validation(
        args.rule_id,
        args.positive_dir,
        args.negative_dir,
        **checker_kwargs
    )

    print_report(results)
    out_path = save_result(results, args.rule_id)
    print(f"\n  결과 저장: {out_path}")

    sys.exit(0 if results['summary']['gate_passed'] else 1)


if __name__ == '__main__':
    main()