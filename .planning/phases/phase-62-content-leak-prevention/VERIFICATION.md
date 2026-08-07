# Phase 62 Plan Verification

## Verdict: PASS_WITH_NOTES

---

## Checklist Results

### PLAN.md
- [x] 목표 명확성: Phase goal "콘텐츠 무결성 규칙 C01~C08을 자동 탐지·차단하는 체계" 구체적, 검증 기준에 dead_links 77건, ETAP 영문 100건+, 오탐 0 등 측정 가능한 수치 포함
- [x] 배경 충분성: 2026-08-06 인체어 60만자 분석 결과 4종 위반 유형 표로 제시
- [x] 설계 구체성: 5개 plan, 5개 wave 구조, 실행 게이트 명확, C02 판정 조건 명시
- [x] 검증 기준: 7개 검증 기준 목록 포함
- [x] 파일 경로: 각 plan 파일명 명시, 실제 파일 존재
- [x] 제약 준수: C02 "첫--- 이후 두 번째 --- 존재 여부"로만 판정 명시, C04 영문 패턴 별도 확인, 실행 게이트, git tag 백업, 파일럿-first 접근법 모두 포함
- [x] 전체 일관성: 5개 plan이 Phase 62 목표 달성을 위해 직렬 의존성으로 구성

### 62-01-reverse-validation.md
- [x] 목표 명확성: "전건 탐지 + 오탐 0 확인" 구체적
- [x] 배경 충분성: CONTEXT.md 역검증 표 인용
- [x] 설계 구체성: Task 1(검증 데이터 3종), Task 2(C01~C08 판정 함수, 코드 예시 포함), Task 3(역검증 실행, 출력 형식 명시) 모두 구체적
- [x] 검증 기준: automated verify 명령어 + checkpoint 포함
- [x] 파일 경로: scripts/c01_c08_reverse_validation.py + scripts/c01_c08_validation_data/*.json 명시
- [x] 제약 준수: C02 "첫---이후 두 번째---" 판정 + 전체 홀수 카운트 금지 명시, C04 영문 패턴 별도 처리, 파일럿-first 접근법
- [x] dead_links 77건(404 6건 + 오염 27건 + 동남냄비받침 44건) 전부 fail, ETAP 영문 3551건 오탐 0 검증 방안이 Task 3에 구체적으로 명시됨

**참고**: C08은 "구현 보류 (라이브 비교 API 필요)"로 placeholder 처리. C01~C07만 실제 검증 대상. 이는 live 비교 API가 필요한 C08의 특성상 불가피하나, 역검증 게이트 "전건 탐지" 요구사항과의 정합성은 요약 노트 참조.

### 62-02-standard-rules-insert.md
- [x] 목표 명확성: "역검증 통과 확인 후 SEED_STANDARD_RULES에 INSERT" 구체적
- [x] 배경 충분성: 기존 R01~R12 현황 + C01~C08 별도 스콥 설명
- [x] 설계 구체성: INSERT 문 코드 예시, 삽입 위치(R12 다음), 주의사항 포함
- [x] 검증 기준: automated verify로 INSERT 확인
- [x] 파일 경로: ops_dashboard/db.py 명시
- [x] 제약 준수: Task 1 checkpoint가 역검증 결과 확인 후 진행, git tag 백업 먼저 수행, 기존 R01~R12와 rule_id 충돌 없음 확인
- [x] C01~C08 rule_id/target/severity/description이 CONTEXT.md 정의와 정확히 일치 (8개 모두 검증 완료)

**INSERT 내용 검증 결과**:
| 규칙 | target | severity | CONTEXT 일치 |
|------|--------|----------|:---:|
| C01 | frontmatter | MAJOR | ✅ |
| C02 | frontmatter | CRITICAL | ✅ |
| C03 | body | MAJOR | ✅ |
| C04 | body | CRITICAL | ✅ |
| C05 | frontmatter+publish | CRITICAL | ✅ |
| C06 | file+deploy | MAJOR | ✅ |
| C07 | body+cross-sell | MAJOR | ✅ |
| C08 | live+file | CRITICAL | ✅ |

### 62-03-cause-tracking-hooks.md
- [x] 목표 명확성: "원인추적 훅 3개 지점 구현" 구체적
- [x] 배경 충분성: CONTEXT.md 원인추적 훅 설계 인용
- [x] 설계 구체성: Task 1(leak_tracker.py, 코드 239줄 예시), Task 2(hugo_writer.py 3개 지점 각각 코드 예시) 매우 구체적
- [x] 검증 기준: automated verify 포함
- [x] 파일 경로: shared/leak_tracker.py, shared/publishers/hugo_writer.py 명시
- [x] 제약 준수: 비파괴·증분적 수정, 한 번에 하나의 개념만 변경

**3개 삽입 지점(a/b/c) 설계 검증**:
| 지점 | CONTEXT 위치 | Plan 위치 | 일치 |
|------|-------------|-----------|:---:|
| (a) 생성 직후 | AI 작성 완료 후, humanizer 투입 전 | _write_hugo_post 시작부, _clean_body 직전 | ✅ |
| (b) humanizer 통과 직후 | humanizer 변환 후, _write_hugo_post 전 | _clean_body 호출 후 다음 줄 | ✅ |
| (c) 저장 직전 | _write_hugo_post 저장 직전 | _validate_frontmatter 직전, content=fm+body_md 이후 | ✅ |

**ETAP 처리**: _write_hugo_post_etap에 (a) 지점 별도 추가, locale="en" 명시 → ✅

**중복 방지**: _logged_slugs 세트 사용 → ✅

**참고**: CONTEXT.md §원인추적 훅 설계 마지막 문장 "코드 삽입은 Phase 62 게이트(62-05)에서 수행"과 62-03이 실제 훅 코드를 삽입하는 것 사이의 문구 불일치가 있음. 62-03의 배경 섹션은 "코드 삽입은 Phase 62 게이트(62-04/62-05)에서 수행"으로 수정했으나, 이는 CONTEXT.md의 원래 표현과 다름. 62-03은 파이프라인 내부 훅 코드 삽입을, 62-04는 dispatcher 게이트 코드 삽입을, 62-05는 대시보드 코드 삽입을 담당하는 것으로 해석하면 전체 흐름상 모순은 없음.

### 62-04-preflight-gate.md
- [x] 목표 명확성: "preflight_check 함수 + _build_and_deploy_central 게이트" 구체적
- [x] 배경 충분성: CONTEXT.md 배포 프리플라이트 게이트 인용, dispatcher 현재 상태 명시
- [x] 설계 구체성: Task 1(preflight_check 함수 전체 코드 197줄), Task 2(게이트 삽입 위치 및 코드) 구체적
- [x] 검증 기준: automated verify + human-verify checkpoint 포함
- [x] 파일 경로: dispatcher.py 명시
- [x] 제약 준수: 파일럿-first 접근법(Task 1이 preflight_check 1개 함수부터 시작), C02 "첫--- 이후 두 번째 ---" 판정, C04 국문+영문 패턴 모두 확인, C08 placeholder

**게이트 위치 검증**:
- 삽입 위치: `_build_and_deploy_central(blog_id)` 함수 첫 줄에 preflight_check 호출 → ✅
- 대상 블로그: CUAP/CAP/STAP/RAP/ETAP/SEAP/TAP → Task 2 human-verify checkpoint에서 모두 확인하도록 명시 → ✅

**C08 처리**: "현재 placeholder (라이브 비교 API 연동 시 활성화)" 명시 → ✅

### 62-05-dashboard-integration.md
- [x] 목표 명확성: "check_results에 기록 + localhost:5050 대시보드 조회" 구체적
- [x] 배경 충분성: 기존 standard.py 패턴, register_check 데코레이터, record_check 함수 인용
- [x] 설계 구체성: Task 1(content_integrity.py, 432줄 코드 예시), Task 2(check_results 기록 확인 + 대시보드 테스트) 구체적
- [x] 검증 기준: automated verify(모듈 import + 체크리스트 등록 확인) + DB 확인 명령어 포함
- [x] 파일 경로: ops_dashboard/checks/content_integrity.py, ops_dashboard/db.py 명시
- [x] 제약 준수: ops_dashboard 기존 코드 패턴 준수, register_check 데코레이터 사용, Stage UI 표준 패턴 언급

**8개 체크 등록 검증**: register_check 데코레이터로 c01~c08 모두 CHECKS 레지스트리에 등록 → ✅

### SUMMARY.md
- [x] 개요: 4종 위반 유형 + 규모 표로 제시
- [x] 규칙 정의: C01~C08 table + C02 판정 주의 명시
- [x] 원인추적 훅: (a/b/c) 3개 지점 표
- [x] 배포 프리플라이트 게이트: preflight_check 설명 + 대상 블로그
- [x] 계획 목록: 5개 plan, wave, 내용 표
- [x] 실행 게이트: 4개 조건 + 오탐 시 대응
- [x] 기술 결정: 5개 항목 (C01~C08 rule_id, 역검증 FIRST, git tag 백업 first, 파일럿-first, 비파괴·증분적)
- [x] 파일 변경 요약: 7개 파일, 작업 유형, 계획 매핑
- [x] 검증 기준: 6개 항목
- [x] PLAN.md, CONTEXT.md와 내용 일치

---

## Issues Found

### Critical (must fix before execution)
_None_

### Warnings (should fix)
_None_

### Notes (informational)

1. **C08 placeholder 범위**: 62-01 역검증은 C01~C07만 검증하고 C08은 placeholder로 남겨둠. C08(live-file 불일치)은 라이브 비교 API가 필요하므로 현재 검증이 불가능한 상태. 실행 게이트 "전건 탐지 + 오탐 0" 요구사항은 C01~C07에 대해 충족하고, C08은 나중에 API 연동 시 별도 검증 필요. 이는 기술적 제한으로 인한 정당한 보류로 판단됨.

2. **CONTEXT.md와 62-03 배경 섹션 문구 불일치**: CONTEXT.md §원인추적 훅 설계 마지막 문장은 "코드 삽입은 Phase 62 게이트(62-05)에서 수행"으로 되어 있으나, 62-03은 실제로 훅 코드를 삽입함. 62-03 배경 섹션은 "코드 삽입은 Phase 62 게이트(62-04/62-05)에서 수행"으로 수정하여 완화했으나, 이는 CONTEXT.md의 원래 표현과 다름. 그러나 62-03(파이프라인 내부 훅), 62-04(dispatcher 게이트), 62-05(대시보드 코드)가 각각 다른 영역에 코드를 삽입하는 것으로 해석하면 전체 흐름상 모순은 없음. 실행 전에 CONTEXT.md의 해당 문장을 "코드 삽입은 Phase 62 게이트(62-03/62-04/62-05)에서 단계별로 수행"으로 업데이트 권장.

3. **62-04와 leak_tracker 독립성**: 62-04의 preflight_check 함수는 dispatcher 내부에 C02/C04 판정 로직을 직접 구현하고 leak_tracker.py를 호출하지 않음. 반면 62-03은 hugo_writer.py 파이프라인 내부에 leak_tracker 기반 훅을 삽입함. 두 모듈이 서로 다른 목적(파이프라인 내부 원인추적 vs 배포 전 프리플라이트)을 가지므로 중복으로 보이지는 않으나, C02/C04 판정 로직이 두 곳에 중복 구현됨. 향후 유지보수 시 한쪽 로직 변경 시 다른 쪽도 함께 수정해야 하는 부담이 있음. 현재 시점에서는 62-04가 파일럿-first로 dispatcher에 독립적인 판정 로직을 넣는 것이 타당함.

4. **wave 의존성 직렬 구조**: 62-01 → 62-02 → 62-03 → 62-04 → 62-05가 완전 직렬(depends_on 체인). 62-01(역검증)과 62-02(INSERT)는 실행 게이트로 연결되어 있어 병렬 불가가 정당함. 그러나 62-04(프리플라이트 게이트)와 62-05(대시보드)는 기능적으로 독립적이므로 이론상 병렬 가능. 현재 62-05가 62-04에 의존하도록 설정된 것은 "프리플라이트 게이트가 먼저 구현되어 있어야 대시보드에 배포차단 상태를 표시할 수 있다"는 논리적 순서 때문으로 이해됨. 실제 구현에서는 62-04의 preflight_check 결과가 62-05의 대시보드 표시로 이어지는 데이터 흐름이 있으므로 의존성 유지 타당.

---

## Overall Assessment

Phase 62 계획은 **전반적으로 충실히 설계됨**.

### 강점
- 규칙 정의(C01~C08)가 CONTEXT.md와 정확히 일치하고, 62-02 INSERT 문이 이를 그대로 반영
- C02 판정 제약이 모든 plan에서 일관되게 준수됨 ("첫--- 이후 두 번째 --- 존재 여부"로만 판정, 전체 홀수 카운트 금지)
- C04 영문 패턴 별도 처리가 62-01, 62-04, 62-05에서 모두 구현됨
- 실행 게이트(역검증 통과 → git tag 백업 → INSERT/코드 삽입)가 PLAN.md, 62-01, 62-02, 62-04, 62-05, SUMMARY.md에 일관되게 명시됨
- 파일럿-first 접근법(62-04 preflight_check 1개 함수부터)이 PLAN.md과 62-04에 명시됨
- 3개 원인추적 훅 지점이 CONTEXT.md → 62-03 → SUMMARY.md에서 일관되게 설계됨
- dead_links 77건 전량 fail + ETAP 영문 오탐 0 검증 방안이 62-01 Task 3에 구체적으로 명시됨

### 실행 전 확인 사항
1. CONTEXT.md §원인추적 훅 설계 마지막 문장 업데이트 권장 (노트 2 참조)
2. C08(live-file 불일치)은 라이브 비교 API 연동 시 별도 구현 필요 — 현재 placeholder 상태임을 인지
3. 62-04 preflight_check와 62-03 leak_tracker의 C02/C04 판정 로직 중복은 향후 리팩터링 검토 사항

### 결론
**단계적 실행 권고**: 62-01(역검증) → 통과 확인 → 62-02(INSERT) → 62-03(훅) → 62-04(게이트) → 62-05(대시보드) 순서로 진행. 모든 제약사항과 실행 게이트가 계획에 반영되어 있음.

---

* verification timestamp: 2026-08-07
* verified by: gsd-plan-checker (Solar Pro4)
