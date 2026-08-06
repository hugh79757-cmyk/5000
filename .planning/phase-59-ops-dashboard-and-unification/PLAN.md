# Phase 59: Ops Dashboard + Blowfish 표준 단일화 + 파이프라인 통합

> **Status:** 📋 Planned
> **Created:** 2026-08-06
> **Mode:** staged rollout (waves)
> **Risk:** HIGH — ETAP 36개 블로그 영향, 테마 변경

---

## Overview

**Goal:** 85개 블로그의 운영 상태를 모바일/웹에서 실시간 파악하고, Blowfish 테마를 단일 소스로 고정하며, 7갈래로 갈라진 파이프라인 분기를 단일 표준으로 수렴.

**Success Criteria:**
1. Ops Dashboard에서 CUAP stale, senior 썸네일, CJK 릭, 표준 위반 최소 1건이 "주의 필요"에 노출
2. Blowfish 테마 오버라이드 파일이 단일 소스에서 관리됨
3. ETAP `_write_hugo_post()` 중복 0건
4. `publisher.py` CLOUDFLARE_API_TOKEN 주입 코드 삭제됨
5. 테마 3종 → Blowfish 1종

**Dependencies:**
- `ops_dashboard/db.py` (419 lines, 완료)
- `ADSENSE-GUIDE.md` (표준 문서)
- `Blowfish-Hugo-테마-업그레이드-표준-지침서.md v1.2` (표준 문서)
- `audit_5000.md` (감사 결과)

---

## Wave 1: Ops Dashboard Core

**Goal:** SQLite 데이터 모델 + 헬스체크 엔진 + Flask UI + JSON API
**Risk:** LOW (읽기 전용, 기존 시스템 미수정)
**Pre-requisite:** ops_dashboard/db.py (완료)

### Tasks

#### 1-1: 표준 규칙 시드 (standard_rules 테이블)
- **파일:** `ops_dashboard/db.py` — `seed_standard_rules()` 함수 추가
- **내용:** R01~R12 규칙 12건을 standard_rules 테이블에 시드
- **검증:** `python -c "from ops_dashboard.db import *; conn=get_conn(); init_db(conn); print(seed_standard_rules(conn))"` → 12

#### 1-2: 헬스체크 엔진 (플러그인 레지스트리)
- **파일:** `ops_dashboard/checks/__init__.py` — 레지스트리 + `run_all_checks(blog_id, conn)`
- **파일:** `ops_dashboard/checks/freshness.py` — `check_freshness()`: 발행일 오래됨 탐지
- **파일:** `ops_dashboard/checks/standard.py` — `check_standard_compliance()`: R01~R12 파일 기반 검사
  - R01: `hugo.toml`에서 `showTableOfContents` 값 확인
  - R02: `hugo.toml`에서 `[params.advertisement]` 섹션 존재 확인
  - R03: `extend-head.html`에서 `site.Params.advertisement.adsense` 사용 확인
  - R04: `extend_head.html`에서 GA4 + 모바일 CSS 존재 확인
  - R05: `adsense/top.html`에서 `overflow:hidden;min-height:100px` 존재 확인
  - R06: `adsense/in-article.html`에서 `fluid`+`in-article` 포맷 확인
  - R07: `single.html`에서 H2 분할 인젝션 로직 존재 확인
  - R08: `single.html`에서 Description(lead) 제거 확인
  - R09: `baseof.html` 커스텀 오버라이드 없음 확인
  - R10: `custom.css`에서 unfilled/다크모드/min-height 규칙 확인
  - R11: `mobile-sticky.html` 미사용 확인
  - R12: 허용 파일 외 오버라이드 없음 확인
- **파일:** `ops_dashboard/checks/render.py` — `check_render_health()`: HTTP + 썸네일 + adsbygoogle
- **파일:** `ops_dashboard/checks/crosscheck.py` — `check_gsd_crosscheck()`: known_issues ↔ check_results 대조
- **검증:** 각 check 함수가 `(blog_id, conn) → {status, detail, evidence_url}` 반환

#### 1-3: Flask 앱
- **파일:** `ops_dashboard/app.py`
- **라우트:**
  - `GET /` — 함대 요약 (계열×상태 매트릭스, 가동률, stale 수, issue 수, 위반 수) + "주의 필요" 섹션
  - `GET /blog/<id>` — 블로그 상세 (헬스 + 표준준수 + issues + 발행이력)
  - `GET /issues` — known_issues 목록 (상태×감지 매트릭스)
  - `GET /standards` — standard_rules + 계열별 준수율
  - `GET /api/fleet` — JSON 함대 요약
  - `GET /api/attention` — JSON 주의 필요
  - `GET /api/issues` — JSON 이슈 목록
  - `GET /api/standards` — JSON 표준 규칙
  - `POST /api/run-checks` — 수동 헬스체크 트리거
- **인증:** Basic Auth (환경변수 `OPS_USER`, `OPS_PASSWORD`)
- **검증:** `python ops_dashboard/app.py` → http://localhost:5060 접속 가능

#### 1-4: 템플릿
- **파일:** `ops_dashboard/templates/base.html` — 반응형 레이아웃 (모바일 카드 뷰)
- **파일:** `ops_dashboard/templates/index.html` — 함대 요약 + 주의 필요
- **파일:** `ops_dashboard/templates/blog.html` — 블로그 상세
- **파일:** `ops_dashboard/templates/issues.html` — 이슈 매트릭스
- **파일:** `ops_dashboard/templates/standards.html` — 표준 준수율

#### 1-5: 정적 파일
- **파일:** `ops_dashboard/static/style.css` — 대시보드 스타일
- **파일:** `ops_dashboard/static/app.js` — 모바일 카드 토글

#### 1-6: 시드 스크립트
- **파일:** `ops_dashboard/seed.py` — CLI: `init_db() + sync_blog_lifecycle() + seed_known_issues() + seed_standard_rules()`
- **검증:** `python ops_dashboard/seed.py` → ops.db 생성, 79 blogs + 52 issues + 12 rules

### Wave 1 Verification
```bash
# 1. DB 초기화 + 시드
python ops_dashboard/seed.py

# 2. 헬스체크 1회 실행
python -c "
from ops_dashboard.db import get_conn, init_db
from ops_dashboard.checks import run_all_checks
conn = get_conn()
results = run_all_checks('camping-hugo', conn)
print(results)
"

# 3. Flask 서버 기동 확인
python ops_dashboard/app.py &
curl -u admin:password http://localhost:5060/api/fleet | python -m json.tool
kill %1
```

---

## Wave 2: Cloudflare Tunnel + Alerts

**Goal:** 원격 접근 + 텔레그램 알림 통합
**Risk:** LOW (추가 전용, 기존 미수정)
**Pre-requisite:** Wave 1 완료

### Tasks

#### 2-1: cloudflared 설정 문서화
- **파일:** `ops_dashboard/SETUP.md` — 설치/인증/터널 생성/config.yml/DNS/서비스 등록 명령어
- **참고:** ops 데이터에 도메인/설정정보 포함 → 공개 노출 금지, 인증 필수

#### 2-2: 텔레그램 알림에 대시보드 링크 삽입
- **파일:** `shared/problem_monitor.py` — 알림 메시지에 `https://<tunnel-host>/blog/<id>` 링크 추가
- **변경:** 기존 알림 포맷에 대시보드 링크 1줄 추가 (additive)

#### 2-3: 표준 위반 → 텔레그램 알림
- **파일:** `ops_dashboard/checks/standard.py` — 신규 위반 발견 시 `shared/telegram_notifier.py` 호출
- **조건:** 이전 검사에서 pass였던 규칙이 fail로 변경된 경우에만 알림

### Wave 2 Verification
```bash
# 1. cloudflared 설치 확인
which cloudflared

# 2. 터널 config 문서 확인
cat ops_dashboard/SETUP.md

# 3. 알림 링크 포함 확인
grep -r "tunnel-host" shared/problem_monitor.py
```

---

## Wave 3: Blowfish Theme Unification

**Goal:** 테마 오버라이드를 단일 소스로 고정, PaperMod/Congo → Blowfish 마이그레이션
**Risk:** MEDIUM (테마 변경 → Hugo 빌드 영향)
**Pre-requisite:** Wave 1 완료 (ops 대시보드가 표준 검사 가능해야 함)

### Tasks

#### 3-1: 전체 블로그 테마 오버라이드 전수 조사
- **파일:** `ops_dashboard/checks/standard.py` — R07~R12 실행하여 현재 상태 파악
- **출력:** `standards.html`에서 계열별 준수율 매트릭스 확인
- **검증:** 85개 블로그 전수 검사 완료

#### 3-2: shared-themes 구조 설계
- **현재:** `/Users/twinssn/Projects/shared-themes/blowfish` (367MB) 존재
- **목표:** 표준 오버라이드(single.html, extend-head/extend_head, adsense/*, custom.css)를 shared-themes에 1곳 관리
- **방식:** 각 블로그가 심볼릭 링크 또는 Hugo Modules로 참조
- **적용 대상:** Blowfish 사용 74개 블로그

#### 3-3: hotissue-hugo PaperMod → Blowfish 마이그레이션
- **대상:** `cap/hotissue-hugo` (PaperMod 1개)
- **변경:** hugo.toml 테마 설정 + layouts 오버라이드 + frontmatter 형식
- **검증:** Hugo 빌드 0 에러 + ops dashboard standard compliance pass

#### 3-4: stock-hugo Congo → Blowfish 마이그레이션
- **대상:** `stap/stock-hugo` (Congo 1개)
- **변경:** hugo.toml 테마 설정 + layouts 오버라이드 + frontmatter 형식
- **검증:** Hugo 빌드 0 에러 + ops dashboard standard compliance pass

#### 3-5: 중복 테마 파일 제거
- **대상:** 각 블로그 내 `themes/` 디렉토리 (Blowfish 복제본)
- **방식:** shared-themes 심볼릭 링크로 교체
- **적용:** 소수 블로그 먼저 → ops dashboard 검사 → 회귀 0 → 전체 확대
- **검증:** 적용 전/후 레포 용량 수치 기록

#### 3-6: 용량 절감 측정
- **적용 전:** `du -sh` 각 블로그 themes/ 디렉토리
- **적용 후:** `du -sh` 각 블로그 themes/ 디렉토리
- **출력:** 용량 절감 수치 문서화

### Wave 3 Verification
```bash
# 1. ops dashboard 표준 검사 실행
curl -u admin:password -X POST http://localhost:5060/api/run-checks

# 2. 표준 준수율 확인
curl -u admin:password http://localhost:5060/api/standards | python -m json.tool

# 3. hotissue/stock Hugo 빌드 확인
cd /Users/twinssn/Projects/cap/hotissue-hugo && hugo --gc --minify 2>&1 | tail -5
cd /Users/twinssn/Projects/STAP/stock-hugo && hugo --gc --minify 2>&1 | tail -5

# 4. 용량 비교
du -sh /Users/twinssn/Projects/cuap/*/themes/ /Users/twinssn/Projects/cap/*/themes/
```

---

## Wave 4: ETAP _write_hugo_post() Consolidation

**Goal:** ETAP 35개 중복 `_write_hugo_post()` 제거 → shared/hugo_writer.py로 수렴
**Risk:** HIGH (36개 블로그 영향)
**Pre-requisite:** Wave 1 완료 + Wave 3 완료 (테마 통일 후)

### Tasks

#### 4-1: ETAP vs Shared 시그니처 비교 분석
- **대상:** ETAP 34개 표준 버전 + 1개 flight_pipeline outlier vs shared/hugo_writer.py
- **차이점:**
  - ETAP: `(article, cover_image, body_images, blog_id, site_path, category)`
  - Shared: `(blog_cfg, title, body_md, slug, category, tags, thumbnail_url, is_draft)`
  - ETAP 특화 기능: `inject_internal_links()`, `insert_adsense()`, `build_cross_sell_html()`, `insert_cross_sell_block()`
- **산출물:** 통합 설계 문서 (어떤 기능을 shared에 추가할지)

#### 4-2: Shared hugo_writer.py에 ETAP 기능 추가
- **파일:** `shared/publishers/hugo_writer.py`
- **변경:** ETAP 특화 기능을 선택적 파라미터로 추가 (additive, 기존 시그니처 보존)
  - `inject_internal_links: bool = False`
  - `adsense_config: dict | None = None`
  - `cross_sell_config: dict | None = None`
- **원칙:** 기존 CUAP/CAP/TAP/RAP/SEAP 호출 코드 미변경

#### 4-3: ETAP pipeline.py 업데이트 (1개 — 중앙)
- **파일:** `pipelines/etap/pipeline.py`
- **변경:** 자체 `_write_hugo_post()` → shared import + ETAP 기능 활성화
- **검증:** `pipelines.etap.pipeline.run()` 호출 시 정상 동작

#### 4-4: ETAP 개별 pipeline 업데이트 (34개 — staged rollout)
- **대상:** `pipelines/etap/*_pipeline.py` (flight_pipeline.py 별도 처리)
- **변경:** 자체 `_write_hugo_post()` 삭제 → shared import
- **적용 순서:**
  1. 소수 블로그 3개 먼저 (예: adventure, airlines, airports)
  2. ops dashboard render_health 검사 → 회귀 0
  3. 나머지 31개 확대
- **flight_pipeline.py:** 별도 시그니처 `(cfg, article)` → 통합 필요

#### 4-5: ETAP _build_and_deploy() 죽은 코드 제거
- **대상:** ETAP 개별 pipeline의 `_build_and_deploy()` 함수
- **확인:** `grep -r '_build_and_deploy' pipelines/etap/` → dispatcher.py 중앙 사용 확인 후 제거
- **원칙:** dispatcher.py `_build_and_deploy_central()` 사용

#### 4-6: ETAP 배포 경로 통일
- **확인:** ETAP `run()` 함수가 자체 배포를 호출하지 않는지 검증
- **변경:** 필요시 ETAP `run()` 반환값 → dispatcher가 배포 처리

### Wave 4 Verification
```bash
# 1. ETAP _write_hugo_post 중복 0건 확인
grep -r 'def _write_hugo_post' pipelines/etap/ | wc -l  # → 0

# 2. ETAP 36개 블로그 Hugo 빌드 확인
for blog in adventure airlines airports bus cruise culture; do
  cd /Users/twinssn/Projects/ETAP/${blog}-hugo && hugo --gc --minify 2>&1 | tail -1
done

# 3. ops dashboard render_health 검사
curl -u admin:password http://localhost:5060/api/fleet | python -m json.tool

# 4. 기존 테스트 회귀 확인
python -m pytest tests/ -x -q
```

---

## Wave 5: Dispatcher + Publisher Cleanup

**Goal:** 이름 불일치 + 토큰 불일치 해소
**Risk:** LOW (삭제/변경 범위 제한적)
**Pre-requisite:** Wave 4 완료

### Tasks

#### 5-1: flights-hugo/flight-hugo 이름 정렬
- **확인:** Cloudflare Pages 프로젝트명 = `flights-hugo` (YAML 기준)
- **변경:** dispatcher.py `ETAP_PIPELINE_BLOGS`에서 `flight-hugo` → `flights-hugo`로 정렬
- **확인:** `_ETAP_BLOG_EXCEPTIONS` 매핑 정확성

#### 5-2: publisher.py CLOUDFLARE_API_TOKEN 죽은 코드 제거
- **파일:** `shared/publisher.py`
- **대상:** lines 651-768 (`_deploy_site_inner` 함수 — legacy copy, 토큰 주입)
- **변경:** 함수 정의 삭제 (re-export at line 788이 대체)
- **확인:** `grep -n '_deploy_site_inner' shared/publisher.py` → re-export만 남음
- **안전:** `grep -rn 'from.*publisher.*import.*_deploy_site_inner' .` → 직접 호출자 0 확인 후 삭제

#### 5-3: publisher.py vs deploy.py 토큰 처리 확인
- **확인:** deploy.py line 78이 `CLOUDFLARE_API_TOKEN` 제거하는지 최종 검증
- **확인:** publisher.py에서 토큰 주입 코드 완전 삭제 확인

#### 5-4: validate_post_extended() 공유 확인
- **확인:** `grep -rn 'validate_post_extended' shared/ pipelines/` → 모든 계열이 shared 사용하는지 검증

### Wave 5 Verification
```bash
# 1. publisher.py 토큰 주입 코드 0건 확인
grep -n 'CLOUDFLARE_API_TOKEN' shared/publisher.py  # → 0건 (또는 re-export만)

# 2. flights-hugo 이름 일치 확인
grep -n 'flight' dispatcher.py | grep -v flights

# 3. 기존 테스트 회귀 확인
python -m pytest tests/ -x -q
```

---

## Wave 6: Final Verification + Documentation

**Goal:** 전체 시스템 최종 검증 + GSD 문서 업데이트
**Risk:** LOW (검증 + 문서)
**Pre-requisite:** Wave 1~5 완료

### Tasks

#### 6-1: ops dashboard 전체 검사 실행
- **명령:** `POST /api/run-checks` → 85개 블로그 전수 검사
- **확인:** "주의 필요" 섹션에 CUAP stale, senior 썸네일, CJK 릭, 표준 위반 최소 1건 노출

#### 6-2: 표준 준수율 최종 확인
- **명령:** `GET /api/standards`
- **확인:** R01~R12 계열별 준수율 매트릭스

#### 6-3: GSD 문서 업데이트
- **파일:** `.planning/STATE.md` — Phase 59 등록 + Quick Tasks에 ops_dashboard 기록
- **파일:** `.planning/ROADMAP.md` — Phase 59 항목 추가

#### 6-4: README 작성
- **파일:** `ops_dashboard/README.md`
- **내용:** 실행법, 검사/규칙 추가법(플러그인 등록), 터널 세팅, API 스펙

### Wave 6 Verification
```bash
# 1. 대시보드에서 전체 fleet 상태 확인
curl -u admin:password http://localhost:5060/api/fleet | python -m json.tool

# 2. 주의 필요 항목 확인
curl -u admin:password http://localhost:5060/api/attention | python -m json.tool

# 3. README 존재 확인
cat ops_dashboard/README.md | head -20
```

---

## Task Dependency Map

```
Wave 1 (1-1 → 1-2 → 1-3 → 1-4 → 1-5 → 1-6)
  │
  ├──→ Wave 2 (2-1 → 2-2 → 2-3)  [Wave 1 완료 후]
  │
  └──→ Wave 3 (3-1 → 3-2 → 3-3 → 3-4 → 3-5 → 3-6)  [Wave 1 완료 후]
         │
         └──→ Wave 4 (4-1 → 4-2 → 4-3 → 4-4 → 4-5 → 4-6)  [Wave 3 완료 후]
                │
                └──→ Wave 5 (5-1 → 5-2 → 5-3 → 5-4)  [Wave 4 완료 후]
                       │
                       └──→ Wave 6 (6-1 → 6-2 → 6-3 → 6-4)  [Wave 5 완료 후]
```

---

## Acceptance Criteria

### Wave 1
- [ ] ops.db 생성: 79 blogs (blog_lifecycle) + 52 issues (known_issues) + 12 rules (standard_rules)
- [ ] Flask UI 모바일 반응형 확인 (http://localhost:5060)
- [ ] JSON API 4개 엔드포인트 정상 응답
- [ ] "주의 필요" 섹션에 CUAP stale 블로그 노출

### Wave 2
- [ ] cloudflared 설치/설정 문서화 완료
- [ ] 텔레그램 알림에 대시보드 링크 포함
- [ ] 표준 위반 → 텔레그램 알림 발송 확인

### Wave 3
- [ ] hotissue-hugo: PaperMod → Blowfish 마이그레이션 + Hugo 빌드 0 에러
- [ ] stock-hugo: Congo → Blowfish 마이그레이션 + Hugo 빌드 0 에러
- [ ] 적용 전/후 레포 용량 절감 수치 기록
- [ ] ops dashboard R07~R12 검사 pass

### Wave 4
- [ ] ETAP `_write_hugo_post()` 중복 0건 (`grep -r 'def _write_hugo_post' pipelines/etap/ | wc -l` → 0)
- [ ] ETAP 36개 블로그 Hugo 빌드 0 에러
- [ ] 기존 CUAP/CAP/TAP/RAP/SEAP 호출 코드 미변경 (회귀 0)
- [ ] ETAP `_build_and_deploy()` 죽은 코드 삭제

### Wave 5
- [ ] `publisher.py` CLOUDFLARE_API_TOKEN 주입 코드 0건
- [ ] dispatcher.py flights-hugo 이름 정렬
- [ ] 기존 테스트 회귀 0건

### Wave 6
- [ ] ops dashboard 85개 블로그 전수 검사 완료
- [ ] "주의 필요"에 CUAP stale + senior 썸네일 + CJK 릭 + 표준 위반 최소 1건 노출
- [ ] STATE.md + ROADMAP.md 업데이트 완료
- [ ] README.md 작성 완료

---

## Risk Mitigation

### Staged Rollout 정책
| Wave | 소수 적용 | 검증 | 전체 확대 |
|------|----------|------|----------|
| 3 | hotissue + stock (2개) | Hugo 빌드 + ops 검사 | 나머지 Blowfish 블로그 |
| 4 | adventure + airlines + airports (3개) | Hugo 빌드 + ops 검사 | 나머지 ETAP 31개 |

### Rollback 계획
| Wave | 롤백 방법 |
|------|----------|
| 1 | ops_dashboard/ 디렉토리 삭제 (기존 시스템 미영향) |
| 2 | cloudflared 서비스 중지 + config 삭제 |
| 3 | Git revert (테마 파일 복원) |
| 4 | Git revert (ETAP pipeline 원복) |
| 5 | Git revert (publisher.py 원복) |

### "break nothing that works" 원칙
- 모든 변경은 additive (기존 코드 보존)
- ETAP 통합 시 shared hugo_writer.py에 기능 추가 → ETAP에서만 활성화
- 기존 CUAP/CAP/TAP/RAP/SEAP 호출 시그니처 미변경
- 매 Wave마다 기존 테스트 회귀 확인 필수

---

## 잔존 위험

1. **ETAP _write_hugo_post() 통합 시 회귀:** 36개 블로그에 영향, staged rollout 필수
2. **flight_pipeline.py 시그니처 불일치:** `(cfg, article)` → 통합 필요, 별도 처리
3. **publisher.py _deploy_site_inner 제거:** 직접 호출자 확인 후 삭제
4. **테마 마이그레이션:** frontmatter 형식 변경, Hugo 빌드 영향
5. **도메인 75개 미확인:** HTTP 전수 확인 필요 (Wave 1 render_health에서 자동 검사)
6. **Blogger 블로그 3개:** 파이프라인 미정의, 수동 관리
