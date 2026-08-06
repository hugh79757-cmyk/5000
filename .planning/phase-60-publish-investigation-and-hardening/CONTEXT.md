# Phase 60: 발행/배포 중단 조사 + 알림 재설계 + 대시보드 보강 + 확장 비롯

> 작성일: 2026-08-06
> 기반: Phase 59 ops_dashboard (부분 완료), publish_ledger 실제 데이터, P-코드 알림 분석
> 원칙: 로그·DB로 근거 확인, 추측 금지, 확인 불가는 UNKNOWN+사유

---

## ⚠️ 순서 위반 기록 + 착수 순서 재조정

### 위반 사실

Phase 59 리팩토링(59-01 ETAP 통합, 59-06 테마 감사, 59-07 hotissue 마이그레이션,
59-08 stock 마이그레이션, 59-09 ETAP wrapper, 59-11 flights naming)이
Phase 60 조사 이전에 실행됨. 사용자가 지정한 순서:

> "Phase 60 Part 1~4 완료 → baseline 태그 → Phase 59 Wave 3~4 리팩토링"

는 **지켜지지 않았음.**

### 영향

- Part 1이 "원래 발행 중단"과 "리팩토링이 유발한 회귀"를 깨끗이 구분할 수 없음
- `pre-refactor-baseline` 태그 미존재 → 소급 태깅 필요

### 조정된 착수 순서 (S1~S5)

| 단계 | 내용 | 선행조건 |
|------|------|----------|
| **S1** | git log에서 리팩토링 직전 커밋 찾아 `pre-refactor-baseline` 태그 소급 | 없음 |
| **S2** | ops_dashboard 마무리: 6개 checks 등록 + standard_rules 시드 + inventory 불일치 규명 + 자기검증 4종 통과 | S1 |
| **S3** | 완성된 대시보드로 "리팩토링 후 전 블로그 상태" 스냅샷 = `post-refactor-baseline` | S2 |
| **S4** | Part 1 착수 — publish_ledger를 리팩토링 커밋 시각과 대조하여 원래 문제 vs 리팩토링 회귀 판별 | S3 |
| **S5** | Part 2~6 — 기존 플랜대로, 조건부/게이트 그대로 | S4 |

### S1 결과

- **pre-refactor-baseline 태그**: `d85095152` (2026-08-06 10:33:52)
  - "docs(audit): 5000 아키텍처 감사 보고서"
  - Phase 59 첫 커밋(`62304d24e docs(phase-59): research`) 직전
- **리팩토링 범위**: 59-01(ETAP 31개 통합), 59-06~08(테마 마이그레이션), 59-09(ETAP wrapper), 59-11(naming fix)
- **dashboard 작업**: 59-02~05 (Flask, UI, tunnel, alerts) — 이건 리팩토링이 아닌 인프라 구축

---

## 0. 배경

Phase 59에서 ops_dashboard 인프라가 구축되었으나 **부분 완료** 상태:
- blog_lifecycle: 56개 블로그 등록 (목표 85개)
- known_issues: 39건 시드 (목표 52건)
- standard_rules 테이블: **미생성**
- check_results: **0건** (검사 실행된 적 없음)
- 등록된 check: **0개** (standard.py가 import되지 않음)
- freshness/render_health/crosscheck check: **미구현**

**Phase 60은 이 대시보드를 완성하고, 실제 발행 중단 문제를 조사·해결하며, 알림 체계를 재설계하는 통합 조사·개선 페이즈다.**

---

## 1. 현재 발행 상태 (publish_ledger 실제 데이터)

### 1-1. 최근 발행 활동 (2026-08-06)
| 블로그 | 성공 | 실패 | 주요 실패 사유 |
|--------|------|------|---------------|
| beauty-hugo | 1 | 1 | similar_title |
| kitchen-hugo | 1 | 2 | irrelevant_products |
| fitness-hugo | 1 | 0 | — |
| baby-hugo | 1 | 0 | — |
| interior-hugo | 1 | 1 | similar_title |
| senior-blogger | 0 | 1 | publish_error |

### 1-2. 파이프라인별 오류 패턴
- **similar_title**: beauty, interior — 제목 유사도 80% 초과로 차단
- **irrelevant_products**: kitchen — 필터 실패 3회 후 포기
- **publish_error**: senior — 발행 단계 자체 실패
- **P09 (repeated segments)**: interior, baby, fitness, kitchen, beauty — 이미지 URL/세그먼트 반복

### 1-3. 미발행 블로그 (8/1 이후 성공 0건 추정)
- pet-hugo, car-hugo, health-hugo, camping-hugo 등 CUAP 다수
- STAP/ETAP 블로그들 — 파이프라인 자체 미가동 추정

---

## 2. 조사 대상 6파트

### Part 1 (최우선): 발행/배포 중단 원인 규명
- blog_id별 마지막 성공 발행 시각 집계
- 8/1 이후 발행 시도 vs 성공 vs 차단 카운트
- P-코드별 차단 사유 분포
- DB vs 라이브 대조 (유실 판별)
- **판정**: (a) 차단 반복 (b) 발행 시도 중단 (c) 배포 유실 중 어떤 원인

### Part 2: P09 근본 원인 (재발 시에만)
- "repeated segments 25 of ~42" 공통 코드 결함 조사
- 이미지 URL 생성/삽입 shared 로직 (ai_writer.py, hugo_writer.py) 점검
- 목표: 블로그별 재생성이 아닌 코드 1곳 수정으로 동시 해결

### Part 3: 알림 재설계
- P09 정상 차단 → 실시간 푸시 중단, ops.db 누적 + 텔레그램 일일 요약
- P02 연속 실패·신종 오류·게이트 미포착만 실시간 푸시
- P-코드 패턴 단위 집계 (블로그 단위 아님)

### Part 4: 대시보드 체크 보강
- cjk_leak: 제목·본문 + URL 슬러그까지 확장
- 크로스링크 주제 일관성 체크 신설 (audit Q5)
- 오염글 목록화 → Part 1 재발행과 대조

### Part 5: 확장성 보강 (목표 규모: 몇백, 500 이하)
- DB 접근을 db.py 함수로 통일 (인라인 SQL 금지)
- render_health 동시성 제한 async
- check_results 보존 정책: 원시 N일 → 일별 롤업
- UI: "주의 필요" 기본 뷰, 정상은 집계, 필터 제공

### Part 6: CUAP 확장 게이트 (15→50)
- Part 1~4 닫힌 뒤에만 검토
- 신규 블로그가 수정 완료된 shared 로직을 상속하도록 설계 확인
- 시범 발행 1개 → 대시보드 전수 검사 → PASS 후 확대

### 부가: 확장 대비 설계 검증 (§5)
- 계열(cap/cuap/etap 등)이 코드에 하드코딩되지 않은지 확인
- config/blogs.d/*.yaml에서 자동 발견(discover) 가능한지 확인
- 더미 계열 1개 추가로 코드 수정 없이 편입 가능한지 검증

### 부가: 확장 준비도 지표 (§6)
- 전 블로그 표준 준수율, stale 블로그 수, 미해결 known_issue 수
- 셋 다 녹색일 때만 확장 검토

---

## 3. 선행 조건

- Phase 59 ops_dashboard 기본 인프라 존재 (db.py, app.py, checks/__init__.py)
- publish_ledger 데이터 가용 (data/content.db)
- 텔레그램 알림 시스템 가동 중 (shared/telegram_notifier.py)

---

## 4. 검증 기준

### Part 1
- [ ] blog_id별 마지막 성공 발행 시각 100% 확인
- [ ] 8/1 이후 발행 시도/성공/차단 카운트 산출
- [ ] P-코드별 차단 비율 집계 완료
- [ ] DB vs 라이브 대조 완료 (유실 글 목록)
- [ ] 각 블로그 공백 원인 판정 완료 (근거 포함)

### Part 2 (조건부)
- [ ] P09 재발 여부 판정
- [ ] 재발 시: 공통 코드 결함 1곳 식별
- [ ] 수정 후 pet/beauty 등 1회 발행 테스트

### Part 3
- [ ] P09 정상 차단 이벤트 → 실시간 푸시 중단 확인
- [ ] ops.db 이벤트 기록 확인
- [ ] 텔레그램 하루 1회 요약 포맷 확인

### Part 4
- [ ] cjk_leak 체크가 URL 슬러그까지 검사하는지 확인
- [ ] 크로스링크 주제 일관성 체크 구현
- [ ] 오염글 목록화 + 재발행 대조

### Part 5
- [ ] 인라인 SQL 0건 (db.py 함수 통일)
- [ ] render_health async 실행 확인
- [ ] check_results 롤업 정책 구현
- [ ] UI "주의 필요" 기본 뷰 동작 확인

### Part 6
- [ ] 더미 계열 YAML 추가 → 코드 수정 없이 편입 확인
- [ ] 확장 준비도 지표 대시보드 표시 확인

---

## 5. 잔존 위험

1. **Part 1 조사가 예상보다 깊어질 수 있음**: publish_ledger 데이터 품질에 따라 조사 범위 확대 가능
2. **P09 코드 결함이 shared 로직에 있을 경우**: multiple 블로그에 영향, staged 수정 필요
3. **알림 재설계 시 기존 텔레그램 알림과 충돌**: additive 변경 필수
4. **확장성 보강 중 기존 기능 회귀**: db.py 함수화 시 기존 호출 코드 영향 확인 필요
5. **ops_dashboard 완성도 불확실**: freshness/render/crosscheck check 미구현 상태에서 Part 4 작업 병행 필요
