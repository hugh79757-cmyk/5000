---
date: 2026-08-22
status: ACTIVE
track: C
title: TRACKC_SELF_IMPROVE — 자가 개선 루프 설계
---

# TRACKC_SELF_IMPROVE — 자가 개선 루프

> 상태: ACTIVE. michelin 파일럿 구조 검증 PASS, 확산 대기(etap 소스 그룹 분류 선행).

## 1. 루프 목표
검증된 구조 요소(E1~E5)를 만족하는 포스트를 생성→검증→미달 시 재생성하여, GSC/GA4 신호 기반으로 ETAP 블로그 체류시간·CTR을 자가 개선한다.

## 2. 구조 요소 E1~E5 + 검증 기준
| ID | 요소 | 검증 기준 |
|----|------|-----------|
| E1 | 명시적 H2 4단계 | `## At a Glance`, `## Where to Eat`, `## Compare`, `## FAQ` 모두 존재 (리터럴 헤딩, 번호리스트 내부 금지) |
| E2 | 비교 테이블 | 본문 `<table>` 행 ≥ 14 |
| E3 | FAQ | `## FAQ` 하위 Q/A 쌍 ≥ 3 |
| E4 | 본문 분량 | word count ≥ 706 |
| E5 | filler 금지 | HARD CONSTRAINT — "Do NOT write filler" 준수 (LLM 프롬프트 고정) |

검증 위치: `pipelines/etap/michelin_writer.py` STRICT STRUCTURE + HARD CONSTRAINT (Step1 적용 완료, Tokyo 생성 4/4 PASS 확인).

## 3. 대상 선정 로직 (Task 7)
- **Tier 1**: `gsc_pages.clicks > 0` → 즉시 개선(체류/전환)
- **Tier 2**: `impressions > 0 & clicks = 0` → CTR 개선
- **Tier 3**: `gsc_pages` 0행(미색인) → 색인 유도 (ETAP 36 중 미색인)
- **Gate 1**: `blog_id ∈ URL_TO_BLOG_ID` roster (writer/route 존재)
- **Gate 2**: 데이터 원소스 유효성 — `publish_ledger` 최근 7일 이력 기반
  - 최근 7일 내 `published` → PASS
  - 최근 생성 `no_result/no_data/...`(EXHAUSTED) → FAIL (소스 고갈)
  - 이력 없음/신호 없음 → UNKNOWN → 보수적 PASS + 경고
- **Gate 3**: 대상 포스트 frontmatter `title+slug+content≥50자` (Stage1 위반 아님)

구현: `scripts/trackc_task7_select.py`. 입력 `data/analytics.db.gsc_pages` (563행 수집 완료).
실행 결과(보강 전): tier_1=38, tier_2=525, tier_3=24, blogs_with_targets=22, gate_filtered=2.

## 4. 실행 흐름 (자가 개선 루프)
```
generate → validate(E1~E5)
  ├─ PASS        → publish
  ├─ FAIL(1회)   → 재생성 (HARD CONSTRAINT 재적용)
  └─ FAIL(2회)   → Telegram escalate + hold (수동 개입)
```

## 5. 확산 설계 (Task 8)
- **Phase 1 (형제)**: michelin (완료) → foodtour
- **Phase 2 (비교형)**: guide / hotissue / deal (도메인별 섹션명 rename 적용)
- **제외**: Tier 3 미색인 24 + Gate 탈락 2
- 확산 순서: michelin → foodtour → guide/hotissue/deal

## 6. 효과 측정
- 지표: GA4 per-blog `engagement_rate` (ga4_measurement_map.yaml 기준 per-blog ID)
- 비교: 개선 포스트 배포 7일 후 tier_1/tier_2 대상 페이지 클릭/체류 전후 대조

## 7. 반복 조건
체류 미개선 시 구조 요소(E1~E5) 재조정 → 재생성 루프 재진입.

## 8. 현재 상태
- michelin: 구조 PASS (파일럿 포스트 배포 완료, 단 초기 1건은 H2 1/4 준수 미달로 라이브 — 재생성 권장)
- 확산: 대기 — etap 소스 그룹 분류 결과 필요

## 9. 의존성
- `/etap` 세션의 소스 그룹 결과 → 확산 순서(Phase 1/2) 확정
- etap writer 수정은 별도 세션 영역 (본 루프는 michelin 단독 파일럿 목적만)

## Monitoring Hold

status: MONITORING_HOLD
start_date: 2026-08-22
midpoint_check: 2026-08-29
end_date: 2026-09-05
resume_trigger: end_date 도달 OR midpoint에서 명확한 양/음 신호 감지 시 조기 판정

### 모니터링 대상
- blog: michelin-hugo
- 배포 포스트: 10건 (S2 구조 재생성 완료)
- 측정 ID: G-73WF2WRN9H

### 측정 지표
| 지표 | baseline(배포 전 7일) | 목표(배포 후 14일) |
|------|----------------------|-------------------|
| avg_engagement_rate | 미확보 — GA4 적용 직후라 이전 데이터 없음 | baseline 대비 +15% 이상 |
| avg_session_duration | 미확보 — GA4 적용 직후라 이전 데이터 없음 | baseline 대비 +20% 이상 |
| pages_per_session | 미확보 — GA4 적용 직후라 이전 데이터 없음 | baseline 대비 +10% 이상 |

### 판정 기준
- PASS: 3개 지표 중 2개 이상 목표 달성 → Task 8 확산 승인 요청
- PARTIAL: 1개만 달성 → 구조 요소별 기여 분석 후 조정, 7일 연장
- FAIL: 0개 달성 → 구조 재설계 (E1~E5 중 비효과 요소 제거/교체)

### 중간 체크 (2026-08-29)
- GA4 데이터 수집 스크립트 실행
- 추세 방향만 확인 (판정 아님, 단 engagement_rate -20% 이하면 조기 FAIL 선언)

### 재개 시 작업
1. GA4 데이터 수집 + baseline 대비 비교표 작성
2. 판정 (PASS/PARTIAL/FAIL)
3. PASS 시: /etap 세션 소스 그룹 결과 확인 → Task 8 확산 순서 확정 → 실행
4. PARTIAL/FAIL 시: 원인 분석 → 구조 조정 → 재배포 → 14일 재모니터링

### 핸드오프 메모
- 이 섹션이 있으면 모니터링 중이란 뜻. 확산 작업 시작하지 마라.
- 재개 조건: end_date 도달 + 판정 완료 + 대표 승인.
- baseline 수집: 배포 직후 GA4에서 배포 전 7일 데이터를 기록해둬야 함 (지금 즉시).

### baseline 수집 결과 및 대체 방안 (2026-08-22 기록)
- 수집 시도: `shared/analytics_collector.collect_ga4()` 경로 확인 → `GA4_PROPERTIES`에 `michelin-hugo` 항목 **없음** (numeric property_id 미등록). 수집기 동작 시 "GA4 속성 미등록, 스킵" 처리되어 baseline 확보 불가.
- 추가 사유: per-blog GA4 measurement_id(`G-73WF2WRN9H`)는 본 트랙 Work B에서 금일(2026-08-22) hugo.toml에 적용 완료. 배포 전 7일(2026-08-15~08-21) 구간은 per-blog GA4 미적용 상태 → 실측 baseline 존재하지 않음.
- **fallback_plan**: 배포 후 1주차(2026-08-22 ~ 2026-08-29)를 baseline으로 대체. 즉, 8/29 중간체크 시점에 수집되는 1주차 지표를 baseline으로 간주하고, 이후 14일(8/29~9/05) 구간과 대비하여 +15%/+20%/+10% 목표 달성 여부를 판정. 단, 이 경우 "배포 효과"而非"구조 효과"와 혼재될 여지가 있으므로, 1주차 지표 자체도 별도 기록해둔다.
- 향후 baseline 신뢰도 확보를 위해 `GA4_PROPERTIES`에 michelin-hugo property_id 등록 권장 (별도 작업, 본 핸드오프 범위 외).

### GA4 수집 경로 연결 완료 (2026-08-22)
- GA4_PROPERTIES 등록 완료, 수집 시작일: 2026-08-22.
- michelin-hugo property_id `531066288` 등록 + ETAP confirmed 34개 블로그 전부 등록.
- `collect_ga4()` 실행 결과: 42 sites / 87 rows / errors=[] (michelin 미포함 스킵 해소).
- 실측 확인: 신규 34개 중 11개 블로그가 2026-08-19~21 데이터를 ga4_daily에 수집됨. michelin-hugo는 gtag 적용 당일(8/22) 기준으로 GA4 처리 지연(~24-48h)으로 인해 8/22 이후 데이터가 누적되기 시작함 (기존 2026-04-16 row는 과거 전역 수집 잔존).
- 따라서 baseline 미확보 사유(경로 누락)는 해소됨. 단 8/22 이전 실측치 부재는 동일하므로, Monitoring Hold의 fallback(배포 후 1주차 8/22~8/29를 baseline 대체) 안을 그대로 따름.
