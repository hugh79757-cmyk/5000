# P0_ROTATION_REPORT.md — 대시보드 비밀번호 순환 결과

> 실행 일시: 2026-08-18
> 대상: ops_dashboard 기본 자격증명 하드코딩 제거 + 신규 비밀번호 순환

---

## 1. 변경 파일

| 파일 | 변경 내용 |
|------|----------|
| `ops_dashboard/app.py` | `_DEFAULT_USER`/`_DEFAULT_PASSWORD` 상수 삭제, `_get_auth_credentials()` fail-closed 전환 (env var 없으면 RuntimeError), `create_app()`의 env var 참조 수정 |
| `.env` | `OPS_USER`, `OPS_PASSWORD` 추가 (따옴표 포함, 특수 문자 처리) |
| `com.5000.auto-triage.plist` | `OPS_USER`/`OPS_PASSWORD` 평문 환경변수 제거 → env_loader를 통한 .env 로드로 전환 |

---

## 2. 백업

| 백업 파일 | 원본 |
|----------|------|
| `ops_dashboard/app.py.pre-p0-rotation` | app.py 수정 전 |
| `logs/com.5000.auto-triage.plist.bak_20260818_*` | auto-triage.plist 수정 전 |

---

## 3. 검증 결과

| 검증 항목 | 방법 | 결과 |
|----------|------|------|
| 미인증 접근 | `curl http://localhost:5060` | **HTTP 401 ✅** |
| 기존 비밀번호 접근 | `curl -u ops:112233 http://localhost:5060` | **HTTP 401 ✅** |
| 신규 비밀번호 접근 | `curl -u ops:{new_password} http://localhost:5060` | **HTTP 200 ✅** |
| 신규 비밀 코드/문서 노출 | `grep -rl` (docs/, ops_dashboard/, shared/) | **0건 ✅** |
| OLD 비밀 plist 잔존 | `grep '112233' auto-triage.plist` | **0건 ✅** |
| .env 권한 | `stat -f '%Lp' .env` | **600 ✅** |
| plist 권한 | `stat -f '%Lp' auto-triage.plist` | **600 ✅** |
| 서비스 상태 | `launchctl list \| grep ops-dashboard` | **PID 42505, exit 0 ✅** |

---

## 4. 파일 권한

| 파일 | 권한 | 의미 |
|------|------|------|
| `.env` | 600 | 소유자 읽기/쓰기만 허용 |
| `com.5000.auto-triage.plist` | 600 | 소유자 읽기/쓰기만 허용 |

---

## 5. 아키텍처 변경

**변경 전:**
```
app.py: _DEFAULT_PASSWORD = "112233" (하드코딩)
  → os.environ.get("OPS_PASSWORD", _DEFAULT_PASSWORD) (env 없으면 기본값 사용)
```

**변경 후:**
```
app.py: _get_auth_credentials()
  → os.environ.get("OPS_PASSWORD") (env 없으면 RuntimeError → 서비스 시작 거부)
  
.env: OPS_PASSWORD="{new_password}" (따옴표로 특수 문자 보호)
  → env_loader.py가 shared 모듈 import 시 자동 로드

auto-triage.plist: OPS_PASSWORD 평문 제거
  → env_loader.py가 auto_triage.py import 시 .env에서 로드
```

---

## 6. 잔존 위험

1. **`~/.env.common`에 OPS_PASSWORD가 있다면** 충돌 가능 — `.env`의 `override=True`가 우선 적용하나 확인 필요
2. **다른 docs/ 파일에도 평문 비밀 잔존 가능** — APPENDIX_C, APPENDIX_D, DASHBOARD_OPS_RUNBOOK 등에서 `ops:112233` 패턴 검색 필요
3. **git 이력에 OLD 비밀 잔존 가능** — 과거 커밋에 `112233`이 포함되어 있다면 git history에 영구 노출
4. **RBAC 없음** — 비밀 변경으로도 역할 분리 불가

---

## 7. 롤백 절차 (이전 비밀 복원 금지)

만약 문제가 발생하면:
1. 이전 비밀번호(`112233`)로 **절대 복원하지 않음**
2. 별도의 **새로운 비밀번호**를 생성하여 재교체
3. `ops_dashboard/app.py.pre-p0-rotation`에서 `_get_auth_credentials()` 로직만 참고하여 적용

---

*이 보고서는 P0-1 조치만 포함합니다. P1/P2/P3 작업은 별도 보고서에서 수행.*
