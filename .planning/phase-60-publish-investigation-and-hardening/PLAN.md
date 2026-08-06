# Phase 60: 발행/배포 중단 조사 + 알림 재설계 + 대시보드 보강 + 확장 비롯

> **Status:** 📋 Planned (S1 완료)
> **Created:** 2026-08-06
> **Mode:** S1~S5 순차 실행, 커밋 per step
> **Risk:** MEDIUM — 조사 기반, 코드 수정은 Part 2에서만 발생
> **⚠️ 순서 위반 기록:** Phase 59 리팩토링(59-01,06,07,08,09,11)이 Phase 60 조사 이전에 실행됨.
>   `pre-refactor-baseline` 태그를 소급 생성(d85095152)하여 기준점 확보.

---

## Overview

**Goal:** 발행/배포 중단의 근본 원인을 규명하고, 대시보드를 완성하며, 알림 체계를 재설계하여 파이프라인이 자가 치유되는 구조를 구축한다.

**Success Criteria:**
1. `pre-refactor-baseline` / `post-refactor-baseline` 태그 2개 존재
2. ops_dashboard 자기검증 4종 통과 (CUAP stale, senior 썸네일, CJK, 표준위반)
3. 각 블로그의 발행 공백 원인이 (a) 차단 반복 (b) 발행 시도 중단 (c) 배포 유실 (d) 리팩토링 회귀로 판정되고 근거 제시됨
4. P09가 재발하는 경우 공통 코드 결함 1곳 수정으로 동시 해결
5. 정상 차단 이벤트는 실시간 푸시 없이 ops.db에 누적, 일일 요약만 발송
6. 대시보드 체크가 cjk_leak 슬러그, 크로스링크 일관성까지 검사
7. 새 블로그/계열 편입이 YAML 추가만으로 가능 (코드 수정 불필요)
8. 확장 준비도 지표가 대시보드 첫 화면에 표시

**Dependencies:**
- Phase 59 ops_dashboard (부분 완료 — db.py, app.py, checks/__init__.py 존재)
- publish_ledger 데이터 (data/content.db)
- shared/telegram_notifier.py

---

## S1: pre-refactor-baseline 태그 소급 ✅ 완료

**Goal:** 리팩토링 이전 코드 상태를 태그로 고정
**Status:** ✅ 완료 — `pre-refactor-baseline` 태그 생성

### 결과
- **태그:** `pre-refactor-baseline`
- **커밋:** `d85095152` (2026-08-06 10:33:52)
- **메시지:** "docs(audit): 5000 아키텍처 감사 보고서"
- **근거:** Phase 59 첫 커밋(`62304d24e docs(phase-59): research`) 직전 커밋

### 리팩토링 범위 (이 태그 이후 실행됨)
| Plan | 내용 | 유형 |
|------|------|------|
| 59-01 | ETAP _write_hugo_post 31개 통합 | 리팩토링 |
| 59-06 | Theme audit + shared Blowfish standard | 리팩토링 |
| 59-07 | hotissue-hugo PaperMod → Blowfish | 리팩토링 |
| 59-08 | stock-hugo Congo → Blowfish | 리팩토링 |
| 59-09 | ETAP wrapper design | 리팩토링 |
| 59-11 | flights-hugo naming fix | 리팩토링 |
| 59-02 | Flask app + CLI seed | 인프라 (비리팩토링) |
| 59-03 | Dashboard UI templates | 인프라 (비리팩토링) |
| 59-04 | Cloudflare tunnel setup | 인프라 (비리팩토링) |
| 59-05 | Dashboard alerts + standard compliance | 인프라 (비리팩토링) |

### 롤백 가능 여부
- `pre-refactor-baseline`에서 `git checkout`으로 리팩토링 이전 상태로 복귀 가능
- 단, 개별 Plan별 revert가 더 안전 (한번에 전체 원복보다 증분적)

---

## S2: ops_dashboard 마무리

**Goal:** 대시보드가 진단 도구로서 신뢰할 수 있도록 자기검증 통과
**Risk:** LOW (기존 코드에 check 추가, 기존 기능 미수정)
**Pre-requisite:** S1 완료
**Commit:** S2 완료 시

### 현재 상태 (진단 결과)
| 항목 | 현재 | 목표 | 상태 |
|------|------|------|------|
| blog_lifecycle | 56개 | 85개 | ⚠️ 불일치 |
| known_issues | 39건 | 52건 | ⚠️ 불일치 |
| standard_rules | 테이블 미생성 | 12건 시드 | 🔴 |
| check_results | 0건 | 실행됨 | 🔴 |
| 등록된 check | 0개 | 6개 | 🔴 |
| freshness check | 미구현 | 구현 | 🔴 |
| render_health check | 미구현 | 구현 | 🔴 |
| crosscheck check | 미구현 | 구현 | 🔴 |

### Tasks

#### 2-1: standard_rules 테이블 생성 + 시드
- **파일:** `ops_dashboard/db.py`
- **변경:**
  - `init_db()`에 standard_rules 테이블 CREATE 추가
  - `seed_standard_rules(conn)` 함수로 R01~R12 12건 시드
- **검증:** `python -c "from ops_dashboard.db import *; conn=get_conn(); init_db(conn); print(seed_standard_rules(conn))"` → 12

#### 2-2: checks 모듈 import 활성화
- **파일:** `ops_dashboard/checks/__init__.py`
- **변경:** 하단에 import 추가하여 standard, freshness, render, crosscheck 모듈 자동 로드
- **검증:** `python -c "from ops_dashboard.checks import CHECKS; print(sorted(CHECKS.keys()))"` → 최소 2개(standard_compliance + 신규)

#### 2-3: freshness check 구현
- **파일:** `ops_dashboard/checks/freshness.py` (신규)
- **내용:**
  - 마지막 성공 발행 후 경과일 vs 계열 예상 주기
  - CUAP: 1일, ETAP: 3일, TAP/STAP: 7일 등 계열별 기준
  - register_check("freshness")
- **검증:** `run_all_checks(conn, ['pet-hugo'])`에서 freshness 결과 포함 확인

#### 2-4: render_health check 구현
- **파일:** `ops_dashboard/checks/render.py` (신규)
- **내용:**
  - 도메인 HTTP HEAD 요청 (httpx)
  - 대표글 썸네일/og:image 200 확인
  - adsbygoogle.js 로드 확인
  - register_check("render_health")
- **검증:** `run_all_checks(conn, ['camping-hugo'])`에서 render_health 결과 포함 확인

#### 2-5: crosscheck check 구현
- **파일:** `ops_dashboard/checks/crosscheck.py` (신규)
- **내용:**
  - known_issues auto_detectable ↔ check_results 대조
  - 자동 감지 가능 이슈가 실제로 check에서 감지되는지 검증
  - register_check("gsd_crosscheck")
- **검증:** `run_all_checks(conn)`에서 gsd_crosscheck 결과 포함 확인

#### 2-6: inventory 불일치 규명
- **파일:** `ops_dashboard/investigate_inventory.py` (신규)
- **내용:**
  - config/blogs.d/*.yaml 전체 블로그 수 vs blog_lifecycle 등록 수 대조
  - 누락된 블로그 목록 + 사유 (YAML 미정의, 수동 관리 등)
  - known_issues 39건 vs 52건 차이 원인 분석
- **검증:** 불일치 원인 보고서 출력

#### 2-7: 자기검증 4종 실행
- **대상:** CUAP stale 탐지, senior 썸네일, CJK 릭, 표준 위반
- **방법:** `run_all_checks()` 전수 실행 → "주의 필요"에 최소 1건 노출 확인
- **검증:**
  - `POST /api/run-checks` → 결과 JSON에서 attention_items 최소 1건
  - CUAP stale (예: pet-hugo) 탐지 확인
  - CJK 릭 탐지 확인
  - 표준 위반 탐지 확인

### S2 Verification
```bash
# 1. standard_rules 시드 확인
python -c "
from ops_dashboard.db import get_conn, init_db, seed_standard_rules
conn = get_conn()
init_db(conn)
count = seed_standard_rules(conn)
print(f'standard_rules seeded: {count}')  # → 12
"

# 2. 등록된 check 확인
python -c "
from ops_dashboard.checks import CHECKS
print('Registered:', sorted(CHECKS.keys()))
# → ['freshness', 'gsd_crosscheck', 'render_health', 'standard_compliance'] + 신규
"

# 3. inventory 불일치 보고서
python ops_dashboard/investigate_inventory.py

# 4. 자기검증 4종
python -c "
from ops_dashboard.db import get_conn, init_db
from ops_dashboard.checks import run_all_checks
conn = get_conn()
init_db(conn)
result = run_all_checks(conn)
print(f'Total: {result[\"total\"]}, Pass: {result[\"pass\"]}, Fail: {result[\"fail\"]}')
print(f'Attention items: {len(result[\"attention_items\"])}')
assert len(result['attention_items']) > 0, 'No attention items — self-validation FAILED'
print('SELF-VALIDATION: PASS')
"
```

---

## S3: post-refactor-baseline 스냅샷

**Goal:** 완성된 대시보드로 리팩토링 후 전 블로그 상태를 스냅샷으로 저장
**Risk:** LOW (읽기 전용 스냅샷)
**Pre-requisite:** S2 완료 (대시보드 자기검증 통과)
**Commit:** S3 완료 시

### Tasks

#### 3-1: 전수 헬스체크 실행 + 스냅샷 저장
- **방법:** `run_all_checks(conn)` 전수 실행
- **저장:** 결과를 `ops_dashboard/snapshots/post-refactor-{date}.json`에 JSON 저장
- **내용:**
  - blog_id별 check 결과 (pass/fail/unknown)
  - 표준 준수율
  - stale 블로그 수
  - 미해결 issue 수
- **검증:** 스냅샷 파일 존재 + 내용 확인

#### 3-2: git 태그 생성
- **태그:** `post-refactor-baseline`
- **커밋:** 스냅샷 커밋의 해시
- **검증:** `git tag -l 'post-refactor*'` → 태그 존재

### S3 Verification
```bash
# 1. 스냅샷 파일 확인
ls -la ops_dashboard/snapshots/post-refactor-*.json

# 2. 태그 확인
git tag -l 'post-refactor*'

# 3. 스냅샷 내용 확인
python -c "
import json
with open('ops_dashboard/snapshots/post-refactor-$(date +%Y%m%d).json') as f:
    data = json.load(f)
print(f'Blogs: {data[\"total_blogs\"]}, Checks: {data[\"total_checks\"]}')
print(f'Pass: {data[\"pass\"]}, Fail: {data[\"fail\"]}, Unknown: {data[\"unknown\"]}')
"
```

---

## Part 1: 발행/배포 중단 원인 규명 (리팩토링 전/후 구분 포함)

**Goal:** 각 블로그의 발행 공백 원인을 데이터로 판정 + 리팩토링 회귀 여부 구분
**Risk:** LOW (읽기 전용 조사, 코드 수정 없음)
**Pre-requisite:** S3 완료 (post-refactor-baseline 존재)
**Commit:** Part 1 완료 시

### Tasks

#### 1-1: 발행 로그 집계 스크립트 작성
- **파일:** `ops_dashboard/investigate_publish.py` (신규)
- **내용:**
  - publish_ledger에서 blog_id별 마지막 성공 발행 시각 추출
  - 8/1 이후 발행 시도 vs 성공 vs 차단 카운트
  - 8/1 이후 성공 발행 0건 블로그 전체 목록
  - 결과를 JSON + 터블 출력으로 병렬 제공
- **검증:** `python ops_dashboard/investigate_publish.py` → 블로그별 요약 테이블 출력

#### 1-2: 리팩토링 전/후 대조 (핵심 신규 작업)
- **파일:** `ops_dashboard/investigate_publish.py`에 추가
- **내용:**
  - `pre-refactor-baseline` 커밋 시각(`2026-08-06 10:33:52`) 추출
  - publish_ledger의 각 발행 시도를 "리팩토링 이전" / "리팩토링 이후"로 분류
  - 리팩토링 이후에 새로 발생한 실패 → "리팩토링 회귀" 의심
  - 리팩토링 이전부터 있던 실패 → "원래 문제"
  - 판정표 형식으로 산출:
    ```
    | 블로그 | 원래 문제 | 리팩토링 회귀 | 미판별 | 근거 |
    ```
- **검증:** 판정표가 모든 블로그에 대해 "원래 문제" 또는 "리팩토링 회귀"로 분류

#### 1-3: 차단 사유 P-코드 분포 분석
- **파일:** `ops_dashboard/investigate_publish.py`에 추가
- **내용:**
  - publish_ledger의 stage 필드에서 P-코드 추출
  - P-코드별 전체 건수 + 비율
  - blog_id별 반복 P-코드 매핑
  - 리팩토링 전/후로 P-코드 분포 비교
- **검증:** P-코드 분포 테이블 출력 + top 3 차단 원인 식별

#### 1-4: DB vs 라이브 대조 (유실 판별)
- **파일:** `ops_dashboard/investigate_publish.py`에 추가
- **내용:**
  - publish_ledger에서 status='published'인 글의 published_url 확인
  - 각 URL을 HTTP HEAD로 라이브 존재 확인 (httpx 사용)
  - DB엔 성공인데 라이브엔 없는 글 → "유실"로 분류
  - 유실 글의 발행 시각을 리팩토링 커밋 시각과 대조
- **검증:** 유실 글 목록 출력 + 재배포 필요성 판정

#### 1-5: 종합 판정 보고서
- **파일:** `.planning/phase-60-*/PART1-REPORT.md`
- **내용:**
  - 각 블로그별 공백 원인 판정: (a) 차단 반복 (b) 발행 시도 중단 (c) 배포 유실 (d) 리팩토링 회귀
  - 판정 근거 (로그 레코드, HTTP 상태코드, 리팩토링 커밋 시각 대조)
  - 리팩토링 회귀로 판정된 블로그의 경우 해당 리팩토링 커밋 번호 기록
  - pet-hugo, beauty-hugo 집중 분석 (오염글 갱신 필요 블로그)
- **검증:** 판정 결과가 모든 블로그에 대해 근거와 함께 제시

### Part 1 Verification
```bash
# 1. 조사 스크립트 실행
python ops_dashboard/investigate_publish.py

# 2. 리팩토링 전/후 판정표 확인
python ops_dashboard/investigate_publish.py --regression-analysis

# 3. 결과 보고서 확인
cat .planning/phase-60-publish-investigation-and-hardening/PART1-REPORT.md

# 4. 판정 근거 확인 (예시)
# - pet-hugo: 발행 시도 0건 → (b) 발행 시도 중단
# - beauty-hugo: 리팩토링 이후 similar_title 4건 → (a) 차단 반복 (원래 문제)
# - kitchen-hugo: 리팩토링 이후 irrelevant_products 2건 → (a) 차단 반복 (원래 문제)
# - interior-hugo: 리팩토링 이전부터 P09 존재 → (a) 원래 문제
```

---

## Part 2: P09 근본 원인 (조건부)

**Goal:** P09가 여전히 재발 중이면 공통 코드 결함 수정
**Risk:** MEDIUM (production 코드 수정, staged 적용)
**Pre-requisite:** Part 1 완료 — P09 재발 여부 판정 필요
**Condition:** Part 1에서 P09가 "여전히 재발 중"으로 판정된 경우에만 실행. 이미 해소된 경우 이 파트 건너뛰고 사실만 기록.
**Commit:** Part 2 완료 시 (또는 건너뛰기 기록 시)

### Tasks (P09 재발 시)

#### 2-1: P09 "repeated segments" 코드 경로 추적
- **파일:** 조사 대상 — `shared/ai_writer.py`, `shared/publishers/hugo_writer.py`, `shared/content_store.py`
- **내용:**
  - "repeated segments 25 of ~42" 메시지 발생 지식 추적
  - 이미지 URL 생성/삽입 로직에서 세그먼트 반복 유발 조건 분석
  - interior, baby, fitness, kitchen, beauty에서 동일 패턴이면 공통 코드 결함 확인
- **검증:** 공통 코드 결함 1곳 식별 + 재현 조건 기술

#### 2-2: 공통 코드 수정
- **파일:** 식별된 코드 1곳 (ai_writer.py 또는 hugo_writer.py)
- **변경:** 세그먼트 중복 방지 로직 추가 (additive)
- **원칙:** 기존 기능 보존, 기존 테스트 회귀 0
- **검증:** 수정 후 관련 테스트 통과

#### 2-3: 수정 실증 발행
- **대상:** pet-hugo 또는 beauty-hugo 1개
- **변경:** dispatcher.py로 1회 발행 실행
- **확인:**
  - 새 글이 라이브에 반영되는지
  - 낡은 오염글이 새 글로 갱신되는지 (Hugo 특성상 새 글이 상단에 옴)
  - P09 오류가 더 이상 발생하는지
- **검증:** 라이브 URL에서 새 글 확인 + publish_ledger 성공 기록

### Tasks (P09 이미 해소 시)
- **기록만:** `PART2-REPORT.md`에 "P09 이미 해소됨 — Part 1에서 [검증] 판정" 기록
- **건너뛰기:** 2-1~2-3 생략

### Part 2 Verification
```bash
# P09 재발 시:
# 1. 코드 수정 확인
git diff shared/ai_writer.py  # 또는 hugo_writer.py

# 2. 테스트 회귀 확인
python -m pytest tests/ -x -q

# 3. 실증 발행 확인
python dispatcher.py pet-hugo  # 또는 beauty-hugo
# → publish_ledger에서 성공 기록 확인
# → 라이브 URL에서 새 글 확인

# P09 해소 시:
# → PART2-REPORT.md에 "해소됨" 기록 확인
```

---

## Part 3: 알림 재설계

**Goal:** 정상 차단 이벤트는 실시간 푸시 중단, ops.db 누적 + 일일 요약
**Risk:** LOW (알림 포맷 변경, 기존 시스템 미파괴)
**Pre-requisite:** Part 1 완료 (P-코드 분포 파악 필요)
**Commit:** Part 3 완료 시

### Tasks

#### 3-1: ops.db 이벤트 기록 연결
- **파일:** `ops_dashboard/checks/__init__.py` — `run_all_checks()` 수정
- **변경:**
  - check 결과를 check_results에 기록 (이미 있음)
  - P-코드 차단 이벤트를 별도 테이블 `blocked_events`에 기록
  - 테이블 스키마: `id, blog_id, p_code, detail, blocked_at`
- **파일:** `ops_dashboard/db.py` — `record_blocked_event()` 함수 추가
- **검증:** 기록 함수 동작 확인

#### 3-2: P-코드 기반 알림 분류
- **파일:** `shared/telegram_notifier.py` (또는 `shared/problem_monitor.py`)
- **변경:**
  - P-코드별 알림 방식 분류:
    - **정상 차단 (P09 등):** 실시간 푸시 중단 → ops.db 기록만
    - **실제 조치 필요 (P02 연속 실패, 신종 오류, 게이트 미포착):** 실시간 푸시 유지
  - 분류 기준: P-코드 + 연속 발생 횟수로 판정
  - 기존 알림 코드를 건드리지 않고 추가 분기만 삽입 (additive)
- **검증:** P09 발생 시 텔레그램에 푸시 없이 ops.db에만 기록되는지 확인

#### 3-3: 텔레그램 일일 요약 구현
- **파일:** `ops_dashboard/daily_summary.py` (신규)
- **내용:**
  - 하루 종일 ops.db에 기록된 blocked_events를 P-코드별로 집계
  - 저녁 특정 시각(예: 22:00)에 텔레그램 요약 발송
  - 포맷: "오늘 P09 12건 차단: interior, baby, fitness, kitchen, beauty..."
  - P-코드 패턴 단위 집계 (블로그 단위 아님)
- **파일:** `scheduler.py`에 일일 요약 작업 추가 (또는 launchd plist)
- **검증:** `python ops_dashboard/daily_summary.py` → 텔레그램 요약 메시지 발송 확인

#### 3-4: check_results P-코드 재사용 확인
- **확인:** Phase 58의 P01~P24 코드·조치문구가 check_results에 재사용되는지 검증
- **변경:** 필요시 check_results에 P-코드 매핑 필드 추가
- **검증:** `grep -r "P01\|P02\|P09" ops_dashboard/` → 매핑 확인

### Part 3 Verification
```bash
# 1. blocked_events 테이블 생성 확인
python -c "
import sqlite3
conn = sqlite3.connect('ops_dashboard/ops.db')
tables = [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]
print('blocked_events' in tables)  # → True
"

# 2. P09 알림이 ops.db에만 기록되는지 확인
# (P09 발생 시도 → 텔레그램 푸시 없음, DB 기록 있음)

# 3. 일일 요약 스크립트 실행 확인
python ops_dashboard/daily_summary.py

# 4. 텔레그램 요약 메시지 포맷 확인
```

---

## Part 4: 대시보드 체크 보강

**Goal:** cjk_leak 슬러그 확장, 크로스링크 일관성 체크, 오염글 목록화
**Risk:** LOW (체크 추가, 기존 체크 미수정)
**Pre-requisite:** Part 1 완료
**Commit:** Part 4 완료 시

### Tasks

#### 4-1: cjk_leak 체크 — URL 슬러그까지 확장
- **파일:** `ops_dashboard/checks/cjk_leak.py` (신규)
- **내용:**
  - 기존: 제목·본문 CJK/타언어 혼입 검사
  - 확장: URL 슬러그에 CJK 인코딩 박힘 검사 (이미 발견된 문제)
  - 정규식: ASCII 이외 문자가 슬러그에 포함된 경우 탐지
  - register_check("cjk_leak")로 등록
- **검증:** CJK 슬러그가 포함된 블로그에서 fail 반환 확인

#### 4-2: 크로스링크 주제 일관성 체크 (audit Q5)
- **파일:** `ops_dashboard/checks/crosslink_consistency.py` (신규)
- **내용:**
  - 크로스링크가 동일/인접 카테고리 내인지 검사
  - 링크 코드 자체는 수정됨 — 이건 회귀 감지용
  - 각 블로그의 내부 링크를 수집하여 타겟 블로그의 카테고리와 비교
  - register_check("crosslink_consistency")로 등록
- **검증:** 다른 계열 블로그로의 크로스링크 발견 시 fail 반환

#### 4-3: 오염글 목록화
- **파일:** `ops_dashboard/investigate_publish.py`에 추가 (또는 별도 스크립트)
- **내용:**
  - 수정 이전 발행분 (CJK 릭, 엔티티 링커 주제이탈 등) 식별
  - publish_ledger에서 해당 블로그의 과거 발행분 중 오염 패턴 검사
  - 오염글 URL 목록 + 재발행 필요 여부 판정
- **검증:** 오염글 목록 출력 + Part 1 재발행과의 대조

### Part 4 Verification
```bash
# 1. 신규 check 등록 확인
python -c "
from ops_dashboard.checks import CHECKS
print('Registered checks:', sorted(CHECKS.keys()))
"

# 2. cjk_leak가 URL 슬러그 검사하는지 확인
python -c "
from ops_dashboard.checks.cjk_leak import _check_slug_cjk
print(_check_slug_cjk('https://pet.informationhot.kr/posts/강아지-장난감/'))  # → fail
print(_check_slug_cjk('https://pet.informationhot.kr/posts/dog-toy/'))        # → pass
"

# 3. 오염글 목록 확인
python ops_dashboard/investigate_publish.py --contaminated
```

---

## Part 5: 확장성 보강 (목표 규모: 몇백, 500 이하)

**Goal:** DB 함수화, async check, 롤업 정책, UI 개선
**Risk:** MEDIUM (db.py 구조 변경, 기존 호출 코드 영향)
**Pre-requisite:** Part 1~4 완료
**Commit:** Part 5 완료 시

### Tasks

#### 5-1: DB 접근 함수 통일 (인라인 SQL 제거)
- **파일:** `ops_dashboard/db.py`
- **변경:**
  - 모든 인라인 SQL을 db.py 내 함수로 이동
  - 함수 시그니처: `def get_blog_stats(conn, blog_id) -> dict`, `def get_publish_summary(conn, since) -> dict` 등
  - 기존 직접 SQL 호출 코드 → 함수 호출로 교체
  - 나중 교체 여지만 확보 (PostgreSQL 등)
- **검증:** `grep -rn 'cursor.execute\|conn.execute' ops_dashboard/*.py` → db.py 외 0건

#### 5-2: render_health async 실행
- **파일:** `ops_dashboard/checks/render.py`
- **변경:**
  - HTTP 프로베를 asyncio + httpx.AsyncClient로 변경
  - 동시성 제한: `asyncio.Semaphore(10)`으로 최대 10개 동시 요청
  - 전수 검사도 몇백 규모는 감당 가능하도록
  - 순차 블로킹 방지
- **검증:** 56개 블로그 render_health 실행 시간 < 60초

#### 5-3: check_results 보존 정책
- **파일:** `ops_dashboard/db.py`
- **변경:**
  - `cleanup_old_checks(conn, keep_days=30)`: 30일 이상 원시 데이터 삭제
  - `daily_rollup(conn)`: 일별 check_results를 `check_rollups` 테이블로 요약
  - 요약 스키마: `date, blog_id, check_name, pass_count, fail_count, unknown_count`
  - 무한 누적 방지
- **검증:** rollups 테이블 생성 + 데이터 확인

#### 5-4: UI "주의 필요" 기본 뷰 + 필터
- **파일:** `ops_dashboard/templates/index.html`
- **변경:**
  - 기본 뷰: "주의 필요" 블로그만 표시 (정상은 집계 숫자로)
  - 필터: 계열(cap/cuap/etap), 체크 유형, 심각도별 필터링
  - 목록에서 클릭 시 `/blog/<id>` 상세 페이지로 이동
- **파일:** `ops_dashboard/app.py`
- **변경:** `/` 라우트에서 check_results 기반 "주의 필요" 목록 생성
- **검증:** 브라우저에서 http://localhost:5060 접속 → "주의 필요" 기본 뷰 확인

#### 5-5: YAML 자동 발견 (계열 하드코딩 제거)
- **파일:** `ops_dashboard/db.py` — `_parse_yaml_file()` 또는 `sync_blog_lifecycle()`
- **변경:**
  - `config/blogs.d/*.yaml` 파일을 glob으로 자동 발견
  - 새 YAML 파일 추가만으로 새 계열이 자동 동기화되도록
  - 코드 본체에 계열 이름 하드코딩 제거
- **검증:**
  1. 더미 YAML 1개 추가 → 동기화로 블로그 등록 확인
  2. 더미 YAML 삭제 → 동기화로 제거 확인

### Part 5 Verification
```bash
# 1. 인라인 SQL 0건 확인 (db.py 외)
grep -rn 'cursor.execute\|conn.execute' ops_dashboard/*.py | grep -v 'db.py' | wc -l  # → 0

# 2. render_health async 확인
python -c "
import time
from ops_dashboard.db import get_conn
from ops_dashboard.checks.render import check_render_health
conn = get_conn()
start = time.time()
result = check_render_health(conn, 'camping-hugo')
elapsed = time.time() - start
print(f'Render check: {result[\"status\"]} in {elapsed:.1f}s')
"

# 3. 롤업 정책 확인
python -c "
import sqlite3
conn = sqlite3.connect('ops_dashboard/ops.db')
tables = [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]
print('check_rollups' in tables)  # → True
"

# 4. 더미 계열 편입 확인
echo 'id: test-hugo' > config/blogs.d/test-brand.yaml
echo 'pipeline: test' >> config/blogs.d/test-brand.yaml
python -c "
from ops_dashboard.db import get_conn, sync_blog_lifecycle, get_all_blogs
conn = get_conn()
sync_blog_lifecycle(conn)
blogs = get_all_blogs(conn)
test = [b for b in blogs if b['blog_id'] == 'test-hugo']
print('test-hugo found:', len(test) > 0)  # → True
"
rm config/blogs.d/test-brand.yaml

# 5. UI 확인
python ops_dashboard/app.py &
curl -s http://localhost:5060/ | grep -c "주의 필요"  # → > 0
kill %1
```

---

## Part 6: CUAP 확장 게이트 (15→50)

**Goal:** 확장 준비도 확인 + 시범 발행 검증
**Risk:** LOW (확인 + 시범 발행, 대규모 변경 없음)
**Pre-requisite:** Part 1~5 모두 닫힌 뒤에만 실행
**Commit:** Part 6 완료 시

### Tasks

#### 6-1: 확장 준비도 지표 계산
- **파일:** `ops_dashboard/readiness.py` (신규)
- **내용:**
  - 전 블로그 표준 준수율: `check_results에서 standard_compliance pass 비율`
  - stale 블로그 수: `freshness check에서 fail인 블로그 수`
  - 미해결 known_issue 수: `known_issues에서 resolution_status != 'resolved'인 건수`
  - 세 지표가 모두 녹색(임계값 충족)인지 판정
  - 대시보드 첫 화면에 한 줄 표시
- **검증:** `python ops_dashboard/readiness.py` → 지표 출력 + 녹색/적색 판정

#### 6-2: 대시보드 확장 준비도 표시
- **파일:** `ops_dashboard/templates/index.html`
- **변경:** 첫 화면 상단에 확장 준비도 한 줄 표시
  - "확장 준비도: ● 표준 95% | stale 0 | 미해결 2 → 🔴 대기"
  - 또는 "확장 준비도: ● 표준 98% | stale 0 | 미해결 0 → 🟢 준비완료"
- **파일:** `ops_dashboard/app.py`
- **변경:** `/api/readiness` JSON 엔드포인트 추가
- **검증:** 대시보드에서 확장 준비도 지표 확인

#### 6-3: 시범 발행 검증 (확장 검토 시)
- **조건:** 확장 준비도가 🟢일 때만 실행
- **대상:** CUAP 신규 블로그 1개 (예: new-cuap-blog-hugo)
- **변경:**
  1. config/blogs.d/에新 YAML 추가
  2. dispatcher.py로 1회 발행
  3. 대시보드 체크 전수 실행
  4. 모든 check pass 확인
- **검증:** 시범 블로그가 대시보드에서 pass 상태로 표시

#### 6-4: 확장 대비 설계 최종 확인
- **확인:**
  - 계열이 코드에 하드코딩돼 있지 않은지 (Part 5에서 확인됨)
  - 새 YAML 추가만으로 편입 가능한지 (Part 5에서 확인됨)
  - 헬스체크 플러그인이 계열 무관하게 동작하는지
  - 특정 계열 전용 규칙을 추가 등록할 수 있는 구조인지
- **검증:** 확인 결과를 PART6-REPORT.md에 기록

### Part 6 Verification
```bash
# 1. 확장 준비도 지표 확인
python ops_dashboard/readiness.py

# 2. 대시보드에서 준비도 확인
python ops_dashboard/app.py &
curl -s http://localhost:5060/api/readiness | python -m json.tool
kill %1

# 3. 시범 발행 (확장 준비도가 녹색일 때만)
# python dispatcher.py new-cuap-blog-hugo
# → 대시보드에서 new-cuap-blog-hugo check pass 확인
```

---

## Task Dependency Map

```
S1 (baseline tag) ✅
  │
  └──→ S2 (dashboard 완성)
         │
         └──→ S3 (post-refactor snapshot)
                │
                └──→ Part 1 (조사 — 리팩토링 전/후 구분)
                       │
                       ├──→ Part 2 (P09 — 조건부)  [Part 1에서 P09 재발 시]
                       │
                       ├──→ Part 3 (알림 재설계)  [Part 1 완료 후]
                       │
                       ├──→ Part 4 (체크 보강)  [Part 1 완료 후]
                       │
                       └──→ Part 5 (확장성)  [Part 1~4 완료 후]
                              │
                              └──→ Part 6 (확장 게이트)  [Part 5 완료 + 준비도 녹색]
```

**Part 2는 조건부:** P09가 이미 해소된 경우 건너뛰고 사실만 기록.
**Part 3, 4는 Part 1 이후 병렬 가능** (서로 독립적).
**Part 5는 Part 1~4 담금질 이후.**
**Part 6은 Part 5 + 확장 준비도 녹색일 때만.**

---

## Acceptance Criteria

### S1
- [x] `pre-refactor-baseline` 태그 존재 (`d85095152`)

### S2
- [ ] standard_rules 테이블 생성 + R01~R12 12건 시드
- [ ] 등록된 check 4개 이상 (standard_compliance, freshness, render_health, gsd_crosscheck)
- [ ] inventory 불일치 원인 규명 보고서
- [ ] 자기검증 4종 통과 (CUAP stale, senior 썸네일, CJK, 표준위반 최소 1건 탐지)

### S3
- [ ] `post-refactor-baseline` 태그 존재
- [ ] 스냅샷 JSON 파일 존재

### Part 1
- [ ] blog_id별 마지막 성공 발행 시각 100% 확인
- [ ] 8/1 이후 발행 시도/성공/차단 카운트 산출 완료
- [ ] 리팩토링 전/후 판정표 산출 완료 (원래 문제 vs 리팩토링 회귀)
- [ ] P-코드별 차단 비율 집계 완료
- [ ] DB vs 라이브 대조 완료 (유실 글 목록)
- [ ] PART1-REPORT.md 작성 완료

### Part 2
- [ ] P09 재발 여부 판정 완료
- [ ] (재발 시) 공통 코드 결함 1곳 식별 + 수정
- [ ] (재발 시) pet/beauty 1회 발행 실증
- [ ] (해소 시) PART2-REPORT.md에 "해소됨" 기록

### Part 3
- [ ] blocked_events 테이블 생성 + 기록 확인
- [ ] P09 정상 차단 → 실시간 푸시 중단 확인
- [ ] 텔레그램 하루 1회 요약 발송 확인
- [ ] P-코드 패턴 단위 집계 확인

### Part 4
- [ ] cjk_leak가 URL 슬러그 검사하는지 확인
- [ ] 크로스링크 주제 일관성 체크 구현
- [ ] 오염글 목록화 + 재발행 대조

### Part 5
- [ ] 인라인 SQL 0건 (db.py 외)
- [ ] render_health async 실행 (< 60초 전수)
- [ ] check_results 롤업 정책 구현
- [ ] UI "주의 필요" 기본 뷰 동작
- [ ] 더미 계열 YAML 추가 → 코드 수정 없이 편입 확인

### Part 6
- [ ] 확장 준비도 지표 대시보드 표시
- [ ] 시범 발행 1개 → 대시보드 전수 검사 PASS
- [ ] 확장 대비 설계 최종 확인 보고

---

## Risk Mitigation

### Staged Rollout
| Part | 소수 적용 | 검증 | 전체 확대 |
|------|----------|------|----------|
| 2 | pet-hugo 1개 | 발행 성공 + P09 해소 | 해당 블로그 전체 |
| 5 | db.py 함수화 | 기존 테스트 회귀 | 전체 코드 |

### Rollback
| Part | 롤백 방법 |
|------|----------|
| S1 | 태그 삭제 (기존 코드 미수정) |
| S2 | 신규 파일 삭제 + checks/__init__.py import 원복 |
| S3 | 스냅샷 삭제 + 태그 삭제 |
| 1 | 조사 스크립트만 삭제 (기존 코드 미수정) |
| 2 | git revert (수정 1곳만 원복) |
| 3 | ops_dashboard/daily_summary.py 삭제 + telegram_notifier 원복 |
| 4 | 신규 check 파일 삭제 + checks/__init__.py import 원복 |
| 5 | git revert (db.py, app.py, templates 원복) |
| 6 | readiness.py 삭제 + index.html 원복 |

### "break nothing that works" 원칙
- S1~S3: 읽기 전용 — 코드 수정 없음
- Part 1: 읽기 전용 조사 — 코드 수정 없음
- Part 2: 수정 시 기존 테스트 회귀 확인 필수
- Part 3: 알림 변경은 additive — 기존 푸시 로직 미수정
- Part 4: 신규 check 추가 — 기존 check 미수정
- Part 5: db.py 함수화 — 기존 시그니처 보존, 내부 구현만 변경
- Part 6: YAML 추가/확인 — 코드 수정 없음

---

## 잔존 위험

1. **S2 ops_dashboard 마무리가 예상보다 어려울 수 있음**: inventory 불일치(56/85) 원인 불명 → YAML 파싱 문제 또는 수동 블로그 미반영
2. **Part 1 조사가 예상보다 깊어질 수 있음**: publish_ledger 데이터 품질에 따라 조사 범위 확대 가능
3. **P09 코드 결함이 shared 로직에 있을 경우**: multiple 블로그에 영향, staged 수정 필요
4. **알림 재설계 시 기존 텔레그램 알림과 충돌**: additive 변경 필수, 기존 포맷 보존
5. **db.py 함수화 중 기존 호출 코드 회귀**: 함수 시그니처 동일 유지, 내부 구현만 변경
6. **Blogger 블로그 3개**: 파이프라인 미정의, 대시보드 범위 밖
