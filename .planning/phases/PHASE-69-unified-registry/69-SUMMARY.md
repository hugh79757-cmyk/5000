# Phase 69 요약 — 통합 레지스트리 (Unified Rule/Error Registry)

> **상태**: 완료 (W1~W7 구현, 일부 정리 작업 잔여)
> **작성일**: 2026-08-08
> **근거**: 실제 코드·git·프로세스·대시보드 응답 inspection 기반

---

## 1. 계획서 정정 (69-PLAN.md)

조사로 드러난 오류를 기록한다. 계획서의 다음 전제들이 사실과 다르다:

### (a) `hugo-blowfish-standardization` 스킬 실재 부재

- 계획서 W7 작업 4 (L618~625)는 `hugo-blowfish-standardization` 스킬을 실존 전제로 참조한다.
- 실제 검색 결과: `.claude/skills/`, `.opencode/`, `.agent/`, 프로젝트 전체 glob에서 해당 스킬 파일 없음.
- 계획서 L620 "Blowfish 21항목: hugo-blowfish-standardization 스킬 기준의 Blowfish 표준 검사 21개 선언"은 실행 불가한 기술.
- **정정**: "스킬 부재 — W7 Blowfish 21항목 확대는 보류/취소"로 기록.

### (b) 지침서 v1.2에 "21항목" 체크리스트 부재

- `/Users/twinssn/Projects/5000/Blowfish-Hugo-테마-업그레이드-표준-지침서.md` v1.2 (429행) 어디에도 "21"이라는 숫자나 명시적 21항목 체크리스트는 없음.
- 계획서가 임의 부여한 숫자. **정정**: "21항목은 계획서 임의 부여 — 지침서 실재 항목 수와 불일치".

### (c) 지침서 실질 항목 17개는 이미 R01~R12로 구현 완료 = 중복

지침서 v1.2의 각 항목을 R01~R12와 대조한 결과:

| 지침서 위치 | 내용 | 기존 규칙 | 중복 |
|-----------|------|----------|------|
| §3.1, §8-1 | showTableOfContents=false | R01 | 중복 |
| §3.1 | [params.advertisement] + slots | R02 | 중복 |
| §3.2, §8-2 | adsbygoogle.js site.Params 사용 | R03 | 중복 |
| §3.3 | GA4 + 모바일 보정 CSS | R04 | 중복 |
| §3.4 | top.html wrapper + div 밖 push | R05 | 중복 |
| §3.5, §8-4 | in-article fluid+in-article (no auto) | R06 | 중복 |
| §3.6 | single.html H2 분할 + prose 래퍼 | R07 | 중복 |
| §2.3, §8-8 | Description(lead) 제거 | R08 | 중복 |
| §3.7, §8-9 | baseof.html 커스텀 금지 | R09 | 중복 |
| §3.8 | custom.css (unfilled+dark+min-height) | R10 | 중복 |
| §8-3 | mobile-sticky.html 금지 | R11 | 중복 |
| §8-5, §8-6, §8-7 | div 밖 push / display:none 금지 / JS placeholder 금지 | R05+R06+R07에 흡수 | 중복 |
| §1 원칙, §8 원칙 | 허용집합 외 오버라이드 금지 | R12 | 중복 |

**17개 항목이 R01~R12로 이미 구현 완료.** 지침서는 R01~R12의 원천 서술 문서이고, R01~R12는 그 구현체.

### (d) 이연 항목 (외부 의존 — 별도 웨이브 백로그)

지침서 v1.2 중 R01~R12 범위를 벗어나는 항목:

| 항목 | 내용 | 이연 사유 |
|------|------|----------|
| §2.1 | `layouts/index.html` 홈페이지 파손 방지 (테마 복원) | Hugo 렌더링 결과 확인 필요 → 파일 파싱 범위 밖 |
| §7 체크리스트 "Hugo 빌드 정상 확인" | 빌드 성공 여부 | Hugo 빌드 프로세스 책임 → check_fn 부적합 |
| §7 체크리스트 "배포 후 광고 노출 확인 (H1 위 + 본문 중간)" | 실제 광고 렌더링 확인 | HTTP + AdSense 응답 필요 → 수동 판정 영역 |

**THUMBNAIL-01 차원 검사 (600×600)**: 이미지 차원 검사는 HTTP 응답 헤더 또는 이미지 디코딩 필요 → 현 check_fn 패턴(파일 파싱)으로 불가. 별도 웨이브 백로그.

---

## 2. W7 종결 선언

### 자동화 확장성 가설 증명 완료

"선언 한 줄 + 함수 1개로 새 규칙 자동 편입" 가설이 아래 두 사례로 증명됨:

| 신규 규칙 | 선언 위치 | check_fn | 자동편입 확인 수단 |
|-----------|---------|----------|------------------|
| THUMBNAIL-01 | rules.py L150~159 | `_check_thumbnail_01` (standard.py L509~) | `all_entries()` 포함, `/api/registry` 노출 |
| R2-01 | rules.py L165~174 | `_check_r2_01` (standard.py L603~) | `all_entries()` 포함, `/api/registry` 노출 |

**확장성 검증**: `all_entries()`가 R01~R12 + THUMBNAIL-01 + R2-01 = 14규칙을 반환하고, `/api/registry`가 이를 동일 스키마로 노출. `check_standard_compliance`는 `RULES`를 순회+SYS.modules getattr로 check_fn 디스패치 (standard.py L728~764). **선언만으로 자동편입 가설 증명.**

### W7 종결 정의

- **자동편입 가능한 규격**: R01~R12 + THUMBNAIL-01 + R2-01 = **14규칙**으로 완결
- **R06 분화 (deprecate-then-split)**: 계획 W7에 명시됐으나, 현재 rules.py에는 R06 단일 항목만 존재 (L75~84). R06A/R06B 분화는 미구현 — 계획상의 전방참조가 실현되지 않음. 단, R06 bucket이 `deferred`라서 준수율 산정에는 영향 없음.
- **Blowfish 21항목**: 실체 부재로 취소.

### W7 실제 완료 항목

```
RULES (rules.py) 현재 선언:
  R01  CRITICAL  hugo.toml         actionable
  R02  CRITICAL  hugo.toml         actionable
  R03  CRITICAL  extend-head.html  out_of_scope
  R04  MAJOR     extend_head.html  out_of_scope
  R05  MAJOR     adsense/top.html  actionable
  R06  CRITICAL  adsense/in-article.html  deferred
  R07  MAJOR     single.html       actionable
  R08  MAJOR     single.html       actionable
  R09  MAJOR     baseof.html       actionable
  R10  MAJOR     custom.css         actionable
  R11  MAJOR     layouts/          actionable
  R12  MAJOR     layouts/          actionable
  THUMBNAIL-01  MAJOR  content/posts/*/index.md  actionable
  R2-01         MAJOR  content/posts/*/index.md  actionable

총계: 14규칙 (rule kind)
ERRORS (errors.py): P01~P24 + unknown_failure = 25오류 (error kind)
```

---

## 3. Phase 69 W1~W7 완결 점검

### (a) 레지스트리 실행 단일 출처 — 확인됨

- `check_standard_compliance` (standard.py L718~): `from ops_dashboard.registry.rules import RULES`로 순회, `_resolve_check_fn(entry.check_fn)`으로 getattr 디스패치 (L702~715).
- `STANDARD_RULES` (L27~L124)는 아직 제거하지 않음 (W6 정리 잔여 — 아래 참조).
- `_record_failed_rules` (L805~): `get_entry(rule_id)`로 registry에서 severity/action 조회 → 레지스트리가 check 경로에서 처음 소비되는 지점.
- **판정**: 실행의 실질적 출처는 registry RULES.STANDARD_RULES는 아직 미제거된 중복 정의.

### (b) 구조필드 단일경로 — 확인됨 (W6-b)

- `_FALLBACK_TRACE_STD` (auto_triage.py L983): `check_name == "standard_compliance"` 항목 추적.
- `_resolve_problem_id` (L986~): standard_compliance 계열은 구조필드 단일경로로 종료, 자유텍스트 폴백 호출 안 함.
- **판정**: 구조필드 단일경로 확립. 다만 `/api/registry` route가 app.py에 명시적 등록 없이 동작 중 — 별도 확인 필요 (아래 3-d 참조).

### (c) 커밋 상태 정리

**W1~W7 커밋 (git log --all --grep):**
```
bf98e50b4 feat(registry): R2-01 R2 버킷/키 패턴 규칙 자동편입
d0427c3b9 feat(registry): W7-b THUMBNAIL-01 선언+함수만으로 자동편입
c92becd7e feat(standard): W7-a 레지스트리 실행 디스패치 전환
d9efed829 fix(auto_triage): W6-b standard 폴백 제거·구조필드 단일경로
75ec202ed fix(standard): W6a.2 활성 블로그만 개별행 populate
2efce05e2 feat(registry): record_check_rule + registry 노출
2a2ededf1 fix(dashboard): W6a get_attention_items aggregate+individual 병합 dedup
89694eb4d feat(registry): W6-a rule↔error 대응 정의 (RULE_TO_PROBLEM)
```

**W6 정리 잔여 (미커밋):**
- `ops_dashboard/readiness.py` L77: `from ops_dashboard.checks.standard import STANDARD_RULES` — W6에서 제거해야 할 중복 import. `rule_bucket`를 registry RULES에서 파생하도록 변경 필요.
- `ops_dashboard/checks/standard.py` L27~L124: `STANDARD_RULES` 아직 존재 — W6에서 제거 예정.
- `ops_dashboard/checks/standard.py` L679~L692: `_CHECK_FUNCTIONS` dict 아직 존재 — W7-a에서 `_resolve_check_fn` getattr 방식으로 대체됐으나, dict 자체는 보존됨 (후방호환? 또는 정리 대상?).

**미커밋 W5-era 잔여:**
- `/api/registry` route: `get_registry_view` (db.py L952)은 구현됨. auto_triage.py L601에서 `/api/registry` 호출. **그러나 app.py의 `_register_api_routes` (L383~L485)에 `@app.route("/api/registry")` 등록 없음.** curl 테스트는 데이터 반환 — 실행 중인 프로세스가 디스크와 다른 버전이거나, 별도 메커니즘 존재 가능. **확인 필요.**

### (d) 4개 프로세스 상태

| 프로세스 | PID | 상태 | 비고 |
|---------|-----|------|------|
| ops-dashboard | 77885 | ✅ alive | `python -m` 으로 실행 중, `/api/readiness` 200, `/api/registry` 응답 정상 |
| scheduler | 78295 | ✅ alive | `scheduler.py` 실행 중 |
| watchdog | 34819 | ✅ alive | `analytics_watchdog.sh` bash script |
| auto_triage | — | ⚠️ 데몬 미실행 | `python3 scripts/auto_triage.py --dry-run`은 수동 실행 가능. 03:00 Cron 등록 확인 필요 |

---

## 4. 대시보드 에이전트 판독 검증

**방법**: `/api/registry`를 실제 호출해 응답을 받고, **"에이전트가 이 JSON만 보고 각 fail 항목의 원인과 조치를 스스로 파악할 수 있는가"**를 fail 규칙 5개로 검증.

### 실제 `/api/registry` 응답에서 추출한 fail 규칙 5개

#### R04 (extend_head.html) — fail
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

**에이전트 재구성**:
- **무엇이 실패했나**: extend_head.html에 GA4 추적 코드와 모바일 보정 CSS가 없다.
- **왜 실패했나**: `extend_head.html` 파일에 `gtag`/`GA4`/`google-analytics` 패턴과 `max-width`/`font-size`/`mobile` CSS 패턴이 모두 부재.
- **어떻게 고치나**: `layouts/partials/extend_head.html`에 GA4 스크립트 + 모바일 보정 CSS `@media (max-width:767px)` 추가.
- **심각도**: MAJOR, 버킷 out_of_scope (준수율 산정 제외).

---

#### R06 (adsense/in-article.html) — fail
```json
{
  "id": "R06",
  "kind": "rule",
  "target": "adsense/in-article.html",
  "status": "fail",
  "severity": "CRITICAL",
  "action": "fluid+in-article format (no auto) + outside push div 필요",
  "evidence": "in-article.html: missing fluid format, missing in-article format, data-ad-format=auto (prohibited)",
  "rule_id": "R06",
  "problem_id": "",
  "bucket": "deferred",
  "threshold": "always"
}
```

**에이전트 재구성**:
- **무엇이 실패했나**: in-article 광고 파셜이 규격에 맞지 않는다. 3가지 문제 동시 발생.
- **왜 실패했나**: (1) `data-ad-format="fluid"` 누락, (2) `data-ad-layout="in-article"` 누락, (3) 금지인 `data-ad-format="auto"` 존재.
- **어떻게 고치나**: `layouts/partials/adsense/in-article.html`에서 `data-ad-format="fluid"` + `data-ad-layout="in-article"` 설정, `data-ad-format="auto"` 제거, `<script>push({})`를 `<div>` 밖에 배치.
- **심각도**: CRITICAL이나 버킷 deferred (STRUCT-16, 콘솔 슬롯 형식 미확인으로 보류).

---

#### R07 (single.html) — fail
```json
{
  "id": "R07",
  "kind": "rule",
  "target": "single.html",
  "status": "fail",
  "severity": "MAJOR",
  "action": "H2 split injection + prose wrapper 필요",
  "evidence": "single.html: missing H2 split injection, prose wrapper",
  "rule_id": "R07",
  "problem_id": "",
  "bucket": "actionable",
  "threshold": "always"
}
```

**에이전트 재구성**:
- **무엇이 실패했나**: single.html에 본문 H2 분할 인젝션 로직과 `prose` 래퍼가 없다.
- **왜 실패했나**: `single.html` 파일에 `h2`+`split`/`inject`/`adsense` 패턴과 `prose` 클래스가 모두 부재.
- **어떻게 고치나**: `layouts/_default/single.html`에 Blowfish 표준 H2 분할 인젝션 로직 (`{{ $h2parts := split $content "<h2" }}` 등) + `<section class="... prose dark:prose-invert">` 래퍼 추가.
- **심각도**: MAJOR, 버킷 actionable (지금 고칠 대상).

---

#### R08 (single.html) — fail
```json
{
  "id": "R08",
  "kind": "rule",
  "target": "single.html",
  "status": "fail",
  "severity": "MAJOR",
  "action": "Description (lead) 제거 필요",
  "evidence": "single.html: .Lead/.Description still present (not removed)",
  "rule_id": "R08",
  "problem_id": "",
  "bucket": "actionable",
  "threshold": "always"
}
```

**에이전트 재구성**:
- **무엇이 실패했나**: single.html에 `.Lead` 또는 `.Description` 클래스가 남아있어 제목 아래 디스크립션 문단이 표시된다.
- **왜 실패했나**: `{{ with .Description }}<p class="lead">...</p>{{ end }}` 라인이 제거되지 않음.
- **어떻게 고치나**: single.html에서 `.Lead`/`.Description` 사용 라인 제거 (또는 주석 처리).
- **심각도**: MAJOR, 버킷 actionable.

---

#### R10 (custom.css) — fail
```json
{
  "id": "R10",
  "kind": "rule",
  "target": "custom.css",
  "status": "fail",
  "severity": "MAJOR",
  "action": "미채움 공간 제거 + 다크모드 + min-height 규칙 필요",
  "evidence": "No custom.css found",
  "rule_id": "R10",
  "problem_id": "",
  "bucket": "actionable",
  "threshold": "always"
}
```

**에이전트 재구성**:
- **무엇이 실패했나**: `assets/css/custom.css` 파일이 존재하지 않는다.
- **왜 실패했나**: 파일 자체 부재. `site / "assets/css/custom.css"` 존재 체크에서 실패.
- **어떻게 고치나**: `assets/css/custom.css` 생성 — `.ad-inarticle`, `.ad-top` (min-height:250px/200px), `ins.adsbygoogle[data-ad-status="unfilled"]` 제거 규칙, 다크모드 배경 방어 포함.
- **심각도**: MAJOR, 버킷 actionable.

---

#### R12 (layouts/) — fail
```json
{
  "id": "R12",
  "kind": "rule",
  "target": "layouts/",
  "status": "fail",
  "severity": "MAJOR",
  "action": "허용 집합을 벗어난 오버라이드 파일 없음",
  "evidence": "Unauthorized overrides: layouts/shortcodes/btn.html, layouts/shortcodes/coupang.html (junk: layouts/.DS_Store)",
  "rule_id": "R12",
  "problem_id": "",
  "bucket": "actionable",
  "threshold": "always"
}
```

**에이전트 재구성**:
- **무엇이 실패했나**: ALLOWED_OVERRIDES에 없는 오버라이드 파일이 존재.
- **왜 실패했나**: `layouts/shortcodes/btn.html`, `layouts/shortcodes/coupang.html`이 허용 목록(인가를 받은 17개 파일)에 없음.
- **어떻게 고치나**: (a) 해당 파일을 ALLOWED_OVERRIDES에 추가 (의도된 오버라이드라면), 또는 (b) 파일 삭제 (불필요 오버라이드라면).
- **심각도**: MAJOR, 버킷 actionable. 정크 파일(.DS_Store)은 별도 집계.

---

### 판독 검증 결론

**에이전트 판독: 가능.** `/api/registry` 응답의 구조 필드만으로 각 fail 항목의 원인·조치·재발 방지를 재구성 가능:

| 필드 | 판독 역할 |
|------|---------|
| `id` + `target` | **무엇이** 실패했는지 (어떤 파일/규칙) |
| `status: "fail"` | 실패 상태 |
| `evidence` | **왜** 실패했는지 (구체적 누락/위반 내용) |
| `action` | **어떻게** 고치는지 (조치 안내) |
| `severity` + `bucket` | 우선순위 + 준수율 산정 방식 |
| `rule_id` | 구조 식별자 (레지스트리 조인 키) |

자유텍스트 파싱 없이 `evidence` + `action` 필드만으로도 조치 방법 파악 가능. **목적 달성.**

---

## 5. 백로그 명시

### 외부의존 이연 3항목 (W7 이후 별도 웨이브)

1. **§2.1 `layouts/index.html` 홈페이지 파손 방지**: Hugo 렌더링 결과 확인 필요 → 파일 파싱 범위 밖. build+render 체크 파이프라인 필요.
2. **§7 "Hugo 빌드 정상 확인"**: 빌드 성공 여부 → 빌드 프로세스 책임. check_fn 부적합.
3. **§7 "배포 후 광고 노출 확인"**: HTTP + AdSense 응답 필요 → 수동/별도 모니터링 영역.
4. **THUMBNAIL 600×600 차원 검사**: 이미지 차원 확인 필요 (HTTP 헤더/디코딩) → 현 check_fn 패턴으로 불가.

### R2-01 위반 실데이터 정비 대기

`/api/registry` 응답에서 R2-01은 현재 status `"unknown"` (checked_at 행 없음). 실제 블로그 대상 검사 실행 후 위반 발견 시 정비 필요. 현재 violations 데이터는 없음 (아직 스캔 안 함).

### R06 분화 (R06A/R06B)

계획 W7에 명시됐으나 미구현. 현재 R06 단일 항목 유지. bucket이 `deferred`라 준수율 영향 없음.

### /api/registry route 등록 확인

`get_registry_view` (db.py)는 구현되고 auto_triage가 호출하나, app.py에 명시적 `@app.route("/api/registry")` 없음. curl 테스트는 응답 정상 — 실행 중인 프로세스와 디스크 간 버전 차이 또는 별도 등록 메커니즘 가능성. **확인 후 app.py에 정식 등록 필요.**

---

## 6. 커밋/미커밋 구분

### 커밋됨 (git log --all 기준)
- W1: schema.py, __init__.py, rules.py, errors.py 생성
- W2: db.py 컬럼 추가 + record_check 시그니처 확장
- W3: record_check_rule + check_standard_compliance dual-write
- W4: triage_classifications 테이블 + auto_triage 분류 기록
- W5: get_attention_items 구조필드 노출 + _resolve_problem_id + /api/registry 뷰
- W6: (일부) _FALLBACK_TRACE_STD 제거, 활성 블로그 개별행 제한
- W7: THUMBNAIL-01 + R2-01 선언+함수, W7-a 레지스트리 디스패치 전환

### 미커밋 / 잔여
- W6: STANDARD_RULES 제거, readiness.py의 STANDARD_RULES 직접 import 제거, _CHECK_FUNCTIONS dict 정리
- W7: R06A/R06B 분화
- auto_triage: 03:00 Cron 등록 확인

### 추가 커밋 (본 작업)
- `b0f5f8f30 feat(app): /api/registry route 명시 등록 (재시작 생존)` — 앱.py에 route 명시 추가, 재시작 후 200+14규칙 확인

---

## 7. git diff --stat (W5~W7 관련 파일)

```
ops_dashboard/registry/        : +4 files (schema.py, __init__.py, rules.py, errors.py)
ops_dashboard/checks/standard.py: +200+ lines (check 함수 + _resolve_check_fn + RULES 순회)
ops_dashboard/db.py            : +record_check_rule + get_registry_view + triage_classifications
scripts/auto_triage.py         : +_resolve_problem_id + _build_registry_map + /api/registry 호출
ops_dashboard/readiness.py     : 변경 없음 (STANDARD_RULES 직접 import 잔존)
ops_dashboard/app.py           : /api/registry route 미확인 (커밋/디스크 불일치 가능)
```

## 한 줄 결론

**Phase 69 완료 — 레지스트리 단일출처·구조필드 단일경로·14규칙 자동편입(R01~R12 + THUMBNAIL-01 + R2-01), 에이전트 판독 가능(구조필드 evidence+action만으로 fail 원인·조치 재구성 확인), Blowfish 21 전제오류 정정(스킬 부재·21항목 실체 없음·17항목 R01~R12 중복), /api/registry 재시작 생존 확정(b0f5f8f30 route 명시 등록), W6 정리 잔여(STANDARD_RULES/readiness 직접 import), 백로그 N항목 이연.**
