# P04 배포 실패 자동수정 스킬

> 매핑 출처: `ops_dashboard/docs/agent-reference/PLAYBOOK_INDEX.yaml` → P04
> playbook_ref: `ERROR_PLAYBOOKS.md#p04`
> automation_level: `human_approval` (코드 제안 가능, 실제 재배포는 승인 필요)
> 최종 갱신: 2026-08-12

## 입력

P04 알림 텍스트. 여러 블로그 ID가 포함될 수 있다.

예:
```
[CRITICAL] 배포 실패
블로그: cruise-hugo
문제: P04 — 배포 실패 (deploy_error)
감지 단계: post_deploy
```

다수의 블로그가 동시에 P04인 경우, 알림을 그대로 입력으로 사용한다.

## 사전 확인 (반드시 먼저)

### 1. PLAYBOOK_INDEX.yaml에서 P04 조회

```bash
cd /Users/twinssn/Projects/5000
python3 -c "
import yaml
d = yaml.safe_load(open('ops_dashboard/docs/agent-reference/PLAYBOOK_INDEX.yaml'))
p04 = next((c for c in d['codes'] if c['code']=='P04'), None)
if not p04:
    print('ERROR: P04 항목이 PLAYBOOK_INDEX.yaml에 없음')
else:
    print('playbook_ref:', p04['playbook_ref'])
    print('target_files:', [t['path'] for t in p04['target_files']])
    print('verify:', p04['verify'])
    print('automation_level:', p04['automation_level'])
"
```

### 2. 실제 실패 로그 확인

P04의 실제 원인을 알기 위해 로그를 확인한다. 로그가 없으면 "로그 미확인 — 진단 불완전"로 표기하고 코드 확인만으로 진행한다.

```bash
# 최근 배포 로그에서 해당 블로그 검색
grep -n "{blog_id}" logs/deploy.log | tail -5

# 트리아지 로그
grep -n "{blog_id}" logs/auto_triage.out.log | tail -5
grep -n "P04\|deploy_error" logs/auto_triage.err.log | tail -5
```

**로그를 찾을 수 없으면:** "로그 미확인 — 진단 불완전. 코드 확인만으로 판정함"이라고 명시.

## 원인 분기

### 분기 A: 인증 오류 (가장 흔함)

**징후:**
- `deploy.log`에 `Authentication error code: 10000` 또는 `Failed to automatically retrieve account IDs`
- `Active profile: hugh79757` 대신 다른 계정 또는 프로필 없음
- `wrangler deploy` 실행 시 인증 실패

**확인 명령:**
```bash
# 현재 wrangler 프로필 확인
cd /Users/twinssn/Projects/5000
wrangler whoami 2>&1 | head -5

# deploy.py의 토큰 제거 로직 확인
grep -n "CLOUDFLARE_API_TOKEN" shared/publishers/deploy.py
# 기대 결과:
#   76:     # CLOUDFLARE_API_TOKEN 제거 — agent 세션에서 설정된 token이
#   78:     _wrangler_env.pop("CLOUDFLARE_API_TOKEN", None)

# dispatcher.py의 토큰 제거 로직 확인
grep -n "CLOUDFLARE_API_TOKEN" dispatcher.py
# 기대 결과:
#   757:             # wrangler auth profile 우선 — CLOUDFLARE_API_TOKEN env var 해제
#   759:             deploy_env = {k: v for k, v in os.environ.items() if k != "CLOUDFLARE_API_TOKEN"}
```

**수정 방법:**

코드에 토큰 제거 로직이 이미 적용돼 있으면 추가 수정 불필요. 미적용 상태면 아래를 적용:

**shared/publishers/deploy.py** (현재 76-78행):
```python
def _wrangler_env(blog_id: str) -> dict:
    env = os.environ.copy()
    # ★ 중요: CLOUDFLARE_API_TOKEN 제거 — agent 세션에서 설정된 token이
    # OAuth auth profile보다 우선 적용되어 잘못된 계정으로 배포됨
    env.pop("CLOUDFLARE_API_TOKEN", None)
    return env
```

**dispatcher.py** (현재 757-759행):
```python
deploy_env = {k: v for k, v in os.environ.items() if k != "CLOUDFLARE_API_TOKEN"}
```

### 분기 B: Hugo 빌드 실패

**징후:**
- `deploy.log`에 `ERROR` 또는 Hugo 관련 에러 메시지
- `Start building sites ...` 이후 에러
- `hugo v0.160.1` 버전 정보 다음에 에러

**확인 명령:**
```bash
# 빌드 실패 로그 확인
grep -A5 "ERROR\|error\|Error" logs/deploy.log | tail -30
```

**수정 방법:** ERROR_PLAYBOOKS.md#p05 참조. 테마/경로/Front Matter 문법 문제.

### 분기 C: 계정 ID 불일치 / 프로젝트 매핑 오류

**징후:**
- Wrangler가 잘못된 계정으로 배포 시도
- `wrangler whoami`에 기대한 계정(hugh79757)이 아닌 다른 계정 표시
- Workers 블로그(health/pet/kitchen/beauty/camping/baby)용 `wrangler.toml` 설정 문제

**확인 명령:**
```bash
# wrangler 프로필 확인
env -u CLOUDFLARE_API_TOKEN wrangler whoami 2>&1

# 8개 블로그가 Workers 타입인지 Pages 타입인지 확인
grep -A2 "WORKERS_BLOGS" dispatcher.py
```

**수정 방법:** 워커/페이지 구분 확인, wrangler.toml 계정 설정 확인.

## 절차 (약한 모델용 결정론적 단계)

**입력:** P04 알림 텍스트

```
STEP 1: 알림에서 blog_id 추출
  - 텍스트에서 "블로그: {blog_id}" 패턴 찾기
  - 여러 블로그면 모두 추출 (쉼표 구분 리스트)
  - 기대: cruise-hugo, culture-hugo, daytrips-hugo, esim-hugo, eurail-hugo, ferry-hugo, flights-hugo, foodtour-hugo

STEP 2: 로그 확인
  - logs/deploy.log에서 각 blog_id 검색
  - 실제 실패 메시지 확인 (인증/빌드/계정 분류)
  - 로그 없으면 "로그 미확인" 표기

STEP 3: 원인 분기 판정
  - 인증 오류 패턴 → 분기 A
  - Hugo 빌드 오류 패턴 → 분기 B
  - 계정/프로젝트 불일치 패턴 → 분기 C
  - 로그 없음 → 코드 확인만으로 "추정: 인증 오류" 또는 "추정: 불명"

STEP 4: 분기 A인 경우 (인증 오류)
  ① dispatcher.py:757-759 토큰 제거 로직 확인
  ② shared/publishers/deploy.py:76-78 토큰 제거 로직 확인
  ③ 둘 다 적용돼 있으면: "코드상 문제 없음. 재배포 시도"
  ④ 미적용 상태면: 코드 수정 후 재검사

STEP 5: 분기 B인 경우 (빌드 실패)
  ① ERROR_PLAYBOOKS.md#p05 확인
  ② Hugo 빌드 오류 로그 분석
  ③ 테마/경로/Front Matter 수정
  ④ Hugo 빌드 로컬 검증

STEP 6: 분기 C인 경우 (계정 불일치)
  ① wrangler whoami 확인
  ② dispatcher.py의 WORKERS_BLOGS / Pages 구분 확인
  ③ wrangler.toml 확인 (Workers 블로그인 경우)

STEP 7: 재배포 (★ 사람 승인 필요)
  - dispatcher.py로 배포: python3 /Users/twinssn/Projects/5000/dispatcher.py {blog_id}
  - 절대 수동 wrangler 명령어 금지
  - 절대 --commit-dirty=true 금지
  - git push로 배포하지 말 것
```

## 재배포 명령 (정확한 형식)

```bash
# 단일 블로그 재배포 (글 생성 + 발행 + 배포)
python3 /Users/twinssn/Projects/5000/dispatcher.py {blog_id}

# 예: cruise-hugo
python3 /Users/twinssn/Projects/5000/dispatcher.py cruise-hugo
```

**중요 규칙 (AGENTS.md §Deployment Rules):**
1. **절대 수동 wrangler 명령어 금지** — Worker/Pages 구분이 꼬임
2. **`--commit-dirty=true` 사용 금지** — git commit 생성 → Cloudflare Pages 자동 빌드 트리거
3. **git push로 배포하지 말 것** — 월 500회 제한 소진
4. `CLOUDFLARE_API_TOKEN` 환경변수 제거는 dispatcher.py가 자동 처리

## 검증

### 재배포 전 검증
```bash
# Hugo 빌드 로컬 검증 (배포 전에 반드시)
HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes hugo --gc --minify --source /path/to/{blog_id}
# 에러 0건 확인
```

### 재배포 후 검증
```bash
# 1. 대시보드 재검사 트리거
curl -s -X POST -u "${OPS_USER:-ops}:${OPS_PASSWORD}" \
  "http://localhost:5060/api/run-checks?blog_id={blog_id}"

# 2. /api/registry에서 P04 상태 확인
curl -s -u "${OPS_USER:-ops}:${OPS_PASSWORD}" \
  "http://localhost:5060/api/registry?blog_id={blog_id}" | python3 -m json.tool | grep -A3 '"problem_id": "P04"'

# 3. /api/attention에서 fail_checks 확인
curl -s -u "${OPS_USER:-ops}:${OPS_PASSWORD}" \
  "http://localhost:5060/api/attention" | python3 -m json.tool | grep "{blog_id}"
```

**FAIL→PASS 확인 없이 완료 보고 금지.**

## needs_human 조건 (자동 수정 불가)

다음 경우 자동으로 진행하지 말고 사람에게 보고:

1. **실제 실패 로그가 없어서 원인 불명** — "로그 미확인. 재배포 전에 로그 확인 필요"
2. **Wrangler 인증 정보 자체가 없음** — `wrangler whoami`가 실패하거나 프로필 없음. OAuth 프로필 재인증 필요:
   ```bash
   env -u CLOUDFLARE_API_TOKEN wrangler auth create hugh79757
   ```
3. **Hugo 빌드 자체가 실패** — 로컬 빌드 에러 발생. 테마/콘텐츠 문제 가능성. ERROR_PLAYBOOKS.md#p05 참조.
4. **8개 블로그 중 일부만 실패하면** — 개별 블로그 설정(YAML) 확인 필요
5. **재배포 후에도 P04 재발** — 원인 재진단 필요

## 근거 (참조 파일·줄 번호)

| 항목 | 파일 | 줄 번호 | 내용 |
|------|------|---------|------|
| P04 플레이북 매핑 | ops_dashboard/docs/agent-reference/PLAYBOOK_INDEX.yaml | P04 항목 | playbook_ref/target_files/verify/automation_level |
| P04 플레이북 본문 | ops_dashboard/docs/agent-reference/ERROR_PLAYBOOKS.md | `<a id="p04"></a>` 행 부근 | "빌드·배포 명령의 실제 실패 지점만 수정" |
| 토큰 제거 (deploy.py) | shared/publishers/deploy.py | 76-78 | `_wrangler_env.pop("CLOUDFLARE_API_TOKEN", None)` |
| 토큰 제거 (dispatcher.py) | dispatcher.py | 757-759 | `deploy_env = {... if k != "CLOUDFLARE_API_TOKEN"}` |
| 배포 명령 | dispatcher.py | - | `python3 dispatcher.py {blog_id}` |
| Hugo 빌드 검증 | AGENTS.md | §Technology Stack | `HUGO_THEMESDIR=... hugo --gc --minify` |
| 배포 규칙 | AGENTS.md | §Deployment Rules | 수동 wrangler·commit-dirty·git push 금지 |

## 공통 원인 가설: 8개 ETAP 블로그 동시 실패

8개 블로그(cruise/culture/daytrips/esim/eurail/ferry/flights/foodtour-hugo)는 모두 ETAP 계열(`informationhot.kr` 도메인). 동시 P04는 공통 원인 가능성이 높다:

- **가설 1 (인증):** CLOUDFLARE_API_TOKEN 환경변수가 OAuth 프로필(hugh79757)을 덮어써서 wrangler가 잘못된 계정으로 배포 시도 → **코드 수정 적용돼 있음 (deploy.py:78, dispatcher.py:759)**
- **가설 2 (계정):** Wrangler 프로필 자체가 없거나 만료됨 → `wrangler whoami`로 확인 필요
- **가설 3 (설정):** blogs.d ETAP YAML의 cf_project/site_path 설정 오류 → YAML 확인 필요

**가설 1이 코드상 수정돼 있으므로**, 현재 실패가 가설 1 때문인지 확인하려면 실제 deploy.log에서 인증 오류 메시지를 찾아야 한다. **로그 미확인 상태에서는 가설 1을 확정할 수 없음.**
