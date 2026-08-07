# Phase 62: Content Leak Prevention — C01~C08 Rule System

**상태**: 계획 수립 완료 (실행 대기 중)  
**작성일**: 2026-08-07  
**계획 수**: 5 plans / 5 waves

---

## 개요

2026-08-06 인체어 60만자 전수 분석에서 4종의 콘텐츠 무결성 위반이 확인됐다:

| 유형 | 규모 |
|------|------|
| 죽은 크로스셀 링크 | 404 6건 + 오염 27건 + 동남냄비받침 44건 |
| 본문 내 프론트매터 키 유출 | 매뉴얼 샘플 |
| draft:true 발행 대상 | - |
| LLM 프롬프트/사고문 누수 | - |

이 4종을 포함한 **8개 규칙(C01~C08)**을 ops_db standard_rules에 등록하고,
파이프라인 각 단계 경계에서 자동 탐지·차단하는 체계를 구축한다.

---

## 규칙 정의

| 규칙 | target | severity | 자동조치 |
|------|--------|----------|----------|
| C01 | frontmatter | MAJOR | 탐지 시 게시 중단 + 로그 |
| C02 | frontmatter | CRITICAL | 탐지 시 배포 차단 |
| C03 | body | MAJOR | 탐지 시 게시 중단 + 로그 |
| C04 | body | CRITICAL | 탐지 시 게시 중단 + 로그 |
| C05 | frontmatter+publish | CRITICAL | 탐지 시 발행 중단 + 로그 |
| C06 | file+deploy | MAJOR | 탐지 시 경고 + 로그 |
| C07 | body+cross-sell | MAJOR | 탐지 시 크로스셀 카드 제거/대체 |
| C08 | live+file | CRITICAL | 탐지 시 배포 차단 + 로그 |

**C02 판정 주의**: 반드시 "첫 --- 이후 두 번째 --- 존재 여부"로만 판정.
전체 `---` 홀수 카운트 판정은 금지 (본문 내 `---` 수평선과 혼동).

---

## 원인추적 훅 (C01·C04)

| 지점 | 위치 | 검사 대상 |
|------|------|-----------|
| (a) 생성 직후 | AI 작성 완료 후, humanizer 투입 전 | raw 생성물 |
| (b) humanizer 통과 직후 | humanizer 변환 후, _write_hugo_post 전 | humanizer 처리 후 |
| (c) _write_hugo_post 저장 직전 | 파일 저장 직전 최종 검사 | 최종 content |

각 지점에서 곡선따옴표(C01)·프롬프트누수(C04)를 검사하고,
**처음 탐지된 지점**을 `logs/leak-origin.log`에 `stage+slug+패턴` 형태로 기록.
같은 slug에 대해 여러 지점에서 탐지되면 첫 지점만 기록(중복 방지).

---

## 배포 프리플라이트 게이트

`dispatcher._build_and_deploy_central()` 직전에 `preflight_check(blog_id)`를 삽입.
C01~C04·C08 중 critical이 1건이라도 있으면 배포 중단 + 위반 slug 리턴 + Telegram 알림.

**대상 블로그**: CUAP / CAP / STAP / RAP / ETAP / SEAP / TAP 모두

---

## 계획 목록

| 계획 | 파일 | Wave | 내용 |
|------|------|------|------|
| 62-01 | 62-01-reverse-validation.md | 1 | 역검증 스크립트 + 검증 데이터 (dead_links 77건, ETAP 영문 100건+, cot_leak 샘플) |
| 62-02 | 62-02-standard-rules-insert.md | 2 | git tag 백업 후 standard_rules에 C01~C08 INSERT |
| 62-03 | 62-03-cause-tracking-hooks.md | 3 | shared/leak_tracker.py + hugo_writer.py 3개 지점 훅 |
| 62-04 | 62-04-preflight-gate.md | 4 | dispatcher preflight_check + _build_and_deploy_central 게이트 |
| 62-05 | 62-05-dashboard-integration.md | 5 | ops_dashboard/checks/content_integrity.py + check_results 통합 |

---

## 실행 게이트

**역검증(62-01)에서 "전건 탐지 + 오탐 0" 확인 후에만 INSERT/코드 삽입 진행:**

1. ✅ dead_links 77건(404 6건 + 오염 27건 + 동남냄비받침 44건) 전부 C07 fail
2. ✅ ETAP 영문 3551건 샘플 100건 이상 오탐 0, 전부 pass
3. ✅ 프롬프트 누수 케이스 오탐 없이 C04 탐지
4. ✅ ETAP 영문 글 영문 프롬프트 누수 패턴 별도 확인, 오탐 없이 통과

**오탐 발생 시**: INSERT/삽입을 보류하고 조건만 수정해 62-01에서 재검증.

---

## 기술 결정

1. **C01~C08 rule_id**: C01~C08 (기존 R01~R12와 충돌 없음, 별도 스콥)
2. **역검증 FIRST**: 코드 삽입 전 실제 사례로 검증 → 조건 조정 → INSERT
3. **git tag 백업 first**: 코드 삽입 전 `phase-62-pre-insert-YYYYMMDD-HHMMSS` 태그 생성
4. **파일럿-first 코드 삽입**: dispatcher preflight_check 1개 함수부터 시작
5. **비파괴·증분적**: 기존 기능 보존, 구조 변경과 로직 변경은 별도 커밋

---

## 파일 변경 요약

| 파일 | 작업 | 계획 |
|------|------|------|
| `scripts/c01_c08_reverse_validation.py` | 신규 | 62-01 |
| `scripts/c01_c08_validation_data/*.json` | 신규 | 62-01 |
| `ops_dashboard/db.py` | 수정 (SEED_STANDARD_RULES) | 62-02 |
| `shared/leak_tracker.py` | 신규 | 62-03 |
| `shared/publishers/hugo_writer.py` | 수정 (훅 3개 지점) | 62-03 |
| `dispatcher.py` | 수정 (preflight_check + 게이트) | 62-04 |
| `ops_dashboard/checks/content_integrity.py` | 신규 | 62-05 |

---

## 검증 기준

- [ ] C01~C08 규칙 definition이 CONTEXT.md와 일치하게 standard_rules에 INSERT됨
- [ ] 역검증: 실제 사례 전건 탐지 + 오탐 0
- [ ] 원인추적 훅 3개 지점이 설계대로 구현됨 (logs/leak-origin.log)
- [ ] preflight_check가 dispatcher._build_and_deploy_central 직전에 삽입됨
- [ ] 대시보드 check_results에 규칙 판정 결과가 표시됨
- [ ] 기존 테스트 21개 실패 외 신규 실패 0

---

## 다음 단계

실행: `/gsd-execute-phase 62-content-leak-prevention`

<sub>`/clear` first - fresh context window</sub>
