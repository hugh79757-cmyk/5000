# ACTION_PLAN.md — 우선순위별 조치 계획

> 기반: BASELINE_RECONCILIATION.md + 4개 워커 조사 결과
> 원칙: 실제 비밀번호 변경·파일 수정·커밋·배포·동결 대상 접근 불가. 승인 단위와 검증·롤백 절차만 기술.

---

## P0: 보안 조치 (즉시)

### P0-1: 대시보드 기본 자격증명 변경

**현재 상태:** `ops_dashboard/app.py:79-80`에 기본값 `_DEFAULT_USER`/`_DEFAULT_PASSWORD` 하드코딩. `com.5000.auto-triage.plist`에 동일 값 XML 평문 저장.

**위험:** 로컬 네트워크에서 Anyone이 `http://localhost:5060` 접속 가능. RBAC 없음.

**승인 단위:**
- 사용자 확인: 새 비밀번호 지정 (앱솔루트 최소 12자, 대소문자+숫자 혼용)

**수행 절차 (승인 후):**
1. `ops_dashboard/app.py:79-80`의 `_DEFAULT_PASSWORD`를 새 값으로 변경
2. `com.5000.auto-triage.plist`의 `OPS_PASSWORD` 환경변수를 새 값으로 변경
3. launchd 리로드: `launchctl unload ~/Library/LaunchAgents/com.5000.auto-triage.plist && launchctl load ~/Library/LaunchAgents/com.5000.auto-triage.plist`
4. ops-dashboard 리로드: `launchctl unload ~/Library/LaunchAgents/com.5000.ops-dashboard.plist && launchctl load ~/Library/LaunchAgents/com.5000.ops-dashboard.plist`

**검증:**
- `curl -u ops:NEW_PASSWORD http://localhost:5060` → 200 예상
- 이전 비밀로 접근 시도 → 401 예상

**롤백:**
- 비밀이 유출된 것으로 의심되면 즉시 재교체:
  1. 새 비밀번호 지정 (앱솔루트 최소 12자, 대소문자+숫자 혼용)
  2. `ops_dashboard/app.py:79-80`의 `_DEFAULT_PASSWORD`를 새 값으로 변경
  3. `com.5000.auto-triage.plist`의 `OPS_PASSWORD` 환경변수를 새 값으로 변경
  4. launchd 리로드: `launchctl unload ~/Library/LaunchAgents/com.5000.auto-triage.plist && launchctl load ~/Library/LaunchAgents/com.5000.auto-triage.plist`
  5. ops-dashboard 리로드: `launchctl unload ~/Library/LaunchAgents/com.5000.ops-dashboard.plist && launchctl load ~/Library/LaunchAgents/com.5000.ops-dashboard.plist`
- 이전 비밀번호로의 복원은 **절대 하지 않음** (유출 가능성이 있는 비밀번호 재사용 금지)

---

### P0-2: 문서 내 평문 자격증명 제거

**현재 상태:** `TROUBLESHOOT-REFERENCE.md`와 `OPS-RUNBOOK.md`에 기본 자격증명 평문 기재 (이미 `[REDACTED]`로 교체 완료).

**위험:** 문서가 git에 커밋되면 비밀이 리포지토리에 노출됨 (.gitignore 대상 아님).

**승인 단위:**
- 사용자 확인: [REDACTED]로 교체하는 것에 동의

**수행 절차 (승인 후):**
1. `TROUBLESHOOT-REFERENCE.md`에서 기본 자격증명 참조를 모두 `[REDACTED]`로 교체
2. `OPS-RUNBOOK.md`에서 동일 교체
3. 각 위치에 "실제 값은 `ops_dashboard/app.py`의 `_DEFAULT_USER`/`_DEFAULT_PASSWORD` 참조" 안내 추가

**검증:**
- 검증: 실행하지 않음 — 값이 노출될 수 있으므로. 대신 위 3단계 완료 후 `grep -c`로 0건 확인은 수동으로 수행할 것

**롤백:**
- 평문 비밀이 다시 노출되지 않도록 [REDACTED] placeholder를 유지
- git revert로 비밀을 되살리는 것은 **절대 하지 않음** (유출된 비밀 재노출 위험)
- 만약 [REDACTED]가 올바르지 않은 값으로 교체되었다면, 수동으로 올바른 placeholder 값 작성

---

## P1: 미푸시 변경 보존 및 롤백 구축

### P1-1: 프로젝트별 단계적 push (강제 push 금지)

**현재 상태:** HEAD `5c757cc17`이 origin/main `a788f0bbc`보다 85커밋 앞섬. 125 files changed, 15,218 insertions(+), 2,001 deletions(-).

**위험:** 로컬 장애 시 85커밋 분량의 작업이 유실됨.

**승인 단위:**
- 각 프로젝트별 push 전 사용자 승인 필수

**수행 절차 (승인 후, 프로젝트별 반복):**
1. `git fetch origin` — 원격 변경 확인
2. `git log --oneline origin/main..HEAD -- {project_dir}` — 해당 프로젝트 커밋 목록 확인
3. `git diff origin/main -- {project_dir}` — 충돌 가능성 검사
4. 충돌 발생 시 수동 해결 후 커밋
5. 백업 태그 생성: `git tag backup/pre-push-{YYYYMMDD}-{project}`
6. 테스트 실행: 관련 파이프라인 테스트 확인
7. 사용자 승인 확인
8. `git push origin main` (절대 `--force` 사용 금지)

**프로젝트 디렉터리 목록:**
- `pipelines/`, `shared/`, `ops_dashboard/`, `config/`, `scripts/`, `.planning/`
- 각 프로젝트별로 위 8단계를 반복

**강제 push 금지 규칙:**
- `git push --force`, `git push --force-with-lease`는 **절대 사용하지 않음**
- 충돌 시 수동 해결이 유일한 방법

**검증:**
- `git log --oneline origin/main..HEAD | wc -l` → 0건 (push 완료)
- `git status` → clean
- `git tag -l 'backup/pre-push-*'` → 백업 태그 존재 확인

**롤백:**
- `git revert HEAD` (마지막 커밋 되돌리기)
- 또는 백업 태그에서 복원: `git diff backup/pre-push-{tag}..HEAD`로 변경 분석 후 `git revert`

---

### P1-2: 16개 미커밋 변경 파일 보존

**현재 상태:** unstaged 변경 16건:
- `.DS_Store`, `.planning/` 5개, `ops_dashboard/checks/content_quality.py`
- `pipelines/curation/pipeline.py`, `pipelines/curation/writer.py`
- `pipelines/etap/cruise_writer.py`, `pipelines/etap/culture_writer.py`, `pipelines/etap/quality_guard.py`
- `scripts/.batch_thumbnails_progress.txt`, `shared/ai_writer.py`
- `shared/publishers/hugo_writer.py`, `shared/title_templates.py`

**승인 단위:**
- 사용자 확인: 변경 내용 검토 후 커밋 여부 결정

**수행 절차 (승인 후):**
1. `git diff`로 각 파일 변경 내용 확인
2. 의미별로 그룹화하여 커밋
3. 또는 `git stash`로 보존 후 필요 시 적용

**검증:**
- `git status` → clean (커밋 후)
- 또는 `git stash list`에 stash 4건 (기존 3건 + 신규 1건)

**롤백:**
- 커밋 후: `git revert`
- Stash 후: `git stash pop`으로 복원

---

### P1-3: git stash 3건 정리

**현재 상태:**
1. `etap-phase61-A-and-B-patterns`
2. `issue-techpawz-hugo 광고 가이드`
3. `fix(phase-08-02)`

**승인 단위:**
- 사용자 확인: 각 stash의 유효성 검토

**수행 절차 (승인 후):**
1. `git stash show -p stash@{N}`로 각 stash 내용 확인
2. 유효한 stash: `git stash pop`으로 적용
3. 무효한 stash: `git stash drop stash@{N}`으로 삭제

**검증:**
- `git stash list` → 필요에 따라 0건 또는 유효 stash만 잔존

**롤백:**
- Stash 삭제 전 백업: `git stash show -p stash@{N} > /tmp/stash_backup_N.patch`
- 필요 시: `git apply /tmp/stash_backup_N.patch`

---

## P2: 유출 2건 및 404 2건 수리

### P2-1: 템플릿 유출 2건 수정

**현재 상태:**
- `laptop-hugo`: `게이밍노트북-추천-hp-오멘부터-에일리언웨어까지-합격점-top-5/index.md` — JSON-LD description에 `{{}}` 존재
- `beauty-hugo`: `neombeojeu-in-3beon-dojagigyeol-vs-1beon-jinjeong-toner-choegeun-chulsi-la-in-eob-cheos-insanggwa-silsa-yong-neu-kkim/index.md` — JSON-LD description에 `{{}}` 존재

**원인:** AI 러이터가 빈 Hugo 숏코드 `{{}}`를 JSON-LD description에 삽입.

**승인 단위:**
- 사용자 확인: 두 포스트의 description에서 `{{}}` 제거에 동의

**수행 절차 (승인 후):**
1. `laptop-hugo` 포스트: JSON-LD `description` 필드에서 `{{}} ` 제거
2. `beauty-hugo` 포스트: 동일
3. Hugo 재빌드: `HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes hugo --gc --minify --source /path/to/site`
4. 배포: `python3 dispatcher.py laptop-hugo` / `python3 dispatcher.py beauty-hugo`

**검증:**
- `curl -s "https://laptop.informationhot.kr/posts/{slug}/" | grep '{{}}'` → 결과 없음
- `curl -s "https://beauty.informationhot.kr/posts/{slug}/" | grep '{{}}'` → 결과 없음

**롤백:**
- git revert로 소스 파일 원복
- Hugo 재빌드 + 재배포

---

### P2-2: issue-techpawz-hugo 404 2건 수리

**현재 상태:**
- `https://issue.techpawz.com/posts/인치-센치-변환-계산기/` → HTTP 404
- `https://issue.techpawz.com/posts/날짜-계산기/` → HTTP 404

**원인:** 소스 파일은 존재하나 Hugo 사이트가 재빌드/재배포되지 않음. 숏코드 `{{< inchcm >}}`, `{{< datecalc >}}` 미등록.

**승인 단위:**
- 사용자 확인: issue-techpawz-hugo 재배포에 동의 (paused 백업 블로그)

**수행 절차 (승인 후):**
1. `issue-techpawz-hugo`의 `layouts/shortcodes/`에 숏코드 정의 생성 (또는 숏코드 제거)
2. `hugo --gc --minify --source /Users/twinssn/Projects/issue-techpawz-hugo --themesDir /Users/twinssn/Projects/shared-themes`
3. `python3 dispatcher.py issue-techpawz-hugo`

**검증:**
- `curl -s -o /dev/null -w "%{http_code}" "https://issue.techpawz.com/posts/인치-센치-변환-계산기/"` → 200
- `curl -s -o /dev/null -w "%{http_code}" "https://issue.techpawz.com/posts/날짜-계산기/"` → 200

**롤백:**
- git revert로 소스 파일 원복
- 재빌드 + 재배포

---

## P3: 내부 링크 개선

### P3-1: 내부 링크 0건 포스트 개선

**현재 상태:** 24,986건 중 18,542건(74.2%)이 내부 링크 0건.

**위험:** SEO 순위 저하, 사용자 이탈률 증가.

**승인 단위:**
- 사용자 확인: 내부 링크 자동 삽입 스크립트 개발/실행에 동의

**수행 절차 (승인 후):**
1. `pipelines/etap/writer.py` 또는 `shared/entity_linker.py`에 내부 링크 자동 삽입 로직 추가
2. 기존 18,542건에 대한 일괄 삽입 스크립트 개발
3. 샘플 100건으로 테스트
4. 전수 적용
5. Hugo 재빌드 + 재배포

**검증:**
- `grep -c '"internal_links": 0' mechanical_all.jsonl` → 18,542 미만
- 블로그별 내부 링크 비율 증가 확인

**롤백:**
- git revert로 코드 원복
- DB 백업 복구 (필요 시)

---

## P3-2: 템플릿 유출 기계 감사 오탐율 개선

**현재 상태:** 기계 감사 5,097건 플래그 중 라이브 확인 2건 → 오탐율 99.96%.

**위험:** 오탐이过多하면 실질적 유출을 놓치거나, 반대로 모든 플래그를 무시하게 됨.

**승인 단위:**
- 사용자 확인: 기계 감사 임계값 조정에 동의

**수행 절차 (승인 후):**
1. `mechanical_check.py`의 `raw_template_markers` 감지 로직 분석
2. JSON-LD 내부 `{{}}`와 Hugo 숏코드 `{{< >}}` 구분 로직 추가
3. `todo_markers` 패턴 재검토
4. 오탐율 재측정

**검증:**
- 기계 감사 재실행 후 오탐율 변화 측정
- 실제 유출 2건이 여전히 감지되는지 확인

**롤백:**
- git revert로 `mechanical_check.py` 원복

---

## 4. 실행 순서도

```
P0-1 (대시보드 비밀 변경) ← 즉시
P0-2 (문서 내 평문 제거) ← 즉시
    ↓
P1-1 (85커밋 push) ← P0 완료 후
P1-2 (16개 변경 보존) ← P1-1과 병렬
P1-3 (stash 정리) ← P1-2 완료 후
    ↓
P2-1 (유출 2건 수정) ← P1 완료 후
P2-2 (404 2건 수리) ← P2-1과 병렬
    ↓
P3-1 (내부 링크 개선) ← P2 완료 후
P3-2 (오탐율 개선) ← P3-1과 병렬
```

---

## 5. 검증·롤백 요약

| 조치 | 검증 방법 | 롤백 방법 |
|------|----------|----------|
| P0-1 비밀 변경 | curl 401/200 테스트 | 유출 시 즉시 재교체 (이전 비밀 복원 금지) |
| P0-2 문서 교체 | grep으로 평문 0건 확인 | [REDACTED] 유지, git revert로 비밀 재노출 금지 |
| P1-1 push | git log로 커밋 0건 | git revert / 백업 태그 복원 (force push 금지) |
| P1-2 변경 보존 | git status clean | git stash pop / git revert |
| P1-3 stash 정리 | git stash list | patch 파일에서 복원 |
| P2-1 유출 수정 | curl + grep으로 {{}} 0건 | git revert + 재빌드 |
| P2-2 404 수리 | curl HTTP 200 확인 | git revert + 재빌드 |
| P3-1 내부 링크 | internal_links=0 카운트 감소 | git revert + DB 복구 |
| P3-2 오탐율 | 오탐율 재측정 | git revert |

---

## 6. 잔존 위험

1. **`~/.env.common`이 저장소 외부에 존재** — .gitignore으로 보호 불가. 파일 무결성 관리가 중요.
2. **ops-dashboard RBAC 없음** — P0-1로 비밀 변경해도 역할 분리가 없어 read-only 접근 제어 불가.
3. **85커밋 push 시 충돌 가능성** — origin/main과의 충돌이 발생하면 수동 해결 필요.
4. **내부 링크 18,542건 자동 삽입** — AI 기반 삽입 시 콘텐츠 품질 저하 위험. 샘플 테스트 필수.
5. **issue-techpawz-hugo는 paused 백업** — 재배포 결정 시 "paused" 상태 해제 필요.
