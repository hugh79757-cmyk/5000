# Universal Error Lookbook (SSOT)

> 모든 발행 오류의 감지→진단→수정→검증 절차 단일 참조.
> 생성: 2026-08-23 · 근거: /tmp/error_taxonomy.txt (P코드·stage·check_results 전수 추출)
> 레거시 레시피: docs/APPENDIX_C_FIX_RECIPES.md (R규칙 상세), ops_dashboard/docs/agent-reference/ERROR_PLAYBOOKS.md (P코드 상세)

## 매핑표

| ERR | 유형 | P코드/체크 | 대시보드 노출 |
|---|---|---|---|
| 001 | no_keyword | stage=no_keyword, P17 | ❌ 미노출 |
| 002 | 콘텐츠 수급 실패 | P01 P02 P26 P27 P30 | ✅ /publish-errors |
| 003 | 썸네일 404 | THUMBNAIL-01, P06 | ✅ /standards |
| 004 | 이미지 URL 손상 | R2-01, P09 P23 | ✅ /standards |
| 005 | GA4 누락 | ga4_id NULL | ✅ /schema |
| 006 | GA4 공유/이중삽입 | ga4:shared | ⚠️ /schema 주의 표시만 |
| 007 | H2 구조 위반 | H2-GUARD | ❌ live 체크 부재 |
| 008 | 누수/제목 차단 | P03 P07 P08 P10 P11 | ✅ /publish-errors |
| 009 | Hugo 빌드 실패 | P05 | ✅ render_health |
| 010 | 배포 실패 | P04 | ✅ /publish-errors (541건 최다) |
| 011 | API rate-limit | P13 | ❌ api_call_log 미노출 |
| 012 | 데이터 만료/소진 | P19 P27 | ⚠️ data_stock 체크만 |
| 013 | 스케줄러 침묵사 | heartbeat stale | ❌ (watchdog 로그 /tmp) |
| 014 | 잡 정지/timeout | P18 P20 P25 | ✅ resource_health |
| 015 | 스키마 드리프트 | schema_registry | ✅ /schema |
| 016 | 계약 불일치 | P28 P29 P32 | ✅ /publish-errors |
| 017 | Telegram 발송 실패 | P31 | ✅ /publish-errors |
| 018 | LLM 폴백 전멸 | P22 | ✅ /publish-errors |
| 019 | 설정 오류 | P21 | ✅ /publish-errors |
| 020 | 미등록 오류 | unknown_failure, P33+ | ⚠️ events에 기록, problems.yaml 미등록 |
| 021 | 콘텐츠 날짜 만료 | CF-01 (content_freshness=stale) | ✅ /standards (content_freshness) |
| 022 | 데이터 소스 갱신 중단 | CF-01 (content_freshness=db_stale) | ✅ /standards (content_freshness) |
| 023 | desc 오염(related 블록 유입) | desc 라인 마커 검사 | ❌ 체크 부재 (2026-09-05 발견, rap 792건) |
| 024 | CoT 릭(발행 유물) | c04_prompt_leak | ⚠️ 최근 7일 윈도우만 — 과거분 미탐지 |
| 025 | 지역 왜곡(rap) | keyword 시군구 vs 본문 | ❌ 사후 체크 부재 (발행 게이트만 존재) |
| 026 | 게이트 자체 오판 | W5 이미지 regex 중첩 대괄호 | ❌ 게이트 내부 결함 — 오판 방지 검사 없음 |
| 027 | 제목 잘림(트렁케이션) | 제목 완결성/'…' 말미 | ❌ 체크 부재 (CAP 67.5% — validators.py 수정됨) |
| 028 | desc-본문 수치 불일치 | desc 수치 vs 본문 산술 | ❌ 체크 부재 (CAP 91%) |
| 029 | stale public 고아 HTML | 삭제 콘텐츠 잔존 배포 | ❌ rc만 확인, 고아 파일 탐지 부재 |
| 030 | Blogger 플랫폼 커버리지 | desc/canonical/로더 회수 | ❌ Hugo 체크 전부 미적용 (senior-blogger) |
| 031 | 광고 로더 2중 로드 | adsbygoogle.js 회수 | ⚠️ render_health 존재만 확인, 회수 미검사 |

---

## 1. 키워드/콘텐츠 수급

### ERR-001 no_keyword
- **감지**: dispatcher 결과 `no_keyword`; curation.db keyword_pool 비어있음
- **진단**: `sqlite3 data/curation.db "SELECT COUNT(*) FROM keyword_pool"` — 2026-08-23 기준 테이블 자체 미생물(첫 harvest 08-24 03:00)
- **수정**: harvest 실행 — `pipelines/curation/run_harvest.py`. 윈도우 게이트 02:00–06:00 KST 외엔 `[SKIP]` exit 0. CLI 플래그(--dry-run) 미지원. 수동 실행은 윈도우 내에서만 의미 있음
- **검증**: keyword_pool 행수 > 0 + `_select_keyword()`가 후보 반환

### ERR-002 콘텐츠 수급 실패 (P01/P02/P14/P26/P27/P30)
- **감지**: publish_error_events problem_id IN (P01,P02,P14,P26,P27,P30); no_result/no_content/no_topics/insufficient_products/irrelevant_products/low_relevance
- **진단**: `GET /api/publish-errors?problem_id=P01` — 소스별 원인 확인. P26/P27=소스 unavailable/exhausted. P14 세분화: `reason`이 `insufficient_products`면 pool <3, `irrelevant_products`면 CATEGORY_FILTERS 허용어 미포함 필터링, `low_relevance`면 relevance gate avg<0.5
- **수정**: 소스 갱신(collector 수동 실행), 데이터 재수집, 가드 완화는 별도 승인. **P14 poison fallback**은 `pipelines/curation/pipeline.py` fallback 경로가 `health_store.is_quarantined`를 스킵했는지 확인 — 2026-09-03 fix(3ca9f463d)로 2곳에 quarantine 필터 추가. **golf bare term**은 allowed에 bare 단어(드라이버/아이언) 누락 시 filter가 9/10 제거 → allowed 보강
- **검증**: 동일 blog_id 재실행 성공 — baby `기저귀분유` / interior `거실다우닝가구느낌` / golf `아이언세트` 2026-09-03 SUCCESS

## 2. 썸네일/이미지

### ERR-003 썸네일 404 (THUMBNAIL-01/P06)
- **감지**: check_results THUMBNAIL-01 fail; broken_featureimage
- **진단**: frontmatter featureimage URL curl -I → 404 여부
- **수정**: `python3 scripts/batch_thumbnails.py --slug "<slug>"` — 썸네일 생성+R2 업로드+frontmatter 수정
- **검증**: R2 URL HTTP 200 + Hugo 재빌드 후 grep

### ERR-004 이미지 URL 손상 (R2-01/P09/P23)
- **감지**: IMAGE-GUARD(hugo_writer), R2-01 fail — 토큰 반복(gLozv0gLozv0...), 길이 초과(>255 macOS)
- **진단**: `/standards` 페이지 fail 목록
- **수정**: URL sanitize(hugo_writer max_len 200), LLM 프롬프트 가드
- **검증**: POST /api/run-checks → R2-01 pass

### ERR-004b 본문 이미지 0건 — 워터스포츠 파생 (IMAGE-GUARD-02 / body_ 0)
- **감지**: `pipelines/etap/quality_scanner.py score_post()`가 `etap/<slug>/body_` R2 이미지 개수를 별도 카운트. 제품카드 `![` 총합으로 마스킹되던 기존 `[WARNING] 이미지 없음`을 보완해 `body_ 0건 → [WARNING] 본문 이미지(body_*) 없음` 경고를 발송(점수 -10). `scan_results` 및 일간 Telegram 리포트(`/publish-errors` 유사)로 노출.
- **진단**: `python3 -c "import glob,re; print(len([p for p in glob.glob('ETAP/*-hugo/content/posts/*/index.md') if 'etap/'+p.split('/')[-2]+'/body_' not in open(p).read()]))"` — 2026-09-03 기준 watersports 49, tours 112, ferry 71 등.
  - 근본 원인: `watersports_pipeline.py:139-140`이 `fetch_city_image(city+" water sport", ...)`로 city 파라미터 오염 → `image_fetcher`가 Pexels 쿼리 `"Kampot water sport Cambodia skyline cityscape"` 생성 → Pexels 0건 → 폴백도 오염 → `body_N` 0건. `shared/publishers/hugo_writer.py`는 `^## ` H2 이후에만 삽입하므로 데이터 부족으로 H2가 `<strong>`으로 대체된 포스트는 삽입 자체가 불가.
- **수정**:
  1) 파이프라인: `fetch_city_image(city, country, slug)` / `fetch_body_images(city, country, slug)` 로 순수 city 전달 (watersports_pipeline.py fix, 2026-09-03). `pipelines/etap/image_fetcher.py`에 `_clean_city()` 방어 + 범용 폴백 `"tropical beach water sports kayak"` 추가.
  2) 기존 포스트 일괄 복구: `python3 /tmp/repair_watersports.py` + `repair_watersports2.py`로 49개 전량 R2 body 2~3장 재생성 및 `<strong>`/lead 이후 삽입.
  3) Hugo 빌드 후 배포는 `env -u CLOUDFLARE_API_TOKEN wrangler auth activate hugh79757 ETAP/watersports-hugo && env -u CLOUDFLARE_API_TOKEN wrangler pages deploy ETAP/watersports-hugo/public --project-name=watersports-hugo` (Pages 타입, Workers 아님)
- **검증**: `grep -c "body_" ETAP/watersports-hugo/content/posts/kampot-water-sports/index.md` → 3, `HUGO_THEMESDIR=... hugo --gc --minify --source ETAP/watersports-hugo` → 512 pages, `score_post()` body 경고 없음, 라이브 배포 `Deployment complete!` URL 확인
- **대시보드 노출**: 기존 `/standards` R2-01은 URL 손상만 탐지해 0건 미탐. 본 건은 `quality_scanner` 일간 스캔(`scan_yesterday`)으로 신규 탐지. `ops_dashboard` 수동 검토 5개 선정 로직은 아직 body_ 필터 미적용 — 향후 `get_sample_urls`에 body_ 0건 우선 필터 추가 예정. ERR-004b는 ERR-004 하위형이지만 탐지 경로가 달라 별도 코드로 분리 기록.

## 3. GA4/추적

### ERR-005 GA4 누락
- **감지**: `/schema` 뷰 ga4:missing; sqlite ga4_id IS NULL AND blog_id NOT LIKE '%blogger%'
- **진단**: layouts/**/extend*head*.html + config에서 ID 탐색 실패 여부
- **수정**: `python3 scripts/ga4_provision.py --account-id 321003076 --blogs <id>` — 신규 속성+스트림 생성(GA4 계정 mdddmddd0322@gmail.com, OAuth token ~/Projects/blogdex/credentials/token_2_informationhot.json). --dry-run 지원
- **검증**: sync_all_schemas 재실행 → ga4_id 채움

### ERR-006 GA4 공유/이중삽입
- **감지**: `/schema` ga4:shared; 빌드 산출물 gtag("config") 2건
- **진단**: 활성 hugo 블로그 GROUP BY ga4_id count>1; extend-head vs config/services 이중 소스
- **수정**: **단일 소스 = config(_default/hugo.toml [services.googleAnalytics])** 유지, extend-head.html의 gtag 블록 제거. 주의: hotissue-hugo(PaperMod)는 하이픈 extend-head.html이 활성 partial(언더스코어 무시됨 — 마커 테스트로 검증됨)
- **검증**: 빌드 후 `grep -c 'gtag("config"' public/index.html` = 1 (minify 더블쿼트 주의)

## 4. H2-GUARD/구조

### ERR-007 H2 구조 위반
- **감지**: shared/publishers/hugo_writer.py _ALLOWED_H2_PATTERNS (AST로 추출 가능). 대시보드 live 체크 없음 — 일회성 감사만 존재
- **진단**: 최신 포스트 샘플링, 허용 패턴 외 H2
- **수정**: 프롬프트/패턴 갱신(roadmap #1) — 코드 수정 수반, 별도 승인
- **검증**: 감사 재실행 FAIL 0

### ERR-008 누수/제목 차단 (P03/P07/P08/P10/P11)
- **감지**: similar_title/title_blocked/llm_cot_leak stage; audit_chain.py SequenceMatcher 80%
- **진단**: 거부 사유 로그 + 유사 제목 원본 확인
- **수정**: 제목 변형 다양화, CJK/CoT 누수는 프롬프트 가드
- **검증**: 재생성 후 title_similar_exists false

## 5. 빌드/배포

### ERR-009 Hugo 빌드 실패 (P05)
- **감지**: render_health fail; deploy_error
- **진단**: `HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes hugo --gc --minify` 로컬 재현 — 에러 라인 확인(이미지 URL 길이, frontmatter 문법 등)
- **수정**: 원인별 — URL sanitize(ERR-004), frontmatter 수정(ERR-016)
- **검증**: exit 0 + 산출물 grep

### ERR-010 배포 실패 (P04) — 최다 발생(541건)
- **감지**: /publish-errors P04; deploy_error
- **진단**: 인증 오류(code 10000)=CLOUDFLARE_API_TOKEN env 충돌 여부
- **수정**: **반드시 dispatcher.py 사용** (Workers/Pages 자동 선택 + env var 제거 + 직렬화 락). 수동 wrangler 직접 실행 금지, --commit-dirty=true 금지(Cloudflare 월 500회 빌드 한도)
- **검증**: `wrangler pages deployment list --project-name=<id>` 최신 배포 확인

## 6. API/Rate-Limit

### ERR-011 API rate-limit/차단 (P13)
- **감지**: data/curation.db api_block_log; 403 트립
- **진단**: `sqlite3 data/curation.db "SELECT * FROM api_call_log ORDER BY called_at DESC LIMIT 20"` — 실제 한도: collector 분40/시간300(2026-07-16 쿠팡 제재 대응), harvester 검색 8/시+COOLDOWN_HOURS=12. **알려진 결함: harvester limiter는 collector의 api_call_log 사용량을 못 봄(단방향 공유)**
- **수정**: 쿨다운 대기가 기본. 구조 수정(harvester 게이트가 api_call_log 카운트)은 별도 승인
- **검증**: api_block_log 신규 행 부재

### ERR-012 데이터 만료/소진 (P19/P27)
- **감지**: check_results data_stock/freshness fail; source exhausted
- **진단**: 해당 파이프라인 DB 잔량 확인(예: heritage 901건 유효 등)
- **수정**: collector 재실행, 소스 추가. airports 사례: 데이터 소진 시 블로그 paused
- **검증**: freshness pass

## 7. 스케줄러/인프라

### ERR-013 스케줄러 침묵사 (2026-08-23 실제 사고)
- **감지**: scheduler.log 공백 구간; logs/heartbeat stale >300s; watchdog(/tmp/5000-watchdog.log) kickstart
- **진단**: `ps aux | grep scheduler` PID 확인, heartbeat mtime, 마지막 로그 라인
- **수정**: `launchctl kickstart -k gui/$(id -u)/com.5000.scheduler` (nohup 수동 기동 금지 — 중복 프로세스). watchdog 미로딩이면 `launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.5000.scheduler-watchdog.plist`. KeepAlive는 사망만 복구 — in-process 블록은 watchdog 몫
- **검증**: 새 PID + 잡 등록 로그(expander 02:00/harvester 03:00/schema_sync 09:00) 존재

### ERR-014 잡 정지/timeout/subprocess (P18/P20/P25)
- **감지**: resource_health stalled; pipeline_retry_exhausted
- **진단**: lock 파일(data/.lock_*) 잔존, Popen 상태
- **수정**: 올바른 격리 패턴 = subprocess + start_new_session + Popen poll 중 heartbeat 갱신 + deadline killpg (참조 구현: scheduler.py _run_car_refresh, _run_keyword_expander). in-process 장기 잡 금지
- **검증**: 잡 완료 로그 + resource_health healthy

## 8. Schema/DB

### ERR-015 스키마 드리프트
- **감지**: `/schema` 뷰 last_synced_at 지연; schemas/*.yaml과 실제 frontmatter 불일치
- **수정**: `python3 -c "from ops_dashboard.schema_registry import sync_all_schemas; print(sync_all_schemas())"` — 즉시 실행 또는 매일 09:00 자동. 기대: total 85, inserted 85
- **검증**: branch 분포 etap36/cuap15/cap13/tap8/stap6/rap5/seap2

### ERR-016 계약 불일치 (P28/P29/P32)
- **감지**: Invalid pipeline result contract / publisher schema mismatch / empty_content_deployed
- **진단**: dispatcher 반환 dict 키(success/reason)와 파이프라인 실제 반환 대조
- **수정**: 파이프라인 반환 계약 준수. 빈본문 배포(P32)는 즉시 차단 최우선
- **검증**: POST /api/run-checks 전체 pass

## 9. 기타 (추가 의무 항목)

### ERR-017 Telegram 발송 실패 (P31)
- **감지**: telegram_delivery_audit; P31 이벤트(151건)
- **수정**: shared/telegram_notifier.py 토큰/chat_id 확인, 네트워크 재시도. 알림 채널일 뿐 근본 원인 아님 — 원인은 구조화 이벤트로 판단
- **검증**: 테스트 메시지 수신

### ERR-018 LLM 폴백 체인 전멸 (P22)
- **감지**: 16 무료 모델 순회 후 유료 DeepSeek까지 실패
- **진단**: config/models.yaml tier_order, 각 provider 에러(429/quota)
- **수정**: 쿼터 회복 대기 또는 키 점검. 유료 호출 실패 = 비용 영향 즉시 보고
- **검증**: 단일 모델 smoke 호출 성공

### ERR-019 설정 오류 (P21)
- **감지**: config_error stage; blogs.d YAML 파싱 실패
- **수정**: yaml.safe_load 검증, blogs.yaml+blogs.d 병합 확인
- **검증**: dispatcher 해당 blog 정상 라우팅

### ERR-020 미등록 오류 (unknown_failure / P33·P34)
- **감지**: publish_error_events에 problem_id 존재하나 config/problems.yaml에 없음 — 현재 P33/P34가 이 상태
- **수정**: problems.yaml에 신규 코드 등록 + ERROR_PLAYBOOKS.md 앵커 추가 → 이 룩북 매핑표 갱신
- **검증**: GET /api/registry 에 코드 반영

---

## 10. 발행 후 발견 결함 — 대시보드 미탐지 사례 (2026-09-05 SEAP+RAP 감아트 유래)

> 배경: SEAP+RAP 7블로그 감사에서 desc 오염 792건·CoT 릭 4건·지역 왜곡 1건·제목 잘림이
> 대시보드 0탐지 상태로 발견됨. 각 항목은 "왜 대시보드가 못 잡았는가"를 포함 — 체크 설계 시
> 윈도우/플랫폼/체크 부재 3종 구멍을 점검할 것.

### ERR-023 desc 오염 — related 블록 조각이 description으로 저장
- **증상**: frontmatter `description:`이 `<strong>함께 읽으면 좋은 글</strong> - [링크](/posts/...)` 형태. 라이브 메타 설명이 링크 목록으로 렌더 → SEO 손해
- **근본 원인**: 후처리가 본문 하단 related 블록을 desc 위치에 복사(LLM 아님 — 링크가 실존 slug를 가리키는 것으로 판별). rap 792건, 8/1 이전 발행 유물
- **왜 미탐지**: desc 라인 내용 검사 체크 자체가 없었음(frontmatter 체크는 구조만, rap_leak는 본문만)
- **수정**: 본문 첫 문단(리드 120자)으로 재생성 백필(`scripts/fix_rap_desc_pollution.py` — PyYAML 검증 필수). 재발 방지: `_check_rap` 게이트(desc 마커 CRITICAL)
- **검증**: 전수 재스캔 마커 0건 + 라이브 meta description 정상 렌더

### ERR-024 CoT 릭 — 과거 발행 유물이 7일 윈도우 밖
- **증상**: 본문에 `그럼 구체적으로 작성해 보겠습니다`, `이제 초단 작성 시작`, `Wait - I need to be careful...` 등 지시문/사고문 노출. rap2 2건 + rap5 2건, 전부 8/1~8/2 발행
- **왜 미탐지**: c04_prompt_leak 체크는 존재하나 `_read_post_files`가 최근 7일 포스트만 읽음 → 과거분은 정상적으로 스킵. 체크 동작은 정상 — **윈도우 설계 자체가 일괄 백스캔을 못 함**
- **수정**: 폐기(rm) + 재배포. 재발 방지는 8/3 CoT 차단 커밋 + c04 게이트가 이미 담당
- **교훈**: 신규 발행 커버리지와 과거 유물 스캔은 별개. 정기 일괄 스캔(무윈도우) 병행 필요

### ERR-025 지역 왜곡 — 키워드와 무관한 지역 데이터로 글 작성 (rap)
- **증상**: '관악드림타운' 제목 글인데 본문 전체가 '서울 강남구에 위치한' + 강남구 단지 시세표
- **근본 원인**: find_lawd_cd 미매칭 → 랜덤 지역 fallback(강남구) → 무관 데이터로 발행. LLM 왜곡 아님 — 데이터 매핑 버그 체인
- **왜 미탐지**: 발행 시점 게이트도 대시보드 사후 체크도 부재. 시간 기반 체크(freshness)로는 구조적으로 불가
- **수정**: 글 폐기(데이터 원천이 잘못돼 부분 수정 불가). 재발 방지: pipeline.py 이중 미매칭 게이트(apt_kw 존재+keyword_trades 0건+lawd 미매칭 → no_trade_data) + `_check_rap` 지역 정합 게이트
- **검증**: 단위 테스트 3케이스(관악드림타운 차단/관악드림(동아) 통과/개포자이 통과)

### ERR-026 게이트 자체 오판 — W5 이미지 regex 중첩 대괄호
- **증상**: 본문 이미지가 있는데 'R13 본문삽입이미지 0장'으로 배포 차단. M850i 글 alt에 `...[2026년 9월 기준]]` 중첩 대괄호
- **근본 원인**: deploy.py W5 regex `!\[[^\]]*\]\(`의 `[^\]]*`가 첫 `]`에서 종료 → `]](` 미매칭 → 0장 오판
- **왜 미탐지**: 게이트 실패 알림은 P04로 가지만 '게이트 오판'이라는 클래스 자체가 미분류
- **수정**: `!\[[^\n]*\]\(` — 개행 제외 전체 매칭. 정규식 단위 테스트 5케이스
- **교훈**: "게이트가 있다"와 "게이트가 옳다"는 별개. 오탐(존재하는 것 차단)은 false-negative만큼 위험 — 게이트 자체 정기 검증 필요

### ERR-027 제목 잘림 — 트렁케이션 시스템 결함
- **증상**: '모델 Y 프리미엄 롱 레인지 구매 전 반드시 확인할 3년…' — 명사/조사 중간 절단. CAP 160샘플 67.5%
- **근본 원인**: validators.py sanitize_title 35자 소프트 트렁케이션이 제목 템플릿 산출물 전부 절단(SEO 의도가 역효과)
- **왜 미탐지**: 제목 길이/완결성 체크 부재. 발행 자체는 성공이라 P코드 미발생
- **수정**: 트렁케이션 제거(제목 템플릿이 35자 내 생성하도록 근본). rap/senior는 자체 writer에 트렁케이션 없음 — 분기별 확인 필요
- **검증**: 신규 발행 샘플 41자 완전 제목

### ERR-028 desc-본문 수치 불일치 — 정의 혼용
- **증상**: desc '월 유지비 약 22만원' vs 본문 '월 103만원'(총비용÷36). CAP 91% — 유지비와 총비용월환산 두 정의를 하나의 라벨로
- **왜 미탐지**: 수치 정합 체크 부재(산술 검증 게이트 없음). LLM 산술 환각(compare 2시리즈 484만원 오기)도 동일 구멍
- **수정**: 계산식 통일(총비용÷36 + '월 환산 약' 라벨). 후속: 발행 후 산술 대조 게이트 검토 가치
- **교훈**: 수치가 나오는 콘텐츠는 '라벨-값-정의' 3자 대조가 필요

### ERR-029 stale public 고아 HTML
- **증상**: 삭제된 콘텐츠(관악/CoT)가 재배포 후에도 라이브 200 유지
- **근본 원인**: Hugo `--gc`는 삭제 콘텐츠의 기존 public/ HTML을 제거하지 않음 → wrangler가 고아 파일 업로드
- **수정**: 콘텐츠 삭제 후 재배포 시 `public/ rm -rf` 후 클린 빌드. 캐시는 `_headers` `/posts/* s-maxage=3600`로 7일→1시간 단축(seo 재발급 주기와 균형)
- **검증**: pages.dev 프리뷰 404 + 엣지 캐시 자연 소멸 대기

### ERR-030 Blogger 플랫폼 커버리지 구멍
- **증상**: senior-blogger(Blogger 플랫폼) desc/canonical 부재 + adsbygoogle 로더 4중 — Hugo 체크 전부 미적용
- **왜 미탐지**: 대시보드 체크가 Hugo 산출물(마크다운/HTML) 기준. Blogger는 별도 경로
- **수정 지침**: `.planning/handoff/senior-blogger-blogger-template-fix-guide.md` 참조 — Blogger 템플릿 HTML 직접 수정(수동 작업)
- **교훈**: 브랜치 온보딩 시 플랫폼별 체크 커버리지를 명시적으로 점검할 것

### ERR-031 광고 로더 2중 로드
- **증상**: 아티클 head에 adsbygoogle.js 2회 선언(테마 head.html 자동 + extend-head.html 수동) — 12 Hugo 사이트 전부(CAP 8 + SEAP/RAP 6 중 겹침 제외)
- **왜 미탐지**: render_health가 로더 존재 여부만 확인, 회수 미검사
- **수정**: extend-head.html 로더 블록 제거(테마 자동 로드 위임). 재발 방지: 온보딩 시 extend-head에서 pagead2 grep
- **검증**: 라이브 아티클 `grep -c pagead2` = 1

---

## 부록: 긴급 대응

| 상황 | 즉시 조치 |
|---|---|
| 스케줄러 무응답 | launchctl kickstart -k com.5000.scheduler → 등록 로그 3종 확인 |
| 배포 인증 전체 실패 | env의 CLOUDFLARE_API_TOKEN 제거 확인 → dispatcher.py만 사용 |
| 광고 백지 다발 | Publisher ID↔도메인 계열 매핑 섹션 참조 (ID 혼입 = 수익 직결) |
| content.db 손상 의심 | 파괴작업 4단계 프로토콜 — 백업 없이 DELETE/UPDATE 금지 |
| 빈본문 배포(P32) | 해당 포스트 즉시 확인, 배포 롤백 판단 |

**원칙**: 조용한 실패 없음 · 수동 해결 없음 · 모든 수정 후 검증 근거 남길 것

