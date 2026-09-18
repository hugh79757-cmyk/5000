# B1-PREFLIGHT — 5000 리포 공개 전환 사전 검증

**실시일시**: 2026-09-18  
**대상**: `hugh79757-cmyk/5000` origin/main 공개 전환 전 읽기 전용 스캔

---

## 1. 크리덴셜 전수 스캔 (git history + working tree)

| 패턴 | 히스토리 히트 | 워킹 트리 히트 | 비고 |
|------|--------------|---------------|------|
| `ghp_` (GitHub PAT) | 0 | 0 | — |
| `pickle` (blogger_token 등) | 0 | 0 | `.gitignore`에 `*.pickle` 차단 |
| `ga4_admin_*.json` | 0 | 0 | `.gitignore`에 `ga4_admin_*.json` 차단 |
| `.sa_creds` (SearchAdvisor 평문) | 0 | 0 | `.gitignore`에 `.sa_creds_tmp` 차단 |
| `env.common` 평문 잔류 | 0 | 0 | `~/.env.common` 로컬만, 리포 미포함 |
| API 키 하드코딩 (`OPENAI_API_KEY=` 등) | 0 | 0 | 전부 `${{ secrets.XXX }}` 또는 `os.getenv()` |

**결과**: **PASS** — 커밋 이력/워킹 트리 어디에도 평문 시크릿 없음.

---

## 2. '어뷰징' 등 커밋 메시지 문구 건수

```bash
git log --all --oneline --grep="abusive"   # 0건
git log --all --oneline --grep="어뷰징"    # 0건
```

**결과**: **0건** — 관련 문구 커밋 없음.

---

## 3. .gitignore 라이브 확인

| 보호 대상 | .gitignore 규칙 | `git check-ignore` 검증 |
|----------|----------------|------------------------|
| `.env` | `.env` (line 1) | ✅ ignored |
| `config/api_keys.yaml` | `config/api_keys.yaml` (line 2) | ✅ ignored |
| `blogger_token.pickle` | `blogger_token.pickle` (line 12) | ✅ ignored |
| `*.pickle` | `*.pickle` (line 13) | ✅ ignored |
| `*.db` | `*.db` (line 14), `data/*.db` (line 22) | ✅ ignored |
| `ga4_admin_*.json` | `ga4_admin_*.json` (line 96) | ✅ ignored |
| `.sa_creds_tmp` | `.sa_creds_tmp` (line 117) | ✅ ignored |
| `naver_captcha*.txt` | `naver_captcha*.txt` (line 118) | ✅ ignored |
| `data/llm_rotation_state.json` | `data/llm_rotation_state.json` (line 120) | ✅ ignored |
| `data/.lock_*` | `data/.lock_*` (line 121) | ✅ ignored |
| `ops_dashboard/logs/` | `ops_dashboard/logs/` (line 126) | ✅ ignored |
| `**/client_secret*.json` | line 47 | ✅ ignored |
| `**/*token*.json` | line 48 | ✅ ignored |
| `**/*token*.pickle` | line 49 | ✅ ignored |
| `**/credentials*.json` | line 50 | ✅ ignored |
| `**/api_keys.yaml` | line 51 | ✅ ignored |

**결과**: **PASS** — 모든 민감 파일 패턴이 gitignore로 차단됨.

---

## 4. GitHub Actions 워크플로 보안 확인

| 체크 항목 | 상태 | 비고 |
|----------|------|------|
| `pull_request_target` 트리거 부재 | ✅ 없음 | `schedule` + `workflow_dispatch`만 사용 |
| Secrets 직접 echo 부재 | ✅ 없음 | `${{ secrets.XXX }}` 패턴만 사용, 로그 마스킹(`***`) 확인됨 |
| `CAP_PAT` 사용 시 x-access-token 패턴 | ✅ 정상 | `https://x-access-token:${{ secrets.CAP_PAT }}@github.com/...` |

**결과**: **PASS** — 워크플로 보안 설정 정상.

---

## 5. 종합 판정

| 영역 | 결과 |
|------|------|
| 크리덴셜 스캔 | **PASS** |
| 어뷰징 문구 | **0건 (PASS)** |
| .gitignore 커버리지 | **PASS** |
| 워크플로 보안 | **PASS** |

**최종**: **B1 공개 전환 진행 가능** — 차단 사유 없음.

---

*생성: `bash` + `git` + `gh` 실측 기반*