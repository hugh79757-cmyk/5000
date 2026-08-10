# Phase 67 — 무인 운영 시스템 (Unattended Ops) 실행 계획

> **상태:** 계획 수립 (2026-08-08)
> **목표:** 사람 개입 없이 발행·감지·자동처리·요약보고가 도는 무인 운영 시스템 완성
> **근거:** `67-RESEARCH.md` (R1-R4 조사) + `CONTEXT.md` (계약/확정 설계)
> **작업 규칙:** **additive, non-destructive** + 연구→게이트→집행 순서 엄수 + 이미 완료된 작업 재실행 금지
> **검증 명령:** 블로그별 Hugo 빌드 + wrangler 재배포 + 라이브 HTTP 확인

---

## 플랜 스코프 요약

### 목표 (Goal, 1문장)

라이브 dead 링크 0건, dead 엔티티 재발 방지 3중 완결(코드+DB+백필), 오토트리아지 실모드 등록·서버 의존성 해소, 텔레그램 진짜 신호만 발송, 사람 개입 "하루 1~2회 요약 확인" 수준 축소를 수치 입증하는 무인 운영 시스템 완성.

### 스코프 (이 Phase가 하는 것)

1. **방안 B 집행:** 집행 직전 alive 재확인 → 여전히 404인 엔티티만 published=0 전환 (테스트2 포함)
2. **라이브 460건 청소:** 재확인 후 여전히 dead인 링크만 제거, 블로그별 빌드·블로그당 1회 wrangler 재배포
3. **백필 재등록 차단:** R2에서 필요 판정 시 URL 검증 추가
4. **오토트리아지 실모드 등록:** 서버 의존성 해소 후 launchd 등록, watchdog 감시 추가
5. **최종 검증:** 라이브 표본 dead 0 확인, 자연 사이클 알림 관찰, exit criteria 5항목 충족 표로 확정

### 비목표 (Non-Goals)

- 신규 블로그/파이프라인 추가
- 콘텐츠 품질 개선 (별도 phase)
- 광고/수익 최적화 (별도 phase)
- STAP/TAP/ETAP 외부 프로젝트 내부 수정
- 이미 완료된 작업 재실행 (C04 오탐 제거, senior 필터, STATE 지표, 오토트리아지 골격, 방안 A, 파일럿)

---

## 개요 (Wave / Task 분해)

### Dependency Graph

```
사전 작업: git tag pre-unattended-phase-2026-08-08 생성 (완료)

Wave 0: 리서치 검토 + 게이트 판정
  ├─ R1-R4 리서치 결과 검토
  ├─ G1-G4 게이트 통과 확인
  └─ [게이트 미통과 시] 그 지점에서 중지, 대안 제시

Wave 1: 방안 B - DB published=0 정리 (E1)
  ├─ Task 1.1: dead 엔티티 목록 확정 (집행 직전 alive 재확인)
  ├─ Task 1.2: 재확인 후 여전히 dead인 엔티티만 published=0 UPDATE
  └─ Task 1.3: 사후 대조 (before/after 카운트)

Wave 2: 라이브 460건 청소 (E2)
  ├─ Task 2.1: dead 링크 재확인 (75개 고유 URL HTTP 체크)
  ├─ Task 2.2: 블로그별 dead 링크 제거 (파일 수정)
  ├─ Task 2.3: 블로그별 Hugo 빌드 + wrangler 재배포
  └─ Task 2.4: 라이브 HTTP 확인 (제거 검증)

Wave 3: 백필 재등록 차단 (E3) [R2 필요 판정 시]
  ├─ Task 3.1: backfill_cuap_entities.py 분석
  ├─ Task 3.2: URL 검증 로직 추가 (published=0→1 복원 시 차단)
  └─ Task 3.3: dry-run 검증

Wave 4: 오토트리아지 실모드 등록 (E4)
  ├─ Task 4.1: 서버 의존성 조사 (대시보드 서버 app.py 의존 확인)
  ├─ Task 4.2: 서버 의존성 해소 (자동 기동 또는 서버 무관 동작)
  ├─ Task 4.3: PROBLEM_ALERT_DRY_RUN=0 전환 테스트
  ├─ Task 4.4: launchd 등록 (오토트리아지 스케줄)
  ├─ Task 4.5: watchdog 감시 범위 확장 (오토트리아지 + 대시보드 서버)
  └─ Task 4.6: silent_skip 오삼킴 검증

Wave 5: 최종 라이브·무인 검증 (E5)
  ├─ Task 5.1: 라이브 표본 dead 링크 0 확인
  ├─ Task 5.2: 자연 사이클 알림 관찰 (텔레그램 진짜 신호만 확인)
  └─ Task 5.3: Exit criteria 5항목 충족 표로 확정 + 보고
```

- **블로킹 관계:** Wave 0(게이트) → Wave 1 → Wave 2 → (Wave 3: 조건부) → Wave 4 → Wave 5
- **병렬 가능:** Task 2.2 각 블로그별 파일 수정은 병렬 가능 (파일 무충돌)
- **파일 소유권:**
  - Wave 1: `data/*.db` (SQLite UPDATE)
  - Wave 2: 각 블로그 `content/posts/*.md` + 블로그별 Hugo 빌드
  - Wave 3: `backfill_cuap_entities.py` (조건부)
  - Wave 4: launchd plist, watchdog 스크립트, 오토트리아지 설정
  - Wave 5: 검증 스크립트, 보고서

### Task 요약표

| Wave | Task | 유형 | 파일/대상 | 산출 |
|------|------|------|-----------|------|
| 0 | T0.1 | [검증] | 67-RESEARCH.md | 리서치 검토 + 게이트 판정 |
| 1 | T1.1 | [조사] | dead 엔티티 목록 | alive 재확인 결과 |
| 1 | T1.2 | [PRODUCTION] | data/*.db | published=0 UPDATE (테스트2 포함) |
| 1 | T1.3 | [검증] | - | before/after 카운트 대조 |
| 2 | T2.1 | [조사] | 75개 dead URL | HTTP 체크 결과 |
| 2 | T2.2 | [PRODUCTION] | 블로그별 index.md | dead 링크 제거 |
| 2 | T2.3 | [DEPLOY] | 블로그별 site_path | Hugo 빌드 + wrangler 재배포 |
| 2 | T2.4 | [검증] | 라이브 URL | HTTP 404 소멸 확인 |
| 3 | T3.1 | [조사] | backfill_cuap_entities.py | 분석 결과 |
| 3 | T3.2 | [PRODUCTION] | backfill_cuap_entities.py | URL 검증 추가 (조건부) |
| 3 | T3.3 | [검증] | - | dry-run 검증 |
| 4 | T4.1 | [조사] | 오토트리아지 코드, app.py | 의존 분석 |
| 4 | T4.2 | [PRODUCTION] | 오토트리아지 코드/설정 | 서버 의존성 해소 |
| 4 | T4.3 | [검증] | - | 실모드 전환 테스트 (오발송 0) |
| 4 | T4.4 | [CONFIG] | launchd plist | 스케줄 등록 |
| 4 | T4.5 | [CONFIG] | watchdog 스크립트 | 감시 범위 확장 |
| 4 | T4.6 | [검증] | silent_skip 필터 | 오삼킴 0 확인 |
| 5 | T5.1 | [검증] | 라이브 URL 표본 | dead 0 확인 |
| 5 | T5.2 | [관찰] | 텔레그램 알림 로그 | 진짜 신호만 확인 |
| 5 | T5.3 | [보고] | - | Exit criteria 표 + 최종 보고 |

---

## 실행 태스크

### Wave 0: 리서치 검토 + 게이트 판정

#### Task 0.1 [검증/조사] — 리서치 결과 검토 + 게이트 G1-G4 판정

- **파일:** 변경 없음. 산출물: 게이트 판정표 (이 PLAN.md 내 기록)
- **동작:**
  1. `67-RESEARCH.md` R1-R4 결과 검토
  2. 각 게이트 G1-G4 통과 여부 판정
  3. 미통과 게이트 있으면 그 지점에서 중지, 대안 제시

---

### Gate G1: 라이브 청소 대상 확정 + 안전장치

**통과 조건:**
- [x] 집행 직전 alive 재확인 워크플로우가 설계됨
- [x] 정상/복구 링크를 지우지 않는 안전장치가 있음

**판정 근거 (코드 조사 완료):**
- dead_links.json(53건 크로스셀 dead 링크) + dongnam_npmb.json(42건) = 95건 데이터 존재
  - `scripts/c01_c08_validation_data/dead_links.json`: camping-hugo 41건, pet-hugo 8건, beauty-hugo 2건, baby-hugo 2건
  - `scripts/c01_c08_validation_data/dongnam_npmb.json`: cuap-hugo 42건 (모두 "동남냄비받침-2026년-8월-최신-스펙과-가격-비교" 타겟)
- 75개 고유 URL 출처는 "방안 A 조사 결과" — 상세 목록은 별도 파일. 현재 repo에서 확인되는 것은 위 2개 JSON 파일 + content.db의 published_url
- ** Alive 재확인 워크플로우:**
  1. dead_links.json + dongnam_npmb.json의 target_slug → `{domain}/posts/{slug}/` URL 재구성
  2. 각 URL HTTP HEAD 실행 (urllib + timeout=5 + User-Agent 헤더)
  3. URL 인코딩 필수: 한국어가 포함된 slug는 `urllib.parse.quote(slug, safe='-')`로 인코딩
  4. HTTP 200 → "복구됨" 분류, 404 → "still dead" 분류
  5. 블로그별·URL별로 결과 기록
- **안전장치:** 방안 A 코드 (`shared/cuap_entity_linker.py: _url_is_alive()`)가 이미 URL alive 확인 기능 제공. 이 함수를 재사용하면 됨.

**상태: ✓ 통과 (워크플로우 설계 완료, 실제 체크는 집행 시 수행)**

---

### Gate G2: 백필 재등록 차단

**통과 조건:**
- [x] 백필이 dead 엔티티를 재등록하지 않음이 확인됐거나
- [x] 재등록 차단 수정 지점이 특정됐음

**판정 근거 (코드 분석 완료):**

**① `backfill_cuap_entities.py` — 안전 확인 ✓**
- 경로: `/Users/twinssn/Projects/5000/scripts/backfill_cuap_entities.py` (108줄)
- 동작: 콘텐츠/posts/ 스캔 → `cuap_entities`에 **INSERT OR IGNORE** 로 신규 등록 (published=1)
- 핵심: 기존 행이 존재하면 **건드리지 않음** (skip). published=0인 기존 행을 published=1로 변경하지 않음.
- 코드: `backfill_cuap_entities.py:84-91` — `SELECT 1 FROM cuap_entities WHERE blog_id=? AND post_slug=?` 체크 후 exists면 `continue`
- 결론: **이 스크립트는 dead 엔티티를 되살리지 않음.**

**② 위험 스크립트 — `fix_cuap_all_entities.py`**
- 경로: `/Users/twinssn/Projects/5000/scripts/fix_cuap_all_entities.py` (91줄)
- 동작: published=1인 모든 엔티티를 읽어 실제 content/posts/에 매칭되는 슬러그가 없으면 `published=0`으로 변경
- 위험: 이 스크립트 실행 시 정상 엔티티가 잘못 unpublished 될 수 있음
- **주의:** 방안 B 실행 전에 이 스크립트를 실행하면 안 됨. 실행해야 한다면 published=0 전환 대상 목록을 미리 백업

**③ `fix_cuap_entity_urls.py`**
- 경로: `/Users/twinssn/Projects/5000/scripts/fix_cuap_entity_urls.py`
- 동작: URL 수정 + 미발행 글은 published=0으로 변경 (80-97줄)
- 주의: 마찬가지로 published=0 변경 가능

**백필 재등록 차단 결론:**
- `backfill_cuap_entities.py`는 dead 엔티티 재등록 위험 **없음**
- `fix_cuap_all_entities.py`/`fix_cuap_entity_urls.py`는 published=0 변경 가능 → 방안 B와 실행 순서 주의
- **별도 URL 검증 추가 불필요** — 백필이 published=0을 published=1로 되돌리지 않기 때문

**상태: ✓ 통과 (backfill_cuap_entities.py 안전 확인, fix_*.py 주의 사항 문서화)**

---

### Gate G3: 오토트리아지 실모드 안전성

**통과 조건:**
- [x] 실모드가 오발송·오분류·서버의존으로 무인 운영을 깨지 않음이 확인됨
- [ ] 특히 silent_skip 오삼킴 0건 확인 (부분 확인)

**판정 근거 (코드 분석 완료):**

**① 대시보드 서버 의존성 — CRITICAL 발견 ✓**
- `scripts/auto_triage.py:28`: `DASHBOARD_URL = "http://localhost:5060"`
- `scripts/auto_triage.py:587-603`: `fetch_dashboard_data()` — 4개 엔드포인트 호출 (/api/attention, /api/issues, /api/fleet, /api/readiness)
- `scripts/auto_triage.py:598-602`: try/except로 오류 처리 → 서버 죽으면 `{"error": str(e)}` 반환
- `scripts/auto_triage.py:706-708`: `attention.get("fail_checks", [])` → 서버가 죽으면 attention이 `{"error": ...}` → fail_checks = [] → **fail_checks 기반 트리아지 조용히 스킵**
- **현재 서버 상태:** PID 94429가 `ops_dashboard/app.py`(포트 5060) 수동 실행 중. launchd 등록 **없음**.
- ** `com.5000.dashboard.plist`**: `data/dashboard/app.py`(포트 5050)를 실행하도록 설정 — **잘못된 앱**. ops_dashboard(5060)는 launchd 미등록.

**→ 서버 의존성 해소 필요:** ops_dashboard를 launchd에 등록해 자동 시작·자동 재시작되게 해야 함.

**② 오발송 위험 — dry-run 기본값으로 안전 ✓**
- `scripts/auto_triage.py:894`: `dry_run = os.environ.get("PROBLEM_ALERT_DRY_RUN", "1") != "0"` → **기본값 dry-run**
- 실모드 전환 시: `PROBLEM_ALERT_DRY_RUN=0 python scripts/auto_triage.py`
- 현재 dry-run 실행 결과: 총 230건 → 자동처리 97건, 사람호출 26건, silent_skip 107건
- 실모드 전환 시 97건 자동처리가 실제 텔레그램 발송됨 → 사전 리뷰 필요

**③ silent_skip 오삼킴 — 부분 확인**
- `scripts/auto_triage.py:284-292`: `informational_keyword` 서브타입 — "추천", "가이드", "비교" 등 정보성 키워드 포함
- `scripts/auto_triage_rules.yaml:116-118`: P14에 `silent_skip` 적용
- `scripts/auto_triage.py:294-298`: `commercial_keyword_fail`도 "추천", "비교" 포함 → **동일 키워드가 양쪽 서브타입에 매칭 가능**
- 규칙 YAML의 우선순위에 따라 첫 매칭된 서브타입의 액션 적용 → 규칙 정의에 따라 오삼킴 가능성 존재
- **검증 필요:** 실제 키워드 데이터로 silent_skip 대상 중 오탐이 있는지 샘플 검증

**상태: ⚠ 부분 통과 (서버 의존성 확인 완료, 해소 필요 — launchd 등록으로 해결 가능. silent_skip 오삼킴 샘플 검증 필요)**

---

### Gate G4: watchdog 감시 구조

**통과 조건:**
- [x] 오토트리아지·대시보드 서버·스케줄러 3자를 watchdog이 감시하는 구조가 설계됨

**판정 근거 (코드 분석 완료):**

**① 현재 watchdog 현황 ✓**
- 스크립트: `/Users/twinssn/Projects/5000/scripts/analytics_watchdog.sh` (88줄)
- launchd: `~/Library/LaunchAgents/com.5000.analytics.watchdog.plist`
- 주기: 1800초 (30분)
- 상태: **활성** (PID 34819, 실행 중)
- 현재 감시 대상:
  1. **scheduler.py** PID 생존 확인 (pgrep) → death 시 텔레그램 알림
  2. analytics 수집 미실행 감지 (8시간+) → 강제 재실행

**② 감시하지 않는 것 (사각지대) ✗**
- **ops_dashboard/app.py (포트 5060)**: launchd 미등록 + watchdog 미감시 → 죽으면 자동 복구 안 됨
- **auto_triage.py**: watchdog 미감시 → 실행 중인지 확인 불가

**③ 3자 감시 구조 설계 ✓**
- **ops_dashboard 감시 추가:**
  - `pgrep -f "ops_dashboard/app.py"` 또는 `lsof -i :5060`로 생존 확인
  - death 감지 시: launchd로 자동 재시작 (아래 launchd 등록으로 해결)
- **auto_triage 감시 추가:**
  - `pgrep -f "auto_triage.py"`로 마지막 실행 시각 확인
  - 실행 주기(예: 매일 1회) 대비 미실행 시 경고
- **스케줄러:** 기존 watchdog이 이미 감시 중 (변경 없음)

**→ watchog 확장 방안:**
1. ops_dashboard launchd 등록 (KeepAlive=true) → 서버 death 자체 해결
2. watchdog 스크립트에 ops_dashboard PID 확인 추가 (보조 감시)
3. watchdog에 auto_triage 마지막 실행 시각 확인 추가

**상태: ✓ 통과 (현존 watchdog 구조 확인 + 3자 감시 확장 설계 완료)**

---

### ▶ Gate 종합 판정

| 게이트 | 상태 | 근거 |
|--------|------|------|
| G1 | ✓ 통과 | dead_links.json(53건)+dongnam(42건) 데이터 확인, alive 재확인 워크플로우 설계 완료. 실제 HTTP 체크는 집행 시 수행 (URL 인코딩 주의) |
| G2 | ✓ 통과 | `backfill_cuap_entities.py`는 INSERT OR IGNORE만 수행 → published=0→1 복원 불가 확인. `fix_cuap_all_entities.py`/`fix_cuap_entity_urls.py`는 published=0 변경 가능 → 실행 순서 주의 |
| G3 | ⚠ 부분 통과 | 서버 의존성 확인 완료: ops_dashboard(포트 5060) launchd 미등록 + 현재 수동 실행(PID 94429) 중. 서버 death 시 fail_checks 트리아지 조용히 스킵. → launchd 등록으로 해소 가능. silent_skip 오삼킴 샘플 검증 필요 |
| G4 | ✓ 통과 | analytics_watchdog.sh(30분 주기, 활성)이 scheduler만 감시 중. ops_dashboard + auto_triage 감시 확장 설계 완료. ops_dashboard launchd 등록(KeepAlive)으로 death 자체 해결 |

**▶ G1·G2·G4 통과, G3 부분 통과 — G3 서버 의존성 해소(ops_dashboard launchd 등록) 후 집행 가능**

---

### Wave 1: 방안 B — DB published=0 정리 (E1)

#### Task 1.1 [조사] — dead 엔티티 목록 확정 (집행 직전 alive 재확인)

- **파일:** `scripts/c01_c08_validation_data/dead_links.json` (53건), `scripts/c01_c08_validation_data/dongnam_npmb.json` (42건), content.db
- **산출물:** `67-dead-urls-reconfirmed.md` (재확인 결과)
- **동작:**
  1. **데이터 소스 확인:**
     - `dead_links.json`: 53건 크로스셀 dead 링크 (camping-hugo 41, pet-hugo 8, beauty-hugo 2, baby-hugo 2)
     - `dongnam_npmb.json`: 42건 (cuap-hugo, 모두 "동남냄비받침-2026년-8월-최신-스펙과-가격-비교" 타겟)
     - **75개 고유 URL 출처:** "방안 A 조사 결과" — 현재 repo에서 확인되지 않음. 필요 시 Phase 67 이전 조사 파일 탐색
  2. **URL 재구성:** `{BLOG_DOMAINS[blog_id]}/posts/{target_slug}/` 형식
     - BLOG_DOMAINS: `shared/cuap_entity_linker.py:59` 참조
     - **주의:** slug에 한국어/공백 포함 → `urllib.parse.quote(slug, safe='-')`로 URL 인코딩 필수
  3. **HTTP HEAD 체크:** timeout=5, User-Agent 헤더 포함
  4. 분류: 200=복구됨, 404=still dead, 기타=error
  5. 결과 기록: 블로그별·URL별 상태

**예상 산출:**
```
- dead_links.json 기반 URL: 27개 고유 (blog, slug) 쌍
- dongnam 기반 URL: 1개 고유 (cuap-hugo, 동남냄비받침...)
- 전체 고유 URL: 28개 (현재 확인 가능한 범위)
- 75개 URL 중 나머지: 별도 데이터 소스 필요
- 복구됨 (HTTP 200): N개
- still dead (404): M개
```

#### Task 1.2 [PRODUCTION] — 여전히 dead인 엔티티만 published=0 UPDATE (테스트2 포함)

- **파일:** `data/*.db` (SQLite)
- **동작:**
  1. Task 1.1에서 확정된 실제 dead 엔티티 목록 사용
  2. 해당 엔티티의 published=0으로 UPDATE
  3. **테스트2:** 1건 파일럿 먼저 실행 → 결과 확인 → 전체 확대
  4. 변경 전/후 카운트 기록

**사전 카운트:**
```
- UPDATE 대상 엔티티: K개 (Task 1.1 결과)
- 변경 전 published=1 & dead URL 포함: K개
```

**사후 대조:**
```
- 변경 후 published=0: K개
- published=0 전환 성공률: 100% (K/K)
```

**주의:** OPERATIONS-CHARTER 원칙 2·3 준수 (백업→파일럿→검증→확대)

#### Task 1.3 [검증] — before/after 카운트 대조

- **파일:** 변경 없음. 산출물: 대조 결과 기록
- **동작:**
  1. UPDATE 전 카운트 vs UPDATE 후 카운트 비교
  2. published=0 전환된 엔티티가 Task 1.1 목록과 일치하는지 확인
  3. 불일치 있으면 원인 조사

---

### Wave 2: 라이브 460건 청소 (E2)

#### Task 2.1 [조사] — dead 링크 재확인 (HTTP 체크)

- **파일:** `scripts/c01_c08_validation_data/dead_links.json`, `scripts/c01_c08_validation_data/dongnam_npmb.json`
- **산출물:** `67-live-dead-links-reconfirmed.md`
- **동작:**
  1. dead_links.json(53건) + dongnam_npmb.json(42건)의 target URL 재구성
  2. URL 인코딩: `urllib.parse.quote(slug, safe='-')`
  3. HTTP HEAD 체크 (timeout=5, User-Agent)
  4. 블로그별 dead 링크 집계

**영향 블로그 (현재 데이터 기준):**
- camping-hugo, pet-hugo, beauty-hugo, baby-hugo, cuap-hugo (5개 블로그)
- 나머지 5개 블로그: 75개 URL 출처 확인 필요

#### Task 2.2 [PRODUCTION] — 블로그별 dead 링크 제거 (파일 수정)

- **파일:** 각 블로그 `content/posts/{slug}/index.md`
- **동작:**
  1. **크로스셀 링크 제거:** `build_cross_sell_card()`가 생성하는 크로스셀 카드가 dead 타겟을 가리키는 경우
     - 방안: cuap_entities DB에서 해당 dead 엔티티의 published=0 전환 (Wave 1) → 크로스셀 카드에서 자동 제외
     - **파일 직접 수정 불필요** (DB 변경으로 해결)
  2. **기타 dead 링크:** content 파일 내 일반 마크다운 링크가 dead URL인 경우 파일 수정
  3. diff 준비 (변경 전/후 비교)

**핵심:** 크로스셀 dead 링크는 `cuap_entities` DB의 published=0 전환으로 해결 → 파일 수정 불필요. 일반 콘텐츠 링크만 파일 수정 대상.

#### Task 2.3 [DEPLOY] — 블로그별 Hugo 빌드 + wrangler 재배포

- **파일:** 각 블로그 site_path (config/blogs.d/*.yaml 참조)
- **동작:**
  1. 블로그별 순차 실행 (동시 배포 방지)
  2. Hugo 빌드: `HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes hugo --gc --minify --source {site_path}`
  3. 빌드 성공 확인 (0 errors)
  4. wrangler 재배포: `python3 dispatcher.py {blog_id}` 또는 deploy.py
  5. 블로그당 1회 배포

**주의:**
- `CLOUDFLARE_API_TOKEN` env var 제거 후 배포
- `--commit-dirty=true` 사용 금지
- 배포 직렬화: `/tmp/wrangler_deploy.lock`

#### Task 2.4 [검증] — 라이브 HTTP 확인 (제거 검증)

- **파일:** 변경 없음. 산출물: 라이브 확인 결과
- **동작:**
  1. 제거된 dead 링크 URL HTTP HEAD 확인 → 404 유지 또는 다른 페이지로 대체 확인
  2. 크로스셀 카드 제거 확인: 실제 블로그 페이지에서 크로스셀 카드가 안 보이는지 샘플 확인
  3. Hugo 빌드 정상 확인 (에러 없음)

**기대 결과:**
```
- dead_links.json 기반 크로스셀: DB published=0 → 빌드 시 크로스셀 카드 미포함 → 라이브에서 사라짐
- 일반 dead 링크: 파일 제거 → 빌드 반영 → 라이브 404 소멸
```

---

### Wave 3: 백필 재등록 차단 (E3) — 조건부 [R2 결과: backfill_cuap_entities.py는 안전]

#### Task 3.1 [조사] — 관련 스크립트 분석 (완료)

- **분석 결과 (완료):**
  - `backfill_cuap_entities.py` (108줄): INSERT OR IGNORE만 수행 → published=0을 published=1로 **변경하지 않음** → **안전**
  - `fix_cuap_all_entities.py` (91줄): published=1 엔티티 중 실제 post 없는 것을 published=0으로 변경 → **방안 B 전에 실행하면 안 됨**
  - `fix_cuap_entity_urls.py`: 미발행 글 published=0 변경 (80-97줄) → 주의

#### Task 3.2 [주의] — fix_cuap_all_entities.py 실행 금지 확인

- **파일:** 해당 없음 (실행하지 않음)
- **동작:**
  1. 방안 B(published=0 전환) 실행 전 `fix_cuap_all_entities.py` 실행 금지 확인
  2. 방안 B 이후 실행해야 한다면, published=0 대상 목록을 미리 백업한 후 실행
  3. 실행 필요 시: 사전 카운트 → 파일럿 1건 → 검증 → 전체 순서 준수

**결론:** `backfill_cuap_entities.py`는 URL 검증 추가 **불필요**. `fix_cuap_all_entities.py`만 실행 순서 주의.

#### Task 3.3 [검증] — dry-run 확인

- **동작:**
  1. `backfill_cuap_entities.py` --dry-run 옵션 확인 (없으면 코드 리뷰로 확인)
  2. 실제 실행 전 DB 백업 (git tag 또는 DB 복사)
  3. 1개 블로그만 대상으로 파일럿 실행 → 결과 확인

---

### Wave 4: 오토트리아지 실모드 등록 (E4)

#### Task 4.1 [조사] — 서버 의존성 조사 (완료)

- **파일:** `scripts/auto_triage.py`, `ops_dashboard/app.py`, `com.5000.dashboard.plist`
- **조사 결과 (완료):**
  - `auto_triage.py:28`: `DASHBOARD_URL = "http://localhost:5060"`
  - `auto_triage.py:587-603`: 4개 API 엔드포인트 호출, try/except로 오류 처리
  - **현재 서버:** PID 94429가 `ops_dashboard/app.py`(포트 5060) 수동 실행 중
  - **launchd:** `com.5000.dashboard.plist`는 `data/dashboard/app.py`(포트 5050) 실행 — **잘못된 앱**. ops_dashboard(5060)는 launchd 미등록
  - 서버 죽으면: `fetch_dashboard_data()`가 `{"error": ...}` 반환 → fail_checks=[] → fail_checks 기반 트리아지 조용히 스킵 (크래시 아님)

#### Task 4.2 [PRODUCTION] — 서버 의존성 해소 (launchd 등록)

- **파일:** `~/Library/LaunchAgents/com.5000.ops-dashboard.plist` (신규), `ops_dashboard/app.py` (변경 없음)
- **동작:**
  1. **신규 launchd plist 생성:** `com.5000.ops-dashboard.plist`
     - ProgramArguments: `/Users/twinssn/Projects/5000/.venv/bin/python`, `ops_dashboard/app.py`
     - WorkingDirectory: `/Users/twinssn/Projects/5000`
     - RunAtLoad: true, KeepAlive: true
     - StandardOutPath: `/tmp/5000-ops-dashboard.out.log`
     - StandardErrorPath: `/tmp/5000-ops-dashboard.err.log`
  2. **기존 plist 수정:** `com.5000.dashboard.plist`가 `data/dashboard/app.py`(포트 5050)를 실행하는 것이 맞는지 확인. ops_dashboard(포트 5060)와 혼동 주의.
  3. launchctl load 등록
  4. 포트 5060 청취 확인: `lsof -i :5060`
  5. **현재 수동 실행 중인 PID 94429 처리:** launchd 등록 후 기존 프로세스 종료 (중복 실행 방지)

**참고:** `data/dashboard/app.py`(포트 5050, analytics 대시보드)는 별도 launchd(`com.5000.dashboard.plist`)로 이미 설정됨. ops_dashboard(포트 5060)와 구분 필요.

#### Task 4.3 [검증] — 실모드 전환 테스트 (오발송 0)

- **파일:** 변경 없음. 산출물: 테스트 결과
- **동작:**
  1. **사전 리뷰:** dry-run 결과(230건 중 자동처리 97건)의 자동처리 97건이 실모드에서 실제 발송되어도 문제 없는지 검토
  2. `PROBLEM_ALERT_DRY_RUN=0` 설정
  3. 오토트리아지 실행: `PROBLEM_ALERT_DRY_RUN=0 python scripts/auto_triage.py`
  4. **텔레그램 발송 확인:** 실제 발송된 알림 내용 검토 → 사람 개입 불필요한 알림이 포함됐는지 확인
  5. **백업:** 실모드 실행 전 텔레그램 알림 로그 백업

**현재 dry-run 결과 (참고):**
```
총 알림: 230건
자동 처리: 97건 (silent_skip + log_only + summary_append + retry)
사람 호출: 26건
silent skip: 107건

유형별:
  excluded: 69건, P02: 36건, leak_detected: 26건, known_issue: 25건,
  P14: 25건, standard_compliance: 22건, ... (총 230건)
```

**주의:** 실전 발송 시 텔레그램 알림 폭탄 가능 — 먼저 소량 블로그로 제한 테스트 권장

#### Task 4.4 [CONFIG] — launchd 등록 (오토트리아지 + ops_dashboard)

- **파일:** launchd plist 2개 (신규)
- **동작:**
  1. **ops_dashboard launchd 등록** (Task 4.2에서 수행)
     - plist: `com.5000.ops-dashboard.plist`
     - 대상: `ops_dashboard/app.py` (포트 5060)
  2. **오토트리아지 launchd 등록** (신규)
     - plist: `com.5000.auto-triage.plist`
     - ProgramArguments: `.venv/bin/python`, `scripts/auto_triage.py`
     - 실행 주기: 매일 1회 (권장: 새벽 03:00)
     - RunAtLoad: false (스케줄 실행)
     - WorkingDirectory: `/Users/twinssn/Projects/5000`
     - 환경변수: `PROBLEM_ALERT_DRY_RUN=0` (실모드)
     - StandardOutPath/StandardErrorPath 로그 설정
  3. `launchctl load` 등록 (2개)
  4. 등록 확인: `launchctl list | grep -E "ops-dashboard|auto-triage"`

#### Task 4.5 [CONFIG] — watchdog 감시 범위 확장

- **파일:** `scripts/analytics_watchdog.sh` (88줄, 현재 scheduler + analytics만 감시)
- **동작:**
  1. **ops_dashboard 생존 확인 추가** (보조 감시):
     - `pgrep -f "ops_dashboard/app.py"` 또는 `lsof -i :5060` 확인
     - PID 없음 → 로그 기록 + (launchd KeepAlive가 자동 복구하므로 긴급 알림은 선택)
  2. **auto_triage 마지막 실행 시각 확인 추가**:
     - `logs/auto_triage_summary.log` 마지막 수정 시각 확인
     - 예상 실행 주기(예: 27시간) 대비 미실행 시 로그 기록 (경고는 선택)
  3. **기존 scheduler 감시는 그대로 유지** (변경 없음)
  4. watchdog 로그 포맷 통일

**참고:** ops_dashboard는 launchd KeepAlive로 자동 재시작되므로 watchdog에서의 death 알림은 보조적. auto_triage는 launchd 스케줄로 실행되므로 미실행 감지가 주요 목적.

#### Task 4.6 [검증] — silent_skip 오삼킴 검증

- **파일:** `scripts/auto_triage.py:276-327` (`_matches_subtype`), `scripts/auto_triage_rules.yaml`
- **동작:**
  1. **키워드 분류 확인 완료:**
     - `informational_keyword` (auto_triage.py:284-292): "근교", "추천", "가이드", "비교", "방법", "후기", "리뷰", "TOP", "순위" 등 + `insufficient_products`/`irrelevant_products` → silent_skip
     - `commercial_keyword_fail` (auto_triage.py:294-298): "추천", "비교", "리뷰", "가격", "구매", "할인", "베스트", "TOP", "순위" 등 → summary_append
     - **위험:** "추천" 키워드가 양쪽 서브타입에 모두 매칭 가능 → 규칙 YAML 우선순위에 따라 처리 방식 결정
  2. **규칙 YAML 확인:** `silent_skip`이 적용된 problem_id와 조건 확인
     - P14 서브타입 `informational_keyword` → silent_skip (YAML:116-118)
     - 기타 auto_skip_possible/auto_handle 타입 → silent_skip
  3. **샘플 검증:** 실제 트리아지 결과(230건)에서 silent_skip 107건의 키워드 분포 확인
     - "추천" 키워드 포함 silent_skip이 상품성 글에서 발생했는지 샘플 체크
     - 오삼킴 의심 케이스 추출 → 수동 검토
  4. **오삼킴 발견 시:** 규칙 YAML 조정 또는 키워드 필터 수정

**현행 규칙의 잠재적 문제:** "추천" 키워드가 정보성으로 분류되면 silent_skip, 상업성으로 분류되면 summary_append. 동일 키워드가 맥락에 따라 다르게 처리되어야 하는데, 현재 로직은 첫 매칭된 서브타입 적용. 규칙 YAML의 서브타입 순서가 중요.

---

### Wave 5: 최종 라이브·무인 검증 (E5)

#### Task 5.1 [검증] — 라이브 표본 dead 링크 0 확인

- **파일:** 변경 없음. 산출물: 검증 결과
- **동작:**
  1. 라이브 블로그 표본 선택 (전체 10개 블로그 중 대표 블로그)
  2. 각 표본 블로그의 포스트 링크 크롤링/확인
  3. dead 링크 0건 확인 (또는 잔여 건수·근거 기록)

**표본 선정 기준:**
- 영향 받았던 10개 블로그 중 대표 3-5개
- 자주 방문하는 페이지 우선

#### Task 5.2 [관찰] — 자연 사이클 알림 관찰

- **파일:** 변경 없음. 산출물: 관찰 기록
- **동작:**
  1. 오토트리아지 실모드 등록 후 1회 이상 자연 사이클 실행 확인
  2. Telegram 알림 내용 확인:
     - 사람 개입이 진짜 필요한 것만 오는지
     - 나머지는 대시보드/요약으로 흡수되는지
  3. 알림 건수·유형 기록

#### Task 5.3 [보고] — Exit criteria 5항목 충족 표로 확정 + 최종 보고

- **파일:** `67-FINAL-REPORT.md`
- **동작:**
  1. Exit criteria 5항목 각각 충족 여부 확인
  2. 충족/비충족 근거 기록
  3. 미충족 항목 있으면 사유·대안 명시
  4. 한 줄 결론 작성

**Exit criteria 확인 표:**

| # | 기준 | 상태 | 근거 |
|---|------|------|------|
| 1 | 라이브 dead 링크 0건 | ○ | Task 5.1 결과 |
| 2 | dead 엔티티 재발 방지 3중 완결 | ○ | 방안 A(완료) + 방안 B(Task 1.2) + 백필 차단(Task 3.2) |
| 3 | 오토트리아지 실모드·스케줄등록 + 서버 의존 해소 | ○ | Task 4.2~4.5 결과 |
| 4 | 텔레그램 진짜 신호만 | ○ | Task 5.2 관찰 결과 |
| 5 | 사람 개입 "하루 1~2회 요약 확인" 수준 입증 | ○ | 수치 근거 |

---

## 검증 명령

### 블로그별 Hugo 빌드
```bash
HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes hugo --gc --minify --source {site_path}
```

### wrangler 배포 (대시보드 서버 토큰 제거)
```bash
# dispatcher.py 사용 권장
python3 /Users/twinssn/Projects/5000/dispatcher.py {blog_id}

# 또는 deploy.py 직접 사용 시
export CLOUDFLARE_API_TOKEN=$(env -u CLOUDFLARE_API_TOKEN wrangler auth token 2>/dev/null | tail -1)
python3 -c "import sys; sys.path.insert(0, '/Users/twinssn/Projects/5000'); from shared.publishers.deploy import deploy_site; deploy_site('{site_path}', '{blog_id}')"
```

### 라이브 HTTP 확인
```bash
curl -I -s {URL} | head -1
# 또는
python3 -c "import requests; r = requests.head('{URL}', timeout=10); print(r.status_code)"
```

### 오토트리아지 실모드 테스트
```bash
PROBLEM_ALERT_DRY_RUN=0 python3 {autotriage_script}
```

---

## 진행률 추적

| Wave | Task | 상태 | 비고 |
|------|------|------|------|
| 0 | T0.1 리서치 검토 + 게이트 판정 | ○ | 게이트 미통과 시 집행 불가 |
| 1 | T1.1 dead 엔티티 alive 재확인 | ○ | |
| 1 | T1.2 published=0 UPDATE (테스트2 포함) | ○ | DB 작업 |
| 1 | T1.3 before/after 대조 | ○ | |
| 2 | T2.1 dead 링크 재확인 | ○ | |
| 2 | T2.2 블로그별 dead 링크 제거 | ○ | 파일 수정 |
| 2 | T2.3 블로그별 빌드 + 재배포 | ○ | 배포 작업 |
| 2 | T2.4 라이브 HTTP 확인 | ○ | |
| 3 | T3.1 backfill 분석 | ○ | 조건부 |
| 3 | T3.2 URL 검증 추가 | ○ | 조건부 |
| 3 | T3.3 dry-run 검증 | ○ | 조건부 |
| 4 | T4.1 서버 의존성 조사 | ○ | |
| 4 | T4.2 서버 의존성 해소 | ○ | |
| 4 | T4.3 실모드 전환 테스트 | ○ | |
| 4 | T4.4 launchd 등록 | ○ | |
| 4 | T4.5 watchdog 감시 확장 | ○ | |
| 4 | T4.6 silent_skip 오삼킴 검증 | ○ | |
| 5 | T5.1 라이브 표본 dead 0 확인 | ○ | |
| 5 | T5.2 자연 사이클 알림 관찰 | ○ | |
| 5 | T5.3 Exit criteria 표 + 보고 | ○ | |

**진행률: 8/21 tasks 조사 완료 (38%) — G1·G2·G4 통과, G3 부분 통과**

| Wave | Task | 상태 | 비고 |
|------|------|------|------|
| 0 | T0.1 리서치 검토 + 게이트 판정 | ✓ 완료 | G1·G2·G4 통과, G3 부분 통과 |
| 1 | T1.1 dead 엔티티 alive 재확인 | ○ 대기 | 데이터 소스 확인됨, 실제 HTTP 체크 필요 |
| 1 | T1.2 published=0 UPDATE (테스트2 포함) | ○ 대기 | T1.1 결과 대기 |
| 1 | T1.3 before/after 대조 | ○ 대기 | |
| 2 | T2.1 dead 링크 재확인 | ○ 대기 | dead_links.json+dongnam 데이터 준비됨 |
| 2 | T2.2 블로그별 dead 링크 제거 | ○ 대기 | 크로스셀은 DB 변경으로 해결, 파일 수정 최소화 |
| 2 | T2.3 블로그별 빌드 + 재배포 | ○ 대기 | |
| 2 | T2.4 라이브 HTTP 확인 | ○ 대기 | |
| 3 | T3.1 backfill 분석 | ✓ 완료 | backfill_cuap_entities.py 안전 확인 |
| 3 | T3.2 URL 검증 추가 | ✗ 불필요 | backfill이 published=0→1 복원하지 않음 |
| 3 | T3.3 dry-run 검증 | ○ 대기 | fix_cuap_all_entities.py 실행 주의 |
| 4 | T4.1 서버 의존성 조사 | ✓ 완료 | ops_dashboard(5060) launchd 미등록, 수동 실행 중 |
| 4 | T4.2 서버 의존성 해소 | ○ 대기 | ops_dashboard launchd 등록 필요 |
| 4 | T4.3 실모드 전환 테스트 | ○ 대기 | 자동처리 97건 사전 리뷰 필요 |
| 4 | T4.4 launchd 등록 | ○ 대기 | ops_dashboard + auto_triage 2개 |
| 4 | T4.5 watchdog 감시 확장 | ○ 대기 | analytics_watchdog.sh 수정 |
| 4 | T4.6 silent_skip 오삼킴이 검증 | ○ 대기 | 규칙 YAML + 실제 데이터 샘플 확인 |
| 5 | T5.1 라이브 표본 dead 0 확인 | ○ 대기 | |
| 5 | T5.2 자연 사이클 알림 관찰 | ○ 대기 | |
| 5 | T5.3 Exit criteria 표 + 보고 | ○ 대기 | |

---

## 잔존 위험

1. **75개 URL 출처 불명:** dead_links.json(53건)+dongnam(42건)=95건 데이터는 있으나, "75개 고유 URL" 출처가 별도로 존재하는지 미확인. 전체 범위 파악을 위해 Phase 67 이전 조사 파일 탐색 필요.
2. **URL 인코딩:** dead_links.json의 slug에 한국어·공백 포함 → HTTP 체크 시 `urllib.parse.quote()` 인코딩 필수. 인코딩 누락 시 false error.
3. **G3 실모드 오발송:** dry-run→실모드 전환 시 자동처리 97건이 실제 텔레그램 발송됨. 사전 리뷰 없이 전환하면 알림 폭탄 가능.
4. **G3 silent_skip:** "추천" 등 겸용 키워드가 정보성/상업성 양쪽 서브타입에 매칭 가능. 규칙 YAML 우선순위에 따라 오삼킴 가능성 존재 → 샘플 검증 필요.
5. **ops_dashboard launchd 등록 후 PID 충돌:** 현재 수동 실행 중인 PID 94429와 launchd가 동시에 실행되면 포트 충돌. launchd 등록 전 기존 프로세스 종료 필요.
6. **com.5000.dashboard.plist 혼동:** 현재 plist가 `data/dashboard/app.py`(포트 5050)를 실행하도록 설정됨. ops_dashboard(포트 5060)와 구분 필요. 기존 plist를 수정할지, 새 plist를 만들지 결정 필요.

---

## 체크포인트: 집행 승인 조건

**현재 상태: 집행 대기 — G3 서버 의존성 해소 필요**

| 조건 | 상태 | 실행 |
|------|------|------|
| G1: dead URL alive 재확인 워크플로우 | ✓ 통과 | 집행 시 HTTP 체크 수행 |
| G2: 백필 재등록 차단 | ✓ 통과 | backfill 안전 확인, fix_cuap_all_entities.py 주의 |
| G3: 오토트리아지 실모드 안전 | ⚠ 부분 통과 | **ops_dashboard launchd 등록 필요** (현재 수동 실행 중, death 시 silent skip) |
| G4: watchdog 3자 감시 | ✓ 통과 | 설계 완료, watchdog 스크립트 수정 필요 |

**▶ 즉시 집행 가능 항목:**
- Wave 1 (E1): DB published=0 정리 — T1.1 dead URL alive 재확인부터 시작
- Wave 2 (E2): 라이브 청소 — 크로스셀 dead 링크는 DB 변경으로 해결 (파일 수정 최소화)

**▶ G3 해소 후 집행 가능 항목:**
- Wave 4 (E4): ops_dashboard launchd 등록 → auto_triage 실모드 실행 → watchdog 확장

**▶ 한 줄 결론:** "Phase 67 PLAN.md 구체화 완료. G1·G2·G4 통과, G3 부분 통과 (ops_dashboard launchd 미등록). 백업 태그 pre-unattended-phase-2026-08-08 생성됨. Wave 1·2는 즉시 시작 가능, Wave 4는 ops_dashboard launchd 등록 후."

_생성: 2026-08-08_
_백업 태그: pre-unattended-phase-2026-08-08_
_리서치 기반: dead_links.json(53건) + dongnam_npmb.json(42건) + auto_triage.py 코드 분석 + ops_dashboard/app.py 분석 + analytics_watchdog.sh 분석_
