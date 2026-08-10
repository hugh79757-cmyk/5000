# Phase 64 Context — 규칙 체계 자기진화 + 운영헌장

## 배경

Phase 62에서 C01~C08 규칙 체계를 구축했고, Phase 63에서 C09(categories/tags 문자열화)를 추가 검증했다. 현재 규칙은 총 9종으로, preflight 게이트·배티스트 훅·대시보드 체크에 모두 연결되어 있다.

그러나 두 가지 구멍이 확인됐다.

### 구멍 1: 반응적(reactive) 규칙 목록

지금 규칙은 "이번 세션에서 우연히 마주친 문제"만 담고 있다. 곡선따옴표(C01), 프론트매터 유출(C02/C03), 프롬프트 누수(C04), draft 발행(C05), 죽은 링크(C07), 문자열화(C09) — 전부 이 대화에서 걸려서 만든 것이다.

즉 규칙 목록에 없는 문제 유형은 탐지되지 않는다. "이미지 0개" 오탐(Phase 63에서 발견), 중복 발행, 잘못된 제휴 링크 URL, SEO 메타 누락, 날짜 오류, 카테고리 정책 위반 등은 규칙에 없다. 대시보드가 "문제 없음"이라고 해도 그건 "우리가 정의한 9종에 안 걸림"일 뿐이지 "정말 깨끗함"이 아니다.

### 구멍 2: 판단 원칙의 구두 전달

규칙이 왜 만들어졌는지, 운영 중 뭘 주의해야 하는지가 사람 머릿속(이 대화 기록 및 구두 지시 속)에만 있다. Phase 63에서 에이전트가 두 번 범위를 넘어 대량 작업을 한 것은 "파괴적 작업은 파일럿부터"라는 원칙이 문서로 안 박혀 있어서다. 같은 대화를 하지 않은 다음 에이전트는 같은 사고를 반복한다.

## 현재 규칙 목록 (Phase 62 + 63)

| 규칙 ID | 이름 | severity | target | 자동조치 |
|---------|------|----------|--------|----------|
| C01 | 프론트매터 곡선따옴표 | CRITICAL | frontmatter | 배포차단 |
| C02 | 프론트매터 미종료 | CRITICAL | frontmatter | 배포차단 |
| C03 | 본문 프론트매터 키 유출 | MAJOR | body | 배포차단 |
| C04 | LLM 프롬프트/사고문 누수 | CRITICAL | body | 배포차단 |
| C05 | draft:true 발행 대상 | CRITICAL | frontmatter | 배포차단 |
| C06 | 로컬 mtime > 배포 시각 | WARNING | file | 경고 (차단 아님) |
| C07 | 죽은 크로스셀 링크 | CRITICAL | body 링크 | 배포차단 |
| C08 | 라이브-파일 불일치 | CRITICAL | live+file | placeholder (미구현) |
| C09 | categories/tags 문자열화 | CRITICAL | frontmatter | 배포차단 |

총 9종. 모두 `ops_dashboard/db.py` SEED_STANDARD_RULES에 등록되어 있고, C01/C02/C04/C05/C07/C09는 CRITICAL(배포차단), C06은 WARNING, C08은 placeholder.

## 설계 방향

### 층 1: 대시보드 규칙 확장 (카테고리화 + 세분화)

규칙을 5개 카테고리로 재편한다:

| 카테고리 | 코드 | 현재 커버 | 관심 문제 영역 |
|----------|------|-----------|----------------|
| 콘텐츠 무결성 | C | C01~C05, C09 | 곡선따옴표, 프론트매터 유출/미종료, 프롬프트 누수, draft, 문자열화 |
| 구조/SEO | S | 없음 | cover 이미지 누락, H2 부족, 메타 설명 누락, 내부링크 0, JSON-LD 누락 |
| 링크 건전성 | L | C07 | 죽은 링크, 404 타겟, 잘못된 제휴 URL, 깨진 이미지 URL |
| 발행 정합 | P | C05(부분), C06(부분) | draft 상태 발행, 중복 발행, 날짜 오류, 카테고리 정책 위반, 배포누락 |
| 라이브-파일 일치 | V | C08(placeholder) | 제목 불일치, og:image 불일치, 본문 불일치, CDN 캐시 stale |

각 카테고리는 severity(CRITICAL/MAJOR/WARNING)와 자동조치(탐지only/경고/배포차단)를 갖는다.

### 층 2: 규칙 자기개선 메커니즘 (3종)

(a) leak_tracker 로그 집계 리포트
- 이미 `shared/leak_tracker.py`가 생성직후/humanizer후/저장직전 3단계에서 C01/C04 탐지를 `logs/leak-origin.log`에 쌓고 있다.
- 이 로그를 주기적으로 집계해서 "어느 규칙이 가장 자주 잡히나", "어느 단계에서 릭이 나오나"를 리포팅하는 방안을 설계한다.
- 예: 주간 리포트 "C04가 42건, 그중 38건이 storage 직전 단계에서 탐지 → humanizer 개선 필요"

(b) 오탐/미탐 피드백 루프
- 게이트가 막았는데 알고 보니 정상이었던 것(오탐) → 규칙 조건 완화 검토
- 게이트 통과했는데 라이브에서 문제였던 것(미탐) → 규칙 조건 강화 또는 신규 규칙 등록
- 기록 구조 설계: 어떤 테이블/로그에 무엇을 기록할지

(c) 신규 규칙 등록 절차 문서화
- 발견 → 임시 관찰규칙(경고만) → 역검증(전건탐지+오탐0) → 정식 승격(배포차단)
- 이번 C01~C09를 만든 그 절차를 템플릿화한다.

### 층 3: 운영헌장 (모든 에이전트가 읽는 문서)

`.planning/OPERATIONS-CHARTER.md` 작성. 포함 내용:
- (a) 각 규칙군의 존재 이유와 배경 사고 (91건 재작성, 죽은 복사본, 배포누락, 곡선따옴표 릭 — 실제 사례)
- (b) 절대 원칙 (진본 경로 확인 우선, 파괴적 작업은 백업→파일럿→검증→확대, "일괄 스크립트/전수 재작성"은 위험신호로 파일럿 선행, 파일 통계만으로 판정 금지, 게이트 우회 금지)
- (c) 운영 중 관찰 지표 (대시보드에서 매일 봐야 할 카테고리, 이상 징후)
- (d) 에스컬레이션 조건 (스케줄러 재개, 대량 수정, 인프라/도메인 변경, 롤백 시 사람 승인 필수)

## 기존 아티팩트 참조

- `ops_dashboard/db.py` — SEED_STANDARD_RULES (C01~C09 포함 20개 규칙)
- `shared/leak_tracker.py` — C01/C04 원인추적 훅
- `shared/publishers/hugo_writer.py` — (a)(b)(c) 3개 지점 훅
- `dispatcher.py` — preflight_check + _build_and_deploy_central 게이트
- `ops_dashboard/checks/content_integrity.py` — C01~C08 체크 8종
- `Phase 62 CONTEXT.md` — C01~C08 설계 근거
- `Phase 63 PLAN.md` — C09 검증 절차
- `scripts/c01_c08_reverse_validation.py` — 역검증 스크립트 (check_c01~check_c09)
- `scripts/c01_c08_validation_data/` — 검증 데이터 (dead_links, contamination, ETAP 영문 샘플, 정상글, C09 샘플)

## 비범위 (이번 phase에서 하지 않음)

- 실제 INSERT (ops_dashboard/db.py 수정 금지)
- 코드 수정 (leak_tracker, hugo_writer, dispatcher, content_integrity 수정 금지)
- 배포
- 기존 C01~C09 규칙의 삭제/변경
- S/L/P/V 카테고리 규칙의 실제 구현
