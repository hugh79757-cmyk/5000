# CURRENT_STATE.md — 5000 프로젝트 종합 현황 보고서

> **생성 시각:** 2026-08-18
> **조사 방법:** READ-ONLY (코드·설정·DB·배포·실험 상태 변경 없음)
> **기준 커밋:** `5c757cc17` (2026-08-18, main 브랜치)

---

## 1. 전체 아키텍처와 콘텐츠 생성→검수→발행 흐름

### 1.1 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│                    5000 (중앙 통제)                       │
│                                                         │
│  scheduler.py ──▶ dispatcher.py ◀── blogs.yaml          │
│  (launchd)        (blog_id→pipe)     blogs.d/*.yaml     │
│       │                │                                 │
│       │         ┌──────┼──────────────┐                 │
│       │         │      │              │                 │
│       │    pipelines/  subprocess    shared/            │
│       │    car/etap/   (STAP/TAP)    modules            │
│       │    curation/   isolation                        │
│       │    senior/rap                                   │
│       │         │                                       │
│       │    SQLite per pipeline                          │
│       │         │                                       │
│       │    Hugo Build + Wrangler Deploy                  │
│       │    (Cloudflare Pages/Workers)                   │
│       │                                                 │
│       └──▶ ops_dashboard (Flask, port 5060)             │
│            quality scans, rechecks, pending-fixes       │
└─────────────────────────────────────────────────────────┘
```

### 1.2 콘텐츠 생성→검수→발행 흐름 (파일 경로·라인 포함)

| 단계 | 모듈 | 함수/위치 | 역할 |
|------|------|-----------|------|
| **1. 스케줄** | `scheduler.py:1237-1346` | `register_schedules()` | `schedule` 라이브러리로 블로그별 시간 등록 |
| **2. 큐잉** | `scheduler.py` | `queue_publish(blog_id)` | 발행 큐에 추가, 60초 블로그 간 딜레이 |
| **3. 라우팅** | `dispatcher.py:1268` | `dispatch(blog_id)` | config 조회, 쿨다운·할당량 체크, 파이프라인 실행 |
| **4. 파이프라인 분기** | `dispatcher.py:463` | `_resolve_pipeline()` | etap/car/stap/tap/curation/senior/rap 동적 import |
| **5. 데이터 수집** | 각 파이프라인별 | 예: `pipelines/car/pipeline.py:84` | SQLite DB에서 토픽/데이터 조회 |
| **6. AI 글쓰기** | `shared/ai_writer.py:110-191` | `openai_chat_completions_with_retry()` | OpenAI GPT → 16개 무료 모델 폴백 체인 → DeepSeek 최후 |
| **7. 사전 검증** | `shared/validators.py:314-400` | `validate_post()` | 제목 길이, AI 잔여물, 유사 제목(72h Jaccard≥0.7), 일일 할당량, 한국어 비율 등 |
| **8. 콘텐츠 기록** | `shared/quality_recorder.py:93` | `record_quality()` | `data/quality.db`에 품질 메트릭 저장 |
| **9. Hugo 콘텐츠 쓰기** | `shared/publisher.py:541-617` | `_write_hugo_post()` | `content/posts/{slug}/index.md`에 프론트머터+본문 기록 |
| **10. Hugo 빌드** | `shared/publishers/deploy.py:46` | `hugo --gc --minify` | 정적 사이트 빌드 |
| **11. 배포** | `shared/publishers/deploy.py:58-93` | `deploy_site()` | `/tmp/wrangler_deploy.lock` 직렬화, Cloudflare 배포 |
| **12. 사후 QA** | `scheduler.py:667-712` | `_run_p32_scan()` | 6시간마다 배포 콘텐츠 빈 값 체크 |
| **13. 전수 재검증** | `scheduler.py:751-808` | `_run_recheck_all()` | 매시간 ops_dashboard 전체 체크 |
| **14. 일일 품질** | `scheduler.py:656-664` | `_run_quality_scan()` | 23:00 품질 스캔 + Telegram 리포트 |

### 1.3 공유 모듈 (`shared/`)

| 모듈 | 역할 |
|------|------|
| `shared/ai_writer.py` | GPT API 호출, 서킷 브레이커(10회 연속 실패→300초 리셋), 폴백 체인 |
| `shared/validators.py` | 제목/본문/유사도/할당량 등 사전 검증 15+ 항목 |
| `shared/quality_recorder.py` | 품질 메트릭 DB 기록 |
| `shared/publisher.py` | Hugo/Blogger/WordPress 콘텐츠 기록 |
| `shared/publishers/hugo_writer.py` | Hugo 프론트머터 정리, H2 가드, IMAGE-GUARD, URL sanitize |
| `shared/publishers/deploy.py` | Hugo 빌드 + Wrangler 배포, lock 직렬화 |
| `shared/content_store.py` | 제목 유사도(`title_similar_exists`), 장소 중복 체크 |
| `shared/r2_uploader.py` | Cloudflare R2 S3 호환 이미지 업로드 |
| `shared/blogger_publisher.py` | Google Blogger API v3 발행 |
| `shared/wordpress_publisher.py` | WordPress XML-RPC 발행 |
| `shared/telegram_notifier.py` | Telegram 알림 전송 |
| `shared/entity_linker.py` | 블로그 간 내부 링크 주입 |
| `shared/publish_slot.py` | 발행 동시성 제어 (`MAX_CONCURRENT_PUBLISH`) |
| `shared/env_loader.py` | `.env` + `~/.env.common` 자동 로드 |

### 1.4 주요 설계 결정

- **중첩 파이프라인 격리:** STAP(`/Users/twinssn/Projects/STAP`), TAP(`/Users/twinssn/Projects/TAP`), ETAP(`/Users/twinssn/Projects/ETAP`) — 각각 독립 venv, 독립 git 저장소
- **SQLite per pipeline:** 중앙 DB 없음, 파이프라인별 독립 DB (`car.db`, `rap.db`, `senior.db` 등)
- **YAML 기반 스케줄링:** 코드가 아닌 YAML에 블로그 스케줄 정의
- **Graceful degradation:** 모든 외부 API 호출 try/except 래핑, 실패 시 로그+계속 (크래시 없음)
- **배포 직렬화:** `fcntl.flock()`으로 `/tmp/wrangler_deploy.lock` — 동시 배포 방지

---

## 2. 저장소·브랜치·서비스·배포 대상별 역할

### 2.1 Git 브랜치

| 분류 | 브랜치명 | 비고 |
|------|----------|------|
| **메인** | `main` | 현재 checkout, origin보다 85커밋 전진 |
| **기능** | `feat/phase62-m5-qb`, `feat/phase69-incident-taxonomy`, `feat/phase69-m4-dashboard-ssot`, `feat/phase71-car-recovery`, `feat/pr-cap-1-pipeline-result-contract`, `feat/pr2-root-cause-retry-control`, `feat/candidate-availability-state` | |
| **수정** | `fix/concurrent-publish-event-id`, `fix/p01-runtime-normalization`, `fix/pr1-incident-lifecycle`, `fix/publish-reliability-morning`, `fix/rap-subscription-backfill`, `fix/table-numbering-postprocess`, `fix/table-numbering-validation` | |
| **원격** | `origin/main`, `origin/fix/rap-subscription-backfill`, `origin/qwen-code-e5c6ab42-...` | |

### 2.2 외부 프로젝트 (독립 git 저장소)

| 프로젝트 | 경로 | `.git` | 블로그 수 | 블로그 ID |
|----------|------|--------|----------|-----------|
| **CAP** | `/Users/twinssn/Projects/cap/` | ✅ | 8 | compare/deal/ev/guide/hotissue/tco/rank/pick-hugo |
| **TAP** | `/Users/twinssn/Projects/TAP/` | ✅ | 6 | tap-blogger, travel/1/2/3/4-hugo |
| **STAP** | `/Users/twinssn/Projects/STAP/` | ✅ | 6 | finance/stock/dividend/etf/sector/ipo-hugo |
| **CUAP** | `/Users/twinssn/Projects/CUAP/` | ✅ | 15 | appliance/baby/fitness/interior/laptop/health/pet/kitchen/beauty/camping/massage/car/homeappliance/golf/bike-hugo |
| **SEAP** | `/Users/twinssn/Projects/SEAP/` | ✅ | 2 | senior-blogger, senior-hugo |
| **RAP** | `/Users/twinssn/Projects/RAP/` | ✅ | 5 | rap/2/3/4/5-hugo |
| **ETAP** | `/Users/twinssn/Projects/ETAP/` | ✅ | 35 | adventure~nomad-hugo (*.techpawz.com) |

### 2.3 브랜치별 서비스 역할

| 브랜치 | 파이프라인 | 배포 대상 | 도메인 계열 | managed_by |
|--------|-----------|-----------|------------|------------|
| **CAP** | `car` | Cloudflare Pages | `*.rotcha.kr` (6), `*.informationhot.kr` (2) | pipeline |
| **TAP** | `travel` | CF Pages (5) + Blogger (1) | `rotcha.kr` 하위 | pipeline |
| **STAP** | `stock` | Cloudflare Pages | `*.techpawz.com` (4), `*.informationhot.kr` (1) | pipeline |
| **CUAP** | `curation` | CF Pages (4) + CF Workers (11) | `*.informationhot.kr` | mde2 |
| **SEAP** | `senior` | CF Pages (1) + Blogger (1) | `*.informationhot.kr`, `2.techpawz.com` | pipeline |
| **RAP** | `rap` | Cloudflare Pages | `*.informationhot.kr` | pipeline |
| **ETAP** | `etap` | Cloudflare Pages | `*.techpawz.com` | pipeline |

### 2.4 배포 유형 분포

| 배포 유형 | 블로그 수 | 해당 블로그 |
|-----------|----------|------------|
| Cloudflare Pages | 65+ | CAP(8), TAP(5), STAP(6), CUAP(4), SEAP(1), RAP(5), ETAP(35), 수동(5+) |
| Cloudflare Workers | 11 | CUAP: baby/health/pet/kitchen/beauty/camping/massage/car/homeappliance/golf/bike-hugo |
| Blogger | 3 | tap-blogger, senior-blogger, tvshow-blogger |

---

## 3. 실제 블로그 목록과 플랫폼·도메인·게시글 수

### 3.1 요약

| 항목 | 값 |
|------|-----|
| config 등록 블로그 수 | **85** |
| 감사 대상 고유 블로그 수 | **78** |
| 감사 대상 총 게시글 수 | **24,986** (기계 감사), **25,455** (전체 분류 포함) |

### 3.2 블로그별 상세 (게시글 수 기준 상위 20개)

| 순위 | 블로그 | 플랫폼 | 도메인 | 게시글 수 |
|------|--------|--------|--------|----------|
| 1 | stock-hugo | Hugo | stock.informationhot.kr | 798 |
| 2 | hotissue-hugo | Hugo | hotissue.rotcha.kr | 924 |
| 3 | travel4-hugo | Hugo | tour3.rotcha.kr | 640 |
| 4 | compare-hugo | Hugo | compare.rotcha.kr | 621 |
| 5 | travel2-hugo | Hugo | tour2.rotcha.kr | 645 |
| 6 | rotcha-blog | Hugo | rotcha.kr | 1,367 |
| 7 | travel-hugo | Hugo | rotcha.kr/travel | 659 |
| 8 | interior-hugo | Hugo | interior.informationhot.kr | 587 |
| 9 | rap5-hugo | Hugo | brand.informationhot.kr | 582 |
| 10 | rap3-hugo | Hugo | tax.informationhot.kr | 572 |
| 11 | rap-hugo | Hugo | apt.informationhot.kr | 554 |
| 12 | travel3-hugo | Hugo | tour3.rotcha.kr | 701 |
| 13 | rap2-hugo | Hugo | apply.informationhot.kr | 521 |
| 14 | senior-hugo | Hugo | senior.informationhot.kr | 518 |
| 15 | rap4-hugo | Hugo | rent.informationhot.kr | 513 |
| 16 | dividend-hugo | Hugo | dividend.techpawz.com | 518 |
| 17 | finance-hugo | Hugo | finance.techpawz.com | 512 |
| 18 | appliance-hugo | Hugo | appliance.informationhot.kr | 499 |
| 19 | travel1-hugo | Hugo | tour1.rotcha.kr | 483 |
| 20 | fitness-hugo | Hugo | fitness.informationhot.kr | 483 |

### 3.3 도메인 계열별 블로그 수

| 도메인 계열 | 블로그 수 | 비고 |
|-------------|----------|------|
| `*.techpawz.com` | 44 | ETAP(35) + STAP(4) + 수동(5) |
| `*.informationhot.kr` | 24 | CUAP(15) + RAP(5) + CAP(2) + SEAP(1) + STAP(1) |
| `*.rotcha.kr` | 12 | CAP(6) + TAP(5) + 수동(1) |
| 기타 | 5 | Blogger 플랫폼 포함 |

### 3.4 수동/일시정지 블로그

| 파일 | 블로그 ID | 상태 |
|------|-----------|------|
| `manual_blogs.yaml` | tvshow-blogger, ud-blogger | paused |
| `manual_blog_for_backup.yaml` | rotcha-blog, informationhot-hugo, techpawz-hugo, biz-techpawz-hugo, issue-techpawz-hugo | paused |

---

## 4. 감사 도구의 실행 코드·입력·판정 규칙·오탐 원인·산출물 경로

### 4.1 감사 도구 구성

| 도모 | 파일 경로 | 역할 |
|------|-----------|------|
| 기계 감사 (L1) | `/tmp/5000-content-audit/mechanical_check.py` | 전체 로컬 Hugo `content/posts/{slug}/index.md` 스캔 |
| 의미 평가 (L2) | `/tmp/5000-content-audit/semantic_eval.py` | 100점 만점 루브릭 (794건 표본) |
| Ops 대시보드 실시간 | `ops_dashboard/checks/content_quality.py` | 라이브 HTML 렌더링 검증 (CQ01~CQ08) |
| 사이트맵 수집기 | `/tmp/5000-content-audit/scan_sitemaps.py` | 사이트맵 크롤링 → 포스트 인벤토리 구축 |
| ETAP 품질 가드 | `pipelines/etap/quality_guard.py` | 파이프라인 사전 필터 |

### 4.2 기계 감사 판정 규칙 (`mechanical_check.py`)

| 플래그 | 조건 | 임계값 |
|--------|------|--------|
| `LONG_TITLE` | 제목 글자 수 | `> 60`자 |
| `SHORT_TITLE` | 제목 글자 수 | `< 10`자 |
| `TOO_SHORT` | 이미지/링크/헤더 제거 후 본문 | `< 500`자 |
| `SHORT` | 동일 | `>= 500 AND < 1,500`자 |
| `OK` | 동일 | `>= 1,500`자 |
| `NO_H2` | `## ` 헤더 수 | `== 0` |
| `TEMPLATE_LEAK` | `{{`/`{%` 마커 **또는** `TODO`/`PLACEHOLDER`/`Lorem ipsum`/`example.com` | 둘 중 하나라도 있으면 플래그 |
| `NO_INTERNAL_LINKS` | `internal_links` 필드 | `== 0` |

### 4.3 의미 평가 점수 (100점)

| 카테고리 | 만점 | 주요 삭감 |
|----------|------|-----------|
| 제목 품질 | 20 | LONG_TITLE(-6), SHORT_TITLE(-4), 숫자/연도 없음(-2) |
| 정보 품질 | 25 | TOO_SHORT(-15), SHORT(-8), TEMPLATE_LEAK(-10) |
| 검색 의도 | 15 | 본문 <1,500자(-5), UNVERIFIED |
| 구조/가독성 | 15 | NO_H2(-6), H2 <3(-2), 날짜 없음(-2), 설명 없음(-2) |
| 신뢰/안전 | 10 | 과장 키워드(-4), 저작권 UNVERIFIED |
| 내부 링크 | 10 | 0개(-6), 1개(-3), 외부 링크 0개(-2) |
| 광고/경험 | 5 | 항상 0 (UNVERIFIED) |

**실질 최대 점수:** ~95점 (광고·의도 영역 UNVERIFIED)

**위험 밴드 (794건 표본 기준):**

| 점수 범위 | 건수 | 라벨 |
|-----------|------|------|
| ≥ 90 | 488 | pass |
| 80–89 | 180 | monitor |
| 70–79 | 113 | marginal |
| 60–69 | 8 | at-risk |
| < 60 | 5 | critical |

**평균 점수:** 87.1 (794건 표본 기준)

### 4.4 오탐 원인과 비율

**템플릿 유출 오탐율: 92.5% (37/40건)**

| 오탐 유형 | 건수 | 원인 |
|-----------|------|------|
| `{{< >}}` 숏코드 노출 | 35 | Hugo 숏코드가 실제 HTML로 렌더링됨 → `{{< inchcm >}}` 등이 정상 표시되나 기계 감사에서 `{{` 패턴 매칭 |
| 프론트머터 `{{` | 2 | YAML 값 내 `{{` — 정상 Hugo 템플릿 문법 |

**CQ03 오탐 (이전):** ETAP(영어) 블로그에서 쿠팡 공시문 검출 → `skip_product_rules` 플래그로 해결

**기계 감사 오탐 메커니즘:**
- `TEMPLATE_LEAK`은 정규식 `{{|\{%` 매칭 → Hugo 숏코드(`{{< >}}`)도 오탐
- `NO_INTERNAL_LINKS`는 본문 마크다운만 검사 → Hugo 숏코드(`{{< relref >}}`) 내 링크 미인식

### 4.5 산출물 경로

| 파일 | 형식 | 설명 |
|------|------|------|
| `/tmp/5000-content-audit/mechanical_all.jsonl` | JSONL (24,986줄) | 전체 기계 감사 결과 |
| `/tmp/5000-content-audit/post_inventory.jsonl` | JSONL | 사이트맵 기반 포스트 인벤토리 |
| `/tmp/5000-content-audit/post_audit_results.jsonl` | JSONL (794줄) | 의미 평가 표본 결과 |
| `/tmp/5000-content-audit/blog_registry_raw.json` | JSON | 블로그 레지스트리 |
| `/tmp/5000-content-audit/batches/batch_00~31.json` | JSON (32파일) | L2 배치 입력 |
| `/tmp/5000-content-audit/priority_queue.csv` | CSV | 상위 40 수리 대상 |
| `/tmp/5000-content-audit-gate/gate_review.md` | MD | 게이트 검토 보고서 |
| `/tmp/5000-content-audit-gate/verdict.json` | JSON | 최종 판정 |
| `/tmp/5000-content-audit-gate/template_leak_live_validation.jsonl` | JSONL | 라이브 템플릿 유출 검증 |
| `/tmp/5000-content-audit-gate/internal_link_validation.jsonl` | JSONL | 내부 링크 검증 |
| `/tmp/5000-content-audit-gate/no_internal_links_classification.json` | JSON | NO_INTERNAL_LINKS 블로그별 분류 |
| `data/audit-archive/audit-20260818/` | 디렉터리 (297파일, 92.5MB) | 영구 보관 (SHA-256 검증 완료) |

---

## 5. NO_INTERNAL_LINKS 18,522건의 집계 근거와 블로그별 분포

### 5.1 집계 방법론

```
Stage 1: mechanical_all.jsonl (24,986건)
         └─ 필터: internal_links == 0
            → 18,542건 (원시 후보)

Stage 2: frozen 제외
         └─ 20개 interior-hugo 실험 slug 제거
            → 18,542 − 20 = 18,522건 (최종)

Stage 3: 블로그별 집계
         └─ 80개 블로그 합계: 18,522 ✅
```

**근거 파일:**
- `mechanical_all.jsonl` (24,986줄) —权威 소스
- `critical_issue_exact_counts.json` — 원시 18,542건 확인
- `no_internal_links_classification.json` — frozen 제외 후 18,522건
- `gate_review.md` 라인 23 — "NO_INTERNAL_LINKS 18,542건" (원시 카운트)

**비율 계산:** 18,522 ÷ 24,986 = 0.7413 → **74.1%**

### 5.2 블로그별 분포 (상위 15개)

| 순위 | 블로그 | NO_INTERNAL_LINKS | 전체 감사 | 비율 |
|------|--------|------------------:|----------:|-----:|
| 1 | techpawz-hugo | 1,556 | 1,558 | 100% |
| 2 | rotcha-blog | 1,265 | 1,367 | 93% |
| 3 | hotissue-hugo | 659 | 681 | 97% |
| 4 | biz-techpawz-hugo | 612 | 612 | 100% |
| 5 | travel3-hugo | 601 | 701 | 86% |
| 6 | travel-hugo | 571 | 659 | 87% |
| 7 | travel4-hugo | 542 | 640 | 85% |
| 8 | compare-hugo | 533 | 621 | 86% |
| 9 | travel2-hugo | 531 | 645 | 82% |
| 10 | interior-hugo | 490 | 601 | 82% |
| 11 | senior-hugo | 486 | 519 | 94% |
| 12 | fitness-hugo | 439 | 483 | 91% |
| 13 | baby-hugo | 425 | 459 | 93% |
| 14 | travel1-hugo | 414 | 483 | 86% |
| 15 | appliance-hugo | 402 | 499 | 81% |

**전체 80개 블로그** 중 NO_INTERNAL_LINKS가 0건인 블로그는 **없음**.

### 5.3 도메인 계열별 분포

| 도메인 계열 | 블로그 수 | NO_INTERNAL_LINKS 합계 |
|-------------|----------|----------------------:|
| `*.rotcha.kr` | 12 | 5,017 |
| `*.informationhot.kr` | 24 | ~7,000+ (CUAP 15 + RAP 5 + CAP 2 + SEAP 1 + STAP 1) |
| `*.techpawz.com` | 44 | ~6,500+ (ETAP 35 + 수동 5 + STAP 4) |

### 5.4 발견된 불일치

| # | 불일치 | 위치 | 상세 |
|---|--------|------|------|
| D1 | `by_family` 값이 블로그별 합계와 불일치 | `no_internal_links_family.json` | techpawz: 44 vs 실제 2,492건 — 다른 지표로 추정 |
| D2 | `ratio_by_blog` 합계 24,473 ≠ 감사 24,986 | `no_internal_links_family.json` | 차이 513건 — ratio_by_blog에서 제외된 블로그 존재 |

---

## 6. 템플릿 유출 2건과 404 2건의 URL·소스 위치·재현 절차

> **참고:** 초기 조사에서 "1건"으로 보고되었으나, 라이브 검증 결과 **템플릿 유출 2건**으로 확인됨.

### 6.1 템플릿 유출 #1 (LIVE_TEMPLATE_LEAK)

| 항목 | 값 |
|------|-----|
| **URL** | `https://laptop.informationhot.kr/posts/게이밍노트북-추천-hp-오멘부터-에일리언웨어까지-합격점-top-5/` |
| **블로그** | `laptop-hugo` |
| **마커** | `{{}}` — JSON-LD `<script type="application/ld+json">` 내 빈 Hugo 숏코드 |
| **소스 파일** | `/Users/twinssn/Projects/CUAP/laptop-hugo/content/posts/게이밍노트북-추천-hp-오멘부터-에일리언웨어까지-합격점-top-5/index.md` |
| **소스 위치** | 125행: `"description": "{{}} 2026년 7월, 게이밍노트북을 알아보고 계신가요?..."` |
| **HTTP 상태** | 200 |
| **재현 절차** | 1. URL 접속 → 2. 페이지 소스 보기 → 3. `<script type="application/ld+json">` 검색 → 4. `"description": "{{}} 2026년 7월..."` 확인 |

### 6.2 템플릿 유출 #2 (LIVE_TEMPLATE_LEAK)

| 항목 | 값 |
|------|-----|
| **URL** | `https://beauty.informationhot.kr/posts/neombeojeu-in-3beon-dojagigyeol-vs-1beon-jinjeong-toner-choegeun-chulsi-la-in-eob-cheos-insanggwa-silsa-yong-neu-kkim/` |
| **블로그** | `beauty-hugo` |
| **마커** | `{{}}` — 동일 패턴, JSON-LD 내 빈 숏코드 |
| **소스 파일** | `/Users/twinssn/Projects/CUAP/beauty-hugo/content/posts/neombeojeu-in-3beon-dojagigyeol-vs-1beon-jinjeong-toner-choegeun-chulsi-la-in-eob-cheos-insanggwa-silsa-yong-neu-kkim/index.md` |
| **소스 위치** | 135행: `"description": "{{}} 2026년 7월, 스킨케어 루틴을 간소화하면서도..."` |
| **HTTP 상태** | 200 |
| **재현 절차** | 위와 동일 — `<head>` 내 JSON-LD에서 `{{}}` 확인 |

**근본 원인:** AI 글쓰기 프롬프트의 섹션 템플릿이 `{{}}` 플레이스홀더를 남기고, JSON-LD 문자열 안에 직렬화되어 Hugo가 처리하지 못하고 통과시킴.

### 6.3 404 #1

| 항목 | 값 |
|------|-----|
| **URL** | `https://issue.techpawz.com/posts/인치-센치-변환-계산기/` |
| **블로그** | `issue-techpawz-hugo` |
| **HTTP 상태** | 404 |
| **소스 파일** | `/Users/twinssn/Projects/issue-techpawz-hugo/content/posts/인치-센치-변환-계산기.md` |
| **프론트머터** | `title: 인치 센치 변환 계산기`, `draft: false`, `featureimage: issue.techpawz.com/wp-content/uploads/...` |
| **원인** | 소스 파일 존재하나 Hugo 사이트에 미빌드/미배포. 숏코드 `{{< inchcm >}}` 미등록. WordPress 마이그레이션 아티팩트 (`wp-content/uploads` URL 포함). |

### 6.4 404 #2

| 항목 | 값 |
|------|-----|
| **URL** | `https://issue.techpawz.com/posts/날짜-계산기/` |
| **블로그** | `issue-techpawz-hugo` |
| **HTTP 상태** | 404 |
| **소스 파일** | `/Users/twinssn/Projects/issue-techpawz-hugo/content/posts/날짜-계산기.md` |
| **프론트머터** | `title: 커플들을 위한 날짜 계산기`, `draft: false` |
| **원인** | 동일 — 소스 존재, 미빌드/미배포. 숏코드 `{{< datecalc >}}` 미등록. |

### 6.5 404 근본 원인 분석

둘 다 `issue-techpawz-hugo`에서 발생. 패턴:
1. `.md` 파일이 로컬 `content/posts/`에 존재, `draft: false`
2. Hugo 사이트가 이 파일이 추가된 후 재빌드/재배포되지 않음
3. `featureimage`가 `issue.techpawz.com/wp-content/uploads/...` — WordPress 아티팩트
4. 미등록 숏코드 (`inchcm`, `datecalc`) 사용

---

## 7. Interior 실험 20개 대상·가설·지표·동결 범위·Day 3 판정 기준

### 7.1 실험 개요

| 항목 | 값 |
|------|-----|
| **실험명** | `APPROVE_INTERIOR_SITEMAP_RESUBMIT_EXPERIMENT` |
| **문서 경로** | `.planning/m5-knowledge-asset/M5-KA2-PLAN.md` (부록 A, 117~239행) |
| **커밋** | `5c757cc17` — `docs: conditional final roadmap + M5-KA2 interior sitemap experiment runbook` |
| **시작 시각** | 2026-08-18T06:31:53.937Z (사이트맵 제출) |
| **Day 3 시각** | 2026-08-21T06:31:54Z (72시간 후) |
| **상태** | `ACTIVE_WAITING_DAY3` |

### 7.2 가설

> **발견 (AUDIT_INTERIOR_ZERO_VISIBILITY):** `interior.informationhot.kr`의 사이트맵이 GSC에 등록되어 있고 오류 0건이나, Google이 20개 URL 전부를 "URL is unknown to Google"(NEUTRAL)으로 보고.
>
> **가설:** 사이트맵 재제출이 대상 URL의 색인을 촉발할 것이다. 처리군(사이트맵 포함 18개)이 `coverageState` 변화를 보이고, 대조군(사이트맵 미포함 2개)은 변화가 없으면, 사이트맵 신호가 확인됨.

### 7.3 20개 대상 slug

**처리군 (18개 — 사이트맵 포함):**

| # | Slug |
|---|------|
| 1 | 허리-편한-게이밍의자-장시간-게임용-제품-비교-분석 |
| 2 | 플럭스장수램프-다운라이트-2026년-최신-스펙과-가격-비교 |
| 3 | 까르엠가구-침실-인테리어-완성하는-수납-침대-실사용-후기 |
| 4 | 허리-통증-줄여주는-학생용-공부의자-고르는-핵심-기준 |
| 5 | 거실-분위기-바꾸는-t5-led-간접조명-설치-팁 |
| 6 | 거실등-교체-눈-피로-적은-led-슬림형-제품-비교 |
| 7 | 집중력-높이는-거실-공부방-인테리어-가구-배치법 |
| 8 | 좁은-원룸-공간-활용도-높은-가구-배치와-실속-정보 |
| 9 | 가구느낌-베스트-책상-실속-있는-인테리어-가구-top-5 |
| 10 | 단일색상-거실가구-인테리어-톤온톤-배치-요령 |
| 11 | 좁은-현관-수납장-공간-활용도-높이는-신발장-비교 |
| 12 | 유니홈바이앳올-이동식-행거-추천-실속-있는-공간-활용-가이드 |
| 13 | 수납장-추천---소웰홈오아루-실속-비교 |
| 14 | 가구밸리-아리브리-top-5-4만원대부터-18만원대-소파의자-추천 |
| 15 | 프린홈-모션핏-vs-클렙튼-전동-리클라이너-36만99만원대-실속-비교 |
| 16 | 가죽소파-추천-50만원-이하-합격점-top-5 |
| 17 | top-5-가구고래-선택한-이유와-특징 |
| 18 | 다용도테이블-고르는-법-2026년-최신-가이드 |

**대조군 (2개 — 사이트맵 미포함, 고아 페이지):**

| # | Slug |
|---|------|
| 19 | 주방-수납장-추천-top5-2026년 |
| 20 | 가구밸리-추천-top5-2026년 |

### 7.4 추적 지표

| 지표 | 설명 |
|------|------|
| `coverageState` | 주요 지표 — "URL is unknown to Google" → 다른 상태 전이 여부 |
| `verdict` | GSC 판정 |
| `robotsTxtState` | robots.txt 상태 |
| `indexingState` | 색인 상태 |
| `pageFetchState` | 페이지 가져오기 상태 |
| `lastCrawlTime` | 마지막 크롤 시각 |
| `googleCanonical` | Google canonical URL |

### 7.5 Day 3 판정 기준 (4가지 판정)

| 판정 | 조건 |
|------|------|
| **SITEMAP_DISCOVERY_SIGNAL** | 처리군 ≥1 URL "unknown" 탈출 **AND** 대조군 0 탈출 → 사이트맵이 색인 신호 |
| **WEAK_SITEMAP_SIGNAL** | 처리군 ≥1 탈출 **AND** 대조군도 탈출 → 비특이적 크롤 (사이賍マップ만이 원인 아님) |
| **NON_SPECIFIC_DISCOVERY** | 처리군 0 탈출 **AND** 대조군 ≥1 탈출 → 사이트맵과 무관한 크롤 |
| **NO_CHANGE** | 둘 다 0 탈출 → 사이트맵 신호 효과 없음 |

### 7.6 동결 범위

- **20개 slug 전부 동결** — 추가·변경·삭제 금지
- Hugo 재빌드 금지, 사이트맵 수정 금지, 내부 링크 삽입 금지
- 색인 요청 금지, DB/코드/스케줄러 변경 금지
- **Day 0 보정:** 2026-08-18 ~14:00에 오류로 Day 3 실행됨 (제출 후 35분) → 제외됨, Treatment 0/18, Control 0/2 = NO_CHANGE

### 7.7 산출물 경로

| 파일 | 경로 |
|------|------|
| 실험 계획 | `.planning/m5-knowledge-asset/M5-KA2-PLAN.md` |
| 동결 slug | `/tmp/5000-content-audit/frozen_interior_slugs.json` |
| 동결 매칭 | `/tmp/5000-content-audit/frozen_match.json` |
| 감사 매니페스트 | `data/audit-archive/audit-20260818/content-audit/audit_manifest.json` |
| 게이트 검토 | `data/audit-archive/audit-20260818/content-audit-gate/gate_review.md` |
| 게이트 판정 | `data/audit-archive/audit-20260818/content-audit-gate/verdict.json` |

---

## 8. CI/CD·스케줄러·환경변수·외부 API 의존성·롤백 방식

### 8.1 CI/CD

| 항목 | 상태 |
|------|------|
| GitHub Actions | `.github/workflows/indexnow.yml` 1개만 존재 — IndexNow URL 전송용 |
| 빌드/테스트 CI | **없음** |
| 린트/타입 체크 | `ruff`, `mypy` requirements.txt에 있으나 CI 미연결 |
| 배포 방식 | 100% 로컬/launchd — `dispatcher.py` → `deploy.py` → `wrangler` |

### 8.2 스케줄러

**핵심 루프 (`scheduler.py:1412-1441`):**
```
main() → register_schedules() → while True: schedule.run_pending() + 30초 대기
```

**스케줄 등록:**

| 주기 | 작업 | 비고 |
|------|------|------|
| 블로그별 시간 | `queue_publish(blog_id)` | `blogs.yaml` 기반, 60초 블로그 간 딜레이 |
| 매일 05:00 | `_run_etap_collectors` | viator, aviasales, topic_expander, nomad, omio, airalo |
| 매일 05:30 | `_run_senior_sync` | senior.db 서비스 데이터 동기화 |
| 매일 06:00 | `_run_festival_refresh` | 페스티벌 데이터 갱신 |
| 매일 06:10 | `_run_stap_collector` | STAP 데이터 수집 |
| 매일 06:30 | `_run_car_refresh` | CAR 일일 갱신 |
| 매일 06:45 | `_run_indexnow` | IndexNow URL 전송 |
| 매일 22:45 | `batch_deploy` | `scripts/batch_push.sh` |
| 매시간 :50 | `_run_cuap_collector` | CUAP 자동 수집 |
| 매일 02:00 | `_run_keyword_expander` | CUAP 키워드 확장 |
| 매일 23:00 | `_run_quality_scan` | 품질 스캔 + Telegram 리포트 |
| 매일 23:50 | `daily_report` | 교차 프로젝트 집계 |
| 6시간마다 | `_run_p32_scan` | 배포 콘텐츠 빈 값 체크 |
| 매시간 | `_run_recheck_all` | Phase 71 안전 재검증 |
| 매주 월 10:00 | `_run_weekly_offtopic_report` | CUAP 오프토픽 리포트 |

**launchd plist:**

| plist | 역할 |
|-------|------|
| `com.5000.scheduler.plist` | 스케줄러 (`RunAtLoad=true`, `KeepAlive=true`) |
| `com.5000.scheduler-watchdog.plist` | 워치독 |
| `com.5000.ops-dashboard.plist` | Flask 대시보드 (port 5060) |
| `com.5000.analytics.plist` | 분석 |
| `com.5000.master-backup.plist` | 마스터 백업 |

### 8.3 환경변수

**필수 환경변수:**

| 변수 | 출처 | 용도 |
|------|------|------|
| `OPENAI_API_KEY` | `~/.env.common` | OpenAI GPT 호출 |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | `~/.env.common` | 에러/일일 알림 |
| `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | `~/.env.common` | Cloudflare R2 업로드 |
| `CLOUDFLARE_ACCOUNT_ID` | `.env` | `fac9808c757df31d797190c529aaa71a` |
| `BLOGGER_CREDENTIALS` | `.env` | Blogger OAuth 토큰 경로 |
| `UPSTAGE_API_KEY` | `.env` | Upstage LLM 프로바이더 |
| `DART_API_KEY` | `.env` | 한국 금융 공시 |
| `DATA_GO_KR_API_KEY` | `.env` | 한국 공공 데이터 포털 |
| `OPENAI_MODEL` | `.env` | 기본값: `gpt-4o-mini` |

**보안 참고:** `.env`에 평문 API 키 존재. `.gitignore`로 보호됨.

### 8.4 외부 API 의존성

| API | 모듈 | 프로토콜 | 용도 |
|-----|------|----------|------|
| **OpenAI GPT** | `shared/ai_writer.py` | REST | 콘텐츠 생성 (16개 무료 모델 폴백 → DeepSeek 최후) |
| **Google Blogger** | `shared/blogger_publisher.py` | REST v3 | Blogger.com 발행 |
| **WordPress** | `shared/wordpress_publisher.py` | XML-RPC | WordPress 발행 |
| **Telegram Bot** | `shared/telegram_notifier.py` | REST | 알림 |
| **Cloudflare R2** | `shared/r2_uploader.py` | S3 호환 | 이미지 업로드 |
| **IndexNow** | `scripts/indexnow.py` | REST | 검색 엔진 색인 알림 |
| **Viator Affiliate** | `pipelines/etap/pipeline.py` | SQLite + URL | 여행 상품 제휴 |
| **Coupang Partners** | `shared/coupang_senior.py` | REST | 상품 제휴 데이터 |
| **Google Search Console** | `.planning/m5-knowledge-asset/` | REST | interior 실험 색인 모니터링 |

### 8.5 롤백 방식

| 메커니즘 | 상태 | 비고 |
|-----------|------|------|
| **공식 롤백 절차** | **없음** | 통합 롤백 프로시저 미정의 |
| **Git 기반** | 부분적 | 이전 커밋으로 되돌리기 가능하나, Hugo 사이트 콘텐츠는 로컬 파일 시스템 |
| **R2 이미지** | 영구 | 업로드된 이미지는 롤백 불가 |
| **`.bak` 파일** | 수동 | DB 백업 (예: `data/content.db.bak_*`) — 수동 복구 |
| **batch_deploy 재실행** | 가능 | `scripts/batch_push.sh` 재실행으로 이전 상태 재배포 가능 |
| **Hugo 소스 재빌드** | 가능 | `content/posts/`에서 이전 버전 복원 후 `hugo --gc --minify` |

**핵심 위험:** 실패한 배포는 수동으로 이전 상태를 재배포해야 함. 자동 롤백 없음.

---

## 9. 최근 커밋·미배포 변경·알려진 장애·기술부채

### 9.1 최근 30커밋 (커밋 SHA 포함)

| # | SHA (단축) | 날짜 | 메시지 |
|---|------------|------|--------|
| 1 | `5c757cc17` | 2026-08-18 | docs: conditional final roadmap + M5-KA2 interior sitemap experiment runbook |
| 2 | `d0dfeca28` | 2026-08-17 | merge: phase62-m5-qb (controlled) [M5] |
| 3 | `9642f71df` | 2026-08-17 | phase-62: add incident contract + pipeline extra (report-only) [62-03] |
| 4 | `060f74ad9` | 2026-08-17 | phase-62: add rule hierarchy loader (global/family/blog) [62-02] |
| 5 | `16505c7c7` | 2026-08-17 | phase-62: add ValidationResult contract (report-only) [62-01] |
| 6 | `403f7fba3` | 2026-08-17 | Merge PR-Phase69-M4: Dashboard SSOT (controlled merge) |
| 7 | `bc9ad24a1` | 2026-08-17 | fix(phase69-M4): API publish-errors total respects blog_id/severity/state filters |
| 8 | `237003227` | 2026-08-17 | feat(phase69-M4): publish-errors dashboard WAITING/pagination/reason exposure |
| 9 | `f03acaa4c` | 2026-08-17 | Merge PR-Phase69-M3: Incident Taxonomy (controlled merge) |
| 10 | `ebd191d08` | 2026-08-17 | fix(phase69): pass resolved pipeline on no_topics event + lock CAP/car contract |
| 11 | `b695664d5` | 2026-08-17 | feat(phase69): populate pipeline on no_topics event + lock incident/taxonomy contract |
| 12 | `75e7f968c` | 2026-08-17 | Merge commit '0879d258e' |
| 13 | `0879d258e` | 2026-08-17 | feat(phase71): add CAP car no_topics recovery runbook + regression test |
| 14 | `7253f0524` | 2026-08-17 | Merge PR-CAP-1: Pipeline Result Contract (controlled merge) |
| 15 | `21c83c9d4` | 2026-08-17 | feat: add backward-compatible pipeline result contract |
| 16 | `1358ec986` | 2026-08-17 | chore(ops): register P1 known issues — DOUBLE-FAILURE-COUNT-INCREMENT + 4 follow-ups |
| 17 | `67b556e50` | 2026-08-17 | release: deploy publish reliability hotfix A through stabilization |
| 18 | `7205f8f66` | 2026-08-17 | fix(ops): serialize incident upsert identity under concurrency |
| 19 | `13569fc86` | 2026-08-17 | fix(dashboard): candidate-state blog table uses blog_id key |
| 20 | `35cdaf0d8` | 2026-08-17 | feat(dashboard): show incident and pipeline availability |
| 21 | `ac96a0011` | 2026-08-17 | feat(ops): gate publishing on candidate availability |
| 22 | `a369cb1fa` | 2026-08-17 | feat(ops): correlate refresh failures and bound catchup retries |
| 23 | `2fc5fff69` | 2026-08-16 | fix(ops): deduplicate publish incidents with stable lifecycle |
| 24 | `fe79d4684` | 2026-08-16 | Phase74: record execution in STATE.md (7/7 SC, additive/non-destructive) |
| 25 | `45f328a1e` | 2026-08-16 | Phase74 W4: connect_branch_db unit test + crash-read site sweep (SC-7) |
| 26 | `2b5ebd240` | 2026-08-16 | Phase74 W1: connect_branch_db guard (allow_create=False) + stock/rap crash-path migration |
| 27 | `59e5f6e36` | 2026-08-16 | Phase74 W2: backup gap fill (senior/course/gap) + 26-DB attribution |
| 28 | `84c544f05` | 2026-08-16 | Phase74 W3: BRANCH_DB_RUNBOOK.md (grade A/B/C + destructive-ops 4-step + source='' preservation) |
| 29 | `826d80881` | 2026-08-16 | Phase73: mark SC-4 applied (CAP ad config) in STATE.md |
| 30 | `10d5dee2d` | 2026-08-16 | Phase73: update STATE.md with execution record (SC-1/2/3/5/7/8 applied, SC-4 skip, SC-7 deferred) |

### 9.2 미배포 변경

| 항목 | 상태 |
|------|------|
| 로컬 커밋 미푸시 | **85건** (origin/main보다 전진) |
| 수정된 작업 트리 파일 | **16건** (unstaged) |
| 추적 안 되는 파일 | **~50건** (untracked) |
| 스테이징된 변경 | 0건 |

**핵심 미배포 파일:**
- `shared/ai_writer.py` (핵심 LLM 모듈, 135줄 변경)
- `shared/publishers/hugo_writer.py` (4줄 변경)
- `pipelines/curation/pipeline.py` (9줄 변경)
- `pipelines/curation/writer.py` (23줄 변경)
- `pipelines/etap/cruise_writer.py`, `culture_writer.py`, `quality_guard.py`
- `ops_dashboard/checks/content_quality.py`

**새로운 파일:**
- `shared/cuap_title_llm.py`, `shared/cuap_title_safety.py`
- `shared/etap_writing_rules.py`, `shared/title_quality.py`
- `tests/ops_dashboard/test_content_quality_etap_gate.py`
- `.planning/worklog/WL-2026081{4~7}-*.md` (22개 워크로그)
- `data/audit-archive/` (감사 영구 보관)
- `logs/destructive_2026-08-0{6~10,14,17}.log`

### 9.3 알려진 장애

| 블로그/패턴 | 증상 | 근본 원인 | 상태 |
|------------|------|-----------|------|
| travel2-hugo | `no_result` (10회 연속) | `_travel_sigungu_recently_published()` 가드 14일 룩백 16개 도 차단 | 부분 해결 (7일로 단축 검토 중) |
| sector-hugo | `no_content` (23회 연속) | 토픽 소진 + 제목/업종 중복 가드 | 미해결 |
| appliance-hugo | `similar_title` | "듀스핀" 키워드 제목 패턴 반복 | 미해결 |
| laptop-hugo | `broken_featureimage` | Coupang 이미지 URL 255자 초과 | **해결** (max_len 200으로 축소) |
| kuta-hugo | `broken_featureimage` | WordPress 도메인 경로, R2 썸네일 없음 | **해결** (batch_thumbnails.py) |
| CUAP 전체 | lead 단락 과대 | Blowfish CSS `.lead` 1.5rem | **해결** (custom.css) |
| kitchen-hugo | 본문 fade-in 빈 값 | CSS+JS 제거 | **해결** |

### 9.4 기술부채

| 항목 | 상세 | 출처 |
|------|------|------|
| **콘텐츠 시스템 규칙 미구현** | 7+ TODO: `interest_posttax < interest_pretax` 게이트, 공통 빈 제목/본문 게이트, Jaccard 유사도, 테이블 내 괄호 보호, 정량 검증 DB, STAP 환경변수 상속, C08 라이브 비교 | `docs/content-system-rules.md` |
| **대시보드 사각지대** | 8개 텍스트/구조 품질 이슈 미감지 (빈 이미지, 본문 <800자, H2 <2, 내부링크 0, OCR 오탈자, 잔존 라틴어, 중복 단어, 브랜드 환각) | `.planning/DIAGNOSIS-2026-08-07.md` |
| **테스트 부채** | Phase 61에서 21개 기존 테스트 실패 유지 | Phase 61 문서 |
| **`.bak` 파일 59개** | DB 백업 파일 누적 | 파일 시스템 |
| **플레이스홀더 GA4 ID** | Google Analytics ID 미설정 | 설정 파일 |
| **Phase 10 숏코드 토글** | `hugo_writer.py`에서 Blowfish 숏코드 토글 비활성화 | `STATE.md` |
| **STAP 환경변수 델타** | `_run_stap` 경로에서 `CLOUDFLARE_API_TOKEN` 상속 위험 | `docs/content-system-rules.md` |
| **INDEX.md 불일치** | 최신 항목 2026-08-05 vs 최신 커밋 2026-08-17 | `.planning/triage/INDEX.md` |

---

## 10. 운영 권한과 승인 절차

### 10.1 저장소 접근

| 항목 | 값 |
|------|-----|
| 원격 저장소 | `git@github.com:hugh79757-cmyk/5000.git` |
| 브랜치 | `main` 단일 브랜치 개발 |
| 기여자 | UNKNOWN (단일 개발자 프로젝트) |

### 10.2 배포 권한

| 항목 | 값 |
|------|-----|
| Cloudflare 프로필 | `hugh79757` (`hugh79757@gmail.com`) |
| Wrangler 버전 | 4.110.0 |
| 계정 ID | `fac9808c757df31d797190c529aaa71a` |
| 권한 범위 | account, user, workers(write), pages(write), d1(write), ai(write), offline_access |
| RBAC | **없음** — 단일 OAuth 프로필 |

### 10.3 대시보드 접근

| 항목 | 값 |
|------|-----|
| 인증 | HTTP Basic Auth |
| 기본 자격증명 | `ops` / `112233` |
| 환경변수 오버라이드 | `OPS_USER`, `OPS_PASSWORD` |
| 역할 분리 | **없음** — 읽기 전용 감사자 vs 배포 승인자 구분 없음 |

### 10.4 승인 절차

| 메커니즘 | 위치 | 설명 |
|-----------|------|------|
| **pending-fixes 승인 큐** | `ops_dashboard/db.py` (`pending_fixes` 테이블) + `ops_dashboard/app.py` | 파괴적 자동 수정이 `proposed`로 큐잉 → Human이 `POST /api/pending-fixes/<id>/approve`로 승인 |
| **severity 기반 정책** | `ops_dashboard/docs/agent-reference/OPERATIONS_SIGNAL_SPEC.yaml` | CRITICAL: publish/deploy/delete/dns 등 human 승인 필수; MAJOR: bulk_retry/publish/deploy; MINOR: rule_relaxation/guard_bypass |
| **파괴적 작업 4단계** | `OPERATIONS-CHARTER.md`, `.planning/worklog/README.md` | 1. 사전 카운트 → 2. 백업 → 3. 실행 → 4. 사후 대조 + 로그 + 워크로그 |
| **배포 기술 검증** | `shared/publishers/deploy.py:_pre_deploy_validate()` | `public/index.html` 존재 검증 (하드 게이트) |
| **배포 직렬화** | `fcntl.flock()` on `/tmp/wrangler_deploy.lock` | 동시 배포 방지 (60초 타임아웃) |

### 10.5 보안 현황

| 항목 | 상태 |
|------|------|
| `.gitignore` | `.env`, `api_keys.yaml`, `*.db`, `*token*.pickle`, `client_secret*.json` 제외 |
| API 키 관리 | `config/api_keys.yaml` (커밋됨, 값은 빈 문자열) + `.env` (평문 키, 추적 안 됨) |
| `~/.env.common` | OPENAI/TELEGRAM/R2 키 포함 — 프로젝트 외부 |
| 비밀 노출 | 감사 산출물에서 refresh_token/client_secret/access_token 0건 확인 |
| 핵심 위험 | **RBAC 없음** — `localhost:5060` 네트워크 접근 시 `ops/112233`으로 배포 승인 가능 |

---

## 잔존 위험

1. **85개 미푸시 커밋:** 로컬과 원격의 괴리가 커지고 있음. 충돌 또는 장애 시 복구 복잡도 증가.
2. **공식 롤백 절차 부재:** 실패 배포 시 수동 복구만 가능.
3. **RBAC 없음:** 대시보드 Basic Auth가 유일한 접근 제어. `localhost` 이상의 네트워크 접근 시 배포 승인 가능.
4. **`shared/ai_writer.py` 미배포 변경:** 핵심 LLM 모듈 변경이 85커밋에 포함되지 않음.
5. **Sector/Travel 가드 과도함:** `no_content`/`no_result` 연속 실패 지속.
6. **Interior Day 3 대기:** 2026-08-21T06:31:54Z까지 72시간 대기. 사전 실행 금지.
7. **콘텐츠 시스템 7+ TODO 미구현:** `docs/content-system-rules.md`에 명시된 미구현 규칙.
8. **테스트 21건 실패:** Phase 61에서 발견된 기존 테스트 부채.
9. **ISSUE-TECHPAWZ 404 2건:** 소스 존재하나 미빌드 — WordPress 마이그레이션 미완료.
10. **템플릿 유출 2건 라이브:** JSON-LD 내 `{{}}` — AI 글쓰기 프롬프트 템플릿 누출.

---

## 감사 산출물 요약

| 산출물 | 경로 | 크기 |
|--------|------|------|
| 기계 감사 원본 | `/tmp/5000-content-audit/mechanical_all.jsonl` | ~28MB |
| 포스트 인벤토리 | `/tmp/5000-content-audit/post_inventory.jsonl` | ~3MB |
| 의미 평가 표본 | `/tmp/5000-content-audit/post_audit_results.jsonl` | ~1MB |
| 게이트 검토 | `/tmp/5000-content-audit-gate/gate_review.md` | ~50KB |
| 게이트 판정 | `/tmp/5000-content-audit-gate/verdict.json` | ~10KB |
| Priority Queue | `/tmp/5000-content-audit/priority_queue.csv` | ~5KB |
| 영구 보관 | `data/audit-archive/audit-20260818/` | 92.5MB (297파일) |
| SHA-256 검증 | `data/audit-archive/audit-20260818/checksums.json` | ~30KB |
| NO_INTERNAL_LINKS 분류 | `/tmp/5000-content-audit-gate/no_internal_links_classification.json` | ~100KB |
| Interior 실험 계획 | `.planning/m5-knowledge-asset/M5-KA2-PLAN.md` | ~15KB |
