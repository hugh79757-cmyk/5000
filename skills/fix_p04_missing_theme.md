# fix_p04_missing_theme

**한 줄 목적**: P04 deploy_error(`module "blowfish" not found`)가 발생한 Hugo 블로그에 패턴 A(hugo.toml 생성 + themesDir=shared-themes)를 적용해 Hugo 빌드를 가능하게 한다.

**트리거**: `problem_registry`에서 `problem_id=P04`, `hook=post_deploy`, 에러 메시지에 `module "blowfish" not found` 또는 `module blowfish not found`가 포함된 경우. (출처: `ops_dashboard/docs/agent-reference/PLAYBOOK_INDEX.yaml` P04 항목, `ERROR_PLAYBOOKS.md` P04/P05)

**연결 문서**:
- `ops_dashboard/docs/agent-reference/PLAYBOOK_INDEX.yaml` → `code: P04` (playbook_ref: ERROR_PLAYBOOKS.md#p04), `code: P05` (playbook_ref: ERROR_PLAYBOOKS.md#p05)
- `ops_dashboard/docs/agent-reference/ERROR_PLAYBOOKS.md#p04` (deploy_error, post_deploy)
- `ops_dashboard/docs/agent-reference/ERROR_PLAYBOOKS.md#p05` (hugo_build_failed, post_deploy)
- AGENTS.md §Hugo 빌드: `HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes hugo --gc --minify --source /경로/블로그`

---

## 1. 전제 조건 점검 (먼저 확인, 하나라도 걸리면 중단)

대상 블로그의 `site_path`(config/blogs.d/*.yaml의 `site_path` 필드)에서 다음을 확인한다.

| 확인 항목 | 방법 | 통과 조건 |
|-----------|------|-----------|
| site_path 실존 | `test -d {site_path}` | 디렉토리 존재 |
| config/_default/params.toml 존재 | `test -f {site_path}/config/_default/params.toml` | 파일 존재 |
| hugo.toml 부재 | `test ! -f {site_path}/hugo.toml` | **없어야** 패턴 A 적용 가능 |
| themes/blowfish 부재 | `test ! -d {site_path}/themes/blowfish` | 없거나 비어있어야 함 (있으면 다른 원인) |

**중단 조건 (이 스킬 범위 밖, needs_human)**:
- `config/_default/params.toml`이 없음 → params.toml도 생성 필요, 이 스킬은 hugo.toml만 담당
- `hugo.toml`이 이미 있음 → 다른 원인(설정 오류, 다른 테마 참조 등). 이 스킬은 hugo.toml **신규 생성**만 담당
- `themes/blowfish`가 이미 있음 → 테마는 있는데 빌드 실패, 다른 원인
- `themesDir`이 이미 hugo.toml에 설정되어 있음 (신규 생성 대상 아님)
- 위 어느 것도 명확하지 않음 → 진단 먼저

**esim-hugo 실제 상태** (참조):
- `site_path`: `/Users/twinssn/Projects/ETAP/esim-hugo` ✅
- `config/_default/params.toml`: 있음 ✅
- `hugo.toml`: 없었음 ✅ (패턴 A 대상)
- `themes/blowfish`: 없었음 ✅ (`themes/` 디렉토리는 있었지만 비어있었음)
- 근거: esim-hugo 배포 실패 로그 `module "blowfish" not found in ".../ETAP/esim-hugo/themes/blowfish"` (dispatcher.py 실행 시)

---

## 2. 원인 분기

```
hugo.toml 없음? ──No──> 이미 hugo.toml 있음 → 이 스킬 범위 밖 (needs_human)
     │
    Yes
     │
     ├─ themes/blowfish 있음? ──Yes──> 테마는 있음, 다른 원인 (needs_human)
     │
    No
     │
     └─> 패턴 A 적용: hugo.toml 신규 생성 + themesDir="/Users/twinssn/Projects/shared-themes"
```

패턴 A는 검증된 표준: CAP/CUAP/RAP/STAP(etf/ipo/finance)/기타 **35개 정상 블로그**가 동일 패턴(`theme="blowfish"` + `themesDir="/Users/twinssn/Projects/shared-themes"`)으로 동작 중.

---

## 3. 실행 절차 (약한 모델은 추론 없이 그대로 따라갈 것)

### a. 백업 (git tag)

```bash
cd /Users/twinssn/Projects/5000
git tag pre-{blog_id}-hugo-toml-{YYYYMMDD}
```

- 태그 명명 규칙: `pre-{blog_id}-hugo-toml-{YYMMDD}` (예: `pre-esim-hugo-hugo-toml-20260812`)
- blog_id 예: `esim-hugo`, `deals-hugo`
- 근거: AGENTS.md §파괴적 작업 프로토콜 (코드 수정 전 git tag)

```bash
# 기존 hugo.toml이 있었다면 백업 (없을 수도 있음 — esim은 없었음)
cp {site_path}/hugo.toml {site_path}/hugo.toml.bak_{YYYYMMDD} 2>/dev/null || true
```

### b. config/blogs.d/*.yaml에서 4개 값 추출

대상 blog_id의 `domain`, `name`, `language`를 `config/blogs.d/*.yaml`에서 추출한다.

**방법 1 (python3, 권장 — 정확)**:

```bash
cd /Users/twinssn/Projects/5000
python3 - <<'PYEOF'
import yaml, sys

blog_id = "{blog_id}"  # 실제 blog_id로 교체 (예: deals-hugo)

for fpath in sorted(__import__('glob').glob("config/blogs.d/*.yaml")):
    if ".bak" in fpath:
        continue
    with open(fpath) as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or "blogs" not in data:
        continue
    for b in data["blogs"]:
        if isinstance(b, dict) and b.get("id") == blog_id:
            domain = b.get("domain", "")
            name = b.get("name", blog_id)
            language = b.get("language", "en")
            print(f"DOMAIN={domain}")
            print(f"NAME={name}")
            print(f"LANGUAGE={language}")
            sys.exit(0)

print(f"ERROR: blog_id '{blog_id}'를 blogs.d에서 찾을 수 없음", file=sys.stderr)
sys.exit(1)
PYEOF
```

실행 결과 예시 (esim-hugo):
```
DOMAIN=esim.techpawz.com
NAME=eSIM Plans
LANGUAGE=en
```

**方法 2 (grep, 간단)**:

```bash
cd /Users/twinssn/Projects/5000
grep -A10 "id: {blog_id}" config/blogs.d/*.yaml | grep -E "domain:|name:|language:"
```

- 주의: YAML 필드 순서는 파일마다 다를 수 있음. `domain:`, `name:`, `language:` 라인을 개별적으로 확인.
- 근거: `config/blogs.d/etap.yaml` L193-207 (esim-hugo 정의: domain, name, language 등)

추출한 값:
- `DOMAIN` → `baseURL = "https://{DOMAIN}/"` 에 사용
- `NAME` → `title = "{NAME}"` 에 사용
- `LANGUAGE` → 언어 코드 결정에 사용 (아래 §4 언어 규칙)

### c. hugo.toml 생성

`{site_path}/hugo.toml`을 **신규 생성**한다. 기존 파일이 있었다면 위 a단계에서 백업했고, 이 단계에서 새로 쓴다.

**고정 상수 (모든 블로그 동일, 바꾸지 말 것)**:
```
theme = "blowfish"
themesDir = "/Users/twinssn/Projects/shared-themes"
enableRobotsTXT = true
```

**블로그별 변수 (§3b에서 추출한 4개 값 사용)**:

```
baseURL            = "https://{DOMAIN}/"
languageCode       = "{LANG_CODE}"
defaultContentLanguage = "{LANG_CODE}"
title              = "{NAME}"
```

**LANG_CODE 결정 규칙 (§4 참조)**: `LANGUAGE` 값이 `"en"`이면 `LANG_CODE="en"`, 그 외(또는 미지정)면 `LANG_CODE="ko"`.

**완성된 hugo.toml 예시 (esim-hugo 실제)**:

```toml
baseURL = "https://esim.techpawz.com/"
languageCode = "en"
defaultContentLanguage = "en"
title = "eSIM Plans"
theme = "blowfish"
themesDir = "/Users/twinssn/Projects/shared-themes"
enableRobotsTXT = true
```

**완성된 hugo.toml 예시 (deals-hugo, 이 스킬 테스트용)**:

```toml
baseURL = "https://deals.techpawz.com/"
languageCode = "en"
defaultContentLanguage = "en"
title = "Travel Deals Guide"
theme = "blowfish"
themesDir = "/Users/twinssn/Projects/shared-themes"
enableRobotsTXT = true
```

**작성 방법** (예시):

```bash
cat > {site_path}/hugo.toml <<'TOML'
baseURL = "https://{DOMAIN}/"
languageCode = "{LANG_CODE}"
defaultContentLanguage = "{LANG_CODE}"
title = "{NAME}"
theme = "blowfish"
themesDir = "/Users/twinssn/Projects/shared-themes"
enableRobotsTXT = true
TOML
```

**⚠️ 약한 모델 주의사항 — heredoc 방식의 함정**:

- 위 예시의 `<<'TOML'`(따옴표 붙은 구분자)은 **셸 변수 치환을 막는다**. 약한 모델이 이 예시를 그대로 따라하면서 `{DOMAIN}`을 실제 값으로 치환하지 않고 **리터럴 `{DOMAIN}` 그대로** 파일에 넣으면 잘못된 hugo.toml이 생성된다.
- 변수 치환을 위해 인용 없는 구분자(`<<TOML`)를 쓰면, `$` 등 특수문자를 이스케이프해야 하는 문제가 생길 수 있다.
- **실제 함정 사례 (2026-08-12 deals-hugo 테스트)**: 첫 시도에서 heredoc이 제대로 닫히지 않아 파일 내용에 `TOML && echo "생성 완료" && cat ...`가 잘못 들어갔음. 두 번째 시도에서 python3로 작성하여 성공.

**✅ 추천 방법 — python3로 작성 (heredoc 특수문자 문제 회피)**:

```bash
# {site_path}, {DOMAIN}, {NAME}, {LANG_CODE}를 실제 값으로 치환할 것
python3 - <<'PYEOF'
content = f"""baseURL = "https://{DOMAIN}/"
languageCode = "{LANG_CODE}"
defaultContentLanguage = "{LANG_CODE}"
title = "{NAME}"
theme = "blowfish"
themesDir = "/Users/twinssn/Projects/shared-themes"
enableRobotsTXT = true
"""
with open({site_path_repr}, "w") as f:
    f.write(content)
print(f"hugo.toml 작성 완료: {site_path}")
PYEOF
```

- 사용 예 (deals-hugo 실제):
```bash
python3 - <<'PYEOF'
content = """baseURL = "https://deals.techpawz.com/"
languageCode = "en"
defaultContentLanguage = "en"
title = "Travel Deals Guide"
theme = "blowfish"
themesDir = "/Users/twinssn/Projects/shared-themes"
enableRobotsTXT = true
"""
with open("/Users/twinssn/Projects/ETAP/deals-hugo/hugo.toml", "w") as f:
    f.write(content)
print("hugo.toml 작성 완료")
PYEOF
```
- 주의: python3 예제에서 `{site_path}` 등은 실제 경로로 치환해야 한다. f-string의 `{site_path}`와 혼동하지 말 것 — 위 예제는 이미 값이 치환된 형태.

- 주의: `{site_path}/hugo.toml` 전체 내용을 위 7라인으로 **덮어쓴다**. 기존에 다른 섹션이 있었어도 패턴 A는 이 7라인만으로 충분 (esim-hugo 검증 완료: 기존 hugo.toml 없었고 이 7라인으로 Hugo 빌드 성공).
- 근거: `compare-hugo/hugo.toml` L1-7 (패턴 A 모델 — 동일한 7개 키, 추가 섹션은 config/_default/params.toml에서 관리)
- 주의: `[params]`, `[pagination]`, `[taxonomies]` 등 추가 섹션은 **넣지 않는다**. 이 스킬은 패턴 A의 최소 구성(7라인)만 사용한다. 추가 섹션은 다른 블로그에서 params.toml로 관리되는 값이며, 이 스킬로 생성하지 않는다.

### d. 로컬 Hugo 빌드 검증 (배포 전 필수)

```bash
HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes \
  /opt/homebrew/bin/hugo --gc --minify --source {site_path}
```

**HUGO_THEMESDIR 설명 (약한 모델 헷갈림 방지)**:

- `HUGO_THEMESDIR`은 hugo.toml의 `themesDir` 설정을 **오버라이드**하는 환경변수다.
- hugo.toml에 `themesDir = "/Users/twinssn/Projects/shared-themes"`가 이미 올바르게 설정되어 있으면, `HUGO_THEMESDIR` 환경변수 없이도 Hugo가 해당 경로를 읽어서 빌드할 수 있다 (실제 검증: deals-hugo, 2026-08-12 — `HUGO_THEMESDIR` 없이 `/opt/homebrew/bin/hugo --gc --minify --source /Users/twinssn/Projects/ETAP/deals-hugo` 실행 → exit code 0, ERROR 없음, public/index.html 생성 확인).
- 따라서 `HUGO_THEMESDIR`은 **필수는 아니지만**, esim-hugo 검증 시 이 환경변수를 사용했으므로 호환성을 위해 설정하는 것을 권장한다.
- 확신이 없으면 스킬 문서의 예시대로 `HUGO_THEMESDIR`을 설정하는 것이 안전하다.

**성공 조건**: 
- exit code 0
- stderr에 `ERROR` 없음 (WARN `deprecated: .Site.Data`는 Hugo 자체 경고로 무시 가능)
- `public/index.html` 생성 확인: `test -f {site_path}/public/index.html`

**실패 시 즉시 중단**:
- `hugo.toml` 생성까지 완료했어도 빌드 실패하면 배포로 넘어가지 않는다
- 에러 원인 확인 후 이 스킬 범위 내면 수정, 범위 밖이면 needs_human
- 흔한 실패 원인: `themesDir` 경로 틀림, `theme` 이름 틀림, shared-themes에 blowfish 없음

**esim-hugo 실제 빌드 결과 (참조)**:
```
Hugo v0.160.1+extended
Pages: 360, Static files: 8, Processed images: 226, Aliases: 62
Total: 436ms
에러: 0건
public/index.html: 31,225 bytes
```
근거: esim-hugo 로컬 빌드 실행 로그 (2026-08-12 13:56)

### e. wrangler direct upload 배포 (실제 배포는 승인 후)

```bash
cd /Users/twinssn/Projects/5000
python3 dispatcher.py {blog_id}
```

- dispatcher.py는 내부적으로 Hugo 빌드 → wrangler pages deploy를 수행
- CLOUDFLARE_API_TOKEN 제거, Workers/Pages 자동 선택 등 처리
- 근거: AGENTS.md §Deployment Rules (dispatcher.py 사용, 수동 wrangler 금지)

**실제 배포는 별도 승인 필요** (이 스킬 문서 범위를 벗어나는 라이브 조치).

### f. 검증: P04 해소 + 라이브 HTTP 200

**대시보드 재검사**:

```bash
curl -s -X POST -u "${OPS_USER:-ops}:${OPS_PASSWORD}" \
  "http://localhost:5060/api/run-checks?blog_id={blog_id}"
```

**P04 상태 확인**:

```bash
curl -s -u "${OPS_USER:-ops}:${OPS_PASSWORD}" \
  "http://localhost:5060/api/registry?blog_id={blog_id}" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for e in d.get('errors',[]):
    if e.get('problem_id')=='P04':
        print(f\"P04 status={e.get('status')}\")
print('fail_checks에 P04 없음 = 해소됨' if not any('P04' in str(f.get('problem_id','')) for f in d.get('fail_checks',[])) else 'P04 still failing')
"
```

**라이브 HTTP 확인**:

```bash
curl -s -o /dev/null -w "HTTP %{http_code}\n" https://{DOMAIN}/
```

- 성공 조건: HTTP 200
- 근거: esim-hugo 배포 후 `https://esim.techpawz.com/` → HTTP 200 (30,914 bytes, 0.1초)
- P04 상태: `status=unknown` (fail 아님), fail_checks에 deploy_error 없음 (에스IM 배포 후 확인)

---

## 4. 언어 규칙 (약한 모델이 틀리기 쉬운 지점, 명확히)

config/blogs.d/*.yaml의 `language` 필드 값에 따라 `languageCode`와 `defaultContentLanguage`을 결정한다.

| `language` 값 | `languageCode` | `defaultContentLanguage` |
|---------------|----------------|--------------------------|
| `"en"` | `"en"` | `"en"` |
| `"ko"` 또는 그 외 값, 또는 미지정 | `"ko"` | `"ko"` |

- `language` 필드가 YAML에 없으면 기본값 `"en"`으로 간주하지 말고 `"ko"`로 처리 (5000은 한국어 블로그가 다수).
- 근거: config/blogs.d/etap.yaml에서 esim-hugo는 `language: en` → `languageCode: "en"` 적용. compare-hugo는 `language` 필드 없지만 한국어 블로그이므로 `languageCode: "ko"` (compare-hugo/hugo.toml L2).

**약한 모델 주의사항**: `language` 필드가 YAML에 없는데 "영어가 default겠지"라고 추측하지 말 것. 5000의 기본 가정은 한국어(`ko`). 확실하지 않으면 YAML에 `language` 필드가 있는지 확인하고, 없으면 `ko`로 처리.

---

## 5. needs_human / 중단 조건 (이 스킬 범위 밖)

다음 중 하나라도 해당하면 이 스킬로 처리하지 말고 humans에게 넘긴다:

1. **`config/_default/params.toml`이 없음** → params.toml도 생성해야 함. 이 스킬은 hugo.toml만 담당.
2. **`hugo.toml`이 이미 있음** → 이미 존재하는 hugo.toml의 다른 문제(설정 오류, 잘못된 테마 참조 등). 이 스킬은 hugo.toml **신규 생성**만 담당.
3. **`themes/blowfish`가 이미 있음** → 테마 파일은 있는데 빌드 실패. 다른 원인(설정 오류 등).
4. **로컬 Hugo 빌드 실패** → 원인 확인. 이 스킬 범위 내면( themesDir 경로 오류 등) 수정, 범위 밖이면 needs_human.
5. **`themesDir`을 이미 다른 값으로 설정해야 하는 경우** → shared-themes 외의 테마 경로 필요. 이 스킬은 shared-themes 기준.
6. **`blog_id`를 config/blogs.d/*.yaml에서 찾을 수 없음** → 블로그 정의 누락. 진단 먼저.
7. **예상과 다른 에러 메시지** → "module blowfish not found"가 아닌 다른 에러. 원인 진단 먼저.
8. **`domain` 필드가 없음** → baseURL 생성 불가. 대안 결정 필요.

---

## 6. 금지 사항

1. **41개 일괄 배포 금지** — 블로그 1개에 대해 hugo.toml 생성 → 로컬 빌드 검증 통과 후, 실제 배포는 승인 후 1개씩 진행. 승인 없이 일괄 배포하지 말 것.
2. **새 방식 고안 금지** — 이 스킬은 패턴 A(`theme="blowfish"` + `themesDir="/Users/twinssn/Projects/shared-themes"`)만 사용. TAP 방식(로컬 themes/blowfish 모듈 복사) 등 다른 방식은 이 스킬 범위 아님.
3. **`config/_default/params.toml` 임의 수정 금지** — 이 스킬은 hugo.toml 생성만 담당. params.toml은 건드리지 않는다 (이미 존재하는 경우 그대로 사용).
4. **`wrangler.toml` 삭제/수정 금지** — 이 스킬 범위 밖. Pages 블로그는 wrangler.toml 없이도 배포 가능.
5. **추가 섹션 추측 삽입 금지** — `[params]`, `[pagination]`, `[markup]` 등 다른 블로그 hugo.toml에 있는 섹션을 "일반적인 설정일 것"이라고 추측해서 넣지 말 것. 이 스킬은 7라인 최소 구성만 사용. esim-hugo 검증에서 이 7라인만으로 빌드 성공.
6. **`language` 필드 추측 금지** — YAML에 `language` 필드가 없으면 `en`으로 추측하지 말고 `ko`로 처리 (§4 언어 규칙).

---

## 7. 근거 (파일 경로·줄 번호)

### esim-hugo 카나리 실제 수행 내역

| 항목 | 값 / 경로 | 근거 |
|------|-----------|------|
| 대상 blog_id | `esim-hugo` | config/blogs.d/etap.yaml L193 |
| domain | `esim.techpawz.com` | config/blogs.d/etap.yaml L197 |
| name | `eSIM Plans` | config/blogs.d/etap.yaml L194 |
| language | `en` | config/blogs.d/etap.yaml L205 |
| site_path | `/Users/twinssn/Projects/ETAP/esim-hugo` | config/blogs.d/etap.yaml L203 |
| 생성 hugo.toml | `/Users/twinssn/Projects/ETAP/esim-hugo/hugo.toml` (7라인) | 실제 생성 파일 |
| 템플릿 모델 | `compare-hugo/hugo.toml` L1-7 | 패턴 A 검증된 모델 (CAP/CUAP/RAP/STAP 등 35개 블로그가 동일 패턴) |
| 백업 태그 | `pre-esim-hugo-hugo-toml-20260812` | git tag 생성 (AGENTS.md 파괴적 작업 프로토콜) |
| Hugo 빌드 명령 | `HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes /opt/homebrew/bin/hugo --gc --minify --source /Users/twinssn/Projects/ETAP/esim-hugo` | 실제 실행 명령 |
| Hugo 빌드 결과 | 에러 0건, 360페이지, public/index.html 31,225 bytes | esim-hugo 로컬 빌드 로그 (2026-08-12 13:56) |
| 실제 배포 | `python3 dispatcher.py esim-hugo` → 성공 | dispatcher.py 실행 로그 (2026-08-12 13:57) |
| 새 배포 ID | `87e1decd-8886-4c98-bdb6-f2251e4805a8` | wrangler pages deployment list (2026-08-12 13:58) |
| P04 해소 | `status=unknown`, fail_checks에 deploy_error 없음 | `/api/registry?blog_id=esim-hugo` 확인 (2026-08-12) |
| 라이브 HTTP 200 | `https://esim.techpawz.com/` → 200 (30,914 bytes, 0.1초) | curl 확인 (2026-08-12) |
| 신규 포스트 C04 | esim-bolivia: firstly/secondly 없음, 다른 C04 패턴 없음 | content_integrity._check_c04 검사 (2026-08-12) |

### 패턴 A 모델 (35개 정상 블로그가 동일 패턴)

| 블로그 | hugo.toml 경로 | themesDir | theme |
|--------|---------------|-----------|-------|
| compare-hugo | `/Users/twinssn/Projects/cap/compare-hugo/hugo.toml` | `/Users/twinssn/Projects/shared-themes` | blowfish |
| etf-hugo | `/Users/twinssn/Projects/STAP/etf-hugo/hugo.toml` | `/Users/twinssn/Projects/shared-themes` | blowfish |
| deal-hugo | `/Users/twinssn/Projects/cap/deal-hugo/hugo.toml` | `/Users/twinssn/Projects/shared-themes` | blowfish |
| health-hugo | `/Users/twinssn/Projects/cuap/health-hugo/hugo.toml` | `/Users/twinssn/Projects/shared-themes` | blowfish |
| rap-hugo | `/Users/twinssn/Projects/RAP/rap-hugo/hugo.toml` | `/Users/twinssn/Projects/shared-themes` | blowfish |

- 공통점: `theme = "blowfish"`, `themesDir = "/Users/twinssn/Projects/shared-themes"`, `enableRobotsTXT = true`
- 근거: 위 파일들의 L1-7 (첫 7라인이 동일 패턴)

### 사전 확인된 사실 (2026-08-12 조사 결과)

- ETAP 36개 + TAP 4개 + STAP 3개 + SEAP 1개 + CAP 2개 = **46개**가 hugo.toml 없음 (1차 판정)
- 그중 TAP 4개(travel/travel2~4)와 STAP 2개(dividend/sector-hugo)는 themes/blowfish 로컬 모듈 있음 → 실제 빌드 가능 → **41개**가 실제 배포 불가
- 41개 중 ETAP이 35개로 대부분
- 41개 모두 `config/_default/params.toml` 이미 존재 (샘플 10개 확인)
- dispatcher.py는 HUGO_THEMESDIR 환경변수를 설정하지 않음 (grep 결과 없음) → Hugo 빌드는 hugo.toml의 themesDir 설정 또는 site root/themes/ 기본값에 의존

---

## 8. 스킬 사용 예시 (완전한 흐름, esim-hugo 기준 재연)

```bash
# 0. 대상 확인
blog_id="esim-hugo"
site_path="/Users/twinssn/Projects/ETAP/esim-hugo"

# 1. 전제 조건 점검
test -d "$site_path"                    # ✅ site_path 실존
test -f "$site_path/config/_default/params.toml"  # ✅ params.toml 있음
test ! -f "$site_path/hugo.toml"        # ✅ hugo.toml 없음 (패턴 A 대상)
test ! -d "$site_path/themes/blowfish"  # ✅ themes/blowfish 없음

# 2. 백업
cd /Users/twinssn/Projects/5000
git tag pre-esim-hugo-hugo-toml-20260812
cp "$site_path/hugo.toml" "$site_path/hugo.toml.bak_20260812" 2>/dev/null || true

# 3. config/blogs.d/*.yaml에서 값 추출
python3 - <<'PYEOF'
import yaml, sys
blog_id = "esim-hugo"
for fpath in sorted(__import__('glob').glob("config/blogs.d/*.yaml")):
    if ".bak" in fpath: continue
    with open(fpath) as f: data = yaml.safe_load(f)
    if isinstance(data, dict) and "blogs" in data:
        for b in data["blogs"]:
            if isinstance(b, dict) and b.get("id") == blog_id:
                print(f"DOMAIN={b.get('domain','')}")
                print(f"NAME={b.get('name','')}")
                print(f"LANGUAGE={b.get('language','en')}")
                sys.exit(0)
PYEOF
# 결과: DOMAIN=esim.techpawz.com, NAME=eSIM Plans, LANGUAGE=en

# 4. hugo.toml 생성
DOMAIN="esim.techpawz.com"
NAME="eSIM Plans"
LANG_CODE="en"   # LANGUAGE=en → en

cat > /Users/twinssn/Projects/ETAP/esim-hugo/hugo.toml <<'TOML'
baseURL = "https://esim.techpawz.com/"
languageCode = "en"
defaultContentLanguage = "en"
title = "eSIM Plans"
theme = "blowfish"
themesDir = "/Users/twinssn/Projects/shared-themes"
enableRobotsTXT = true
TOML

# 5. 로컬 Hugo 빌드 검증
HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes \
  /opt/homebrew/bin/hugo --gc --minify --source /Users/twinssn/Projects/ETAP/esim-hugo
# → 에러 0건, public/index.html 생성 확인 ✅

# 6. (승인 후) 실제 배포
# python3 dispatcher.py esim-hugo

# 7. (배포 후) 검증
# curl -s -X POST -u "${OPS_USER}:${OPS_PASSWORD}" "http://localhost:5060/api/run-checks?blog_id=esim-hugo"
# curl -s -u "${OPS_USER}:${OPS_PASSWORD}" "http://localhost:5060/api/registry?blog_id=esim-hugo" → P04 status=unknown
# curl -s -o /dev/null -w "%{http_code}" https://esim.techpawz.com/ → 200
```
