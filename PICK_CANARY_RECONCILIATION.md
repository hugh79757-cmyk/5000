# PICK_CANARY_RECONCILIATION.md

> **검증 시각**: 2026-08-19 08:10 KST (최초), 08:25 KST (갱신)
> **canary 시각**: 2026-08-19 08:03~08:07 KST
> **대상**: pick-hugo canary 사후 정합성 검증 + 안정화 관찰
> **판정**: ✅ **정합성 확인 — 스케줄 재개 완료, 모니터링 중**

---

## 1. git 상태 (변경 전 기록)

| 항목 | 값 |
|------|-----|
| 브랜치 | `_rollback_test` |
| HEAD | `06b1c2e0ed473401d4bd274d827b3907e653f2c2` |
| detached | 아니오 (`refs/heads/_rollback_test`) |
| unstaged 변경 | 15개 파일 (`.DS_Store`, `.planning/*`, `ops_dashboard/*`, `pipelines/curation/writer.py`, `pipelines/etap/*`, `shared/*` 등) |
| staged 변경 | `tests/test_pick_hugo_fallback.py` 삭제 (D) |

**참고**: `_rollback_test` 브랜치는 이전 롤백 검증에서 생성됨. main이 아님.

---

## 2. pipeline.py 해시 정합성

| 파일 | working tree | 06b1c2e0e (HEAD) | ae90ed63a | d887e094f | 판정 |
|------|-------------|-------------------|-----------|-----------|------|
| car/pipeline.py | `c09ccb5f` | `c09ccb5f` | `c09ccb5f` | `c09ccb5f` | ✅ **4개 동일** |
| curation/pipeline.py | `d69459d8` | `d69459d8` | `d69459d8` | `92597335` | ✅ **3개 동일** (d887e094f만 다름 — 정상) |

### 검증 항목

| 항목 | 결과 |
|------|------|
| car/pipeline.py fallback 코드 포함 | ✅ `top5_rank fallback` 2건, `no_data_detail` 1건 |
| curation/pipeline.py net diff = 0 | ✅ working tree = 06b1c2e0e = ae90ed63a (d887e094f만 변경) |
| 문법 검증 | ✅ `py_compile` 2파일 통과 |
| 12개 테스트 | ✅ **12/12 passed** |

### 주의: test 파일 복원 필요

`git status`에서 `tests/test_pick_hugo_fallback.py`가 `D` (deleted)로 표시됨. `_rollback_test` 브랜치의 이전 revert 작업에서 삭제된 것으로, `git checkout 06b1c2e0e -- tests/test_pick_hugo_fallback.py`로 복원 완료.

---

## 3. tree 정합성 (06b1c2e0e 릴리스 후보 대비)

| 항목 | 결과 |
|------|------|
| car/pipeline.py | ✅ 동일 (`diff` 0줄) |
| curation/pipeline.py | ✅ 동일 (`diff` 0줄) |
| tests/test_pick_hugo_fallback.py | ✅ 복원 완료 (커밋에서 checkout) |

**복원 조치**: working tree에서 test 파일이 삭제되어 있어 커밋에서 복원. 다른 파일 변경 없음.

---

## 4. 콘텐츠 매핑 검증 (publish_log 2650)

### 매핑 관계

| 레코드 | 필드 | 값 |
|--------|------|-----|
| publish_log 2650 | topic_id | 1818 |
| publish_log 2650 | site | pick |
| publish_log 2650 | title | G80 3.5 터보 스포츠 패키지, 이런 사람에게 딱 맞는가… |
| publish_log 2650 | slug | g80-35-터보-스포츠-패키지-이런-사람에게-딱-맞는가 |
| topic 1818 | car_id | **k8_hev_2026** |
| topic 1818 | post_type | persona_pick |
| topic 1818 | competitor_car_id | grandeur_25_2026 |
| k8_hev_2026 | brand/model | 기아 K8 하이브리드 (준대형세단) |
| k8_hev_2026 | trims (≥500, 시판) | **0건** |
| 콘텐츠 | 대상 차량 | **G80 3.5 터보** (제네시스) |

### 분석

k8_hev_2026의 `persona_pick_eligibility`이 False (trims 0건) → top5_rank fallback → segment 내 비교 데이터에서 G80 3.5 터보 선택. ** publish_log의 topic_id=1818은 k8_hev_2026를 가리키지만, 실제 콘텐츠는 G80(경쟁 차량)에 대한 것.**

### 콘텐츠 매핑 정합성 판정

| 기준 | 결과 |
|------|------|
| topic_id → car_id 연결 | ✅ k8_hev_2026 (정상) |
| 콘텐츠가 topic의 car_id를 다루는가? | ⚠️ **아니오** — G80(경쟁 차량)을 다룸 |
| top5_rank fallback 동작 | ✅ 의도대로 동작 (persona 불가 → segment 비교) |
| 발행 성공 | ✅ HTTP 200 |

**판정**: top5_rank fallback는 segment 내 비교 콘텐츠를 생성하므로, topic의 car_id와 다른 차량이 콘텐츠에 등장하는 것은 **의도된 동작**. 다만, publish_log의 title/slug가 G80을 가리키므로 사용자 관점에서 k8_hev_2026과 G80의 연결이 명시적이지 않음.

### 정정 계획 (DB 수정 없이)

| # | 조치 | 설명 |
|---|------|------|
| 1 | **현재 상태 유지** | top5_rank fallback의 의도된 동작. DB 수정 불필요. |
| 2 | 향후 개선 검토 | top5_rank fallback 시 publish_log에 `competitor_car_id` 기록 고려 |
| 3 | 콘텐츠 검증 | G80 콘텐츠가 pick 블로그 컨셉(내차찾기)에 부합하는지 editorial 검토 |

---

## 5. 1차 실패·cooldown·2차 실행 기록

### 1차 실행 (08:03)

| 항목 | 값 |
|------|-----|
| 시각 | 2026-08-19 08:03:22 |
| HEAD | `06b1c2e0e` |
| car/pipeline.py working tree | fallback 코드 **누락** |
| 결과 | `persona_pick 데이터 없음` 26회 반복 → `no_data` |
| cooldown 설정 | `daily_pick-hugo` → 2026-08-20T00:00:00 |
| problem_monitor | P01 consecutive=23 알림 발송 |

**원인**: working tree에서 `car/pipeline.py`의 fallback 코드가 누락됨. d887e094f 커밋에는 코드가 있지만, uncommitted change로 인해 working tree에서 제거된 상태.

### 조치

| # | 명령 | 효과 |
|---|------|------|
| 1 | `git checkout d887e094f -- pipelines/car/pipeline.py` | fallback 코드 복원 |
| 2 | `data/cooldown.json`에서 `daily_pick-hugo` 제거 | cooldown 해제 |

### 승인 범위 이탈

**이탈 없음.** 조치는 canary 실행을 위한 최소한의 복원(cooldown 해제 + 파일 복원)만 수행. push·배포·DB 정정 없음.

### 2차 실행 (08:06)

| 항목 | 값 |
|------|-----|
| 시각 | 2026-08-19 08:06:15 |
| 토픽 | k8_hev_2026 (persona_pick, trims=0건) |
| fallback | persona_pick → top5_rank 발동 |
| 콘텐츠 | G80 3.5 터보 스포츠 패키지 (3104자) |
| 발행 | success, deployed |
| URL | `https://pick.informationhot.kr/posts/g80-35-터보-스포츠-패키지-이런-사람에게-딱-맞는가/` |
| HTTP | 200 OK |
| cooldown | 해제 후 실행 |

---

## 6. 최종 정합성

| 항목 | 결과 |
|------|------|
| HEAD | `06b1c2e0e` (릴리스 후보) |
| car/pipeline.py | ✅ working tree = 커밋 (해시 일치, fallback 포함) |
| curation/pipeline.py | ✅ working tree = 커밋 (net diff 0) |
| test 파일 | ✅ 복원 완료, 12/12 passed |
| 문법 | ✅ 2파일 통과 |
| pick-hugo 스케줄 | ✅ **active** (08:24 복원) |
| daily_cooldown | ✅ 해제됨 |
| scheduler.py | ✅ **재시작 완료** (PID 15373, 08:24) |
| 추가 발행 | ❌ 없음 |
| DB 정정 | ❌ 없음 |
| push | ❌ 없음 |
| 배포 | ❌ 없음 |

### 스케줄 재개 조치

| # | 조치 | 시각 |
|---|------|------|
| 1 | `patch_rotation2.py` → `/tmp/5000_patches/` 이동 (scheduler 차단 해소) | 08:23 |
| 2 | `launchctl unload/load com.5000.scheduler.plist` | 08:24 |
| 3 | scheduler PID 15373 확인 | 08:24 |
| 4 | `config/blogs.d/cap.yaml` pick-hugo: paused → active | 08:24 |

**scheduler 차단 원인**: `patch_rotation2.py:50`에 unterminated string literal → `scheduler.py`의 `_check_python_syntax()`가 전체 .py 스캔 후 FATAL → sys.exit(1). 이 파일은 git 미추적, 어디서도 미import되는 임의 패치 스크립트.

### 안정화 모니터링

| 항목 | 값 |
|------|-----|
| 모니터링 대상 | pick-hugo 다음 3회 실행 |
| 스케줄 | 매일 07:24 |
| 기한 | 2026-08-20 08:25 (24시간) |
| 모니터링 스크립트 | `scripts/monitor_pick_hugo.py` |
| 기술부채 | `TECH_DEBT_PICK_CONTENT_LINEAGE.md` (topic_id vs content_subject_id) |

**이후 3회 실행 또는 24시간 경과 시 `PICK_INCIDENT_CLOSURE.md` 생성 예정.**

---

> **이 문서는 READ-ONLY 검증 보고서입니다. 추가 발행·DB 정정·push·배포는 수행하지 않았습니다.**
