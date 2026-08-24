#!/usr/bin/env python3
"""
rule_promote.py — 규칙 severity 승격 헬퍼 (인간 승인 게이트 필수)

ops_dashboard/db.py의 SEED_STANDARD_RULES 리스트 내 특정 rule_id 항목의
severity 값을 inplace로 치환한다.

설계 원칙:
- `--approve` 플래그 **필수** (없으면 exit 1 + "human approval required per charter §6-2")
- 정규식 기반 치환으로 최소 변경 보장
- 성공 시 사후 체크리스트 자동 출력
- 백업 자동 생성 (파일 수정 전 .bak 생성)

사용 예시:
    # 실패: --approve 없음
    python scripts/rule_promote.py --rule-id S01 --from WARNING --to CRITICAL
    # → exit 1, "human approval required per charter §6-2"

    # 성공: --approve 포함
    python scripts/rule_promote.py --rule-id S01 --from WARNING --to CRITICAL --approve
    # → SEED_STANDARD_RULES 내 S01 severity 변경, 사후 체크리스트 출력
"""

import argparse
import re
import shutil
import sys
from pathlib import Path

SEED_FILE = Path('ops_dashboard/db.py')
VALID_SEVERITIES = {'CRITICAL', 'MAJOR', 'WARNING', 'INFO'}


def read_seed_file() -> str:
    """SEED 파일 읽기."""
    if not SEED_FILE.exists():
        print(f"❌ SEED 파일 없음: {SEED_FILE}", file=sys.stderr)
        sys.exit(1)
    return SEED_FILE.read_text(encoding='utf-8')


def find_rule_entry(content: str, rule_id: str) -> tuple[int, int, str] | None:
    """
    SEED_STANDARD_RULES 리스트 내 rule_id 항목 찾기.
    반환: (시작인덱스, 끝인덱스, 매칭된_문자열) 또는 None
    """
    # 패턴: {"rule_id": "S01", "target": "...", "severity": "WARNING", "description": "..."}
    # 여러 줄에 걸쳐 있을 수 있으므로 DOTALL 모드로 탐색
    pattern = re.compile(
        rf'(\{{[^}}]*"rule_id"\s*:\s*"{re.escape(rule_id)}"[^}}]*\}})',
        re.DOTALL
    )
    match = pattern.search(content)
    if match:
        return match.start(), match.end(), match.group(1)
    return None


def update_severity_in_entry(entry: str, new_severity: str) -> str:
    """항목 문자열 내 severity 값 치환."""
    # "severity": "WARNING" → "severity": "CRITICAL"
    return re.sub(
        r'("severity"\s*:\s*")([^"]+)(")',
        rf'\1{new_severity}\3',
        entry
    )


def write_seed_file(content: str) -> None:
    """SEED 파일 쓰기 (백업 생성 후)."""
    # 백업 생성
    backup_path = SEED_FILE.with_suffix('.py.bak')
    shutil.copy2(SEED_FILE, backup_path)
    print(f"  📦 백업 생성: {backup_path}")

    # 원본 쓰기
    SEED_FILE.write_text(content, encoding='utf-8')
    print(f"  ✅ 파일 갱신: {SEED_FILE}")


def verify_update(rule_id: str, expected_severity: str) -> bool:
    """갱신 후 검증: SEED_STANDARD_RULES에서 해당 rule_id의 severity 확인."""
    content = read_seed_file()
    entry_match = find_rule_entry(content, rule_id)
    if not entry_match:
        print(f"❌ 검증 실패: {rule_id} 항목을 찾을 수 없음", file=sys.stderr)
        return False

    entry = entry_match[2]
    severity_match = re.search(r'"severity"\s*:\s*"([^"]+)"', entry)
    if not severity_match:
        print(f"❌ 검증 실패: {rule_id} 항목에 severity 필드 없음", file=sys.stderr)
        return False

    actual = severity_match.group(1)
    if actual == expected_severity:
        print(f"  ✅ 검증 통과: {rule_id} severity = {actual}")
        return True
    else:
        print(f"❌ 검증 실패: {rule_id} severity = {actual} (기대: {expected_severity})", file=sys.stderr)
        return False


def print_post_promote_checklist(rule_id: str, new_severity: str) -> None:
    """승격 후 필수 체크리스트 출력."""
    print()
    print("=" * 60)
    print(f"  📋 {rule_id} → {new_severity} 승격 후 체크리스트")
    print("=" * 60)
    print()
    checklist = [
        f"[ ] Preflight: rule_id '{rule_id}' 조회 시 새 severity('{new_severity}') 반환 확인",
        f"[ ] Dashboard: /standards 페이지에서 {rule_id} severity 표시 일치 확인",
        f"[ ] Telegram alert: {new_severity} 위반 시 알림 포맷 정상 동작 확인",
        f"[ ] 배포 게이트: blocked=True 경로 동작 확인 (테스트 블로그 1건)",
        f"[ ] 64-RULE-CATEGORIES.md 카테고리 매핑에 {rule_id} 추가됨 확인",
        f"[ ] docs/RULE_REGISTRATION_RUNBOOK.md 이력 테이블에 등록 행 추가됨 확인",
    ]
    for item in checklist:
        print(f"  {item}")
    print()
    print("=" * 60)
    print("  ⚠️  위 체크리스트 모두 완료 후 실제 배포 파이프라인에서 테스트 권장")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description='규칙 severity 승격 (ops_dashboard/db.py SEED_STANDARD_RULES 수정) — 인간 승인 게이트 필수'
    )
    parser.add_argument('--rule-id', required=True, help='대상 규칙 ID (예: S01, C01, L01)')
    parser.add_argument('--from', required=True, dest='from_severity', choices=VALID_SEVERITIES,
                        help='현재 severity (검증용)')
    parser.add_argument('--to', required=True, dest='to_severity', choices=VALID_SEVERITIES,
                        help='변경할 severity')
    parser.add_argument('--approve', action='store_true',
                        help='인간 승인 확인 플래그 (필수, 없으면 실행 거부)')

    args = parser.parse_args()

    # 인간 승인 게이트
    if not args.approve:
        print("=" * 60)
        print("  ❌ 인간 승인 필요 (--approve 플래그 필수)")
        print("=" * 60)
        print()
        print("  운영헌장 §6-2: severity 변경은 사람 승인 필수.")
        print("  --approve 플래그를 추가하여 다시 실행하세요.")
        print()
        print(f"  예: python scripts/rule_promote.py --rule-id {args.rule_id} "
              f"--from {args.from_severity} --to {args.to_severity} --approve")
        print("=" * 60)
        sys.exit(1)

    # severity 동일 체크
    if args.from_severity == args.to_severity:
        print(f"❌ from과 to severity가 동일함: {args.from_severity}", file=sys.stderr)
        sys.exit(1)

    print("=" * 60)
    print(f"  {args.rule_id} severity 승격: {args.from_severity} → {args.to_severity}")
    print("=" * 60)
    print()

    # 파일 읽기
    content = read_seed_file()

    # 항목 찾기
    entry_match = find_rule_entry(content, args.rule_id)
    if not entry_match:
        print(f"❌ {args.rule_id} 항목을 SEED_STANDARD_RULES에서 찾을 수 없음", file=sys.stderr)
        print(f"  힌트: 규칙 ID 철자 확인, 또는 SEED_STANDARD_RULES에 먼저 추가 필요", file=sys.stderr)
        sys.exit(1)

    start, end, old_entry = entry_match

    # 현재 severity 검증
    current_severity_match = re.search(r'"severity"\s*:\s*"([^"]+)"', old_entry)
    if not current_severity_match:
        print(f"❌ {args.rule_id} 항목에 severity 필드 없음", file=sys.stderr)
        sys.exit(1)

    current_severity = current_severity_match.group(1)
    if current_severity != args.from_severity:
        print(f"❌ 현재 severity 불일치: 파일={current_severity}, 인자={args.from_severity}", file=sys.stderr)
        sys.exit(1)

    print(f"  📍 대상 항목 발견 (line ~{content[:start].count(chr(10)) + 1})")
    print(f"  🔄 severity 변경: {current_severity} → {args.to_severity}")

    # 치환 수행
    new_entry = update_severity_in_entry(old_entry, args.to_severity)
    new_content = content[:start] + new_entry + content[end:]

    # 파일에 쓰기
    write_seed_file(new_content)

    # 검증
    if not verify_update(args.rule_id, args.to_severity):
        print("❌ 검증 실패 — 백업에서 복구 필요", file=sys.stderr)
        sys.exit(1)

    # 사후 체크리스트 출력
    print_post_promote_checklist(args.rule_id, args.to_severity)

    print()
    print(f"  ✅ {args.rule_id} 승격 완료: {args.from_severity} → {args.to_severity}")
    print("=" * 60)


if __name__ == '__main__':
    main()