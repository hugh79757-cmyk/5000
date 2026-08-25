---
date: 2026-08-25
type: chore
status: resolved
---

# 변경사항 저장 + 코드 기준 GSD 문서 업데이트

## What
1. 미커밋 변경사항 저장 (dispatcher S03/S04 fix + test + analytics_status + scheduler ETAP)
2. 코드 기준으로 모든 GSD 문서 업데이트 (STATE.md, ROADMAP.md 등)

## Why
gsd-triage 요청 — Phase 체계와 코드 상태 불일치 해소, 미커밋 변경 커밋, ETAP topic_expander 연동 반영

## Files changed
- dispatcher.py — S03 24h 연령 게이트(_age_h, _s03_critical), S04 Hugo shortcode 제외 regex
- tests/test_editorial_quality.py — editorial_cosine env 의존 skip + test_s04_ignores_hugo_shortcodes 회귀 테스트
- scheduler.py — ETAP topic_expander daily 01:00 (이미 커밋 62691e6)
- pipelines/etap/topic_expander.py — 신규 686 lines (커밋 27130ee)
- data/analytics_status.json — runtime GA4/GSC/AdSense last_run_id 갱신 (20260825_113811)
- .planning/STATE.md — All Phases Status, Quick Tasks 갱신 예정
- .planning/ROADMAP.md — Phase 71/72 상태 동기화 예정
- .planning/triage/INDEX.md — 본 항목 추가

## How
1. git add/commit으로 dispatcher+test 저장 (analytics_status는 runtime이므로 제외 또는 chore 커밋)
2. git log/code scan으로 실제 Phase 상태 파악 → STATE.md/ROADMAP.md 반영
3. triage 파일 작성 + INDEX.md prepend

## Verification
- git status clean (analytics_status 제외) 확인
- STATE.md All Phases Status에 Phase 71/72 및 ETAP expander 반영 확인
- ROADMAP Phase 70/71/72 표기 일치 확인
- ls -1t .planning/triage + cat INDEX.md 확인
