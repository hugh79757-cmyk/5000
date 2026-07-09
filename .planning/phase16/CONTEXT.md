# Phase 16: Production Hardening — 마무리 작업

**Date:** 2026-07-09
**Phase Goal:** Phase 1-15에서 남은 사소한 hardening 항목들을 전부 정리하여 모든 requirements를 100% 완료 상태로 만든다.

## Locked Decisions

1. **GitHub Actions CI는 활성화하지 않음** — Cloudflare Pages 배포 500회/월 제한 때문. wrangler 직접 빌드/배포 유지.
2. **wrangler 직접 배포 유지** — launchd + scheduler 기반 로컬 배포 파이프라인 그대로 간다.

## In Scope

### P0 — Known Bug Fix
1. **`keywords.py` import 경로 문제** — `keyword_expander.py`에서 `from pipelines.curation.keywords import validate_keyword` 할 때 circular import 가능성 확인 및 방어

### P1 — Requirements 미완료 항목
2. **STB-02**: Hardcoded absolute paths (`/Users/twinssn/...`) 제거 — config/env-driven으로 대체
3. **STB-13**: Config schema validation — `blogs.yaml`, `prompts.yaml` 스키마 검증 로직 추가

### P2 — 기존 구현 활성화/확장
4. **Phase 10 Blowfish shortcode toggle 활성화** — 이미 hugo_writer.py에 구현됨, toggle만 ON
5. **Phase 15 pipeline hook 확장** — travel, stock(STAP) pipeline에 `record_quality()` 연결 (현재 curation만 연결)
6. **`detect_problematic_posts.py --scan-body` 실행** — Phase 12에서 구현만 하고 실행 안 한 body rescan 실행 및 결과 처리

### P3 — 검증 및 Housekeeping
7. **empty_template fix 검증** — 다음 pipeline 실행에서 `{{}}` 정상 제거 확인
8. **Uncommitted changes 정리** — 7개 modified 파일 commit 또는 discard

## Out of Scope

- STB-06: GitHub Actions CI 복원 (명시적 제외 — Cloudflare Pages 배포 제한)
- 새로운 기능 개발 (hardening만)
- Phase 11 AdSense 광고 성과 분석 (Out of Scope by design)
- Phase 14 미적용 GSC 사이트 등록 (None 항목)

## Requirements Traceability

| Requirement | Phase 16 Task | Priority |
|-------------|--------------|----------|
| STB-02 | Task 16-02 | P1 |
| STB-13 | Task 16-03 | P1 |
| Phase 10 toggle | Task 16-04 | P2 |
| Phase 15 hook extend | Task 16-05 | P2 |
| --scan-body 실행 | Task 16-06 | P2 |
| empty_template 검증 | Task 16-07 | P3 |
| uncommitted 정리 | Task 16-08 | P3 |
