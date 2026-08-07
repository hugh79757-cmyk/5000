---
phase: 62-content-leak-prevention
plans:
  - id: 62-01
    file: 62-01-reverse-validation.md
    wave: 1
    objective: "C01~C08 역검증 스크립트 + 검증 데이터 준비 및 실행"
  - id: 62-02
    file: 62-02-standard-rules-insert.md
    wave: 2
    objective: "역검증 통과 확인 후 standard_rules에 C01~C08 INSERT"
  - id: 62-03
    file: 62-03-cause-tracking-hooks.md
    wave: 3
    objective: "shared/leak_tracker.py + hugo_writer.py 3개 지점 훅 구현"
  - id: 62-04
    file: 62-04-preflight-gate.md
    wave: 4
    objective: "dispatcher.py preflight_check 함수 + _build_and_deploy_central 게이트"
  - id: 62-05
    file: 62-05-dashboard-integration.md
    wave: 5
    objective: "ops_dashboard/checks/content_integrity.py + check_results 통합"
---

# Phase 62: Content Leak Prevention — C01~C08 Rule System

## Phase Goal

**As a** 파이프라인 운영자,
**I want to** 콘텐츠 무결성 규칙 C01~C08을 자동 탐지·차단하는 체계를 갖게 되어,
**so that** 프롬프트 누수, 프론트매터 오류, 죽은 크로스셀 링크 등의 위반을 배포 전에 감지하고 차단할 수 있다.

## 배경

2026-08-06 인체어 60만자 전수 분석에서 4종의 콘텐츠 무결성 위반이 확인됨:

| 유형 | 규모 | 설명 |
|------|------|------|
| (a) 죽은 크로스셀 링크 | 404 6건 + 오염 27건 | 크로스셀 카드가 존재하지 않는 slug를 가리키거나 라이브 404 |
| (a) 크로스셀 링크 오판 | 동남냄비받침 44건 | 크로스셀 로직이 잘못된 slug를 산출한 사례 |
| (b) 본문 내 프론트매터 키 유출 | 매뉴얼 샘플 | 제목·og_image 등 프론트매터 키가 본문에 그대로 노출 |
| (c) draft:true 발행 대상 | - | draft:true인데 발행 파이프라인에 도달한 케이스 |
| (d) LLM 프롬프트/사고문 누수 | - | "Need think", "We need to write" 등 프롬프트·CoT 패턴이 본문에 노출 |

이 4종을 포함한 **8개 규칙(C01~C08)**을 ops_db standard_rules에 등록하고,
파이프라인 각 단계 경계에서 자동 탐지·차단하는 체계를 구축한다.

## 역검증 실행 게이트

**아래 조건이 충족되기 전에는 INSERT/코드 삽입을 진행하지 않는다:**

1. ✅ 역검증(62-01)에서 "실제 사례 전건 탐지 + 오탐 0" 확인
2. ✅ git tag 백업 완료 (`phase-62-pre-insert-YYYYMMDD-HHMMSS`)

**오탐 발생 시**: INSERT/삽입을 보류하고 조건만 수정해 62-01에서 재검증.

## 규칙 정의 요약

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

## 원인추적 훅 설계 (C01·C04)

C01(곡선따옴표)과 C04(프롬프트 누수)를 파이프라인 각 단계 경계에서 검사:

| 지점 | 위치 | 검사 대상 |
|------|------|-----------|
| (a) 생성 직후 | AI 작성 완료 후, humanizer 투입 전 | raw 생성물의 곡선따옴표·프롬프트 패턴 |
| (b) humanizer 통과 직후 | humanizer 변환 후, _write_hugo_post 전 | humanizer가 패턴을 제거했는지/남겼는지 |
| (c) _write_hugo_post 저장 직전 | 파일 저장 직전 최종 검사 | 저장 직전 최종 무결성 확인 |

## 배포 프리플라이트 게이트

`dispatcher._build_and_deploy_central()` 직전에 `preflight_check(blog_id)`를 두어,
C01~C04·C08 중 critical이 1건이라도 있으면 배포를 중단하고 위반 slug를 리턴.

**대상 블로그**: CUAP / CAP / STAP / RAP / ETAP / SEAP / TAP 모두

## 계획 목록

| 계획 | 파일 | Wave | 내용 |
|------|------|------|------|
| 62-01 | 62-01-reverse-validation.md | 1 | C01~C08 역검증 스크립트 + 검증 데이터 |
| 62-02 | 62-02-standard-rules-insert.md | 2 | standard_rules에 C01~C08 INSERT (git tag 백업 후) |
| 62-03 | 62-03-cause-tracking-hooks.md | 3 | shared/leak_tracker.py + hugo_writer.py 3개 지점 훅 |
| 62-04 | 62-04-preflight-gate.md | 4 | dispatcher preflight_check + _build_and_deploy_central 게이트 |
| 62-05 | 62-05-dashboard-integration.md | 5 | ops_dashboard 체크 + check_results 대시보드 통합 |

## 검증 기준

- [ ] C01~C08 규칙 definition이 CONTEXT.md와 일치하게 standard_rules에 INSERT됨
- [ ] 역검증: 실제 사례 전건 탐지 + 오탐 0 (dead_links 77건 전부 fail, ETAP 영문 오탐 0)
- [ ] 원인추적 훅 3개 지점이 설계대로 구현됨 (logs/leak-origin.log)
- [ ] preflight_check가 dispatcher._build_and_deploy_central 직전에 삽입됨
- [ ] 대시보드 check_results에 규칙 판정 결과가 표시됨
- [ ] 기존 테스트 21개 실패 외 신규 실패 0
- [ ] CUAP/CAP/STAP/RAP/ETAP/SEAP/TAP 모두 preflight_check 호출 가능

## 제약사항

- **기존 기능을 보존하며 증분적으로 수정** (break nothing that works)
- **한 번에 하나의 개념만 변경** — 구조 변경과 훅 로직 변경은 별도 커밋
- **C02 판정**: 반드시 "첫 --- 이후 두 번째 --- 존재 여부"로만 판정. 전체 --- 홀수 카운트 판정은 금지.
- **C04 영문 패턴**: ETAP 영문 글에서 영문 프롬프트 누수 패턴을 별도 확인 (오탐 없이).
- **preflight_check 대상**: CUAP/CAP/STAP/RAP/ETAP/SEAP/TAP 모두 확인.

---

<execution_context>
@/Users/twinssn/.config/opencode/get-shit-done/workflows/execute-plan.md
</execution_context>
