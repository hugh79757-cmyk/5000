## Appendix C — FIX 레시피북 (의도·경계 기반)

> **[2026-08-23] SSOT 이전 안내**: 오류 유형별 감지→진단→수정→검증 절차의 단일 기준 문서는
> 이제 `docs/lookbook/ERROR_LOOKBOOK.md` (ERR-001~020)이다. 이 문서는 R규칙 상세 레시피의
> 원본으로 **유지·삭제 금지**이며, 새 오류 유형은 룩북에 먼저 등록한다.
>
> 추가일: 2026-08-08 | 상태: 활성 | 목적: 실행 에이전트가 블로그 구조를 읽고 명령을 생성할 때, 그 생성이 벗어나지 못할 울타리를 정의함. 정확한 명령·정확한 라인은 기록하지 않는다 — 실행 시점에 블로그 구조에서 생성한다.
> 이 레시피북은 AGENTS.md §대시보드 운영 런북의 READ→INTERPRET→FIX 흐름을 대체하지 않으며, FIX 단계의 "무엇을 해도 되고 무엇을 하면 안 되는지"를 성문화한다.

### C.0 등급 요약표

실행 에이전트는 아래 표를 먼저 보고 rule_id/problem_id의 기본등급과 조건부 분기를 확인한다. "결정지점 있음"이면 진행 전 사용자에게 질문 1개를 던진다.

| rule_id / problem_id | 기본등급 | 조건부 분기 (evidence 조건 → 등급) | 사용자 결정지점 |
| ----------------------| -------- | ---------------------------------- | -------------- |
| **R01** | A | `showTableOfContents = true` → A / 이미 false거나 항목 없음 → pass(unknown) / 테마가 TOC를 하드컨트롤해 params로 제어 불가 → B(구조 확인) | 없음 |
| **R02** | A | `[params.advertisement]` 누락 → A(섹션+슬롯 추가) / 섹션 있으나 adsense·슬롯 ID 오류 또는 불명 → B(계정·슬롯 확인) / publisher ID가 계열과 다름 → B(계열 매핑 확인) | 슬롯 ID 실재 여부·계열 확인 필요 시 1회 |
| **R03** | A(단, bucket out_of_scope) | 하드코딩 ca-pub- 없음 + site.Params 사용 → pass / 하드코딩 존재 + site.Params 미사용 → A(사이트.Params 이전) / informationhot 이중관리(STRUCT-15) → B(단일 소스 결정) | informationhot 이중관리 해소 시 단일 소스 결정 1회 |
| **R04** | B | GA4 완전 누락 + mobile CSS 누락 → B(gtag 측정 ID 필요) / GA4 있으나 mobile CSS만 누락 → A(CSS만 추가) / 둘 다 있음 → pass / 측정 ID 제공 불가 → C(측정 ID 결정) | GA4 측정 ID(블로그별) — 없거나 생성 필요시 |
| **R05** | A | overflow:hidden/min-height 누락 → A / push div 위치 오류 → A / 규격 충족 → pass | 없음 |
| **R06** | B(deferred) | auto→fluid 교체만으로 충분 + 슬롯 정책 이슈 없음 → A(파셜 교체) / 슬롯 정책 확인 필요 → B(일괄 승인 1회) / 이미 fluid인데 다른 문제 → B(재Diagnosis) / format 불명 → C | 19블로그 일괄 교체 승인 1회 (B등급 핵심 결정지점) |
| **R07** | A | H2 split injection + prose wrapper 없음 → A / 하나만 없음 → A(없는 쪽 추가) / 둘 다 있음 → pass | 없음 |
| **R08** | A | .Lead/.Description 잔존 → A(삭제) / 이미 제거 → pass / 어떤 요소가 lead인지 불명 → B(식별 확인) | 없음 |
| **R09** | A | 커스텀 baseof.html 존재 → A(삭제, 테마 기본값) / 없음 → pass / 필요 여부 판단 애매 → B(허용 범위 확인) | 특정 오버라이드 필요 여부 애매 시 1회 |
| **R10** | A | custom.css 없음 → A(생성) / 있으나 미채움·다크모드·min-height 누락 → A(보완) / 완비 → pass | 없음 |
| **R11** | A | mobile-sticky.html 존재 → A(삭제) / 없음 → pass | 없음 |
| **R12** | A | 허용 집합 벗어난 오버라이드 + junk 있음 → A(초과 삭제+junk 정리) / 허용 여부 판단 애매 → B(사용자 확인) / junk만 → A(정리) | 허용 판단 애매 시 1회 |
| **THUMBNAIL-01** | B | featureimage 이미 R2 webp → pass / 비R2 → B(원본 R2 존재→A로 전환, 부재→B 유지·재업로드) | 원본 이미지 R2 존재 여부 확인 1회 |
| **R2-01** | B | 모든 이미지 URL R2 → pass / 비R2 존재 → B(원본 R2 존재→A, 부재→B) / featureimage만 위반·본문 이미지 모두 R2 → 영향 축소(A에 가까움) / 본문 이미지 다수 위반 → B 유지·일괄 승인 필요 시 결정 | 원본 이미지 R2 존재 여부 확인 1회 |
| **P02** (no_content) | D(현재 auto_handled) | 재발 시 C(데이터·토픽 보충 결정) / auto_handled 유지 → D | 토픽·데이터 소스 보충 결정 |
| **P06** (broken_featureimage) | B | 썸네일 R2 존재 → A(batch_thumbnails.py) / 원본 소실 → B(재업로드 판단) / 구조적 경로 문제 → B/C(경로 정책 확인) | 원본 재업로드 판단 1회 |
| **P14** (keyword 소진) | C | informational_keyword → C(키워드 소스 보충 결정) / 데이터 소스 보충 완료 → A 재개 / 정책 유지 → D | 키워드 소스 보충 결정 |
| **P17** (매일 소진) | D(quiet, auto_skipped) | 정책 변경 필요 → C / 유지 → D | 정책 변경 결정 |
| **P15** (발행 후 검증 실패) | C | 로그 확인 후 원인 특정 → B / 원인 불명 → C | 원인 조사 범위 결정 |
| **P01** (no_result) | C | 가드 완화로 해결 가능 → B / 데이터 소스 보충 필요 → C / auto_skipped 유지 → D | 가드 조정 vs 데이터 보충 결정 |
| **P10** (title_blocked) | B | 패턴 조정·변형 다양화로 해결 → B / 차단 정책 자체 변경 필요 → C / auto_skipped 유지 → D | 차단 패턴 정책 결정 |
| **P18** (동시 실행 방지) | D(quiet, auto_skipped) | lock 강화 필요 → B / 유지 → D | lock 정책 결정 |
| **leak_detected** | B | 스캔→발견→재현 생성 방지 조치(A) / CoT 누출 경로 모호 → C(재Diagnosis) / 의심만·특정 불가 → C | 재현 경로 확인 |
| **known_issue** | C(또는 D) | 재현·해결책 명확 → B / 불명 → C / 백로그 이연 결정 → D | 해결 우선순위 결정 |
| **dead_entity_link** | B | 404 링크 탐지→교체/제거 결정(B) / 엔티티 재등록 필요 → C / 탐지 불가 → C | 링크 처리 방식 결정 |

> 등급: A=자동, B=반자동(판단 1회), C=사람 필요, D=외부/보류. 기본등급은 현재 증거 기준; evidence 조건이 바뀌면 등급도 바뀐다. 조건부 분기를 먼저 평가한다.

### C.1 후자 방식 공통 원칙

#### C.1.1 의도·경계 기반 실행 모델

실행 에이전트는 레시피의 "목표 상태"와 "허용 범위"를 읽고, 해당 블로그의 실제 파일 구조를 확인한 뒤 **스스로 명령을 생성**한다. 레시피에는 정확한 sed/정규식/라인 번호를 기록하지 않는다 — 그건 블로그마다 다르기 때문이다. 대신 다음만 기록한다:

- **목표 상태**: 어떤 조건을 만족하면 "고쳐졌다"고 볼 수 있는가 (증거 기반)
- **허용 범위**: 수정이 건드려도 되는 파일/영역과 절대 건드리면 안 되는 것
- **STOP 조건**: 생성이 폭주하는 신호를 감지하는 체크포인트
- **사용자 결정지점**: B/C 등급일 때 사람에게 물을 단 하나의 질문

에이전트는 생성된 계획(예상 변경 파일 목록·예상 변경 규모)을 실행 전에 보고하고, STOP 조건에 걸리지 않을 때만 진행한다. 목표 상태가 불명확하거나 허용 범위와 충돌하면 창의적 재해석을 금지하며 즉시 사용자에게 회신한다.

#### C.1.2 필수 공통 게이트 (모든 FIX에 적용)

1. **백업**: 코드 수정 전 `git tag pre-<작업명>-<YYYYMMDD>` + DB 관련 시 `cp data/<db>.db data/<db>.db.bak_<YYYYMMDD>`. 백업 없이 수정 금지.
2. **로컬 Hugo 빌드 0에러**: `HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes hugo --gc --minify --source /경로/블로그`. 에러 있으면 중단·롤백.
3. **배포**: `dispatcher.py`로 블로그별 1회 배포. 수동 wrangler·`--commit-dirty=true`·git push 금지. Workers 블로그(health/pet/kitchen/beauty/camping/baby)는 `wrangler deploy --config wrangler.toml`, 그 외 Pages는 `wrangler pages deploy` — dispatcher.py가 자동 구분.
4. **재검사 트리거 (필수, 누락 금지)**: 코드 수정·배포 후 화면이 갱신되려면 반드시 수동 재검사 호출이 필요하다. 대시보드에는 자동 재검사 스케줄이 없으므로, **POST /api/run-checks?blog_id={blog_id}**(개별 블로그) 또는 **POST /api/run-checks**(전체)를 호출하지 않으면 `/api/registry`·`/api/attention`·블로그 상세 페이지에 수정 결과가 반영되지 않는다.
   - 개별 블로그 FIX 후: `curl -s -X POST -u "${OPS_USER}:${OPS_PASSWORD}" "http://localhost:5060/api/run-checks?blog_id={blog_id}"` → 반환 직후 check_results 갱신. 그 다음에 `/api/registry` status 확인.
   - 정비 체크리스트 항목(M01~M10) FIX 후: `curl -s -X POST -u "${OPS_USER}:${OPS_PASSWORD}" -H "Content-Type: application/json" -d "{\"blog_id\":\"{blog_id}\"}" "http://localhost:5060/api/maintenance/checklist"` → 정비 체크리스트 재실행.
   - **경고**: 이 호출 없이는 FAIL→PASS를 확인할 수 없다. 체크 결과를 "믿고" 완료 보고하는 것은 금지.
5. **재검증 FAIL→PASS 확인**: 재검사 트리거 호출 후 `/api/registry`에서 해당 rule_id의 status가 `"fail"` → `"pass"` 또는 `"unknown"`(체크 미실행 상태로 전환)으로 바뀌었는지 확인. 예: R04 fix 후 `/api/registry` → R04 status=`"pass"`, evidence에 `"extend_head: GA4 + mobile CSS found"` 등. **FAIL→PASS 확인 없이 완료 보고 금지.**
6. **로그**: 파괴적 작업 포함 시 `logs/destructive_YYYY-MM-DD.log`에 한 줄 append. 민감정보 마스킹.

게이트 실패 시: 빌드 에러 → 원복구(git checkout 또는 백업 복원) 후 재구성. 배포 실패 → dispatcher 로그 확인, 재시도 금지. 재검증 여전히 FAIL → action이 잘못됐거나 추가 문제 — 사용자 보고 후 진행. **재검사 트리거를 호출하지 않은 상태에서 "FAIL→PASS 예상"으로 완료 보고하는 것은 게이트 위반.**

#### C.1.2.1 자동 갱신 대기의 STOP 조건

- 현재 대시보드는 **자동 재검사 스케줄이 없다**. "배포했으니 잠시 후 화면이 갱신되길 기다린다"는 계획은 STOP 조건 (e): 목표 상태가 증거 기반으로 특정되지 않음 + "자동 갱신이 언제 올지 불명"에 해당. 에이전트는 재검사를 명시적으로 직접 호출해야 하고, 호출 전까지 화면 상태를 "확정된 것"으로 취급하지 않는다.
- 재검사 트리거 후에도 FAIL이 유지되면, 재시도 무한루프는 금지. 원인 귀속 후 진행(코드 수정 재시도 vs action 오류 판단).

#### C.1.3 STOP 조건 (공통, 실행 에이전트 필수 체크)

실행 에이전트는 계획 실행 전/중/후에 아래 조건을 체크한다. **하나라도 걸리면 즉시 중단하고 사용자에게 보고한다.** 애매하면 실행하지 말고 보고한다.

| # | STOP 조건 | 트리거 예시 |
| -- | -------- | ---------- |
| (a) | **허용 범위 벗어남** | 레시피에서 허용한 파일 외 파일이 diff에 포함됨 |
| (b) | **예상 변경 규모 초과** | 1파일 기대인데 3파일 diff / 예상 7건 교체인데 20건 변경 |
| (c) | **빌드 에러** | Hugo 빌드에서 에러 발생 (로컬 빌드 게이트) |
| (d) | **/api/registry 총량·분포 이상 변화** | 목표 rule_id 외에 인접 규칙까지 fail로 변함 / fail 총량이 레시피 목표와 다르게 움직임 |
| (e) | **목표 상태 불명확** | evidence로 목표 상태가 특정되지 않음 / "유체화"처럼 정성적 표현으로만 정의됨 |
| (f) | **비가역 작업 감지** | DB DELETE/UPDATE/DROP, 테마 변경, 대량 삭제, 실발행 행 덮어쓰기가 계획에 포함됨 → 자동 금지, 별도 웨이브·명시 승인 필요 (C.4 참조) |

> (f)는 하드 STOP이다. 레시피에 "자동 금지" 플래그가 붙은 항목은 에이전트가 스스로 계획을 생성하더라도 실행하지 않는다. 사용자에게 명시적 웨이브 승인 없이는 진행 불가.

### C.2 규칙 레시피 (R01~R12, THUMBNAIL-01, R2-01)

> 각 항목은 아래 스키마를 따른다: rule_id/한 줄 정의 → 등급 결정트리 → 수정 의도(목표 상태) → 허용 범위(경계) → 사용자 결정지점(B/C) → STOP 조건 → 검증 → 비가역 플래그.

#### R01 — hugo.toml: showTableOfContents

- **정의**: Hugo 사이트의 목차(TOC) 표시가 활성화되어 있어 표준과 어긋나는 상태.
- **등급 결정트리**:
  - `showTableOfContents = true` → **A**
  - 이미 `false`거나 항목이 없음 → **unknown**(패스)
  - hugo.toml이 없거나 테마가 TOC를 하드컨트롤해서 params로 제어 불가 → **B**(구조 확인 필요)
- **수정 의도 (목표 상태)**: 사이트 전체 글에서 자동 생성되는 TOC가 비활성화된 상태. `showTableOfContents`가 `false`로 설정되어 있고, Hugo 빌드가 이를 수용하는 상태.
- **허용 범위 (경계)**:
  - ✅ 건드려도 됨: hugo.toml의 `[params]` 또는 최상위 `showTableOfContents` 값.
  - ❌ 건드리면 안 됨: layouts, 콘텐츠, 다른 params, 테마 파일.
- **사용자 결정지점**: 없음 (A).
- **STOP 조건**:
  - (a) hugo.toml 외의 파일이 변경됨 → 중단
  - (d) R01 외에 다른 rule_id까지 fail로 변함 → 중단·보고
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 대시보드에는 자동 재검사 스케줄 없음 — 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면을 갱신한 뒤 재검증해야 함. 자동 갱신을 기다리는 계획은 STOP.
- **검증**: `/api/registry` R01 status = `pass` (또는 `unknown`).
- **비가역 플래그**: 없음.

#### R02 — hugo.toml: [params.advertisement] + AdSense slots

- **정의**: hugo.toml에 광고 설정 파라미터가 누락되거나 슬롯 구성이 표준과 다른 상태.
- **등급 결정트리**:
  - `[params.advertisement]` 섹션 자체가 없음 → **A**(섹션 추가 + adsense + topSlot/inArticleSlot 설정)
  - 섹션은 있으나 adsense/publisher ID 오류 또는 슬롯 ID 불명 → **B**(AdSense 콘솔에서 슬롯 ID 확인 필요)
  - publisher ID가 계열의 것과 다름(AdSense ID 매핑 위배) → **B**(계열 확인 후 정정)
- **수정 의도 (목표 상태)**: hugo.toml에 `[params.advertisement]`가 존재하고, `adsense`(publisher ID), `topSlot`, `inArticleSlot`(또는 테마가 요구하는 슬롯 키)가 채워져 있으며, publisher ID가 해당 사이트 계열의 올바른 계정인 상태.
- **허용 범위 (경계)**:
  - ✅ hugo.toml의 `[params.advertisement]` 섹션 및 그 키들.
  - ❌ layouts, 콘텐츠, 다른 설정 파일. 슬롯 ID 자체를 악의적으로 바꾸지 말 것(실제 존재하는 슬롯인지 확인).
- **사용자 결정지점**: 슬롯 ID가 실제 AdSense 계정에 존재하는지 확인이 필요할 때 1회.
- **STOP 조건**:
   - (a) hugo.toml 외 파일 변경 → 중단
   - (d) R02 수정 후 R03/R06 등 연관 광고 규칙이 예상과 다르게 변함 → 중단·보고
   - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: `/api/registry` R02 status = `pass`.
- **비가역 플래그**: 없음. 단, publisher ID 변경은 수익 영향 → 변경 전 계열 매핑 확인 필수.

#### R03 — extend-head.html: adsbygoogle.js 하드코딩 제거 (site.Params 사용)

- **정의**: extend-head.html에 AdSense 클라이언트 ID가 하드코딩되어 있고, site.Params를 쓰지 않는 상태. (주의: informationhot-hugo는 STRUCT-15로 이중 관리 중 — extend-head.html 하드코딩 + params.toml advertisement.adsense 동시 존재.)
- **등급 결정트리**:
  - 하드코딩 ca-pub- 없음 + site.Params 사용 중 → **pass**
  - 하드코딩 ca-pub- 존재 + site.Params 미사용 → **A**(사이트.Params 기반으로 이전) — 단, bucket이 out_of_scope이므로 준수율 산정에서는 제외. 그래도 수정은 가능.
  - informationhot 계열에서 하드코딩과 params.toml이 이중 존재(STRUCT-15) → **B**(어느 쪽을 소스로 할지 결정: 사이트.Params 기준으로 단일화)
- **수정 의도 (목표 상태)**: AdSense 클라이언트 ID가 사이트 설정(params)에서만 관리되고, extend-head.html 템플릿은 그 값을 참조하는 상태. 하드코딩된 ca-pub- 문자열이 템플릿에서 사라짐.
- **허용 범위 (경계)**:
  - ✅ extend-head.html 내 adsbygoogle.js 로딩 부분의 클라이언트 참조 방식.
  - ❌ 콘텐츠, 다른 파셜, params.toml의 광고 설정을 임의로 삭제(단, 이중 관리 해소 시는 예외 — B등급으로 판단 1회).
- **사용자 결정지점**: informationhot 계열처럼 이중 관리 해소 시, 어느 쪽을 단일 소스로 할지 1회.
- **STOP 조건**:
  - (a) extend-head.html 외 파일 변경 → 중단
  - (f) params.toml 광고 설정을 레시피 의도와 다르게 삭제/변경 → 중단 (의도: 하드코딩 제거 + 사이트.Params 참조. 설정값 자체를 없애는 것 아님.)
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: `/api/registry` R03 status = `pass` (또는 체크 방식상 `unknown`로 전환).
- **비가역 플래그**: 없음. 단, informationhot의 이중 관리 해소는 STRUCT-15 연계 → 변경 전 확인.

#### R04 — extend_head.html: GA4 + 모바일 보정 CSS

- **정의**: extend_head.html에 GA4(gtag) 추적 스니펫이 없고, 일부 블로그는 모바일 보정 CSS(`@media (max-width:767px)`)도 없는 상태.
- **등급 결정트리**:
  - GA4 완전 누락 + 모바일 CSS 누락 → **B**(GA4 측정 ID 필요 + 모바일 CSS 추가)
  - GA4는 있으나 모바일 CSS만 누락 → **A**(모바일 보정 CSS만 추가)
  - 둘 다 있음 → **pass**
  - GA4 측정 ID가 무엇인지 확인 불가/제공 안 됨 → **C**(측정 ID 결정 필요)
- **수정 의도 (목표 상태)**: extend_head.html에 구글 애널리틱스 4(gtag) 스니펫이 블로그별 측정 ID로 삽입되어 있고, 모바일 화면(최대 767px)에서 레이아웃 보정을 위한 CSS가 포함된 상태.
- **허용 범위 (경계)**:
  - ✅ extend_head.html 내 GA4 스니펫 추가 + 모바일 보정 CSS 블록 추가.
  - ❌ 콘텐츠, 레이아웃, 다른 파셜, GA4 측정 ID 자체를 에이전트가 만들어내지 말 것(측정 ID는 사람이 제공).
- **사용자 결정지점**: GA4 측정 ID(블로그별). 없으면 생성 여부·계정을 사람이 결정. **이 질문이 B등급의 유일한 개입 지점.**
- **STOP 조건**:
  - (a) extend_head.html 외 파일 변경 → 중단
  - (e) 측정 ID가 제공되지 않았고 에이전트가 임의로 추정 생성하려 함 → 중단·보고 (추정 금지)
  - (d) R04 수정 후 R03/R17(STRUCT-17 연계) 등 상태 이상 변화 → 중단·보고
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: `/api/registry` R04 status = `pass`.
- **비가역 플래그**: 없음. 단, GA4 측정 ID 변경은 추적 단절 → 기존 ID가 있으면 재사용, 없으면 신규 생성 결정은 사람.

#### R05 — adsense/top.html: overflow:hidden;min-height 래퍼 + outside push div

- **정의**: top 광고 파셜에 `overflow:hidden` 및 `min-height`가 없거나, push 스크립트/스타브가 래퍼 밖에 제대로 배치되지 않은 상태.
- **등급 결정트리**:
  - overflow:hidden 및 min-height 누락 → **A**(래퍼 추가)
  - push div가 래퍼 밖에 없음 → **A**(div 밖 배치)
  - 이미 규격 충족 → **pass**
- **수정 의도 (목표 상태)**: top 광고 영역에 `overflow:hidden; min-height:100px` 스타일의 래퍼가 있고, 광고 push를 위한 스크립트(div 밖)가 래퍼 외부에 위치한 상태.
- **허용 범위 (경계)**:
  - ✅ `layouts/partials/adsense/top.html` 내부 구조.
  - ❌ 다른 파셜, 콘텐츠, config.
- **사용자 결정지점**: 없음 (A).
- **STOP 조건**:
  - (a) top.html 외 파일 변경 → 중단
  - (b) 1파일 기대인데 다수 파일 diff → 중단·보고
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: `/api/registry` R05 status = `pass`.
- **비가역 플래그**: 없음.

#### R06 — adsense/in-article.html: fluid + in-article format (no auto) + outside push div

- **정의**: in-article 광고 파셜이 `data-ad-format="auto"`를 쓰거나 fluid/in-article format이 누락되어 AdSense 표준과 어긋난 상태. bucket은 `deferred` — AdSense 정책 확인 후 처리 권장.
- **등급 결정트리**:
  - auto → fluid/in-article 교체만으로 충분, 슬롯 정책 이슈 없음 → **A**(파셜 교체)
  - 교체 자체는 명확하나 AdSense 계정에서 해당 슬롯의 포맷 정책을 확인해야 함 → **B**(일괄 처리 전 승인 1회)
  - 이미 fluid인데 다른 문제(예: push 위치)가 있음 → **B**(정확히 무엇이 잘못됐는지 재Diagnosis)
  - data-ad-format이 auto도 fluid도 아닌데 불명 → **C**(재Diagnosis)
- **수정 의도 (목표 상태)**: in-article 광고가 fluid 레이아웃으로 렌더되고, `data-ad-format="fluid"` 및 `data-ad-layout="in-article"`이 설정되어 있으며, `<script>push({})</script>`가 `<ins>` 태그 밖에 위치한 상태.
- **허용 범위 (경계)**:
  - ✅ `layouts/partials/adsense/in-article.html` 내부.
  - ❌ layouts 전체, 콘텐츠, config, 다른 광고 파셜(top.html 등 — 이 레시피 범위 아님).
- **사용자 결정지점**: 19개 블로그의 in-article 파셜을 일괄 fluid로 교체할지 1회 승인. (B등급의 핵심 결정지점.)
- **STOP 조건**:
  - (a) in-article.html 외 파일 변경 → 중단
  - (b) 1블로그 1파일 기대인데 여러 파일/블로그가 한 번에 변경됨 → 중단·보고 (레시피는 블로그별 1파일. 일괄이 필요하면 별도 승인.)
  - (e) 목표 상태가 evidence로 특정되지 않음 — 예: "fluid가 뭔지 모호" → 중단. 이 레시피에서는 "data-ad-format=fluid + data-ad-layout=in-article + push div 밖"으로 특정됨 → 통과.
  - (d) R06 수정 후 R05/R11/R12 등 인접 규칙 상태 이상 변화 → 중단·보고
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: `/api/registry` R06 status = `pass` + 동일 블로그의 R05·R11·R12 무영향 확인.
- **비가역 플래그**: 없음(파일 내용 수정). 단, AdSense 슬롯 실제 동작은 외부 의존 → 라이브에서 blank 광고 발생 시 별도 조사.

#### R07 — single.html: H2 split injection + prose wrapper

- **정의**: single.html에 H2 분할 인젝션 로직과 prose wrapper(`<section class="... prose ...">`)가 없는 상태.
- **등급 결정트리**:
  - H2 split injection + prose wrapper 없음 → **A**(표준 패턴 추가)
  - 하나만 있고 하나만 없음 → **A**(없는 쪽 추가)
  - 둘 다 있음 → **pass**
- **수정 의도 (목표 상태)**: single.html의 본문 영역에서 H2마다 콘텐츠 분할이 일어나고, 본문이 prose 클래스가 붙은 section 래퍼로 감싸진 상태.
- **허용 범위 (경계)**:
  - ✅ single.html 내 본문 출력 부분의 구조(인젝션 로직 + 래퍼).
  - ❌ 콘텐츠, 다른 레이아웃, config.
- **사용자 결정지점**: 없음 (A).
- **STOP 조건**:
  - (a) single.html 외 파일 변경 → 중단
  - (b) 예상 1파일 변경인데 다수 템플릿이 영향받음 → 중단·보고
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: `/api/registry` R07 status = `pass`.
- **비가역 플래그**: 없음.

#### R08 — single.html: .Lead / .Description 제거

- **정의**: single.html에 `.Lead`/`.Description` 클래스 요소가 남아 있어 표준과 어긋난 상태(정보 없음-hot, senior-hugo 등).
- **등급 결정트리**:
  - .Lead/.Description 잔존 → **A**(해당 라인 제거)
  - 이미 제거됨 → **pass**
  - 어떤 요소가 lead인지 불명확 → **B**(단일 요소 식별 확인)
- **수정 의도 (목표 상태)**: single.html에서 `.Lead`/`.Description` 클래스 요소가 제거되어, 본문 첫 문단이 과대 표시되는 블로우피시 기본 동작이 비활성화된 상태.
- **허용 범위 (경계)**:
  - ✅ single.html 내 .Lead/.Description 관련 라인.
  - ❌ 콘텐츠, 다른 템플릿, 본문 출력 로직 전체.
- **사용자 결정지점**: 없음 (A).
- **STOP 조건**:
  - (a) single.html 외 파일 변경 → 중단
  - (e) "lead"가 어떤 요소인지 특정 안 됨 → 중단·보고 (이 레시피는 .Lead/.Description 클래스명으로 특정)
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: `/api/registry` R08 status = `pass`.
- **비가역 플래그**: 없음.

#### R09 — baseof.html: 커스텀 오버라이드 없음 (테마 기본값 사용)

- **정의**: baseof.html에 테마 기본값을 벗어나는 커스텀 오버라이드가 있는 상태.
- **등급 결정트리**:
  - 커스텀 baseof.html 존재(5줄 초과 등) → **A**(삭제, 테마 기본값 사용)
  - 커스텀 없음 → **pass**
  - 어떤 오버라이드가 필요한지/불 필요한지 판단 애매 → **B**(허용 범위 확인)
- **수정 의도 (목표 상태)**: `layouts/_default/baseof.html`이 없거나(삭제) 테마 기본값을 그대로 사용하는 상태. 불필요한 커스텀 오버라이드가 없음.
- **허용 범위 (경계)**:
  - ✅ layouts/_default/baseof.html (삭제 가능).
  - ❌ 다른 레이아웃, 파셜, 콘텐츠.
- **사용자 결정지점**: 어떤 baseof.html 오버라이드가 실제로 필요한지 판단 애매할 때 1회.
- **STOP 조건**:
  - (a) baseof.html 외 파일 변경 → 중단
  - (e) "불필요한 오버라이드" 범위가 애매 → 중단·보고
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: `/api/registry` R09 status = `pass`.
- **비가역 플래그**: 없음(삭제). 단, 삭제 후 실제 사이트에 필요한 오버라이드였으면 복원 필요 → 삭제 전 diff 기억.

#### R10 — custom.css: 미채움 공간 제거 + 다크모드 + min-height

- **정의**: `assets/css/custom.css`가 없거나, 있어도 미채움(unfilled) 공간 처리·다크모드·min-height 규칙이 누락된 상태.
- **등급 결정트리**:
  - custom.css 없음 → **A**(표준 custom.css 생성)
  - 있으나 미채움·다크모드·min-height 누락 → **A**(규칙 보완)
  - 이미 완비 → **pass**
- **수정 의도 (목표 상태)**: `assets/css/custom.css`가 존재하고, 미채움(unfilled) 요소 공간 제거, 다크모드 대응, 적절한 min-height 조절이 포함되어 있는 상태.
- **허용 범위 (경계)**:
  - ✅ `assets/css/custom.css` (신규 생성 또는 보완).
  - ❌ Hugo config, 테마 파일, 다른 CSS, 콘텐츠.
- **사용자 결정지점**: 없음 (A).
- **STOP 조건**:
  - (a) custom.css 외 파일 변경 → 중단
  - (b) CSS 생성이 여러 파일로 번짐 → 중단·보고 (1파일 생성 기대)
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: `/api/registry` R10 status = `pass`.
- **비가역 플래그**: 없음.

#### R11 — layouts/: mobile-sticky.html 사용 금지

- **정의**: `layouts/partials/adsense/mobile-sticky.html` 등 mobile-sticky 광고 파셜이 존재하는 상태(사용 금지 대상).
- **등급 결정트리**:
  - mobile-sticky.html 존재 → **A**(삭제)
  - 없음 → **pass**
- **수정 의도 (목표 상태)**: mobile-sticky 광고 파셜이 레이아웃에서 제거되어, 금지된 sticky 광고 패턴이 더이상 사용되지 않는 상태.
- **허용 범위 (경계)**:
  - ✅ `layouts/partials/adsense/mobile-sticky.html` (삭제).
  - ❌ 다른 광고 파셜, 콘텐츠, config.
- **사용자 결정지점**: 없음 (A).
- **STOP 조건**:
  - (a) mobile-sticky.html 외 파일 변경 → 중단
  - (f) 삭제 대신 비활성화만 하려는 시도가 범위를 넘는지 확인 (이 레시피는 삭제 지향; 다른 방식의 비활성화는 별도 검토)
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: `/api/registry` R11 status = `pass`.
- **비가역 플래그**: 없음(삭제). 단, 삭제 후 필요하면 재생성 가능.

#### R12 — layouts/: 허용 집합 벗어난 오버라이드 없음 (junk 정리 포함)

- **정의**: layouts/ 디렉터리에 허용된 집합을 벗어난 오버라이드 파일이 있거나, `.DS_Store`·`.bak`류 junk가 남아 있는 상태.
- **등급 결정트리**:
  - 허용 집합 벗어난 오버라이드 존재 + junk 있음 → **A**(초과 파일 삭제 + junk 정리)
  - 허용 여부 판단 애매(어느 게 필요한지 불명확) → **B**(사용자 확인 1회)
  - junk만 있음 → **A**(junk만 정리)
- **수정 의도 (목표 상태)**: layouts/ 디렉터리가 허용 집합 내의 오버라이드만 남기고, `.DS_Store`·`.bak`·`.bak2` 등 junk가 제거된 상태.
- **허용 범위 (경계)**:
  - ✅ 허용 집합 외 오버라이드 파일 삭제 + junk(.DS_Store, *.bak, *.bak2 등) 정리.
  - ❌ 허용 집합 내 파일, 콘텐츠, config. "무엇이 허용 집합인지"는 이 레시피가 정하지 않음 — 표준 compliance 체크(standard.py)의 허용 집합을 따름.
- **사용자 결정지점**: 특정 파일이 허용 집합인지 판단이 애매할 때 1회. (B.)
- **STOP 조건**:
  - (a) 허용 집합 내 파일이 diff에 포함됨 → 중단
  - (b) junk 정리가 여러 디렉터리로 번짐 → 중단·보고 (레시피는 layouts/ 내 junk만)
  - (e) "허용 집합" 기준 불명확 → 중단·보고 (이 경우 standard.py의 허용 목록을 먼저 확인)
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: `/api/registry` R12 status = `pass`.
- **비가역 플래그**: 없음(삭제). 단, 삭제 전 어떤 파일을 지웠는지 기록(복원 가능하게).

#### THUMBNAIL-01 — content/posts/*/index.md (featureimage): R2 호스팅 webp

- **정의**: 포스트의 frontmatter `featureimage`가 R2(pub-<hash>.r2.dev)에 호스팅된 webp가 아닌 URL로 설정된 상태.
- **등급 결정트리**:
  - featureimage가 이미 R2 webp URL → **pass**
  - 비R2 URL → **B**(원본 이미지가 R2에 존재하는지 확인)
    - 원본 R2 존재 → 해당 URL로 치환: **A**로 전환
    - 원본 R2 부재 → **B** 유지 (재업로드 필요, batch_thumbnails.py 또는 수동 업로드 판단)
- **수정 의도 (목표 상태)**: 포스트의 `featureimage`가 `pub-<hash>.r2.dev` 도메인의 webp URL을 가리키는 상태.
- **허용 범위 (경계)**:
  - ✅ 해당 포스트의 `content/posts/<slug>/index.md` frontmatter `featureimage` 필드.
  - ❌ 다른 포스트, layouts, config, 본문 이미지(R2-01 영역 — 이 레시피 범위 아님).
- **사용자 결정지점**: 원본 이미지가 R2에 이미 있는지 확인. 없으면 재업로드 여부·방법 판단 1회. (B.)
- **STOP 조건**:
  - (a) featureimage 외 필드/파일 변경 → 중단
  - (b) 1포스트 기대인데 여러 포스트가 한 번에 변경됨 → 중단·보고 (레시피는 포스트별 1건. 일괄이 필요하면 별도 승인.)
  - (f) featureimage를 R2 URL로 바꾸면서 원본 이미지를 삭제/덮어쓰는 행위 → 중단 (원본 보존이 전제)
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: `/api/registry` THUMBNAIL-01 status = `pass` + 해당 포스트 featureimage가 R2 webp URL인지 확인.
- **비가역 플래그**: 없음(URL 치환). 단, 원본 이미지 소실 시 재업로드가 필요해지면 작업 범위 확대 → 그때 B 유지.

#### R2-01 — content/posts/*/index.md (featureimage + 본문 이미지): 모든 이미지 URL R2 버킷

- **정의**: featureimage 및 본문 내 이미지 URL이 승인된 R2 버킷(pub-<hash>.r2.dev)이 아닌 외부 도메인으로 설정된 상태.
- **등급 결정트리**:
  - 모든 이미지 URL이 R2 → **pass**
  - 비R2 URL 존재 → **B**(원본 R2 존재 여부 확인)
    - 원본 R2 존재 → URL 치환만: **A**로 전환
    - 원본 R2 부재 → **B** 유지 (이미지 재업로드 필요)
  - featureimage만 위반이고 본문 이미지는 모두 R2 → 영향 범위 축소(A에 가까움)
  - 본문 이미지 다수가 비R2 → 규모 확인 후 B 유지, 일괄 치환 승인 필요 시 결정지점
- **수정 의도 (목표 상태)**: 포스트의 featureimage와 본문 내 모든 이미지 URL이 `pub-<hash>.r2.dev` 도메인을 가리키는 상태. 원본 이미지가 R2에 호스팅되어 있고, URL이 그 R2 주소로 치환된 상태.
- **허용 범위 (경계)**:
  - ✅ 해당 포스트의 `content/posts/<slug>/index.md` frontmatter `featureimage` + 본문 Markdown 내 이미지 URL(`![...](...)`).
  - ❌ 다른 포스트, layouts, config, 이미지 원본 파일(삭제/수정 금지 — URL만 치환).
- **사용자 결정지점**: 원본 이미지가 R2에 이미 호스팅돼 있는지 확인. 없으면 재업로드 여부·방법 판단 1회. (B.)
- **STOP 조건**:
  - (a) 해당 포스트 외 파일/포스트 변경 → 중단
  - (b) 예상 변경 건수(예: 7건)를 초과해 다수 포스트·이미지가 변경됨 → 중단·보고
  - (f) 이미지 원본을 삭제/변환/덮어쓰는 행위 → 중단 (URL 치환만 허용)
  - (e) "본문 이미지" 범위가 불명확(예: 어떤 마크업이 이미지인지 식별 곤란) → 중단·보고 (이 레시피는 `![...](url)`와 HTML `<img src=>`를 이미지로 본다; 그 외 애매하면 정지)
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: `/api/registry` R2-01 status = `pass` + 해당 포스트의 featureimage·본문 이미지 URL이 모두 R2 도메인인지 확인.
- **비가역 플래그**: 없음(URL 치환). 단, 원본 이미지가 실제로 R2에 없으면 재업로드가 수반되고, 그때는 작업 범위가 늘어나므로 B 유지.

### C.3 발행 오류 레시피 (select)

> 아래 recipe는 `/api/registry` errors 배열에서 status가 active한 문제idio에 적용한다. status가 `auto_handled`/`auto_skipped`/`logged`이면 현재 활성 fail이 아니므로, 레시피를 "대기" 상태로 두고 재발 시 적용한다. 각 레시피는 status별 사람 개입 필요 여부를 명시한다.

#### P02 — no_content (콘텐츠 생성 실패)

- **정의**: 파이프라인이 토픽을 시도했으나 article을 생성하지 못한 상태.
- **status별**:
  - `auto_handled` (현재): 에이전트가 자동으로 처리함. 추가 개입 불필요 — **D**(현재 상태 유지). 재발 시 아래 적용.
  - `fail`/미처리: **C** — 데이터 소스·토픽 보충 결정 필요. 에이전트가 단독 재개 불가.
- **수정 의도 (목표 상태)**: 파이프라인이 유효한 데이터·토픽으로 content를 생성해 발행하는 상태. 현재 active fail이면 "재시도 가능한 데이터/토픽이 확보된 상태".
- **허용 범위**: 파이프라인 코드·데이터 수집 설정 영역. 콘텐츠 자체 재작성 아님.
- **사용자 결정지점 (C)**: 어떤 데이터 소스·키워드·토픽을 보충할지 결정 1회. 에이전트 단독 불가.
- **STOP 조건**: (e) 목표 상태가 "데이터 보충"으로만 정의되고 구체적 소스·토픽이 없음 → 중단·보고.
- **검증**: 해당 블로그의 freshness·표준 compliance가 정상화되고, 발행이 succeeds.
- **비가역 플래그**: 없음.

#### P14 — keyword 소진 / 제품 멸망 (informational_keyword)

- **정의**: 키워드 소스로 쓸 데이터가 고갈되거나 제품이 멸망해 발행 불가 상태. 현재 `auto_skipped`.
- **status별**:
  - `auto_skipped` (현재): 자동 스킵 중. **D**(현재 상태 유지). 재발·정책 변경 시 아래.
  - 활성 fail: **C** — 키워드 소스 보충·콘텐츠 방향 결정 필요.
- **수정 의도 (목표 상태)**: 유효한 키워드·데이터 소스가 확보되어 파이프라인이 다시 콘텐츠를 생성할 수 있는 상태.
- **허용 범위**: 데이터 소스·키워드 설정 영역.
- **사용자 결정지점 (C)**: 키워드 소스를 어떻게 보충할지(새 소스 추가, 기존 소스 재수집, 콘텐츠 방향 전환 등) 결정 1회.
- **STOP 조건**: (e) "키워드 보충"이 구체적인 소스로 특정되지 않음 → 중단·보고.
- **검증**: 해당 블로그 발행 정상화가 확인됨.
- **비가역 플래그**: 없음.

#### P17 — 매일 소진 (일일 소진 한도)

- **정의**: 일일 발행 한도에 도달해 추가 발행이 막힌 상태. 현재 `auto_skipped`, quiet.
- **status별**:
  - `auto_skipped`/quiet (현재): **D** — 정책 유지로 충분. 변경 필요 시 아래.
  - 정책 변경 필요: **C** — 한도·스케줄 정책 결정.
- **수정 의도 (목표 상태)**: 일일 소진 정책이 의도와 맞게 설정되어 있고, 한도 도달 시 적절히 스킵되는 상태.
- **허용 범위**: 스케줄·설정 영역.
- **사용자 결정지점 (C)**: 일일 한도·스케줄을 how 조정할지 결정 1회. 현 상태 유지는 결정 불필요.
- **STOP 조건**: (e) "한도 조정"이 수치·정책으로 특정되지 않음 → 중단·보고.
- **검증**: 해당 블로그의 daily quota 동작이 의도와 같음.
- **비가역 플래그**: 없음.

#### P15 — 발행 후 검증 실패

- **정의**: 발행한 콘텐츠에 대해 사후 검증에서 실패가 발생한 상태. 현재 `logged`.
- **status별**:
  - `logged` (현재): 로그만 남음. 재발 시 조사. **C**(원인 조사 필요).
  - 원인 특정 후: **B** — 조치 방향이 정해지면 반자동.
  - 원인 불명: **C**.
- **수정 의도 (목표 상태)**: 발행 후 검증이 통과하고, 실패 원인이 해소된 상태.
- **허용 범위**: 콘텐츠·검증 로직 영역. 원인에 따라 다르다 — 레시피는 원인 특정 전에는 범위를 넓게 잡지 않음.
- **사용자 결정지점 (C)**: 원인 조사 범위·방식 결정 1회. (로그 확인 후 B로 강등 가능.)
- **STOP 조건**: (e) "검증 실패"가 어떤 검증 항목인지 특정 안 됨 → 중단·보고.
- **검증**: 동일 유형 검증 통과.
- **비가역 플래그**: 없음.

#### P01 — no_result (데이터 수집 성공 → 가드 차단 → None)

- **정의**: 데이터 수집은 성공했으나 가드(예: 시군구 중복 차단)로 결과를 못 낸 상태. 현재 `auto_skipped`.
- **status별**:
  - `auto_skipped` (현재): **D** — 자동 스킵 중. 가드 조정 또는 데이터 보충 필요 시 아래.
  - 활성: **C** — 가드 조정 vs 데이터 소스 보충 결정 필요.
- **수정 의도 (목표 상태)**: 파이프라인이 유효 결과를 낼 수 있는 상태. 가드 기간을 조정하거나 데이터 소스를 보강해 발행 가능한 결과가 나오는 상태.
- **허용 범위**: 파이프라인 가드 로직·데이터 수집 설정.
- **사용자 결정지점 (C)**: 가드 조정(예: 룩백 기간 단축)인지 데이터 소스 보충인지 결정 1회. 에이전트 단독 결정 불가.
- **STOP 조건**: (e) "가드 완화/데이터 보충" 중 무엇이 필요한지 특정 안 됨 → 중단·보고.
- **검증**: 해당 블로그 발행 성공 + no_result 재발 없음.
- **비가역 플래그**: 없음. 단, 가드 로직 변경은 다른 블로그 영향 가능 → 범위 확인.

#### P06 — broken_featureimage (썸네일 404)

- **정의**: featureimage가 존재하지 않는 URL을 가리켜 썸네일이 깨지는 상태. 현재 error 등록돼 있으나 active fail 여부는 체크리스트에서 확인.
- **등급 결정트리**:
  - 썸네일 R2 존재 → **A**(batch_thumbnails.py 실행 → R2 업로드 → frontmatter 수정)
  - 원본 이미지 소실 → **B**(재업로드 판단 필요)
  - featureimage가 WordPress 전용 도메인 경로 등 구조적 문제 → **B/C**(경로 정책 확인)
- **수정 의도 (목표 상태)**: featureimage가 실제로 존재하는 R2 이미지 URL을 가리키고, 브라우저에서 200이 나오는 상태.
- **허용 범위**: 해당 포스트 frontmatter featureimage + (필요 시) 썸네일 재생성·R2 업로드.
- **사용자 결정지점 (B)**: 원본 이미지가 존재하는지, 재업로드가 필요한지 확인 1회.
- **STOP 조건**:
  - (a) featureimage 외 변경 → 중단
  - (f) 원본 이미지 삭제/변형 → 중단
  - (e) 썸네일이 왜 깨졌는지(URL 오류·R2 부재·경로 정책) 특정 안 됨 → 중단·보고
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: `/api/registry` THUMBNAIL-01·R2-01 관련 상태 + featureimage URL HTTP 200 확인.
- **비가역 플래그**: 없음(원본 보존 전제).

#### P10 — title_blocked (제목 패턴 차단)

- **정의**: 제목이 특정 패턴(예: 블로그/템플릿 패턴 차단)에 걸려 발행이 막힌 상태. 현재 `auto_skipped`.
- **status별**:
  - `auto_skipped` (현재): **D** — 자동 스킵 중. 패턴 조정 필요 시 아래.
  - 활성: **B** — 제목 패턴을 어떻게 조정할지 결정.
  - 패턴 차단 정책 자체의 변경이 필요하면 **C**.
- **수정 의도 (목표 상태)**: 제목이 차단 패턴에 걸리지 않으면서도 콘텐츠 의도를 유지하는 상태로 발행될 수 있는 상태.
- **허용 범위**: 제목 생성·차단 패턴 설정.
- **사용자 결정지점 (B/C)**: 차단 패턴을 어떻게 조정할지(패턴 완화, 제목 변형 다양화, 차단 유지 등) 결정 1회.
- **STOP 조건**: (e) "차단 패턴 조정"이 어떤 패턴을 how 바꾸는지 특정 안 됨 → 중단·보고.
- **검증**: 해당 블로그 발행 정상화 + 유사 제목 차단 재발 없음.
- **비가역 플래그**: 없음.

#### P18 — 동시 실행 방지 (하루 동시 실행)

- **정의**: 같은 날 같은 파이프라인이 중복 실행되는 것을 방지하는 로직 관련. 현재 `auto_skipped`, quiet.
- **status별**:
  - `auto_skipped`/quiet (현재): **D** — 유지. lock 강화 필요 시 아래.
  - lock 강화 필요: **B** — lock 방식을 어떻게 개선할지.
- **수정 의도 (목표 상태)**: 중복 실행이 방지되고, 필요 시에는 정상 실행되는 상태.
- **허용 범위**: 스케줄·lock 설정.
- **사용자 결정지점 (B)**: lock 방식 개선 필요 시 결정 1회. 현 상태 유지는 결정 불필요.
- **STOP 조건**: (e) "lock 강화"가 구체적 방식으로 특정 안 됨 → 중단·보고.
- **검증**: 중복 실행 방지 동작 확인.
- **비가역 플래그**: 없음.

#### leak_detected (프롬프트 릭 / CoT 누출)

- **정의**: 생성된 콘텐츠에 프롬프트 지시문·시스텀 메시지·CoT(추론) 내용 등 누출이 탐지된 상태.
- **등급 결정트리**:
  - 누출 특정 가능(어떤 프롬프트/마커가 누출) → **B**(재현 경로 확인 후 재발 방지 조치)
  - 누출 경로는 보이나 재발 방지 방법이 불명 → **C**(재Diagnosis)
  - 누출 의심만 있고 특정 안 됨 → **C**
- **수정 의도 (목표 상태)**: 생성된 콘텐츠에 프롬프트 지시문·CoT 등 내부 정보가 포함되지 않고, 재발 방지 조치가 적용된 상태.
- **허용 범위**: 프롬프트·발행 전 검증·콘텐츠 검사 영역. 콘텐츠 자체를 임의로 수정하지 말 것(누출 제거는 재발 방지 중심).
- **사용자 결정지점 (C)**: 재현 경로가 모호할 때 조사 범위 결정 1회.
- **STOP 조건**:
  - (e) "누출"이 어떤 내용인지 특정 안 됨 → 중단·보고
  - (a) 허용 범위(프롬프트·검사)를 벗어나 콘텐츠 본문을 임의 수정 → 중단
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: leak 스캔 통과 + 동일 유형 재발 없음.
- **비가역 플래그**: 없음. 단, 프롬프트 변경은 글쓰기 품질에 영향 → 변경 전 확인.

#### known_issue (등록된 known problem)

- **정의**: 대시보드에 known issue로 등록된 문제(STRUCT/QA 계열 등).
- **등급 결정트리**:
  - 재현 경로·해결책 명확 → **B**(조치 가능)
  - 불명 → **C**(Investigation 필요)
  - 백로그 이연 결정됨 → **D**
- **수정 의도 (목표 상태)**: 해당 known issue가 해소되거나, 해소 계획이 명시적으로 백로그에 등록되고 이연 사유가 기록된 상태.
- **허용 범위**: 이슈 유형별 다름 — 레시피는 이슈별 허용 범위를 개별 정의하지 않음. 해당 이슈의 evidence·action을 따른다.
- **사용자 결정지점**: 이슈별 다름. 불명 → **C**로 보고하고 사람이 조사 범위를 정함.
- **STOP 조건**:
  - (e) known issue의 목표 상태가 불명확 → 중단·보고
  - (a) 허용 범위를 벗어난 조치 → 중단
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: `/api/attention`·`/api/registry`에서 해당 issue/status 변화 확인.
- **비가역 플래그**: 이슈별 다름 — STRUCT-11/12/13 등 DB 관련은 C.4로.

#### dead_entity_link (끊긴 엔티티 링크)

- **정의**: 크로스블로그 엔티티 링크 중 404/끊긴 링크가 있는 상태.
- **등급 결정트리**:
  - 끊긴 링크 특정 가능 → **B**(교체/제거 결정)
  - 엔티티 재등록 필요 → **C**
  - 어떤 링크가 끊겼는지 탐지 불가 → **C**
- **수정 의도 (목표 상태)**: 크로스블로그 엔티티 링크가 유효한 대상(존재·접근 가능)을 가리키고, 끊긴 링크가 교체/제거된 상태.
- **허용 범위**: 엔티티 링크 정의·타겟 URL. 콘텐츠 본문 자체는 이 레시피의 직접 범위 아님(연결된 엔티티의 존재 여부가 문제).
- **사용자 결정지점 (B/C)**: 끊긴 링크를 어떻게 처리할지(교체/제거/엔티티 재등록) 결정 1회.
- **STOP 조건**:
  - (e) "끊긴 링크" 범위가 특정 안 됨 → 중단·보고
  - (a) 허용 범위(엔티티 링크)를 벗어나 콘텐츠 본문 임의 수정 → 중단
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증**: 엔티티 링크 검사 통과 + 404 없음.
- **비가역 플래그**: 없음(링크 교체/제거). 단, 엔티티 재등록은 콘텐츠·DB 변경 수반 가능 → 그때 별도 검토.

### C.4 🔴 비가역군 — 자동 금지 (별도 웨이브·명시 승인 필수)

아래 항목은 에이전트가 레시피를 읽더라도 **자동으로 실행하지 않는다.** 아무리 목표 상태가 명확해도, 아래 플래그가 붙은 항목은 별도의 웨이브 승인과 명시적 롤백 계획 없이는 진행하지 않는다.

| 항목 | 사유 | 필수 선행 조건 |
|------|------|---------------|
| **STRUCT-11** (idx_ledger_dedup non-unique → schema migration) | DB 인덱스 DROP+CREATE UNIQUE, 대량 INSERT OR IGNORE 영향 | 콘텐츠 DB 백업 + 롤백 태그 + 스케줄러 정지 확인 + 삭제 예정/영향 카운트 보고 + 사용자 승인 |
| **STRUCT-12** (source='' 중복 2,935건 삭제) | 실발행 행 보존 여부 등 데이터 정책 결정 필요, 대량 DELETE | 백업 + 보존 범위 결정 + 사용자 승인 |
| **STRUCT-13** (backfill_blank_titles 966건 title 덮어씀) | 발행된 title을 원본 제목으로 덮어쓴 오염 복구 — 범위·기준 결정 필요 | 백업 + 복원 범위·기준 결정 + 사용자 승인 |
| **테마 마이그레이션** (STRUCT-03 hotissue-hugo PaperMod→Blowfish / STRUCT-04 stock-hugo Congo→?) | 테마 변경은 레이아웃 전면 재작업, 대규모 변경 | 별도 웨이브 승인 + 영향 블로그 리스트 + 롤백 계획 |
| **index.html 렌더링 의존 검증** | 외부 HTTP/렌더링 결과에 의존하는 검증은 에이전트 단독 완결 불가 | 외부 상태 확인 수단 확보 또는 수동 검증 |
| **콘텐츠 재생성으로 라이브 글 덮어쓰기** | 라이브 발행 글을 파이프라인이 재작성·덮어쓰는 작업 | 별도 웨이브 승인 + 덮어쓰기 범위·대상 명시 + 롤백 계획 |
| **DB 대량 INSERT (run_sync류, 소스 전체 재삽입)** | 이미 발생한 STRUCT-11 류의 재발 가능 | 백업 + 영향 카운트 + 스케줄러 정지 + 사용자 승인 |

> 공통 규칙: 비가역군이 "해체"되려면, 해당 항목을 담당하는 별도 웨이브에서 (1) 사전 카운트/영향 범위 출력, (2) 백업/롤백 수단 확보, (3) 사용자 승인, (4) 사후 대조를 모두 거친 뒤에야 실행 가능하다. 이 레시피북의 그 어떤 A/B 등급 레시피도 위 항목을 우회하지 않는다.

### C.4.1 재검사 트리거 — 수동 갱신 전제 (공통)

> 2026-08-08 추가. 대시보드에 자동 재검사 스케줄이 없어, FIX·배포 후 화면이 갱신되려면 반드시 수동 호출이 필요하다.

- **대시보드 상태**: 현재 Ops 대시보드(`http://localhost:5060`)에는 자동 재검사 스케줄이 없다. 코드 수정·배포 후 `/api/registry`·`/api/attention`·블로그 상세 페이지의 check_results는 **자동으로 갱신되지 않는다.**
- **필수 수동 호출**:
  - 개별 블로그 FIX 후: `POST /api/run-checks?blog_id={blog_id}` — curl 또는 HTTP 클라이언트. 반환 직후 check_results 갱신.
  - 정비 체크리스트(M01~M10) FIX 후: `POST /api/maintenance/checklist` + JSON body `{"blog_id":"{blog_id}"}`.
  - 전체 재검사: `POST /api/run-checks` (blog_id 없이).
- **경고**: 이 호출 없이는 FAIL→PASS를 확인할 수 없다. "배포했으니 잠시 후 화면이 갱신되길 기다린다"는 계획은 STOP 조건 (e)에 해당. 에이전트는 재검사를 명시적으로 직접 호출해야 하고, 호출 전까지 화면 상태를 "확정된 것"으로 취급하지 않는다.
- **UI 부재**: 현재 Ops 대시보드 화면에는 위 세 API를 트리거하는 버튼·폼·JS가 없다. "마스터 갱신 버튼"은 존재하지 않음 — curl로만 호출 가능. UI 버튼 추가는 별도 작업(추가 지점: `ops_dashboard/templates/index.html`에 전체 재검사 폼, `blog.html`에 개별 재검사·정비용 fetch JS 버튼).
- **재검사 트리거 후 검증**: 호출 직후 `/api/registry`에서 해당 rule_id status가 `"fail"` → `"pass"` 또는 `"unknown"`으로 전환됐는지 확인. FAIL→PASS 확인 없이 완료 보고 금지.

### C.5 매뉴얼 시뮬레이션 증명 (문서화 목적, 실제 수정 없음)

> 아래 2건은 이 Appendix C를 완성한 뒤, 레시피만 읽고 "실제 수정 없이" 계획 생성→STOP 대조까지 수행한 기록이다. 실행 에이전트가 블로그 구조를 읽고 생성할 계획이, 이 레시피의 경계 안에서 안전하게 나오는지와, 애매한 지점에서 제대로 멈추는지를 확인한다.

#### 시뮬레이션 1 — R06, pet-hugo (active fail 1건)

- **레시피**: C.2 R06
- **입력 evidence(실제)**: `"in-article.html: missing fluid format, missing in-article format, data-ad-format=auto (prohibited)"`
- **등급 판정**: 
  - 기본등급 B (deferred). 
  - 조건부 분기 평가: "auto→fluid 교체만으로 충분, 슬롯 정책 이슈 없음"인지 불명 → B 유지. 
  - 이유: data-ad-format=auto가 문제인 것은 특정되나, AdSense 계정에서 해당 슬롯이 fluid/in-article을 허용하는지, 기존 auto 슬롯을 유지할지 삭제할지 확인이 필요할 수 있음. 레시피는 "일괄 처리 전 승인 1회"를 요구.
  - → 등급: **B**. 사용자 결정지점 1개: "pet-hugo 포함 19개 블로그 in-article.html을 일괄 fluid로 교체 진행 승인?"
- **목표 상태 서술**: pet-hugo의 `layouts/partials/adsense/in-article.html`에서 `data-ad-format="auto"`가 제거되고 `data-ad-format="fluid"` + `data-ad-layout="in-article"`이 설정되며, `<script>push({})</script>`가 `<ins>` 태그 바깥에 위치하는 상태.
- **예상 변경 계획 (블로그 구조 읽은 뒤 생성)**:
  1. 대상 파일: `pet-hugo/layouts/partials/adsense/in-article.html` (1파일)
  2. 변경:
     - `data-ad-format="auto"` → `data-ad-format="fluid"` 및 `data-ad-layout="in-article"` 추가
     - `<script>push({})</script>`가 `<ins ...>...</ins>` 내부에 있으면 외부로 이동
  3. 예상 규모: 1파일, 소폭 수정(속성 교체 + 요소 위치 이동)
- **STOP 조건 대조**:
  - (a) 허용 범위[in-article.html만] 준수? 예 — 1파일만. 통과.
  - (b) 예상 규모(1파일) 초과? 아니오 — 1파일 기대, 1파일 계획. 통과.
  - (c) 빌드 에러? 계획 단계에선 미확정 — 게이트에서 Hugo 빌드 0에러로 확인 예정. 계획 자체론 STOP 아님.
  - (d) /api/registry 총량·분포 이상 변화? R06만 fail→pass 예상, 인접 R05·R11·R12 무영향 예상. 통과(예상으로는).
  - (e) 목표 상태가 evidence로 명확? 예 — "missing fluid, missing in-article, data-ad-format=auto" 3가지가 evidence로 특정되며, 목표 상태(fluid+in-article+push 밖)가 그 부정형을 해소함. 통과.
  - (f) 비가역 작업? 아니오 — 파일 내용 수정, 삭제 아님. 통과.
- **결과**: STOP 조건 걸리지 않음. **계획 안전.** 단, B등급이므로 실행 전 사용자 승인 1회 필요. 승인 있으면 게이트(백업→빌드→배포→재검증)로 진행.

#### 시뮬레이션 2 — R2-01, techpawz-hugo (active fail, 7건)

- **레시피**: C.2 R2-01
- **입력 evidence(실제)**: `"R2 패턴 위반 7건 / 검사 7건: 킹스데일cc-20260808-s3/featureimage: https://img.techpawz.com/...; ... (R2 아님) 외 4건"` — featureimage 3건 + 본문 이미지 4건이 비R2.
- **등급 판정**:
  - 기본등급 B.
  - 조건부 분기 평가: 
    - "모든 이미지 URL이 R2" 아님 → fail 상태.
    - "원본 R2 존재 여부" 미확인 → B 유지. 
    - featureimage만 위반 아님(본문 이미지도 4건) → 영향 범위 확대. 일괄 치환 필요 시 결정지점.
  - 이유: URL만 보고는 원본이 R2에 업로드돼 있는지 알 수 없음. evidence상 img.techpawz.com 도메인이므로 현재 R2 아님. R2에 재업로드 필요 가능성 있음 → B.
  - → 등급: **B**. 사용자 결정지점 1개: "7건 이미지(킹스데일cc·코스터cc·bmw모델·기타)의 원본이 R2에 이미 존재하는가? 없으면 재업로드 필요한가?"
- **목표 상태 서술**: techpawz-hugo의 해당 포스트(킹스데일cc-20260808-s3, 코스터cc-..., bmw모델-..., 기타)들의 featureimage와 본문 이미지 URL이 `pub-<hash>.r2.dev` 도메인의 webp URL로 치환된 상태. 원본 이미지는 보존됨(삭제·변형 없음).
- **예상 변경 계획 (블로그 구조 읽은 뒤 생성)**:
  1. 대상 포스트들: 해당 7건의 featureimage가 걸린 포스트 각각의 `content/posts/<slug>/index.md` + 해당 포스트 본문 Markdown (이미지 URL 7건).
  2. 변경:
     - 각 포스트 frontmatter `featureimage`를 R2 URL로 치환 (R2에 원본이 존재한다고 가정 시).
     - 본문 내 `![...](img.techpawz.com/...)` / `<img src="img.techpawz.com/...">`도 R2 URL로 치환.
  3. 예상 규모: 포스트 수 N개, 이미지 URL 7건 치환. (정확한 포스트 수·이미지 위치는 블로그 구조 확인 시 결정.)
  4. 전제조건: R2에 원본 이미지가 존재. 없으면 재업로드(batch_thumbnails.py 등)가 선행되어야 함 → 이건 이 계획의 전제, 충족되지 않으면 계획 중단·보고.
- **STOP 조건 대조**:
  - (a) 허용 범위[해당 포스트의 featureimage + 본문 이미지 URL만] 준수? 예 — 다른 포스트·레이아웃·config 건드리지 않음. 통과.
  - (b) 예상 규모 초과? evidence상 7건 특정됨. 계획은 7건 치환 지향. 실제 블로그 구조에서 7건이 맞는지 확인 필요 — 맞으면 통과, 초과면 중단·보고.
  - (c) 빌드 에러? URL 문자열 치환이므로 Hugo 빌드 에러 가능성 낮음 — 게이트에서 확인. 계획 자체론 STOP 아님.
  - (d) /api/registry 총량·분포 이상 변화? R2-01 fail→pass 예상, THUMBNAIL-01도 연관돼 동반 통과 가능. 인접 R06 등 무영향 예상. 통과(예상으로는).
  - (e) 목표 상태가 evidence로 명확? 예 — "7건 이미지가 비R2" + 목표는 "모두 R2". 통과. 단, "본문 이미지" 범위가 특정되는지는 블로그 구조에서 확인 — `![...](...)`·`<img src>`로 한정하며, 그 외 애매하면 정지.
  - (f) 비가역 작업? 아니오 — URL 치환, 원본 보존 전제. 통과. 단, 원본 이미지를 삭제/변환하는 행위가 계획에 섞이면 즉시 STOP.
- **전제조건 실패 시 STOP**: R2에 원본 이미지가 없으면, 이 계획은 "URL 치환"만으로 목표 상태에 도달할 수 없음. 이때는 계획을 중단하고 사용자에게 보고: "7건 중 N건의 원본이 R2에 없음 — 재업로드 필요. 재업로드 진행 승인?" 이 지점에서 멈춘다.
- **결과**: 원본 R2 존재가 확인되면 STOP 없이 진행 가능(규모·범위 재확인 조건). 확인되지 않으면 B 유지, 사용자에게 원본 존재 여부 결정 1회 요청. 계획은 레시피 경계 안에서 생성되며, 애매한 지점(전제조건 불충족)에서 제대로 멈춘다.

---

### C.6 콘텐츠 무결성 검사(C01~C09) 및 정비 체크리스트 레시피

> 추가일: 2026-08-09 | 상태: 활성 | 출처: `ops_dashboard/checks/content_integrity.py`, `ops_dashboard/checks/maintenance.py` 판정 로직 확인 기반.
> 적용 우선순위: c06_mtime_deploy(22건) > c05_draft_publish(14건) > maintenance_checklist M01~M11(7건).
> 나머지 C-계열(gsd_crosscheck, freshness)은 판정 로직 확인·분류만 수록하고 레시피 초안은 선택(🔽 참고). c03_fm_key_leak·c04_prompt_leak은 위 C.6에 정식 등재됨.

#### C06 — 로컬 파일 수정 시각 검사 (c06_mtime_deploy) — INFO 등급 (참고용)

- **정의**: 최근 1일(24시간) 이내 수정된 포스트 파일이 존재하면 checker는 fail(현재 코드 기준)을 반환한다. check_name은 "c06_mtime_deploy"이나, 현재 구현(`_check_c06`, `ops_dashboard/checks/content_integrity.py:152-160`)은 배포 시각과의 비교가 아니라 파일 mtime이 1일 이내인지 여부만 판정한다.
- **INFO 등급 확정**: 현재 c06은 fail/위반이 아니라 참고용 INFO 신호로만 취급한다. `_check_c06()`이 반환하는 "C06 경고" 문자열 자체가 "위반"보다 약한 표현이며, 최근 수정은 대부분 정상 작업(이미지 교체, frontmatter 수정, 콘텐츠 보강 등)의 흔적이다. "배포 시각 vs mtime" 비교가 아니라 "최근 24시간 내 수정" 여부만 보기 때문에, deploy 후 파일이 변조됐는지 감지하는 체크가 아니다.
- **fail 판정 근거 (evidence)**:
  - `_check_c06()`: 파일 mtime이 1일 이내면 `False, f"C06 경고: 최근 수정 ({mtime.strftime('%Y-%m-%d')})"` 반환.
  - check_c06 전체 결과: `"C06 경고 N건: C06 경고: 최근 수정 (YYYY-MM-DD); ..."` (`ops_dashboard/checks/content_integrity.py:360-361`).
  - **"C06 경고" 문자열 사용** — "위반"보다 약한 표현으로, 경고 수준임을 시사.
- **등급**: **INFO (참고용)** — fail로 취급하지 않으며, 등급 계산·주의필요(fail_checks) 표에서 제외 대상. 가장 얕은 신호.
- **조치 방침**: 기본적으로 조치 불필요. 최근 수정은 대부분 정상 작업의 흔적이다. 예외로, "수정됐을 리 없는 파일"(예: 배포 직후 단시간 내 대형 포스트가 mtime 갱신됨, 또는 정상 파이프라인 외부에서 Touch된 파일)이 c06에 뜨면 그때만 변조 여부를 읽기전용으로 조사하고, **자동 수정 금지**. 실제 변조가 확인돼도 자동 삭제·원복하지 않고 보고 후 사람 판단.
- **조치 대상 파일**: 해당 블로그의 `content/posts/<slug>/index.md` (최근 7일 내 포스트 중 mtime 1일 이내인 파일) — 단, INFO 등급이므로 "fail 대응 대상"이 아니라 "참고 확인 대상".
- **STOP 조건**:
  - 코드·DB·블로그 파일 수정, 재배포, 체크 로직 변경을 수반하는 계획은 즉시 중단·보고 (이번 작업은 AGENTS.md 문서 편집으로 한정).
  - "수정됐을 리 없는 파일"이 c06에 뜬 경우 → 읽기전용 조사(mtime 비교, 어떤 프로세스가 Touch했는지, git diff 등)까지만. 변조 확인돼도 자동 원복 금지.
  - **(e) 재검사 트리거 호출이나 대시보드 반영(코드 변경)을 하려는 계획** → 중단. 이번 작업은 AGENTS.md 문서 편집으로 한정, 대시보드 표시 로직 변경은 별도 웨이브에서.
- **비가역 플래그**: 없음 (INFO 등급, 자동 조치 없음). 단, 추후 "무시/참고 처리"를 체크 로직 수준에서 구현하려면 그 자체는 별도 코드 변경으로, 이번 범위 밖.
- **대시보드 표시에 대한 메모 (TODO, 이번엔 구현 안 함)**:
  - c06은 fail이 아닌 INFO/참고 버킷으로 표시하는 것이 바람직하며, 등급 계산·주의필요(fail_checks) 표에서 제외 대상.
  - 별도 웨이브에서 대시보드 반영 예정: `ops_dashboard/checks/content_integrity.py`의 `_check_c06` 반환값을 pass/info로 조정하거나, c06을 fail_checks가 아닌 별도 참고 통계로 분리. (TODO — 이번 세션 미시행)

#### C05 — draft:true 발행 감지 (c05_draft_publish)

- **정의**: 발행된 포스트의 frontmatter에 `draft: true`(대소문자 무관)가 남아 있는 상태. draft:true 포스트는 발행 대상에서 제외되어야 하나 실제 발행된 경우 감지.
- **fail 판정 근거 (evidence)**:
  - `_check_c05()` (`ops_dashboard/checks/content_integrity.py:145-149`): `fm.get("draft", "").lower() == "true"` → `False, "C05 위반: draft:true 발행 대상"`.
  - check_c05 전체 결과: `"C05 위반 N건: <slug>: C05 위반: draft:true 발행 대상; ..."` (`ops_dashboard/checks/content_integrity.py:337-338`).
- **조치 대상 파일**: 해당 블로그의 `content/posts/<slug>/index.md` (draft:true가 적발된 포스트 각각의 frontmatter)
- **조치 내용**:
  - frontmatter의 `draft: true`를 `draft: false`로 변경(또는 `draft: true` 라인 제거).
  - 주의: 이미 발행된 포스트의 frontmatter 수정이므로 수정 후 재배포 필요.
  - draft:true를 그대로 두는 것은 정책 위반 상태이므로 방치 불가.
  - **P09 false positive 수정(2026-08-09, BUG-P09-001)과의 관계**: 무관. P09 수정은 `detect_post_generate`가 본문 전체가 아닌 개별 이미지 URL만 검사하도록 변경한 것(`shared/problem_detectors.py`); c05는 frontmatter draft 플래그 검사로 서로 독립적.
- **등급 결정트리**:
  - draft:true 삭제 + 재배포 → **B**(파일 수정 + 재배포, 판단 1회)
- **사용자 결정지점**: 없음 (B등급이나 조치는 명확 — draft:true 제거 + 재배포).
- **STOP 조건**:
  - (a) 조치 범위가 해당 포스트의 draft 필드 변경으로만 한정되는지 확인. 다른 필드·다른 포스트까지 번지면 중단.
  - (f) 조치 과정에서 원본 콘텐츠 본문이 삭제/변형되지 않도록 주의 (frontmatter만 수정).
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증 방법**: 조치 후 `POST /api/run-checks?blog_id={blog_id}` → c05_draft_publish status가 pass로 전환 확인.
- **비가역 플래그**: 없음 (draft 플래그 변경 + 재배포, 본문 보존 전제).

#### C03 — 프론트매터 키 본문 유출 (c03_fm_key_leak)

- **정의**: 포스트 본문(프론트매터 이후)에 프론트매터 키 형식의 라인(title:, og_image:, featureimage:, date:, slug:, categories:, tags:, description:, draft:, image:, pubDate:, author: 등)이 노출되어 있는 상태. 프론트매터 영역이 아닌 본문에 이런 라인이 있으면 파싱 오류나 표시 문제의 원인이 될 수 있음.
- **fail 판정 근거 (evidence)**:
  - `_check_c03()` (`ops_dashboard/checks/content_integrity.py:123-129`): 본문에 `^\s*(FM_KEYS):\s*` 정규식이 매치되는 라인이 있으면 fail. FM_KEYS = ["title", "og_image", "featureimage", "date", "slug", "categories", "tags", "description", "draft", "image", "pubDate", "author"].
  - fail 증거: `"C03 위반: N건 — leaked_line"` (예: `"C03 위반: 2건 — title: 서울 맛집 top5"`).
  - check_c03 전체 결과: `"C03 위반 {len(violations)}건: {slug}: {detail}; ..."` (`ops_dashboard/checks/content_integrity.py:285-287`).
- **조치 대상 파일**: 해당 블로그의 `content/posts/<slug>/index.md` (본문 내 앞머터 키 라인 노출이 적발된 포스트)
- **조치 내용**:
  - 본문에서 앞머터 키 형식의 라인 제거. 대부분 다음과 같은 원인:
    - LLM이 본문 첫 부분에 프론트매터 복사본을 실수로 생성
    - 앞머터에 넣어야 할 필드를 본문에 적어넣음
    - 이미지 URL이나 제목이 본문 상단에 중복 기재됨
  - 제거 시 본문 내용(실제 글 텍스트)은 보존하고, 키가 노출된 라인만 삭제.
  - 제거 후 재배포 필요 (Hugo 빌드 시 frontmatter 이후 본문 출력).
- **등급**: **B** — 본문에서 노출 라인 제거 + 재배포. 어느 라인이 키 노출인지 개별 확인 1회 필요하나 조치는 명확.
- **사용자 결정지점**: 없음 (B등급이나 조치는 명확 — 노출 라인 제거 + 재배포). 단, 제거 대상 라인이 본문 내용인지 앞머터 키 유출인지 애매하면 판단 1회.
- **STOP 조건**:
  - (a) 조치 범위가 해당 포스트의 본문 내 키 노출 라인 제거로 한정되는지 확인. 다른 포스트·다른 필드까지 번지면 중단.
  - (f) 조치 과정에서 원본 콘텐츠 본문이 삭제/변형되지 않도록 주의 (키 노출 라인만 제거).
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증 방법**: 조치 후 `POST /api/run-checks?blog_id={blog_id}` → c03_fm_key_leak status가 pass로 전환 확인.
- **비가역 플래그**: 없음 (본문 중 키 노출 라인 제거, 본문 내용 보존 전제). 단, 제거 대상이 실제 본문 내용인데 키 노출로 오판한 경우 복원 필요 → 제거 전 해당 라인 보존(복사) 권고.

#### C04 — LLM 프롬프트/사고문 누수 (c04_prompt_leak)

- **정의**: 포스트 본문에 LLM 프롬프트 지시문·사고Chain-of-Thought 마커·시스템 메시지 등 내부 정보가 국문·영문 패턴으로 포함된 상태. 예: "생각해보자", "다음 단계로 넘어", "We need to write", "Let's think step by step" 등.
- **fail 판정 근거 (evidence)**:
  - `_check_c04()` (`ops_dashboard/checks/content_integrity.py:132-142`): C04_KO_PATTERNS + C04_EN_PATTERNS 목록으로 본문 검사. 매치되면 fail.
  - C04_KO_PATTERNS (10개): `생각해보자`, `생각해 보자`, `다음 단계로 넘어`, `단계별로 진행해`, `우선, 우리가 해야`, `우리가 해야 할 것은`, `생각 과정을 통해`, `결론부터 말하면`, `먼저 생각해보자`, `단계별로 생각`.
  - C04_EN_PATTERNS (8개): `Need to think`, `We need to write`, `Let's think step by step`, `think step by step`, `let's break this down`, `here's the plan`, `in order to achieve`, `as an AI language model`. (2026-08-12: firstly/secondly는 오탐 이력으로 제거 — `\bfirstly,?\s+`와 `\b secondly,?\s+`의 `\b` 뒤 공백 오타로 인해 " secondly,"만 잡고 "secondly," 단독은 못 잡는 문제 + 실발행 글에 이 패턴이 실제와 무관하게 검출되는 오탐 빈발)
  - fail 증거: `"C04 위반: 프롬프트 누수 N건 — matched_text"` (예: `"C04 위반: 프롬프트 누수 1건 — 생각해보자"`).
  - check_c04 전체 결과: `"C04 위반 {len(violations)}건: {slug}: {detail}; ..."` (`ops_dashboard/checks/content_integrity.py:302-304`).
  - **leak_detected(C.3)와의 관계**: C04는 "프롬프트/사고문 누수"라는 문제 유형에서 C.3의 leak_detected와 동일 계열. C.3 leak_detected 레시피의 "수정 의도·허용 범위"를 공유한다. C04는 dashboard에서 별도 check_name으로 감지되는 구체적 검사.
- **조치 대상 파일**: 해당 블로그의 `content/posts/<slug>/index.md` (본문 내 누수 패턴 적발 포스트)
- **조치 내용**:
  - 본문에서 누수 패턴 제거 (누수 라인/문장 삭제 또는 자연어로 재작성).
  - 주의: 누수 제거는 재발 방지 중심. 프롬프트·방지 로직도 함께 점검 필요.
  - 누수 패턴 제거 후 재배포 필요.
  - **C.3 leak_detected 레시피 참조**: 허용 범위·비가역 플래그 등 공통 원칙은 C.3 leak_detected 레시피를 따른다. 여기선 check_name별 구체적 판정 로직만 추가 기술.
- **등급**: **B** — 본문 누수 패턴 제거 + 재배포 + 프롬프트 점검. 어느 패턴이 누수인지 개별 확인 필요하나 조치는 명확.
- **사용자 결정지점**: 없음 (B등급이나 조치는 명확 — 누수 패턴 제거 + 재배포 + 프롬프트 점검). 단, 누수 패턴이 프롬프트 지시문인지 실제 콘텐츠인지 불명하면 판단 1회.
- **STOP 조건**:
  - (a) 조치 범위가 해당 포스트의 본문 내 누수 패턴 제거로 한정되는지 확인. 다른 포스트·다른 영역까지 번지면 중단.
  - (a) 허용 범위(프롬프트·검사)를 벗어나 콘텐츠 본문을 임의 수정 → 중단. 누수 제거만 허용.
  - (e) "누출"이 어떤 내용인지 특정 안 됨 → 중단·보고.
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 수정·배포 후 반드시 `POST /api/run-checks?blog_id={blog_id}` 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증 방법**: 조치 후 `POST /api/run-checks?blog_id={blog_id}` → c04_prompt_leak status가 pass로 전환 확인.
- **비가역 플래그**: 없음 (본문 중 누수 패턴 제거·재작성, 본문 의도 보존 전제). 단, 프롬프트 변경은 글쓰기 품질에 영향 → 변경 전 확인.

#### maintenance_checklist (M01~M11 정비 체크리스트)

- **정의**: 블로그 정비 대상 블로그(maintenance_status != 'none')에 대해 M01~M11 정비 항목을 일괄 실행하고 전체 통과 여부를 판정. maintenance_checklist 자체가 fail이면 하나 이상의 M-항목이 fail 상태. 현재 7건이 fail (M01~M11 중 하나 이상이 실패한 블로그 7개).
- **fail 판정 근거 (evidence)**:
  - `check_maintenance_checklist()` (`ops_dashboard/checks/maintenance.py:504-567`): MAINTENANCE_CHECKS(M01~M11) 순회 실행 → fail 있으면 `"M-체크리스트: N/M 통과, K개 실패"`, 전체 통과면 `"M-체크리스트: 전체 11항목 통과 — 재개 준비 완료"`.
  - 개별 M-항목 fail은 `set_check_item_status()`로 DB(`maintenance_checklist_items` 테이블)에 기록됨.
- **조치 대상**: fail된 개별 M-항목 (maintenance_checklist_items 테이블에서 blog_id별 체크 항목별 status 확인 가능).
- **M01~M11 각 항목 판정 로직·조치 요약** (판정 로직 출처: `ops_dashboard/checks/maintenance.py`):
  - **M01** (제목 CJK 없음, `_check_cjk_in_title` L30-71): 최근 20개 발행 제목에 한자(\u4e00-\u9fff)·히라가나(\u3040-\u309f)·가타카나(\u30a0-\u30ff) 포함 시 fail. 조치: 제목 재생성(CJK 제거) → **콘텐츠 재생성 수반, 🔴 별도 웨이브 승인 필요.**
  - **M02** (이미지 정상, `_check_image_repetition` L153-198): 최근 20개 포스트 featureimage 중 동일 URL 3회 이상 반복 시 fail. 조치: 중복 이미지 사용 포스트의 featureimage 변경 → **content 수정.**
  - **M03** (크로스링크 주제 일관, `_check_crosslink_relevance` L204-206): `check_crosslink_consistency` 실행, fail 시 크로스링크 관련 조치. 조치: 크로스링크 검토·수정이 필요하면 content 수정. [crosslink.py 상세 참조]
  - **M04** (본문 품질 게이트, `_check_content_quality` L209-225): known_issues에서 issue_id가 Q로 시작하고 open 상태인 이슈 존재 시 fail. 조치: 해당 Q 이슈 해결 → **이슈 종류별 조치 상이.**
  - **M05** (표준 준수, `_check_standard_compliance` L228-239): 최신 standard_compliance check_results가 fail이면 fail. 조치: R01~R12 각 규칙별 조치 → **Appendix C.2 레시피로 위임 (이미 존재).**
  - **M06** (키워드 잔량 충분, `_check_keyword_availability` L242-327): defined 키워드 - published_products 사용 < 24개(남은 키워드)면 fail. 조치: keywords.py/KEYWORD_MAP에 키워드 추가 또는 publish_products 정산 → **키워드 관리.**
  - **M07** (P03 유사제목 안전, `_check_similar_title_safety` L330-357): 최근 7일 내 similar_title 차단 발생(content.db publish_ledger) 시 fail. 조치: 차단 원인 조사·제목 패턴 조정 → **P10(title_blocked) 레시피 참조 가능.**
  - **M08** (CoT/프롬프트 누수 없음, `_check_cot_leak` L360-372): known_issues에서 P07/P08이 open 상태면 fail. 조치: 누수 이슈 해결 → **leak_detected 레시피(C.3) 참조.**
  - **M09** (publish_log 기록 정상, `_check_publish_log_integrity` L375-457): content.db publish_ledger 발행 건수 > 0이나 모든 소스 DB(curation.db, stap_content.db, car.db, stock.db, rap.db 등) 로그 0건이면 fail. 조치: 소스 DB 로그 기록 누락 원인 조사·수정 → **파이프라인 로그 설정 점검.**
  - **M10** (도메인 가용성, `_check_domain_health` L460-482): 도메인 HTTP HEAD가 200-399 범위 아니면 fail, 연결 실패도 fail. 조치: 도메인 상태·배포 확인 → **인프라 점검.**
    - M10 도메인 이상 시: 도메인 HEAD 200 확인 실패면 → 배포 상태 확인 (`wrangler pages deployment list {blog_id}`), DNS 설정 확인, 서버/Cloudflare 상태 확인. 코드/콘텐츠 수정 범위 아님.
  - **M11** (본문·슬러그 CJK 없음, `_check_cjk_in_body_and_slug` L74-150): 최근 20개 포스트 본문 또는 슬러그(디렉토리명)에 한자·히라가나·가타카나 포함 시 fail. 조치: 본문/슬러그 재생성(CJK 제거) → **콘텐츠 재생성 수반, 🔴 별도 웨이브 승인 필요.**
- **등급 결정트리** (전체 maintenance_checklist):
  - 개별 M-항목 fail → 해당 항목 조치로 해결 → `POST /api/maintenance/checklist` (JSON body `{"blog_id": "{blog_id}"}`) 재실행 → 전체 pass 전환 → resume_ready = True.
  - M01/M11(콘텐츠 본문·제목 재생성), M02(콘텐츠 수정) 등 콘텐츠 변경이 필요한 항목은 비가역적 변경 수반 가능 → **🔴 별도 웨이브 승인 필요.**
- **사용자 결정지점**: M01/M11 등 콘텐츠 본문·제목 재생성이 필요한 항목의 조치 범위와 방식 결정 시.
- **STOP 조건**:
  - (f) M01/M11 조치 계획에 콘텐츠 본문·제목 삭제/재생성이 포함 → 재생성 범위·대상 명시한 별도 웨이브 승인 필요. 자동 금지.
  - (a) maintenance_checklist 외 파일·DB 수정으로 번지면 중단.
  - **(e) 재검사 트리거 호출 전 "FAIL→PASS 예상"으로 완료 보고** → 중단. 조치 후 반드시 `POST /api/maintenance/checklist` ({blog_id} 대상) 호출로 화면 갱신 후 재검증. 자동 갱신 대기는 STOP.
- **검증 방법**: 개별 M-항목 조치 후 `POST /api/maintenance/checklist` (JSON body `{"blog_id": "{blog_id}"}`) 재실행 → maintenance_checklist status가 pass로 전환 + resume_ready = True 확인.
- **비가역 플래그**: M01/M11(콘텐츠 본문·제목 재생성)은 🔴 별도 웨이브·명시 승인 필요. M02~M10은 조치 내용에 따라 다름(대부분 콘텐츠 수정·설정 변경·인프라 점검 수준, 본문 삭제/변형 없는 범위에서 처리 가능).

---

#### C-계열 기타 검사 — 판정 로직 확인·분류만 (레시피 초안 선택)

아래 C-계열 검사들은 현재 fail 발생하고 있으나, 이번 룩북 추가에서는 판정 로직 확인·분류만 수행하고 레시피 초안은 선택(필요 시 별도 세션에서 작성).

| check_name | fail 건수 | 판정 로직 요약 | 분류 |
|------------|----------|--------------|------|
| **gsd_crosscheck** | 3건 | `check_crosscheck()` (`ops_dashboard/checks/crosscheck.py:19-58`): auto_detectable 이슈가 있으나 해당 블로그의 fail check_results가 없으면 fail. **메타 검사**(다른 체크가 이슈를 제대로 catch했는지 검증). 조치: 근본은 각 auto_detectable 이슈에 대한 개별 체크가 fail을 내도록 하는 것 — gsd_crosscheck 자체보다 해당 이슈의 담당 체크를 정비. **별도 레시피 불필요(메타 검사).** |
| **c03_fm_key_leak** | 3건 | `_check_c03()` (`ops_dashboard/checks/content_integrity.py:123-129`): 본문(프론트매터 이후)에 FM_KEYS(title, og_image, featureimage, date, slug 등) 라인이 regex로 검출되면 fail. 증거: `"C03 위반: N건 — leaked_line"`. 조치: 본문에서 frontmatter 키 형식의 라인 제거 → **content 수정(경미).** 레시피: **위 C.6 C03 참조 (정식 등재).** |
| **c04_prompt_leak** | 1건 | `_check_c04()` (`ops_dashboard/checks/content_integrity.py:132-142`): C04_KO_PATTERNS + C04_EN_PATTERNS(국문·영문 LLM 프롬프트/사고문 패턴)으로 본문 검사, 검출 시 fail. 증거: `"C04 위반: 프롬프트 누수 N건 — matched_text"`. P08/P07(leak_detected)과 밀접. 조치: 본문에서 누수 패턴 제거 + 프롬프트/방지 로직 점검 → **leak_detected 레시피(C.3) 참조, 본문 수정은 별도.** 레시피: **위 C.6 C04 참조 (정식 등재).** |
| **freshness** | 1건 | `check_freshness()` (`ops_dashboard/checks/freshness.py:27-69`): 계열별 stale 기준(cuap=1일, etap/tap/stap/cap/rap/seap=7일, manual=30일) 대비 마지막 성공 발행 후 경과일 초과 시 fail. 조치: 해당 블로그 신규 발행 → **파이프라인 정상 발행으로 해소, 별도 FIX 레시피 불필요(설계상 정상).** |

> 참고: freshness는 "조치가 파이프라인 정상 발행"이라는 점에서 FIX 레시피북의 "코드 수정·콘텐츠 수정" 유형과 성격이 다름. freshness fail은 파이프라인을 정상 가동하면 자동 해소되므로 레시피북에 등재하지 않음.
>
> **freshness 발생 시 확인할 항목 (체크리스트 — 수정 레시피 아님, 운영 액션):**
> - 스케줄러 실행 중인가? (`ps aux | grep scheduler.py`)
> - 해당 블로그 daily_quota 소진됐는가? (`config/blogs.d/*.yaml`)
> - 데이터 소스 고갈? (festival.db, course.db, tap.db content_pool 잔여량)
> - blocked 사유? (P01 no_result, P14 keyword 소진, P17 daily 소진 등)
> - 파이프라인 정상 동작? (`logs/` 최근 오류, dispatcher.log)

---
