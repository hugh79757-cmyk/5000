# WL-20260814-c-integrity-c02-expansion

작업일: 2026-08-14
작업자: LLM 에이전트 (5000 ops_dashboard)
계통: Phase C-무결성-3 확산 재개 — W1(C02) 타블로그 확산

## 배경

- 검수엔진 신뢰 확보(C01 전수 + OR 병합, 커밋 2fbbd8ecd) 후 확산 재개.
- 대시보드 수치를 진실소스로 신뢰, 전수 전환으로 갱신된 재고 기준으로 확산 계획 재수립.

## Step0 — 갱신 재고 스냅샷 (전체 재검사 후)

- W1(C02) fail 타블로그: **techpawz-hugo 4건** (유일한 C02 타블로그, hotissue 제외)
- W2(C03) fail: 10개 블로그 (fitness 10, appliance 4, techpawz 4, informationhot 3, kitchen 2, rotcha 2, beauty/camping/health/issue-techpawz 1)
- W3(C01) fail: 49개 블로그 총 490건 (techpawz 91 최대)
- 이번 착수: W1만. W2/W3 순차 별도 승인.

## Step1 — W1(C02) techpawz 확산

### 변형 특정
- techpawz C02 4건이 전부 **새 변형**: 닫는 `---`가 개행 없이 본문 첫 문단과
  같은 줄에 병합(`---2026 근로장려금 ...`). hotissue의 여는 쪽 `^---[^\n]` 유형과
  배열이 다름.
- 첫 `---`(라인0) 정상, 두 번째 독립 `---` 줄 없음 → `line.strip()=='---'` 매치
  실패 → C02 fail.
- **실제 영향**: frontmatter 미파싱으로 Hugo가 이 4개 포스트 HTML을 생성하지
  않음(라이브 404) = 실질 파싱 결함 + 페이지 누락.

### 교정
- 백업: git tag `pre-c02-variant-20260814` (techpawz repo), `pre-publish-20260814-0000` (5000 repo)
- 규칙: `\n---(?=[^\s\n])` → `\n---\n` 치환. 본문 첫 줄 무손실.
- 4/4 적용. Hugo 재빌드 0에러. 해당 포스트 HTML 4건 생성 확인(제목 정상 렌더).
- 규칙카드 C02(62-01 문서)에 변형 유형 + 교정 규칙 + 검증 방법 문서화.

### 배포 + 검증
- 배포: shared/publishers/deploy.py `deploy_site(techpawz-hugo, techpawz-hugo)`.
  wrangler OAuth 토큰 추출 후 Pages 배포. 성공.
- 라이브: 4개 포스트 전부 HTTP 200.
- 대시보드 재검사: `c02_frontmatter_close` → **pass (791건)**.
- 남은 techpawz fail(c01 91, c06 8, R2-01/THUMBNAIL-01)은 W1 범위 밖.

### 확대
- 대시보드 기준 C02 fail 타블로그는 techpawz가 유일 → 추가 대상 없음. W1 완결.

## 정책 경계 / 잔존 위험
- techpawz C01 91건·R2-01·THUMBNAIL-01은 W3/W2 등 별도 웨이브 대상.
- C02 변형(닫는---개행누락)이 다른 블로그에도 잠복 가능하나, 대시보드 C02 전수
  기준으로는 techpawz만 노출됨. 이후 전체 재검사에서 C02 fail이 새로 뜨면
  이 규칙카드 유형으로 교정.

## 관련 파일
- `techpawz-hugo/content/posts/{3874,3834,3828,3851}_*/index.md` — 4건 교정
- `.planning/phases/phase-62-content-leak-prevention/62-01-reverse-validation.md` — 규칙카드 C02 변형 문서화
- git 태그: `pre-c02-variant-20260814`, `pre-publish-20260814-0000`

## Step5 — description 오염 격리 (별도 이슈 기록)

### 위반 감지
- 커밋 직전 검토에서 4개 교정 파일의 working diff에 **내 newline 교정 외에
  `description:` 키 추가가 섞여** 있음을 발견.
- 원인: 이전 세션의 미완료(미커밋) 작업 — HEAD에는 description이 없었으나,
  working tree에 절단된 description(135~141자, 문장 중간 `'`로 종료)이 이미 존재.
- C02 레시피 "다른 필드 안 건드림" 원칙 위배 소지 → 사용자 결정(선택지3)에 따라
  C02 커밋에서 **description 원복**, newline 교정만 커밋하기로 격리.

### 오염 범위 확정 (전수 스캔)
- `git diff -z`로 modified index.md 756개 전수 비교.
- `[A] HEAD 무desc → working 추가`: **4개** — 정확히 내 배치(3828/3834/3851/3874).
- `[C] desc 값 변경`: 3개(주휴수당/tcl-tv/뵈다-봬다) — 내 배치 아님, 별개 이전 세션
  작업. 사용자 지시대로 **건드리지 않음**.
- `[R] desc 삭제`: 0개.

### 순수 C02 재구성 + 재배포
- 4개 파일을 `HEAD 원본 + newline 치환`으로 재구성(description 제거).
- Hugo 재빌드 0에러, 4개 포스트 HTML 생성(제목 정상).
- `deploy_site(techpawz-hugo, techpawz-hugo)` 배포 성공.
- 라이브: 4개 전부 HTTP 200, description이 사이트 기본값("생활정보, IT테크,
  금융재테크 전문 블로그")으로 원복 — 절단본 제거 확인.
- 대시보드 재검사: fail=3 (standard_compliance THUMBNAIL-01/R2-01, c01 91건,
  c06 8건) — **c02 없음 = pass 유지**. registry fail 규칙 R12/THUMBNAIL-01/R2-01만.
  타 체크 신규 파손 없음(이 3건은 C02 작업 전부터 있던 기존 fail).

### 분리 이슈 (이번엔 처리 안 함 — 범위 격리)
- **오염 source**: techpawz-hugo 4개 포스트(3874/3834/3828/3851)에 이전 세션이
  절단된 description(135~141자, 문장 중간 종료)을 추가·미커밋 상태로 남김.
- 원인 규명(어느 세션/스크립트가 135자 절단을 만들었는지)과 정상 description
  재생성은 **C02 확산과 분리된 별도 웨이브**로 처리.
- 현재 라이브는 HEAD 상태(desc 부재)로 복구됨 — 노출 위험 없음.

## 잔존 위험 (Step5 반영)
- 4개 포스트는 description이 없어 메타 description이 사이트 기본값으로 노출.
  정상 SEO description 보강은 별도 이슈(분리 웨이브)에서.
- `[C] desc 변경 3파일`(주휴수당/tcl-tv/뵈다)의 미커밋 편집은 이번 작업 범위 밖
  — 별도 확인 필요.
