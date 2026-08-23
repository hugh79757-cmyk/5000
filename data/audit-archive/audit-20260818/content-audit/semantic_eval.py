#!/usr/bin/env python3
"""semantic_eval.py — 배치별 의미·콘텐츠 품질 평가 (읽기 전용, 로컬 md 기반)
평가 스키마 (합계 100): 제목 20 / 정보 25 / 검색의도 15 / 구조·읽기 15 / 신뢰성 10 / 내부링크 10 / 광고 5
사용법: python3 semantic_eval.py batch_00.json [batch_01.json ...] --out results/
"""
import json, sys, re, hashlib, os

def norm(s):
    return re.sub(r'\s+', ' ', (s or '')).strip()

def load_batch(path):
    return json.load(open(path, encoding='utf-8'))

def parse_md(filepath):
    """--- frontmatter + 본문 분리"""
    try:
        txt = open(filepath, encoding='utf-8').read()
    except Exception:
        return None, None, None
    m = re.match(r'^---\n(.*?)\n---\n?(.*)$', txt, re.S)
    if not m:
        return None, None, txt
    fm, body = m.group(1), m.group(2)
    title = None
    for line in fm.splitlines():
        if line.startswith('title:'):
            title = line.split(':', 1)[1].strip().strip('"\'')
    return fm, title, body

def eval_post(sample):
    """단일 표본 평가 — 기계적 규칙 기반, 의미적 판단은 UNVERIFIED"""
    blog, slug = sample['blog'], sample['slug']
    url = sample.get('url', '')
    mech = sample.get('mech', {}) or {}
    filepath = sample.get('file', '')
    fm, title, body = parse_md(filepath)

    result = {
        'blog': blog, 'slug': slug, 'url': url, 'file': filepath,
        'frozen': mech.get('frozen', False),
        'remediation_status': 'FROZEN_UNTIL_SITEMAP_EXPERIMENT_COMPLETE' if mech.get('frozen') else 'NONE',
    }

    # --- 제목 품질 (20) ---
    t = mech.get('title') or title or ''
    tlen = mech.get('title_len', len(t or ''))
    title_score = 20
    title_notes = []
    if mech.get('title_flag') == 'LONG_TITLE':
        title_score -= 6; title_notes.append('LONG_TITLE(>60자)')
    if mech.get('title_flag') == 'SHORT_TITLE':
        title_score -= 4; title_notes.append('SHORT_TITLE(<10자)')
    # 숫자/연도 포함 여부 (구체성)
    if not re.search(r'\d', t or ''):
        title_score -= 2; title_notes.append('숫자/연도 없음')
    if not t or t == slug:
        title_score = 0; title_notes.append('제목 없음/슬러그 동일')
    result['title_score'] = max(0, title_score)
    result['title_notes'] = title_notes

    # --- 정보 품질 (25) — 로컬에서 검증 가능한 것만 ---
    body_len = mech.get('body_len', len(body or ''))
    info_score = 25
    info_notes = []
    if mech.get('body_flag') == 'TOO_SHORT':
        info_score -= 15; info_notes.append(f'TOO_SHORT({body_len}B)')
    elif mech.get('body_flag') == 'SHORT':
        info_score -= 8; info_notes.append(f'SHORT({body_len}B)')
    if mech.get('template_flag') == 'TEMPLATE_LEAK':
        info_score -= 10; info_notes.append('TEMPLATE_LEAK(원본 템플릿 잔여)')
    result['info_score'] = max(0, info_score)
    result['info_notes'] = info_notes

    # --- 검색 의도 충족 (15) — 로컬 근거 한정, 의미 판단은 UNVERIFIED ---
    intent_score = 15
    intent_notes = []
    if body and len(body) < 1500:
        intent_score -= 5; intent_notes.append('본문 짧아 의도 충족 판단 어려움')
    result['intent_score'] = max(0, intent_score)
    result['intent_notes'] = intent_notes
    result['intent_verification'] = 'UNVERIFIED'  # 의미적 판단은 자동 검증 불가

    # --- 구조·읽기 경험 (15) ---
    struct_score = 15
    struct_notes = []
    h2 = mech.get('h2_count', 0) or 0
    if mech.get('h2_flag') == 'NO_H2':
        struct_score -= 6; struct_notes.append('NO_H2(섹션 헤더 없음)')
    if h2 < 3:
        struct_score -= 2; struct_notes.append(f'H2 {h2}개(3개 미만)')
    if not mech.get('has_date'):
        struct_score -= 2; struct_notes.append('date 없음')
    if not mech.get('has_desc'):
        struct_score -= 2; struct_notes.append('description 없음')
    result['struct_score'] = max(0, struct_score)
    result['struct_notes'] = struct_notes

    # --- 신뢰성·안전성 (10) ---
    trust_score = 10
    trust_notes = []
    b = body or ''
    # 과장 표현 탐지
    hype = re.findall(r'(최고의|최강|100%|무조건|완벽한|반드시|절대적|특효|치료|완치|의학적 효능)', b)
    if hype:
        trust_score -= 4; trust_notes.append(f'과장/절대 표현 {len(hype)}건: {sorted(set(hype))[:4]}')
    # 저작권 위험 시그널 (외부 블로그 전문 복사 추정 불가 — 로컬로는 UNVERIFIED)
    trust_notes.append('의료 효능·저작권 판단은 로컬 근거 한정')
    result['trust_score'] = max(0, trust_score)
    result['trust_notes'] = trust_notes
    result['trust_verification'] = 'UNVERIFIED'

    # --- 내부 링크 (10) ---
    link_score = 10
    link_notes = []
    il = mech.get('internal_links', 0) or 0
    el = mech.get('external_links', 0) or 0
    if il == 0:
        link_score -= 6; link_notes.append('내부 링크 0건(오펀 위험)')
    elif il < 2:
        link_score -= 3; link_notes.append(f'내부 링크 {il}건(2건 미만)')
    if el == 0:
        link_score -= 2; link_notes.append('외부 링크 0건')
    result['link_score'] = max(0, link_score)
    result['link_notes'] = link_notes

    # --- 광고·페이지 경험 (5) — 로컬 md로는 광고 배치 미검증 ---
    ad_score = 5
    ad_notes = ['광고 배치는 HTML 렌더 검증 필요 — 로컬 md 한정']
    result['ad_score'] = max(0, ad_score)
    result['ad_notes'] = ad_notes
    result['ad_verification'] = 'UNVERIFIED'

    # --- 총점 + 치명적 문제 ---
    total = (result['title_score'] + result['info_score'] + result['intent_score']
             + result['struct_score'] + result['trust_score'] + result['link_score']
             + result['ad_score'])
    result['total_score'] = total
    critical = []
    if mech.get('template_flag') == 'TEMPLATE_LEAK':
        critical.append('TEMPLATE_LEAK')
    if mech.get('body_flag') == 'TOO_SHORT':
        critical.append('EMPTY_OR_TOO_SHORT_BODY')
    if mech.get('frozen'):
        critical.append('FROZEN_EXPERIMENT_URL')
    result['critical_issues'] = critical
    result['human_review_required'] = bool(critical)
    return result

def main():
    out_dir = 'results'
    if '--out' in sys.argv:
        i = sys.argv.index('--out')
        out_dir = sys.argv[i + 1]
        del sys.argv[i:i + 2]
    batches = [a for a in sys.argv[1:] if a.endswith('.json')]
    os.makedirs(out_dir or 'results', exist_ok=True)
    total_ok, total_fail = 0, 0
    all_results = []
    for bp in batches:
        try:
            samples = load_batch(bp)
        except Exception as e:
            print(f'FETCH_FAILED {bp}: {e}')
            continue
        for s in samples:
            r = eval_post(s)
            all_results.append(r)
            total_ok += 1
        base = os.path.basename(bp).replace('.json', '')
        with open(os.path.join(out_dir or 'results', f'{base}_results.jsonl'), 'w', encoding='utf-8') as f:
            for r in all_results:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
    # 요약
    if all_results:
        avg = sum(r['total_score'] for r in all_results) / len(all_results)
        crit = sum(1 for r in all_results if r['human_review_required'])
        print(f'PROCESSED={total_ok} FAILED={total_fail} AVG={avg:.1f} CRITICAL={crit}')
        for r in sorted(all_results, key=lambda x: x['total_score'])[:5]:
            print(f"  LOW {r['blog']}/{r['slug'][:30]} score={r['total_score']} crit={r['critical_issues']}")
    else:
        print('PROCESSED=0')

if __name__ == '__main__':
    main()