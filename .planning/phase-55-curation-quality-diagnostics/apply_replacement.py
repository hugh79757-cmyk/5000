#!/usr/bin/env python3
"""Q3 자동 치환 스크립트 — 안전 패턴만 적용

치환 규칙:
  1. "도움이 됩니다" → "도움이 될 수 있습니다"
  2. "도움을 줍니다" → "도움을 줄 수 있습니다"

그 외 패턴은 수동 확인 대상으로 자동 치환하지 않음.
"""
import re
import sys
import json
import hashlib
from pathlib import Path

CUAP = Path("/Users/twinssn/Projects/CUAP")

# 자동 치환 규칙 (✅ 안전 — 맥락 독립적)
AUTO_RULES = [
    (re.compile(r'도움이\s*됩니다'), '도움이 될 수 있습니다'),
    (re.compile(r'도움을\s*줍니다'), '도움을 줄 수 있습니다'),
    (re.compile(r'도움이\s*됩니다'), '도움이 될 수 있습니다'),  # 중복 방지
    (re.compile(r'도움을\s*줍니다'), '도움을 줄 수 있습니다'),  # 중복 방지
]

# 수동 확인 대상 패턴 (⚠️ — 치환하지 않음, 목록에만 기록)
MANUAL_PATTERNS = [
    re.compile(r'개선[된된다됩니다]+'),
    re.compile(r'향상[된된다됩니다]+'),
    re.compile(r'탄력[을을이가 ]{0,2}(더해|생기|있|좋|강화)'),
    re.compile(r'환해[집니다지다]+'),
    re.compile(r'피부가\s*(환하게|맑게|깨끗하게|개선)'),
    re.compile(r'활력[을을이가 ]{0,2}(더하|주|있|줄|생기)'),
    re.compile(r'기억력[을을이가 ]{0,2}(개선|향상|좋|나쁨|도움)'),
    re.compile(r'집중력[을을이가 ]{0,2}(개선|향상|좋|나쁨|도움)'),
    re.compile(r'완화[한다됩니다]+'),
    re.compile(r'치료[한다됩니다]+'),
    re.compile(r'예방[한다됩니다]+'),
    re.compile(r'효과[가이가 ]{0,2}(있습니다|있다|있는)'),
]


def apply_auto_rules(text):
    """안전 패턴만 자동 치환, 변경 사항 리스트 반환"""
    changes = []
    for pattern, replacement in AUTO_RULES:
        for m in pattern.finditer(text):
            changes.append({
                'original': m.group(),
                'replacement': replacement,
                'position': m.start(),
            })
        text = pattern.sub(replacement, text)
    # 중복 제거 (동일 위치의 중복 치환 방지)
    return text, changes


def find_manual_patterns(text):
    """수동 확인 대상 패턴 위치 탐지 (읽기 전용)"""
    findings = []
    for pattern in MANUAL_PATTERNS:
        for m in pattern.finditer(text):
            start = max(0, m.start() - 30)
            end = min(len(text), m.end() + 30)
            context = text[start:end].replace('\n', ' ').strip()
            findings.append({
                'pattern': pattern.pattern,
                'match': m.group(),
                'context': context[:80],
            })
    return findings


def test_posts(n=10):
    """health/beauty에서 자동 치환 대상 n건 시험"""
    # 백업 매니페스트 로드
    manifest_path = Path(".planning/phase-55-curation-quality-diagnostics/backups/q3_cleanup_v1/MANIFEST.json")
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    # 자동 치환 가능한 글만 필터
    test_candidates = []
    for m in manifest:
        post_path = Path(m['src'])
        content = post_path.read_text(encoding='utf-8')
        _, changes = apply_auto_rules(content)
        if changes:
            test_candidates.append({**m, 'changes': changes})
    
    print(f"=== 자동 치환 가능 글: {len(test_candidates)}건 ===")
    print(f"=== 시험 대상: {min(n, len(test_candidates))}건 ===\n")
    
    results = []
    for candidate in test_candidates[:n]:
        post_path = Path(candidate['src'])
        original = post_path.read_text(encoding='utf-8')
        modified, changes = apply_auto_rules(original)
        
        if not changes:
            continue
        
        # 변경 내용 요약
        unique_changes = {}
        for c in changes:
            key = f"{c['original']}→{c['replacement']}"
            unique_changes[key] = unique_changes.get(key, 0) + 1
        
        print(f"[{candidate['blog_id']}] {candidate['slug'][:50]}")
        print(f"  치환 건수: {len(changes)}건")
        for desc, count in unique_changes.items():
            print(f"    {desc}: {count}건")
        
        # diff 출력 (변경된 라인만)
        orig_lines = original.split('\n')
        mod_lines = modified.split('\n')
        diff_shown = 0
        for i, (ol, ml) in enumerate(zip(orig_lines, mod_lines)):
            if ol != ml and diff_shown < 3:
                print(f"  L{i+1}: - {ol.strip()[:70]}")
                print(f"  L{i+1}: + {ml.strip()[:70]}")
                diff_shown += 1
        
        # 파일에 기록 (시험 적용)
        post_path.write_text(modified, encoding='utf-8')
        
        results.append({
            'blog_id': candidate['blog_id'],
            'slug': candidate['slug'],
            'src': str(post_path),
            'original_hash': candidate['sha256'],
            'changes': changes,
            'unique_changes': unique_changes,
        })
        print()
    
    return results


if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    results = test_posts(n)
    
    # 결과 저장
    out_path = Path(".planning/phase-55-curation-quality-diagnostics/samples/test_replacement_results.json")
    save_data = [{k: v for k, v in r.items() if k != 'modified_content'} for r in results]
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {out_path}")
