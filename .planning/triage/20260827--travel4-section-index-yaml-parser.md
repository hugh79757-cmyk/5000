---
date: 2026-08-27
type: fix
status: resolved
---

# travel4-hugo YAML 파싱 거짓양성 (check_section_index.sh)

## What
travel1/3-hugo 배포가 사전배포 GUARD에서 travel4-hugo 2개 포스트 'while scanning a quoted scalar'로 실패. 실제 포스트는 정상.

## Why
`scripts/check_section_index.sh:38` `end = txt.find("---", 3)` — 첫 '---' 서브스트링을 찾는데, 포스트 description 필드의 '------'(6대시)를 클로징 구분자로 오인 → frontmatter를 인용문 중간에서 잘라 PyYAML 실패. (대시보드 _index.md 버그와 동일 계열의 체커 결함)

## Files changed
- /Users/twinssn/Projects/TAP/scripts/check_section_index.sh (`:38` `txt.find("---",3)` → `txt.find("\n---",3)`)

## How
클로징 구분자는 반드시 행 시작(`\n---`)에 위치해야 함. 외에도 동일 패턴(`.find("---")`)이 다른 위치에 있는지 점검 권장.

## Verification
- `bash scripts/check_section_index.sh` → BAD=0 (✅ 5개 블로그 정상).
- `dispatcher.py travel3-hugo` → `{"success":true,"reason":"cooldown"}` (기존 false no_result 해소, 차단 해제).
- travel1-hugo는 GUARD 통과 후에도 no_result 유지 → 별개 원인(토픽 고갈, 아님 fetch) 확인됨.

## Next observation
travel1-hugo no_result는 진짜(토픽 고갈/후보 소진) — 콘텐츠 확보 전 배포 안 됨. 다음 발행 시 자동 배포 대기.
