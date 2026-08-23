# P1_PUSH_READINESS.md

> **조사 시각**: 2026-08-18 23:20 KST
> **목적**: P0 원격 반영 준비 상태 조사 — branch 생성/checkout/fetch/cherry-pick/push/merge/rebase/reset/tag/배포 **수행 없음**

---

## 1. 커밋 그래프 + 선후관계

```
origin/main: a788f0bbc ──── (85건 ahead) ────▶ 5c757cc17 ──▶ 67227b610 ──▶ 03740d8a
               │                                      │            │            │
               │                               pre-P0 HEAD     P0-1        P0-2 (현재 HEAD)
               │
               └── 공통 조상 (common ancestor)
```

| 항목 | SHA | 비고 |
|------|-----|------|
| origin/main | `a788f0bbc` | `git ls-remote origin main` 확인 |
| 공통 조상 | `a788f0bbc` | origin/main과 동일 (anel up 없음) |
| pre-P0 HEAD | `5c757cc17` | 85건 미푸시 커밋의 최신 |
| P0-1 | `67227b610` | `5c757cc17` 위 |
| P0-2 | `037404d8a` | `67227b610` 위 (현재 HEAD) |

**선후관계 확정:**
- `a788f0bbc` → (85건) → `5c757cc17` → `67227b610` (P0-1) → `037404d8a` (P0-2)
- P0 커밋 2건은 **85건의 직후**에 위치
- 총 ahead: **87건** (85 + P0-2)

---

## 2. 반영 방안 비교

### 방안 A: 전체 87건 순차 push

```
git push origin main
```

| 평가 항목 | 결과 |
|-----------|------|
| 충돌 위험 | **없음** — ahead만 존재, behind 0건 |
| 테스트 영향 | 87건 전부 단일 push → 빌드/배포 시 전체 영향 |
| 리뷰 난이도 | **어려움** — 87건 혼재, 보안 변경 식별 불가 |
| 롤백 | `git revert`로 개별 커밋 되돌리기 가능하나, 87건 중 P0 2건 추적 어려움 |
| **보안 위험** | ⚠️ 보안 커밋이 85건 기능 변경에 묻힘 |

### 방안 B: 보안 브랜치 분리 push

```
# 브랜치 생성 (checkout 없이)
git branch security/p0-dashboard-auth a788f0bbc
# → cherry-pick P0-1, P0-2
# → push security/p0-dashboard-auth
# → PR 생성 → review → merge → main push
```

| 평가 항목 | 결과 |
|-----------|------|
| 충돌 위험 | **없음** — P0 커밋은 85건과 독립 (app.py, 코드/문서 파일만 변경) |
| 테스트 영향 | P0 2건만 격리 테스트 가능 |
| 리뷰 난이도 | **쉬움** — P0 2건만 diff, 12건 파일 |
| 롤백 | 브랜치 revert 또는 PR close로 즉시 롤백 |
| **보안 위험** | ✅ 보안 변경 격리, 명확한 감사 추적 |

### 방안 비교 요약

| 기준 | 방안 A (전체 push) | 방안 B (보안 브랜치) |
|------|-------------------|---------------------|
| 충돌 | 없음 | 없음 |
| 테스트 | 전체 영향 | P0 격리 |
| 리뷰 | 87건 혼재 | 2건 명료 |
| 롤백 | 개별 revert | 브랜치 관리 |
| 보안 감사 | 묻힘 | 격리 |
| **권장** | | **✅ 권장** |

---

## 3. test_publish_errors 회귀 여부 판정

**증명 과정:**
1. P0-2 이전 커밋 `67227b610`에서 동일 테스트 실행
2. 동일하게 4건 `ERROR` 발생 — `ops.db 경로 guard` 실패
3. P0-2(`037404d8a`)는 `conftest.py` 변경 없음, auth header만 변경

**결론:**

| 항목 | 판정 |
|------|------|
| P0-2 이전 동일 실패 | **확인** ✅ |
| P0-2가 guard 로직 변경 | **아니오** — auth header만 변경 |
| 회귀 여부 | **회귀 아님** — 사전 존재하는 문제 |
| 근본 원인 | `test_publish_errors.py`가 `OPS_DB_PATH`를 monkeypatch하지 않아 운영 ops.db 경로 사용 |
| 기존 21건 실패 포함 | **미확인** — `STATE.md:338`의 21건 목록에 별도 기재 필요 |

---

## 4. 신규 환경 OPS_USER/OPS_PASSWORD 주입 체크리스트

| # | 체크 항목 | 현재 상태 | 비고 |
|---|-----------|-----------|------|
| 1 | `.env`에 `OPS_USER`/`OPS_PASSWORD` 항목 존재 | ✅ 있음 | 값은 비밀 — 존재만 확인 |
| 2 | `.env` 권한 600 | ✅ `-rw-------` | 소유자 읽기/쓰기만 허용 |
| 3 | `shared/env_loader.py`가 `.env` 로드 | ✅ `override=True` | `.env` > `~/.env.common` 순서 |
| 4 | `~/.env.common`에 OPS_USER/OPS_PASSWORD | ❌ 없음 | `.env`가 유일한 소스 |
| 5 | launchd plist에 OPS_PASSWORD 주입 | ❌ 없음 | env_loader가 `.env`에서 로드 |
| 6 | `.env.example` 템플릿 존재 | ❌ 없음 | **신규 환경 온보딩 시 가이드 필요** |
| 7 | `ops_dashboard/app.py` fail-closed | ✅ 적용 | env 없으면 RuntimeError |
| 8 | `.gitignore`에 `.env` 포함 | ✅ 포함 | 비밀 유출 방지 |

**신규 환경 온보딩 절차:**
```bash
# 1. .env 생성 (비밀값은 직접 입력)
cp /dev/null .env
echo 'OPS_USER=ops' >> .env
echo 'OPS_PASSWORD="{안전한_32자리_값}"' >> .env

# 2. 권한 설정
chmod 600 .env

# 3. 검증
python3 -c "from ops_dashboard.app import _get_auth_credentials; print(_get_auth_credentials())"
```

---

## 5. 권장 push/PR 절차

### 권장: 방안 B (보안 브랜치 분리)

**대상 커밋 SHA:**
- P0-1: `67227b610`
- P0-2: `037404d8a`

**단계:**

```
Step 1: 보안 브랜치 생성 (checkout 없이)
  git branch security/p0-dashboard-auth 67227b610

Step 2: P0-2 cherry-pick
  git checkout security/p0-dashboard-auth
  git cherry-pick 037404d8a

Step 3: 보안 브랜치 push
  git push origin security/p0-dashboard-auth

Step 4: PR 생성 (GitHub)
  base: main
  head: security/p0-dashboard-auth
  title: fix(security): P0 dashboard credential hardcoding removal
  reviewers: 보안 검토자

Step 5: PR merge (스쿼시 또는 일반 merge)
  → main에 P0 2건 반영

Step 6:残り 85건 push
  git checkout main
  git push origin main
  → 85건 + P0 2건 = 87건
```

** 롤백 시나리오:**
```
PR merge 전: PR close 또는 branch 삭제
PR merge 후: git revert {merge-commit-sha}
```

### 대안: 방안 A (전체 push — 보안 브랜치 불가 시)

```
git push origin main
```

- 87건 단일 push
- 롤백: `git revert` 개별 커밋

---

## 6. 요약

| 항목 | 값 |
|------|-----|
| origin/main SHA | `a788f0bbc` |
| 로컬 HEAD | `03740d8a` (P0-2) |
| ahead | **87건** (85 + P0-2) |
| P0-1 SHA | `67227b610` |
| P0-2 SHA | `037404d8a` |
| test_publish_errors 회귀 | **아니오** — 사전 존재 |
| 권장 방안 | **방안 B: 보안 브랜치 분리** |
| env_loader 준비 | ✅ 완료 (단, .env.example 부재) |

---

> **이 문서는 조사 전용입니다. branch 생성/checkout/fetch/cherry-pick/push/merge/rebase/reset/tag/배포는 수행하지 않았습니다.**
