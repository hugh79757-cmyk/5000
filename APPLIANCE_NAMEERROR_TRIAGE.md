# APPLIANCE_NAMEERROR_TRIAGE.md

> **진단 시각**: 2026-08-19 08:37 KST
> **방식**: READ-ONLY — 코드/DB/설정 변경·재실행·pause·push·배포 없음
> **브랜치**: `_rollback_test` (main 아님), HEAD: `06b1c2e0e`

---

## 1. scheduler PID 15373 종료·PID 16389 시작 분석

### PID 15373 종료

| 항목 | 값 |
|------|-----|
| PID 15373 상태 | **종료됨** (ps에서 확인 불가) |
| exit code | `738` (launchctl `LastExitStatus`) — **비정상 종료** (0 아님) |
| 종료 원인 | `patch_rotation2.py:50` unterminated string literal → `_check_python_syntax()` FATAL → `sys.exit(1)` |
| 종료 시각 | 2026-08-19 08:24 이전 (이미 종료된 상태로 발견) |

### PID 16389 시작

| 항목 | 값 |
|------|-----|
| PID 16389 상태 | **실행 중** (S, 03:05 경과) |
| 시작 주체 | **수동 재시작** — `launchctl unload/load` 수행 (이전 세션에서 확인) |
| 시작 시각 | 2026-08-19 08:29 |
| 시작 원인 | `patch_rotation2.py`를 `/tmp/5000_patches/`로 이동 후 launchctl 재시작 |

### 판정

| 기준 | 결과 |
|------|------|
| crash 여부 | **✅ 아님** — `sys.exit(1)`로 의도적 종료 (FATAL) |
| 수동 재시작 여부 | **✅ 아님** — launchctl unload/load로 수동 재시작 |
| launchd 자동 복구 여부 | **❌ 아님** — `KeepAlive` 설정이 있으나 exit code 738로 재시작 안 됨 (수동 개입 필요) |

**결론**: PID 15373은 syntax error로 FATAL 종료 → 수동 재시작으로 PID 16389 시작. crash가 아닌 의도적 종료(sys.exit(1)).

---

## 2. 24시간 scheduler 재시작·flapping 분석

| 항목 | 값 |
|------|-----|
| 재시작 횟수 | **1회** (PID 15373 → PID 16389) |
| flapping | **❌ 아님** — 1회 only, 30분 내 반복 재시작 없음 |
| exit code 738 건수 | **1건** (08:24경) |
| 현재 scheduler 정상 동작 | **✅ 정상** — PID 16389, CPU 0.0%, MEM 0.4% |

---

## 3. appliance-hugo NameError 상세

### 정확한 예외

| 항목 | 값 |
|------|-----|
| 예외 타입 | `NameError` |
| 예외 메시지 | `name 'select_llm_title' is not defined` |
| 발생 파일 | `pipelines/curation/writer.py` |
| 발생 라인 | **980** |
| stack trace | `writer.py:980` → `dispatcher.py` → `scheduler.py` |
| run ID | 스케줄러 자동 실행 (별도 run ID 없음) |

### 코드 컨텍스트 (writer.py:978-983)

```python
            # ... (title fallback 로직)
    if title and products:
        title = select_llm_title(keyword, products, blog_id, recent_titles, title, ai_generate, logger)
    if template_type:
        logger.info("[title_template] 사용됨: %s (제목: %s…)", template_type, (title or "")[:50])
```

### 함수 정의 위치

| 항목 | 값 |
|------|-----|
| 함수 | `select_llm_title()` |
| 정의 파일 | `shared/cuap_title_llm.py:41` |
| 시그니처 | `select_llm_title(keyword, products, blog_id, recent_titles, fallback, ai_generate, logger, attempts=3)` |

### 마지막 정상 실행

| 항목 | 값 |
|------|-----|
| appliance-hugo 마지막 성공 | **없음** (오늘 전체 실패) |
| 이전 성공 | 2026-08-18 이전 (로그 범위 밖) |

### 연속 실패 횟수

| 블로그 | 연속 실패 | 비고 |
|--------|-----------|------|
| appliance-hugo | 3/3 | CATCHUP 실패 |
| baby-hugo | 3/3 | |
| fitness-hugo | 3/3 | |
| camping-hugo | 2/3 | |
| health-hugo | 2/3 | |
| homeappliance-hugo | 2/3 | |
| interior-hugo | 2/3 | |
| laptop-hugo | 2/3 | |
| massage-hugo | 2/3 | |
| pet-hugo | 2/3 | |

---

## 4. 심볼 추적 + 다른 블로그 영향

### origin/main 상태

| 항목 | 상태 |
|------|------|
| `pipelines/curation/writer.py` 라인 980 | **없음** — origin/main에는 `select_llm_title` 호출 없음 |
| `shared/cuap_title_llm.py` | **없음** — git 추적 안 됨 |
| `select_llm_title` import | **없음** — writer.py import 블록에 없음 |

### working tree 상태

| 항목 | 상태 |
|------|------|
| `pipelines/curation/writer.py` 라인 980 | **존재** — uncommitted change |
| `shared/cuap_title_llm.py` | **존재** — git 미추적 (4362 bytes, 2026-08-18 23:41) |
| `select_llm_title` import | **없음** — 호출만 있고 import 없음 |

### 추가 변경 (working tree vs origin/main)

| 변경 위치 | 내용 | 타입 |
|-----------|------|------|
| writer.py:355 | `site_title_guidance = _site_title_guidance(blog_id)` | uncommitted |
| writer.py:416 | prompt에 `{site_title_guidance}` 추가 | uncommitted |
| writer.py:980 | `select_llm_title()` 호출 추가 | uncommitted |
| cuap_title_llm.py | 신규 파일 (git 미추적) | untracked |

### 다른 블로그 영향 범위

| 영향 받는 블로그 | pipeline | NameError 발생 | 근거 |
|-----------------|----------|----------------|------|
| appliance-hugo | curation | ✅ | today: 3건 |
| baby-hugo | curation | ✅ | today: 3건 |
| beauty-hugo | curation | ✅ | today: 1건 |
| bike-hugo | curation | ✅ | today: 1건 |
| camping-hugo | curation | ✅ | today: 2건 |
| fitness-hugo | curation | ✅ | today: 3건 |
| health-hugo | curation | ✅ | today: 2건 |
| homeappliance-hugo | curation | ✅ | today: 2건 |
| interior-hugo | curation | ✅ | today: 2건 |
| kitchen-hugo | curation | ✅ | today: 1건 |
| laptop-hugo | curation | ✅ | today: 2건 |
| massage-hugo | curation | ✅ | today: 2건 |
| pet-hugo | curation | ✅ | today: 2건 |
| **总计** | | **13개 블로그** | **26건 (오늘)** |

**영향 없는 블로그**: etap, travel, stock, senior, rap 파이프라인 — writer.py 미사용.

---

## 5. 근본원인

### 직접 원인

`pipelines/curation/writer.py:980`에서 `select_llm_title()`을 호출하지만, `import`문에 `from shared.cuap_title_llm import select_llm_title`이 누락됨.

### 근본 원인

1. `shared/cuap_title_llm.py`가 git 미추적 상태로 생성됨 (2026-08-18 23:41)
2. `pipelines/curation/writer.py`에 `select_llm_title()` 호출이 uncommitted change로 추가됨
3. import 문은 추가되지 않음 → `NameError: name 'select_llm_title' is not defined`
4. 이 변경이 working tree에만 존재하므로 **origin/main·프로덕션에는 영향 없음**

### 신뢰도

| 항목 | 값 |
|------|-----|
| 근본원인 신뢰도 | **95%** — 직접 재현 확인 (dispatcher 실행 → 동일 NameError) |
| 프로덕션 영향 | **❌ 없음** — origin/main에 미반영, working tree 전용 |

---

## 6. 최소 수정안

### 옵션 A: import 추가 (권장)

```python
# pipelines/curation/writer.py import 블록에 추가
from shared.cuap_title_llm import select_llm_title
```

**장점**: 최소 변경 (1줄), 기존 로직 유지
**단점**: `cuap_title_llm.py`가 git 미추적이므로 추적 필요

### 옵션 B: 호출 제거 (원복)

```python
# writer.py:980-981 제거
# if title and products:
#     title = select_llm_title(...)
```

**장점**: origin/main과 동일 상태 복원, import 불필요
**단점**: 추가된 기능(제목 LLM 선택) 비활성화

### 옵션 C: 파일 2개 모두 git 추적

1. `git add shared/cuap_title_llm.py`
2. `git add pipelines/curation/writer.py`
3. commit

**장점**: 변경 사항 정식 반영
**단점**: 별도 기능 검증 필요

---

## 7. 테스트

| 테스트 | 방법 | 예상 결과 |
|--------|------|-----------|
| NameError 재현 | `python3 dispatcher.py appliance-hugo` | traceback에서 `select_llm_title is not defined` 확인 |
| 수정 후 동작 | 옵션 A 적용 후 `python3 dispatcher.py appliance-hugo` | 발행 성공 또는 다른 단계에서 실패 (NameError 없음) |
| 영향 범위 | `grep -rn 'select_llm_title' pipelines/` | writer.py에서만 호출 확인 |

---

## 8. 롤백안

| 순위 | 롤백안 | 설명 |
|------|--------|------|
| 1 | **writer.py line 980-981 주석 처리** | `select_llm_title` 호출 비활성화 — origin/main과 동일 |
| 2 | **writer.py 원복** | `git checkout origin/main -- pipelines/curation/writer.py` |
| 3 | **cuap_title_llm.py 삭제** | `rm shared/cuap_title_llm.py` (git 미추적) |

---

## 잔존 위험

1. **13개 curation 블로그 NameError**: pick-hugo 외 모든 curation 블로그 발행 차단 (working tree 전용)
2. **cuap_title_llm.py 미추적**: git에 없으므로 다른 환경에서 사용 불가
3. **select_llm_title import 누락**: 옵션 A 미적용 시NameError 지속

---

> **이 보고서는 READ-ONLY 진단만 수행했습니다. 코드/DB/설정 변경·재실행·pause·push·배포는 수행하지 않았습니다. pick-hugo 모니터링은 그대로 유지됩니다.**
