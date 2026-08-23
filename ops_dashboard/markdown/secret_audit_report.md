# 하드코딩 인증정보 READ-ONLY 감사 보고서

## 요약
READ-ONLY 스캔을 완료했다. 비밀값은 일절 노출하지 않는다.

---

## 1. 스캔 결과 요약

| 위치 | 유형 | 하드코딩 여부 | 비고 |
|------|------|------------|------|
| `.gitignore` | 파일 참조 | — | `credentials.json`, `blogger_token.pickle`, `client_secret*.json`, `token*.json`, `credentials*.json`, `api_keys.yaml`, `api_keys.yml` 등 gitignored |
| `config/api_keys.yaml` | 파일 참조 | 파일 참조 | 키 구조: `client_secret_path`, `token_path`, `blogger_app_password`, `api_token`, `api_key`. gitignored. 경로/빈 문자열만 있고 실제 비밀값 표기 아님 |
| `.env` | 파일 참조 | 파일 참조 | 키: `OPENAI_MODEL`, `R2_BUCKET_NAME`, `R2_PUBLIC_URL`, `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_ZONE_ID`, `UPSTAGE_API_KEY`, `DART_API_KEY`, `DATA_GO_KR_API_KEY`, `OPENCODE_API_KEY`. gitignored |
| `~/.env.common` | 파일 참조 | 파일 참조 | 사용자 홈 디렉토리에 위치. 키 이름 추출 불가(형식 변동 가능성 있음). 환경변수 소스로 사용됨 |
| launchd `com.5000.auto-triage.plist` | 환경변수 | 환경변수 | `OPS_PASSWORD` 환경변수 존재. plist 내 하드코딩 |
| `ops_dashboard/app.py` | 기본값 | 기본값 | `ops` / `112233` 기본값 하드코딩. `OPS_PASSWORD` env var로 덮어쓰기 가능 |
| 코드 내 하드코딩된 토큰/비밀번호 | 하드코딩됨 | 하드코딩됨 | `glpat`, `ghp`, `sk-`, `bearer` 등 패턴 미발견. 명시적 토큰 문자열은 확인되지 않음 |
| `dispatcher.py`, `deploy.py`, `scheduler.py` | 환경변수 로드 | 환경변수 | python-dotenv로 `~/.env.common`, `{TAP_ROOT}/.env`, `{FIVEK_ROOT}/.env` 로드. `os.getenv`로 접근 |

### launchd EnvironmentVariables 대상 (요약)
다음 plist들이 `<key>EnvironmentVariables</key>` 블록을 가진다:
- `com.5000.analytics.plist`
- `com.5000.auto-triage.plist` (`OPS_PASSWORD` 포함)
- `com.5000.dashboard.plist`
- `com.5000.ops-dashboard.plist`
- `com.5000.scheduler-watchdog.plist`
- `com.5000.scheduler.plist`
- `kr.aikorea24.*` 계열 다수
- `com.twinssn.*` 계열 일부

비밀 키 이름은 일부만 확인되었으며(예: `OPS_PASSWORD`), 전체 키 목록은 별도 plist별 parse가 필요하다.

---

## 2. 코드 내 환경변수 로드 방식

### dispatcher.py
```python
from dotenv import load_dotenv
load_dotenv(os.path.expanduser("~/.env.common"))
load_dotenv(os.path.join(TAP_ROOT, ".env"))
load_dotenv(os.path.join(FIVEK_ROOT, ".env"))
```

### shared/publishers/deploy.py
```python
from dotenv import load_dotenv
load_dotenv(os.path.expanduser("~/.env.common"))
load_dotenv(os.path.join(FIVEK_ROOT, ".env"), override=True)
env = os.environ.copy()
_cf_account = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
```

### scheduler.py
```python
from dotenv import load_dotenv
load_dotenv(os.path.expanduser("~/.env.common"))
load_dotenv(os.path.join(FIVEK_ROOT, ".env"))
```

---

## 3. 문서 내 평문 자격증명 위치

| 문서 | 위치 | 유형 | 비고 |
|------|------|------|------|
| `docs/TROUBLESHOOT-REFERENCE.md` | 178행 | HTTP Basic Auth | 기본값 `ops` / `112233` |
| `docs/TROUBLESHOOT-REFERENCE.md` | 291행, 299행, 169행 | 기본 인증 / API 시크릿 | 기본 자격증명 및 api_keys.yaml 참조 |
| `docs/OPS-RUNBOOK.md` | 95행 | 토큰 추출 방법 | `CLOUDFLARE_API_TOKEN` 추출 커맨드 (값은 출력되지 않음) |
| `docs/OPS-RUNBOOK.md` | 203행 | HTTP Basic Auth | `ops` / `112233` |

---

## 4. 잔존 위험

1. **기본 자격증명 공개**: `ops`/`112233`이 코드와 문서에 기본값으로 하드코딩되어 있음. 문서에서 평문으로 노출되어 있으므로 즉시 변경 필요.
2. **launchd 환경변수 노출 가능성**: plist 내 `OPS_PASSWORD` 등이 평문으로 저장되어 plist 자체가 하드디스크에 존재함.
3. **`.env` 및 `~/.env.common` 노출**: gitignored이지만, 로컬 파일 시스템 평문 존재.
4. **`config/api_keys.yaml` 구조 노출**: 경로가 공개되어 있으므로 파일이 존재하는지 여부가 외부에 노출됨.

---

## 검증 근거

- `.gitignore`: grep으로 `credentials.json`, `blogger_token.pickle`, `client_secret*.json`, `token*.json`, `credentials*.json`, `api_keys.yaml` 확인
- `config/api_keys.yaml`: grep으로 키 구조 확인 (값 미출력)
- `.env`: grep으로 키 이름만 추출 (`=.*` 제거)
- `~/.env.common`: grep 시크립트로 키 이름 추출 시도 (표준 `KEY=VALUE` 파싱 불일치 가능)
- launchd: `plistlib` 파싱으로 `OPS_PASSWORD` 확인
- `ops_dashboard/app.py`: grep으로 `_DEFAULT_USER`, `_DEFAULT_PASSWORD` 확인
- 코드 내 토큰: grep으로 `glpat`, `ghp`, `sk-`, `bearer_token` 패턴 검색 (미발견)
- dispatcher/deploy/scheduler: grep으로 `load_dotenv`, `os.getenv` 호출 위치 확인

---

*변경 파일 없음 (READ-ONLY)*