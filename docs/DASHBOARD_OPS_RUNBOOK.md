## 대시보드 운영 런북 (Dashboard Ops Runbook)

> **목적**: 5000에 붙는 모든 LLM 에이전트가 대시보드를 읽고→문제를 진단·수정하고→사용자에게 보고하는 표준 절차. 별도 SKILL.md 디렉터리는 만들지 않는다(5000에 자동 로드된 전례 없음 — `hugo-blowfish-standardization` 스킬은 계획서에서만 참조되고 실체 파일이 없어 박제된 오류 사례). 이 섹션을 AGENTS.md에 직접 둔다.

### 0. 자동 로드 컨텍스트

- 이 섹션은 `AGENTS.md`(프로젝트 루트, 세션 시작 시 자동 로드)에 있다.
- 대시보드는 5000의 **단일 진실원(single source of truth)**. 대시보드가 말하는 문제만 수정한다. 대시보드 외부 추측으로 코드 수정 금지.
- 대시보드는 `ops_dashboard/app.py` (Flask, 포트 5060)에 의해 제공되며, `ops_dashboard/ops.db`를 읽는다.

---

### 1단계 — 읽기 (READ): 대시보드에서 문제 수집

**대시보드 서버**: `http://localhost:5060`, Basic Auth.

**자격 정보 (평문 하드코딩 금지)**:
- 환경변수 `OPS_USER` / `OPS_PASSWORD`가 있으면 그 값으로 인증.
- 없으면 앱은 RuntimeError 발생 (fail-closed). 반드시 환경변수 설정 필요.
- **스킬 본문에 평문 비밀번호를 하드코딩하지 말 것** — 항상 환경변수 우선, fallback은 "기본값 사용"이라고만 명시.

**핵심 엔드포인트 (GET, 인증 필요)**:

```bash
# 현재 fail·issue 목록 (알림 대상)
curl -s -u "${OPS_USER}:${OPS_PASSWORD}" \
  http://localhost:5060/api/attention

# 규칙 14개 + 오류 25개 선언 + 실데이터를 단일 스키마로
curl -s -u "${OPS_USER}:${OPS_PASSWORD}" \
  http://localhost:5060/api/registry | python3 -m json.tool
```

**`/api/registry` 응답 스키마 (규칙 1건 예시)**:
```json
{
  "id": "R04",
  "kind": "rule",
  "target": "extend_head.html",
  "status": "fail",
  "severity": "MAJOR",
  "action": "GA4 + 모바일 보정 CSS 필요",
  "evidence": "extend_head: missing GA4, mobile CSS",
  "rule_id": "R04",
  "problem_id": "",
  "bucket": "out_of_scope",
  "threshold": "always"
}
```

**핵심 필드만 보면 됨**:
- `id` + `target` → **무엇이** 실패했는지
- `status` (`"pass"` / `"fail"` / `"unknown"`) → 실패 여부
- `evidence` → **왜** 실패했는지 (구체적인 누락·위반 내용)
- `action` → **어떻게** 고치는지 (조치 안내)
- `severity` → 우선순위 (CRITICAL / MAJOR / MINOR)
- `bucket` → 준수율 산정 방식 (actionable / deferred / out_of_scope)

**`/api/attention`의 `fail_checks` 항목 스키마**:
```json
{
  "blog_id": "techpawz-hugo",
  "check_name": "standard_compliance",
  "pattern": "...",
  "error_msg": "...",
  "rule_id": "R04",
  "problem_id": "standard_compliance",
  "severity": "MAJOR",
  "action": "GA4 + 모바일 보정 CSS 필요"
}
```

`fail_checks`에서 `rule_id`가 있으면 `/api/registry`의 해당 규칙 entry를 조회해 `evidence`·`action`을 얻는다.

---

### 2단계 — 해석 (INTERPRET): 구조필드만 사용, 자유텍스트 파싱 금지

**규칙**: `evidence`가 무엇이 왜 틀렸는지, `action`이 어떻게 고치는지를 담고 있으니 **그대로 따른다**. 자유텍스트(`detail`, `error_msg`, `pattern`) 파싱하지 않는다.

**해석 테이블 (rule_id → evidence → action → severity)**:

| rule_id | target | 실패 시 evidence 패턴 | action (조치) |
|---------|--------|---------------------|---------------|
| R01 | hugo.toml | `showTableOfContents=true` | `showTableOfContents = false`로 변경 |
| R02 | hugo.toml | `[params.advertisement]` 없음 / adsense·slots 누락 | `[params.advertisement]` 섹션 + `adsense`, `topSlot`, `inArticleSlot` 추가 |
| R03 | extend-head.html | `ca-pub-` 하드코딩 | `site.Params`로 교체 |
| R04 | extend_head.html | `missing GA4, mobile CSS` | GA4 스크립트 + `@media (max-width:767px)` 모바일 보정 CSS 추가 |
| R05 | adsense/top.html | `missing overflow:hidden` / `missing min-height` | `overflow:hidden; min-height:100px` 래퍼 + div 밖 push div 추가 |
| R06 | adsense/in-article.html | `missing fluid format` / `data-ad-format=auto (prohibited)` | `data-ad-format="fluid"` + `data-ad-layout="in-article"`, `auto` 제거, `<script>push({})`를 div 밖에 배치 |
| R07 | single.html | `missing H2 split injection, prose wrapper` | H2 분할 인젝션 로직 + `<section class="... prose ...">` 래퍼 추가 |
| R08 | single.html | `.Lead/.Description still present` | `.Lead`/`.Description` 라인 제거 |
| R09 | baseof.html | 커스텀 오버라이드 (5줄 초과) | `layouts/_default/baseof.html` 삭제, 테마 기본값 사용 |
| R10 | custom.css | `No custom.css found` / unfilled·dark 규칙 누락 | `assets/css/custom.css` 생성 (unfilled 제거 + 다크모드 + min-height) |
| R11 | layouts/ | `mobile-sticky.html found` | `layouts/partials/adsense/mobile-sticky.html` 삭제 |
| R12 | layouts/ | `Unauthorized overrides: ...` | 허용 집합 내로 조정하거나 불필요 오버라이드 삭제 |
| THUMBNAIL-01 | content/posts/*/index.md (featureimage) | `썸네일 위반 N건` / R2 아님 / webp 아님 | featureimage를 R2(pub-<hash>.r2.dev) 호스팅 webp로 설정 |
| R2-01 | content/posts/*/index.md (featureimage+본문 이미지) | `R2 패턴 위반 N건` / 비R2 URL | 모든 이미지 URL을 승인된 R2 버킷(pub-<hash>.r2.dev)으로 이전 |

**실제 예시 (이번 세션 관측)**:

1. **techpawz-hugo R2-01 fail**
   ```
   evidence: "R2 패턴 위반 7건 / 검사 7건: 킹스데일cc-20260808-s3/featureimage: https://..."
   action: "모든 이미지 URL을 승인된 R2 버킷(pub-<hash>.r2.dev)으로 설정"
   → 원인: featureimage가 R2 도메인이 아닌 외부 URL. 조치: R2로 이전.
   ```

2. **techpawz-hugo R04 fail**
   ```
   evidence: "extend_head: missing GA4, mobile CSS"
   action: "GA4 + 모바일 보정 CSS 필요"
   → 원인: extend_head.html에 GA4·모바일 CSS 없음. 조치: 추가.
   ```

3. **techpawz-hugo R06 fail**
   ```
   evidence: "in-article.html: missing fluid format, missing in-article format, data-ad-format=auto (prohibited)"
   action: "fluid+in-article format (no auto) + outside push div 필요"
   → 원인: in-article.html에 fluid·in-article 없음 + 금지인 auto 존재. 조치: 규격 맞게 수정.
   ```

**해석 원칙**:
- `status: "unknown"` → 아직 체크 안 됨 (데이터 없음). 무시하거나 체크 실행.
- `bucket: "out_of_scope"` / `"deferred"` → 준수율 산정에서 제외. 지금 고칠 대상 아닐 수 있음 (구조적 문제로 보류).
- `bucket: "actionable"` → 지금 고칠 대상.

---

### 3단계 — 수정 (FIX): action이 지시하는 파일 수정 + 게이트 통과

**수정 원칙**:
1. `action`이 지시하는 파일을 수정한다. 엉뚱한 파일 수정 금지.
2. **설명·의미는 바꾸지 않는다** — 따옴표 이스케이프·컴마·필드명 등 구조적 문제만 수정한다. (이번 세션의 "description 미이스케이프 수정" 패턴 참조)
3. **다른 필드·다른 블로그는 건드리지 않는다** — 해당 blog_id·해당 파일만.

**게이트 (수정 전·중·후 통과 필수)**:

ⓐ **파괴적 작업 전 백업** (신규 명문화 — 이번 세션 정례화):
   - 코드 수정 전: `git tag pre-<작업명>-<YYYYMMDD>`
   - DB 수정 전: `cp data/<db>.db data/<db>.db.bak_<YYYYMMDD>`
   - 예: `git tag pre-r04-fix-20260808` + `cp data/ops.db data/ops.db.bak_r04_20260808`
   - **백업 없이 수정 금지.**

ⓑ **로컬 Hugo 빌드 0에러**:
   ```bash
   HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes hugo --gc --minify --source /경로/블로그
   ```
   - 에러 0건 확인. 에러 있으면 중단·롤백.
   - Hugo 경로는 AGENTS.md §Technology Stack 참조 (`/opt/homebrew/bin/hugo`).

ⓒ **배포는 §Deployment Rules 준수** (AGENTS.md L494~L574 참조, 중복 작성 금지):
   - `dispatcher.py`로 배포: `python3 /Users/twinssn/Projects/5000/dispatcher.py {blog_id}`
   - **절대 수동 wrangler 명령어 금지** (L562).
   - **절대 `--commit-dirty=true` 금지** (L563).
   - **절대 git push로 배포하지 말 것** (L498).
   - Workers 블로그(health, pet, kitchen, beauty, camping, baby)는 `wrangler deploy --config wrangler.toml`, 그 외 Pages 블로그는 `wrangler pages deploy public --project-name={blog_id}` — dispatcher.py가 자동 구분 (L534~L537).
   - 블로그별 **1회 배포**. 동시 배포·반복 배포 금지.

ⓓ **수정 후 재검증 FAIL→PASS 확인** (신규 명문화 — 이번 세션 정례화):
   - 코드 수정 후: `/api/registry`에서 해당 rule_id의 status가 `"fail"` → `"pass"` 또는 `"unknown"`(체크 미실행 상태로 전환)으로 바뀌었는지 확인.
   - 예: R04 fix 후 `/api/registry` → R04 status=`"pass"`, evidence에 `"extend_head: GA4 + mobile CSS found"` 등.
   - **FAIL→PASS 확인 없이 완료 보고 금지.**

ⓔ **변경과 검사 범위가 겹치는 기존 PASS 규칙도 재검증** (2026-08-21 추가):
   - 수정한 코드/콘텐츠의 검사 범위와 겹치는 규칙이 예전에 PASS였더라도, 재검사 전 PASS 주장 금지 — 반드시 `POST /api/run-checks?blog_id={blog_id}` 재실행 후 before/after를 보고에 함께 기재.

**게이트 실패 시**:
- 빌드 에러 → 원복구 (git checkout 또는 백업 복원) 후 재구성.
- 배포 실패 → dispatcher 로그 확인, 재시도하지 말고 원인 보고.
- 재검증 여전히 FAIL → action이 잘못됐거나 추가 문제. 사용자 보고 후 진행.

---

### 4단계 — 보고 (REPORT): 사용자에게 표준 형식

매 작업 종료 시 아래 형식으로 보고한다:

```
## 대시보드 기반 수정 보고

### 대상
- 블로그: {blog_id}
- rule_id: {R04 등}
- status 변경: fail → {pass/unknown}

### 원인 (evidence)
- {/api/registry evidence 필드의 실제 텍스트}

### 조치 (action + 실제 diff)
- 지시: {/api/registry action 필드의 실제 텍스트}
- 수정 파일: {파일 경로}
- diff 요약:
  ```diff
  - 이전 내용
  + 이후 내용
  ```

### 게이트
- [ ] 백업: git tag pre-{작업명}-{YYYYMMDD} + ops.db.bak_{작업명}_{YYYYMMDD}
- [ ] 로컬 Hugo 빌드: 0에러 (로그 링크 또는 "에러 없음")
- [ ] 배포: dispatcher.py로 {blog_id} 1회 배포 (블로그·시간)
- [ ] 재검증: /api/registry {rule_id} status → {pass/unknown} (FAIL→PASS 확인)

### 남은 항목 (백로그)
- {아직 남은 문제 또는 다음 턴으로 넘길 항목}
```

**한 줄 결론 형식**: `"{blog_id} {rule_id} 수정 완료 — evidence: {원인}, action: {조치}, 게이트: 빌드·배포·재검증 통과, 남은: {백로그}."`

---

### 부록 A — 현재 규칙 14개 참조표

| rule_id | kind | target | severity | bucket | action (요약) |
|---------|------|--------|----------|--------|------|
| R01 | rule | hugo.toml | CRITICAL | actionable | showTableOfContents=false |
| R02 | rule | hugo.toml | CRITICAL | actionable | [params.advertisement] + adsense slots |
| R03 | rule | extend-head.html | CRITICAL | out_of_scope | adsbygoogle.js site.Params 사용 |
| R04 | rule | extend_head.html | MAJOR | out_of_scope | GA4 + 모바일 보정 CSS |
| R05 | rule | adsense/top.html | MAJOR | actionable | overflow:hidden;min-height 래퍼 + outside push |
| R06 | rule | adsense/in-article.html | CRITICAL | deferred | fluid+in-article (no auto) + outside push div |
| R07 | rule | single.html | MAJOR | actionable | H2 split injection + prose wrapper |
| R08 | rule | single.html | MAJOR | actionable | Description (lead) 제거 |
| R09 | rule | baseof.html | MAJOR | actionable | 커스텀 오버라이드 없음 — 테마 기본값 |
| R10 | rule | custom.css | MAJOR | actionable | 미채움 공간 제거 + 다크모드 + min-height |
| R11 | rule | layouts/ | MAJOR | actionable | mobile-sticky.html 사용 금지 |
| R12 | rule | layouts/ | MAJOR | actionable | 허용 집합 벗어난 오버라이드 없음 |
| THUMBNAIL-01 | rule | content/posts/*/index.md (featureimage) | MAJOR | actionable | featureimage를 R2 호스팅 webp로 |
| R2-01 | rule | content/posts/*/index.md (featureimage+본문 이미지) | MAJOR | actionable | 모든 이미지 URL R2 버킷으로 |

- 오류 선언: P01~P24 + unknown_failure (25개, errors.py). 문제idio별 detect_fn/hook·action은 `/api/registry` errors 배열에서 확인.

### 부록 B — 새 규칙 추가법

```
새 규칙 추가 = rules.py에 UnifiedEntry 선언 1행 + standard.py에 _check_xxx 함수 1개
```

- **rules.py** (`ops_dashboard/registry/rules.py`): `RULES: list[UnifiedEntry]`에 `UnifiedEntry(id=..., kind="rule", target=..., severity=..., threshold="always", check_fn="_check_xxx", action=..., bucket=...)` 추가.
- **standard.py** (`ops_dashboard/checks/standard.py`): `_check_xxx(site: Path) -> tuple[bool, str]` 함수 구현 + `_CHECK_FUNCTIONS` dict에 등록.
- **W7 확립 패턴**: 선언만으로 자동편입 — `check_standard_compliance`가 `RULES`를 순회 + `_resolve_check_fn`(getattr)로 디스패치. 하드코딩 등록·별도 매핑 불필요.
- **금지**: `check_fn`이 빈 문자열이거나 존재하지 않는 함수명을 가리키는 선언 (W7 검증 게이트: `all(e.check_fn for e in all_entries() if e.kind=="rule")`).

<!-- GSD:dashboard-ops-runbook-end -->

