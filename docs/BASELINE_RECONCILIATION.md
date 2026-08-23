# BASELINE_RECONCILIATION.md — 보고 간 충돌 분석 및 최종 확정값

> 기반: 2026-08-18 정밀 조사 (4개 워커 병렬 검증)
> 목적: 기존 보고서들 간 수치·사실 충돌을 정리하고 최종 확정값을 기록

---

## 1. 충돌 분석 표

| 항목 | CURRENT_STATE.md | STATE.md | audit_manifest.json | gate_review.md | verdict.json | 충돌 여부 |
|------|-----------------|----------|---------------------|----------------|--------------|----------|
| 블로그 수 | 85(config), 78(감사), 80(내부링크) | 미언급 | 85(registry), 81(site_path) | 85 | 85 | **부분 충돌** — 동일 문서 내 85/78/80 공존 |
| NO_INTERNAL_LINKS | 18,522(최종), 18,542(원시) | 미언급 | 미언급 | 18,542 | 18,542 | **충돌** — 18,522 vs 18,542 |
| 템플릿 유출 | 2건(라이브), 92.5%오탐율 | 미언급 | 미언급 | 5,097(오탐), LIVE 2 | 5,097, LIVE 2 | **충돌 아님** — 개념 차이 |
| 404 | 2건 | 미언급 | 미언급 | 미언급 | 미언급 | 없음 |
| 테스트 실패 | 21건(사전 baseline) | 미언급 | 미언급 | 미언급 | 미언급 | 없음 |
| 평균 품질 점수 | 87.1(794건 표본) | 미언급 | 87.1 | 87.1(PROVISIONAL) | 87.1 | 없음 |

---

## 2. 충돌 항목 상세 분석

### 2.1 블로그 수 — 85/78/80 세 수치 공존

**발견:** CURRENT_STATE.md 내에서 세 다른 수치가 별도 기준 없이 사용됨.

| 수치 | 기준 | 출처 |
|------|------|------|
| 85 | config/blogs.d/*.yaml 전체 등록 | audit_manifest, gate_review, ROADMAP |
| 81 | mechanical_all.jsonl 고유 블로그 (4 Blogger 제외) | 기계 감사 |
| 80 | NO_INTERNAL_LINKS 합계 블로그 수 (ratio_by_blog 기준) | no_internal_links_family.json |
| 78 | post_inventory.jsonl 고유 블로그 (3 paused 백업 추가 제외) | 최종 감사 대상 |

**원인:** `ratio_by_blog`의 합계(24,473)가 전체 감사 대상(24,986)과 513건 차이 — ratio_by_blog에서 누락된 블로그가 존재. 80개는 NO_INTERNAL_LINKS ratio 집계에 참여한 블로그 수.

**최종 확정값:**
- **85** = config 등록 전체 (감사 범위 정의 기준)
- **81** = 기계 감사 대상 (Blogger 4개 제외)
- **78** = 최종 감사 대상 (.paused 백업 3개 추가 제외)

**⚠️ 주의:** `no_internal_links_family.json`의 `ratio_by_blog` 합계(24,473)가 전체 감사 대상(24,986)과 불일치하므로, NO_INTERNAL_LINKS의 "80개 블로그"라는 수치는 별도 기준이 명시되어야 함.

### 2.2 NO_INTERNAL_LINKS — 18,522 vs 18,542

**발견:** CURRENT_STATE.md가 frozen 20건을 제외한 18,522를 "최종"으로 제시하나, 감사 산출물(audit_verdict, gate_review)은 18,542를 사용.

| 수치 | 의미 | 근거 |
|------|------|------|
| 18,542 | frozen 제외 없이 internal_links=0인 전체 포스트 | mechanical_all.jsonl에서 `grep -c '"internal_links": 0'` |
| 18,522 | frozen 20건 제외 후 | 18,542 - 20 (frozen_interior_slugs.json) |

**분석:**
- 감사 게이트(gate_review.md)는 frozen을 "읽기 전용"으로 지정했으나, 수치에서 제외한다는 명시적 규칙은 없음
- `verdict.json`과 `gate_review.md`는 18,542를 사용
- CURRENT_STATE.md의 18,522는 자체 계산이 근거 없이 "최종"으로 포장됨

**최종 확정값:**
- **18,542** = 감사 원시 카운트 (표준값으로 사용)
- **18,522** = frozen 20건 제외 조건부 값 (별도 명시 필요)

### 2.3 템플릿 유출 — 초기 1건 vs 최종 2건

**발견:** CURRENT_STATE.md에 "초기 1건" 과거 기록이 남아 있어 혼동 가능.

| 시점 | 수치 | 근거 |
|------|------|------|
| 초기 | 1건 (travel3-hugo) | priority_queue_live_verify.json (40건 표본) |
| 최종 | 2건 (laptop-hugo, beauty-hugo) | template_leak_live_validation.jsonl (104건 표본) |

**차이 원인:** priority_queue는 상위 40개만 검증(travel3 포함), template_leak_live_validation은 104개 광범위 검증(travel3 미포함, beauty/laptop 포함). 서로 다른 샘플 세트.

**최종 확정값:**
- **2건** = 라이브 확인된 실시간 유출 (laptop-hugo, beauty-hugo)
- 1건(travel3) = priority_queue 40건 표본에서 발견, 104건 표본에서는 미검출

### 2.4 템플릿 유출 오탐율 — 92.5%

**산출 근거:**
- `priority_queue_live_verify.json`: 40건 중 `LIVE_CLEAN` = 37건 → 오탐율 = 37/40 = 92.5%
- 기계 감사 전체: 5,097건 플래그 중 라이브 확인 2건 → 오탐율 = 99.96%

**⚠️ 주의:** 92.5%는 40건 표본 기준. 104건 표본에서는 100건 중 2건 = 98.1% 오탐율.

**최종 확정값:**
- **92.5%** = 40건 표본 오탐율 (priority_queue 기준)
- **98.1%** = 104건 표본 오탐율 (template_leak_live_validation 기준)
- **99.96%** = 전체 기계 감사 오탐율 (5,097건 중 2건)

---

## 3. 문서 QA에서 발견된 오류

### 3.1 dispatcher.py `--dry-run` / `--force` 옵션 — 존재하지 않음

**위치:**
- `TROUBLESHOOT-REFERENCE.md:318` — `python3 dispatcher.py {blog_id} --dry-run` 기술
- `OPS-RUNBOOK.md:154` — `python3 dispatcher.py {blog_id} --force` 기술
- `OPS-RUNBOOK.md:284` — `python3 dispatcher.py {blog_id} --dry-run` 기술

**실제:** `dispatcher.py:1591-1633`의 `main()`은 `sys.argv`를 직접 파싱하며, 허용 옵션은 `<blog_id>`, `report [--quality]`, `init-db` 뿐. `--dry-run`, `--force`는 존재하지 않음.

**수정안:**
- `--dry-run` → 해당 옵션 없음. 대안: `dispatcher.py report`로 최근 실행 결과 확인
- `--force` → 해당 옵션 없음. 대안: 쿨다운 해제 후 재실행

### 3.2 launchd plist — 문서에 3개만 기재, 실제 8개 존재

**위치:** `TROUBLESHOOT-REFERENCE.md` 및 `OPS-RUNBOOK.md`에서 `com.5000.scheduler`, `com.5000.scheduler-watchdog`, `com.5000.ops-dashboard`만 언급.

**실제 8개:**
1. `com.5000.scheduler.plist`
2. `com.5000.scheduler-watchdog.plist`
3. `com.5000.ops-dashboard.plist`
4. `com.5000.analytics.plist`
5. `com.5000.analytics.watchdog.plist`
6. `com.5000.auto-triage.plist`
7. `com.5000.dashboard.plist` (이전 버전, superseded)
8. `com.5000.master-backup.plist`

**수정안:** TROUBLESHOOT-REFERENCE.md에 전체 8개 plist 테이블 추가.

---

## 4. 하드코딩 인증정보 현황

### 4.1 발견된 하드코딩 비밀

| 위치 | 유형 | 위험도 |
|------|------|--------|
| `ops_dashboard/app.py:79-80` | 기본 자격증명 하드코딩 | **높음** — 로컬 네트워크에서 anyone이 대시보드 접근 가능 |
| `com.5000.auto-triage.plist` | OPS_USER/OPS_PASSWORD XML 평문 | **높음** — plist 평문에 비밀 저장 |

### 4.2 관리되는 비밀 (코드 내 하드코딩 아님)

| 파일 | 유형 | 관리 방식 |
|------|------|----------|
| `.env` | OPENAI_API_KEY, CLOUDFLARE_ACCOUNT_ID 등 | .gitignore, dotenv 로드 |
| `~/.env.common` | 50+ 비밀키 | 저장소 외부, dotenv 로드 |
| `config/api_keys.yaml` | Cloudflare, Blogger, WordPress 등 | .gitignore, YAML 구조 |

### 4.3 코드 내 하드코딩 토큰 미발견

`grep` 결과, 코드 내에 평문 토큰/API 키 하드코딩은 없음. 모든 외부 API 키는 `os.getenv()` 또는 `dotenv`로 로드.

---

## 5. 문서 내 평문 자격증명 위치

| 문서 | 위치 | 유형 |
|------|------|------|
| `TROUBLESHOOT-REFERENCE.md` | §5.1, §9.1 | 기본 자격증명 기재 (이미 `[REDACTED]`로 교체 완료) |
| `OPS-RUNBOOK.md` | §1.4, §4.3, §7 | 기본 자격증명 기재 (이미 `[REDACTED]`로 교체 완료) |

**수정안:** 두 문서 모두 `[REDACTED]`로 교체하고, 실제 값은 `ops_dashboard/app.py` 참조로 안내.

---

## 6. 최종 확정값 요약

| 항목 | 최종값 | 근거 |
|------|--------|------|
| 블로그 등록 | **85** | config/blogs.d/*.yaml |
| 기계 감사 대상 | **81** | mechanical_all.jsonl (4 Blogger 제외) |
| 최종 감사 대상 | **78** | post_inventory.jsonl (3 paused 백업 추가 제외) |
| NO_INTERNAL_LINKS 원시 | **18,542** | mechanical_all.jsonl, audit_verdict.json |
| NO_INTERNAL_LINKS (frozen 제외) | **18,522** | 18,542 - 20 (frozen_interior_slugs.json) |
| 템플릿 유출 라이브 확인 | **2건** | laptop-hugo, beauty-hugo |
| 404 | **2건** | issue-techpawz-hugo |
| 테스트 실패 (사전 baseline) | **21건** | Phase 61 이전부터 존재 |
| 평균 품질 점수 | **87.1** | 794건 표본 |
| 템플릿 유출 오탐율 (40건 표본) | **92.5%** | 37/40 |
| 하드코딩 비밀 | **2건** | ops_dashboard 기본값, auto-triage.plist |
