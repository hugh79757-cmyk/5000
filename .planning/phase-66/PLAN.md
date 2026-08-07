# Phase 66 — P09 시나리오 A/B 판별 (조사 전용, 수정 금지)

## 목표

연구 결과(66-RESEARCH.md) 기반, P09 현재 상태 확정 + 감지-수정 설계 정합성 조사 + 재발 대비 방향성 제안. 코드 수정·INSERT·배포·fixer 로직 변경·임계값 변경 일체 금지.

## 전제 (연구 완료 — 사실로 취급)

- **P09 알림 로그: 0건** — leak-origin.log(7줄), scheduler.log(223,966줄), deploy.log 어디서도 P09 repeated segments 감지 기록 없음
- **health-hugo 라이브 URL: 모두 Clean** — 확인된 5건 모두 세그먼트 중복 없음
- **pet-hugo 라이브 URL: 모두 Clean** — 확인된 5건 + 다른 포스트 6건 모두 세그먼트 중복 없음
- **deploy.log "range can't iterate" 오류: P09와 무관** — tags YAML repr 문제 (별개 이슈)
- **탐지-수정 이원화는 실재:** P09 감지(segment 중복률) ≠ _fix_repeated_image_urls(substring 연속 반복)

## 현재 상태 확정 — 한 줄

> **현재 P09 알림은 반복 발생하고 있지 않다.** 라이브 콘텐츠는 모두 깨끗하며, P09 감지 로그도 존재하지 않는다. 조사 전제였던 "최근 P09 알림이 뜬 slug들"은 실제 로그에서 확인되지 않았다.

---

## 태스크 1: 현재 상태 확정 (증거 정리)

### 1-1. P09 알림 로그 0건 증거

**확인한 로그 파일:**
- `logs/leak-origin.log` — 7줄, P09 관련 기록 없음
- `logs/scheduler.log` — 223,966줄, P09/repeated segments 감지 기록 없음
- `logs/deploy.log` — P09 알림 기록 없음

**통과 조건:** 위 3개 로그 파일에서 P09 감지 기록이 0건임을 확인.

**입력·방법 제한:**
- dry-run 상한: 최대 3회까지 시도. 3회 모두 재현 실패 시 0단계 증거(로그 확인 결과)로 판정하고 추가 dry-run 중단.
- 합성 URL 금지: 조사 입력으로 임의의 합성/예시 URL을 생성해 사용하지 않음. 재현 입력은 실제 감지 slug의 raw URL 또는 라이브 URL만 사용.
- 로그 검색은 기존 로그 파일의 grep 확인으로 충분 — 별도 dry-run 불필요 시 스킵.

### 1-2. 라이브 URL Clean 증거

**health-hugo (5건 확인):**
- 고함량오메가-고민된다면-검색니즈별-실속-선정: segments=10, unique=10 ✅
- 혈당-관리-돕는-당뇨-건강식품-성분별-핵심-비교: segments=11, unique=10 ✅
- 포인드-비건-손톱영양제-포함-2026년-8월-추천-2만원대-합격점-top-5: segments=11, unique=10 ✅
- 저혈압-증상-완화-돕는-필수-영양-성분과-섭취법: segments=11, unique=10 ✅
- 여드름-피부-영양제-추천-고민된다면-지금-사야-하는-이유: segments=11, unique=10 ✅

**pet-hugo (5건 확인):**
- 강아지-쿨매트-여름철-반려견-열사병-예방-필수템-비교: segments=10/6/6, unique=10/6/6 ✅
- 소형견-산책용-강아지유모차-모델별-장단점-비교: segments=10/6/6, unique=10/6/6 ✅
- 반려견-건강을-위한-강아지사료-성분-분석과-급여-팁: segments=10/6/6, unique=10/6/6 ✅
- 강아지방석-체형별-맞춤형-메모리폼-고르는-꿀팁: segments=10/6/6, unique=10/6/6 ✅
- 흡수-빠른-단백질-보충제-가수분해-유청-단백질-비교-분석: segments=11/6/6, unique=10/6/6 ✅

**pet-hugo 추가 (6건 확인, 다른 포스트):**
- 모든 이미지 URL segments=6, unique=6 ✅ (thumbnails 경로)

**통과 조건:** health-hugo 5건 + pet-hugo 5건 + 추가 6건 = 총 16건 모두 segment 고유 확인.

**입력 제한:**
- 입력으로 사용하는 URL은 실제 P09 감지가 발생한 slug의 raw URL(생성 직후 본문) 또는 라이브 URL(게시된 페이지 소스)만 허용.
- 임의의 URL 생성·합성(예: `https://img.example.com/a/a/a/...` 형태의 테스트용 가상 URL)을 조사 입력으로 사용하지 않음.
- 66-RESEARCH.md 0-2절에 기록된 실제 감지 slug URL 목록이 입력 출처.

---

## 태스크 2: 감지-수정 설계 정합성 조사 (Python 시뮬레이션)

### 2-1. 조사 대상 패턴

_fix_repeated_image_urls(_has_repeated_pattern)가 segment 반복을 잡을 수 있는지 시뮬레이션:

| # | 패턴 | 예시 |
|---|------|------|
| A | 짧은 세그먼트 반복 | `/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/a/` (19회) |
| B | 2개 세그먼트 패턴 반복 | `/ab/cd/ab/cd/ab/cd/ab/cd/ab/cd/ab/cd/` (6회) |
| C | 긴 세그먼트 반복 | `/curation-images/curation-images/curation-images/curation-images/curation-images/` (5회) |
| D | date 경로 반복 | `/2026/08/07/2026/08/07/2026/08/07/` (3회) |
| E | 5개 고유 segment 그룹 반복 | `/a1/b2/c3/d4/e5/` ×3 (15 unique segments 중 5 unique) |
| F | 3개 고유 segment 그룹 반복 | `/ab/cd/ef/` ×4 (12개 중 3 unique) |

### 2-2. 시뮬레이션 결과 (연구 단계 확인)

| # | 패턴 | segments | unique | P09 감지 | _fix 수정 가능 | 판정 |
|---|------|----------|--------|----------|---------------|------|
| A | `/a/` ×19 | 19 | 1 | O (18 of 19) | O (`/a/a` x8) | 감지·수정 모두 됨 |
| B | `/ab/cd/` ×6 | 13 | 2 | O (11 of 13) | O (`/ab/cd` x5) | 감지·수정 모두 됨 |
| C | `/curation-images/` ×5 | 9 | 5 | X (5 < 9/2 거짓) | O (`/curation-images` x5) | 감지X·수정O (P09 오탐 아님, 그냥 감지 안 됨) |
| D | `/2026/08/07/` ×3 | 10 | 3 | X (3 < 10/2 거짓) | X (substring 연속 반복 없음) | 감지X·수정X |
| E | 5개 고유 ×3 | 16 | 6 | O (10 of 16) | X (substring 연속 반복 없음) | **감지O·수정X → 시나리오 A 가능성** |
| F | 3개 고유 ×4 | 13 | 4 | O (9 of 13) | X (substring 연속 반복 없음) | **감지O·수정X → 시나리오 A 가능성** |

### 2-3. 핵심 발견

**감지O·수정X인 패턴이 실존한다:**
- Task E: 5개 고유 segment가 3회 반복 → P09 감지 O, _fix_repeated_image_urls 수정 X
- Task F: 3개 고유 segment가 4회 반복 → P09 감지 O, _fix_repeated_image_urls 수정 X

즉, **감지-수정 이원화로 인해 "감지되지만 수정 못 하는" 패턴의 존재 가능성은 확인된다.** 하지만 현재 라이브에는 이런 패턴의 URL이 존재하지 않는다 (태스크 1의 전수 확인 결과).

**통과 조건:**
- [ ] 위 6개 패턴별 시뮬레이션 결과 표 작성 완료
- [ ] 감지O·수정X 패턴 실존 확인
- [ ] 현재 라이브에 해당 패턴 없음 확인 (태스크 1 증거와 교차)

---

## 태스크 3: 재발 대비 제안 (실행 금지)

### 3-1. 감지-수정 단일 진실 소스 통합 방향성

현재 이원화:
- P09 감지: segment 기반 (problem_detectors.py:59)
- URL 수정: substring 기반 (writer.py:219)

**방향성 제안 (코드 수정 지시 아님):**
- segment 반복을 고칠 수 있게 _fix_repeated_image_urls 확장 → 감지된 패턴을 실제로 제거할 수 있게 됨
- 또는 감지 로직을 substring 기반으로 일원화 → 감지·수정 동일 패턴 사용
- 두 방향 중 어느 쪽이 나은지는 재발 시 실제 URL 패턴에 따름

### 3-2. 감지 시점 조정 방향성

현재: post_generate (raw, _sanitize_body 이전)

**방향성 제안:**
- post_validate로 이동 → sanitize 이후 "실제로 남았는지"만 알림
- 단, CoT 누수(BUG-54-001)처럼 sanitize 이후 감지로 늦어지는 문제가 URL 반복에도 적용되는지 확인 필요
- URL 반복은 CoT와 달리 _fix_repeated_image_urls가 sanitize 단계에서 이미 수정하므로, post_validate 이동 시 "이미 수정된 문제"에 대한 알림이 줄어들 수 있음

### 3-3. 제안 정리 (실행 금지)

| 제안 | 방향성 | 우선도 |
|------|--------|--------|
| 감지-수정 단일 진실 소스 통합 | segment 반복도 고칠 수 있게 _fix_repeated_image_urls 확장 or 감지를 substring 기반으로 일원화 | 중 |
| 감지 시점 재검토 | post_generate → post_validate 이동 검토 (실제 잔존만 알림) | 하 |
| 현재 상태 모니터링 | P09 로그 0건 + 라이브 Clean → 현재 재발 없음. 재발 시 Task 2의 감지O·수정X 패턴template으로 긴급 조사 | 하 |

---

## 검증 기준

- [ ] 태스크 1: P09 알림 로그 0건 + 라이브 URL 전수 Clean 증거 정리 완료
- [ ] 태스크 1: "현재 P09 반복 발생 없음" 한 줄 확정 완료
- [ ] 태스크 2: 6개 패턴별 시뮬레이션 결과 표 작성 완료
- [ ] 태스크 2: 감지O·수정X 패턴 실존 확인 + 현재 라이브에 없음 확인
- [ ] 태스크 3: 재발 대비 방향성 2가지 제시 완료 (코드 수정 지시 없음)
- [ ] 금지 사항 일체 위반 없음 확인

---

## 금지 사항 (재명시)

- ❌ `_fix_repeated_image_urls` 로직 정의 수정 금지 (호출·반환값 확인은 허용)
- ❌ P09 감지 임계값 변경
- ❌ tags YAML 수정
- ❌ hugo_writer 훅 변경
- ❌ 스케줄러 조작
- ❌ content/posts/에 새 파일 생성
- ❌ DB INSERT/UPDATE/DELETE
- ❌ wrangler deploy / Hugo 빌드
- ❌ 어떤 처방도 실행하지 않음 (판정·제안까지만)

---

PLAN.md 작성 완료. 다음: `/gsd-execute-phase --phase 66` 또는 `/gsd-execute-phase -p 66`으로 실행.

> 이 Phase는 조사·판정·제안만 수행한다. 코드 수정 없음. 스케줄러 정지 유지.
