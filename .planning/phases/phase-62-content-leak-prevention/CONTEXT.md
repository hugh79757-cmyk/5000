# Phase 62: Content Leak Prevention — C01~C08 Rule System

## 왜 이 단계가 필요한가

2026-08-06 인체어 60만자 전수 분석에서 4종의 콘텐츠 무결성 위반이 확인됐다:

| 유형 | 규모 | 설명 |
|------|------|------|
| (a) 죽은 크로스셀 링크 | 404 6건 + 오염 27건 | 크로스셀 카드가 존재하지 않는 slug를 가리키거나 라이브 404 |
| (a) 크로스셀 링크 오판 | 동남냄비받침 44건 | 원인이 링크 오판(크로스셀 로직이 잘못된 slug를 산출한 사례) |
| (b) 본문 내 프론트매터 키 유출 | 매뉴얼 샘플 | 제목·og_image 등 프론트매터 키가 본문에 그대로 노출 |
| (c) draft:true 발행 대상 | - | draft:true인데 발행 파이프라인에 도달한 케이스 |
| (d) LLM 프롬프트/사고문 누수 | - | "Need think", "We need to write" 등 프롬프트·CoT 패턴이 본문에 노출 |

이 4종을 포함한 **8개 규칙(C01~C08)**을 ops_db standard_rules에 등록하고, 파이프라인 각 단계 경계에서 자동 탐지·차단하는 체계가 필요하다.

## 규칙 정의 (이전 확정, 변경 금지)

### C01 — 프론트매터 내 곡선따옴표
- **target**: frontmatter
- **판정조건**: YAML 값(타이틀·description·카테고리·태그 등)에 직선따옴표(`'` `"`)가 아닌 곡선따옴표(`'` `'` `"` `"`)가 포함됨
- **severity**: MAJOR
- **자동조치**: 탐지 시 게시 중단 + slug·필드명·문자열 기록(logs/leak-origin.log)

### C02 — 프론트매터 미종료
- **target**: frontmatter
- **판정조건**: 첫 `---` 이후 두 번째 `---`가 존재하지 않음. **전체 `---` 홀수 카운트 판정은 금지**(본문 내 `---` 수평선과 혼동). 반드시 "첫 `---` 이후 두 번째 `---` 존재 여부"로만 판정.
- **severity**: CRITICAL
- **자동조치**: 탐지 시 배포 차단

### C03 — 본문에 프론트매터 키 라인 유출
- **target**: body
- **판정조건**: 본문에 `title:`, `og_image:`, `featureimage:`, `date:`, `slug:` 등 프론트매터 키 라인과 유사한 라인이 존재
- **severity**: MAJOR
- **자동조치**: 탐지 시 게시 중단 + 누수 키·라인 기록

### C04 — 본문에 LLM 프롬프트/사고문 누수
- **target**: body
- **판정조건**: 본문에 프롬프트 지시문·CoT 사고문이 노출. 패턴 예: "Need think", "We need to write", "Let's think step by step", "먼저", "생각해보자" 등 LLM이 지시를 그대로 복술한 흔적
- **severity**: CRITICAL
- **자동조치**: 탐지 시 게시 중단 + 패턴·slug 기록

### C05 — draft:true 발행 대상
- **target**: frontmatter+publish
- **판정조건**: frontmatter에 `draft: true`가 설정되어 있는데 발행 파이프라인이 이를 발행 대상으로 처리
- **severity**: CRITICAL
- **자동조치**: 탐지 시 발행 중단 + slug 기록

### C06 — 로컬 mtime > 배포 시각
- **target**: file+deploy
- **판정조건**: 로컬 파일의 mtime이 마지막 배포 시각보다 최신. 배포 후 로컬에서 파일이 수정된 상태.
- **severity**: MAJOR
- **자동조치**: 탐지 시 경고 + 슬러그 기록 (배포 차단은 옵션)

### C07 — 죽은 크로스셀 링크
- **target**: body+cross-sell
- **판정조건**: 크로스셀 카드가 가리키는 대상 slug가 (1) DB에 published=0이거나 (2) 라이브에서 HTTP 404
- **severity**: MAJOR
- **자동조치**: 탐지 시 해당 크로스셀 카드 제거/대체 + 대상 slug 기록

### C08 — 라이브-파일 불일치
- **target**: live+file
- **판정조건**: 라이브 프런트와 로컬 파일 간 불일치. (1) 제목 빔(라이브 제목이 파일 제목과 다름), (2) og_image 유출(라이브 OG 이미지가 본문 내용과 불일치)
- **severity**: CRITICAL
- **자동조치**: 탐지 시 배포 차단 + 불일치 유형·슬러그 기록

## 원인추적 훅 설계 (C01·C04)

C01(곡선따옴표)과 C04(프롬프트누수)를 파이프라인 각 단계 경계에서 검사해 **어느 단계에서 처음 나타나는지** 특정한다.

### 삽입 지점 3곳
| 지점 | 위치 | 검사 대상 |
|------|------|-----------|
| (a) 생성 직후 | AI 작성 완료 후, humanizer 투입 전 | raw 생성물의 곡선따옴표·프롬프트 패턴 |
| (b) humanizer 통과 직후 | humanizer 변환 후, _write_hugo_post 전 | humanizer가 패턴을 제거했는지/남겼는지 |
| (c) _write_hugo_post 저장 직전 | 파일 저장 직전 최종 검사 | 저장 직전 최종 무결성 확인 |

### 로직
각 지점에서 곡선따옴표(C01)·프롬프트누수(C04) 패턴을 검사하고, **처음 탐지된 지점**을 `logs/leak-origin.log`에 `stage+slug+패턴` 형태로 기록한다. 같은 slug에 대해 여러 지점에서 탐지되면 첫 지점만 기록(중복 방지).

이것이 다음 발행부터 릭 원인을 자동으로 특정한다. **삽입 지점과 로직만 설계. 코드 삽입은 Phase 62 게이트(62-03/62-04/62-05)에서 단계별 수행: 62-03은 파이프라인 내부 훅, 62-04는 dispatcher 게이트, 62-05는 대시보드 통합.**

## 배포 프리플라이트 게이트

`dispatcher._build_and_deploy_central()` 직전에 `preflight_check(blog_id)`를 두어, C01~C04·C08 중 critical이 1건이라도 있으면 배포를 중단하고 위반 slug를 리턴한다.

### 대상 블로그 (전 분기 공통)
CUAP / CAP / STAP / RAP / ETAP / SEAP / TAP 모두 이 게이트를 통과하는지 dispatcher 코드로 확인한다.

### 현재 dispatcher 상태
- `_build_and_deploy_central(blog_id)` 존재함 (dispatcher.py:529)
- preflight_check 함수 없음 — 삽입 지점 존재
- 파일 수정 없이 차단만 수행 (게이트 로직만 추가)

## 역검증 표

작성한 규칙을 이번 세션 실제 사례에 돌려 검증한다:

| 검증 항목 | 사례 | 기대 결과 |
|-----------|------|-----------|
| (a) 죽은 크로스셀 링크 | 404 6건 + 오염 27건 + 동남냄비받침 44건 | 전부 fail로 잡아야 함 |
| (b) 정상 글 | ETAP 영문 글 3551건 | 오탐 0, 전부 pass |
| (c) C04 패턴 | 프롬프트 누수 케이스 | 오탐 없이 탐지 |
| (d) 영문 글 C04 | ETAP 영문 글 | 영문 프롬프트 누수 패턴 별도 확인, 오탐 없이 통과 |

**오탐이 나면 조건을 조정하고 재검증한다.**

## 실행 게이트

**역검증에서 "실제 사례 전건 탐지 + 오탐 0"이 확인돼야** 다음 단계로 진행한다:

1. standard_rules INSERT (C01~C08)
2. 원인추적 훅 코드 삽입 (3개 지점)
3. 프리플라이트 게이트 코드 삽입

**반드시 git tag 백업을 먼저 수행한다.**

**코드 삽입은 파일럿부터**: dispatcher 프리플라이트 1개 함수부터 시작.

**역검증이 오탐을 내면**: INSERT/삽입을 보류하고 조건만 수정해 재검증한다.

## 대시보드 표시

규칙 판정 결과를 `localhost:5050` 대시보드의 `check_results`에 분기별로 뜨도록 연결한다. 사용자가 대시보드에서 어느 블로그에 어느 릭이 몇 건인지 보고 배포차단 상태를 확인할 수 있게 한다.

## 기존 standard_rules 현황

ops_dashboard/db.py에 R01~R12가 이미 등록되어 있음 (프론트엔드/테마 표준):

| rule_id | target | severity |
|---------|--------|----------|
| R01 | hugo.toml | CRITICAL |
| R02 | hugo.toml | CRITICAL |
| R03 | extend-head.html | CRITICAL |
| R04 | extend_head.html | MAJOR |
| R05 | adsense/top.html | MAJOR |
| R06 | adsense/in-article.html | CRITICAL |
| R07 | single.html | MAJOR |
| R08 | single.html | MAJOR |
| R09 | baseof.html | MAJOR |
| R10 | custom.css | MAJOR |
| R11 | layouts/ | MAJOR |
| R12 | layouts/ | MAJOR |

C01~C08은 콘텐츠 무결성·누수 계열로 R01~R12와 별개 스콥.

## 기술 제약

- **기존 기능을 보존하며 증분적으로 수정** (break nothing that works)
- **한 번에 하나의 개념만 변경** — 구조 변경과 훅 로직 변경은 별도 커밋
- ops_dashboard/ 기존 코드 패턴(check_results 기록 방식, CHECKS 등록 패턴)을 따름
- Stage UI 관련: Stage Banners, Checkpoint Boxes 등 표준 패턴 적용

## 검증 기준

- [ ] C01~C08 규칙 definition이 CONTEXT.md와 일치하게 standard_rules에 INSERT됨
- [ ] 원인추적 훅 3개 지점이 설계대로 구현됨
- [ ] preflight_check가 dispatcher._build_and_deploy_central 직전에 삽입됨
- [ ] 역검증: 실제 사례 전건 탐지 + 오탐 0
- [ ] 대시보드 check_results에 규칙 판정 결과가 표시됨
- [ ] 기존 테스트 21개 실패 외 신규 실패 0
