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

---

## 1. 키워드/콘텐츠 수급

### ERR-001 no_keyword
- **감지**: dispatcher 결과 `no_keyword`; curation.db keyword_pool 비어있음
- **진단**: `sqlite3 data/curation.db "SELECT COUNT(*) FROM keyword_pool"` — 2026-08-23 기준 테이블 자체 미생물(첫 harvest 08-24 03:00)
- **수정**: harvest 실행 — `pipelines/curation/run_harvest.py`. 윈도우 게이트 02:00–06:00 KST 외엔 `[SKIP]` exit 0. CLI 플래그(--dry-run) 미지원. 수동 실행은 윈도우 내에서만 의미 있음
- **검증**: keyword_pool 행수 > 0 + `_select_keyword()`가 후보 반환

### ERR-002 콘텐츠 수급 실패 (P01/P02/P26/P27/P30)
- **감지**: publish_error_events problem_id IN (P01,P02,P26,P27,P30); no_result/no_content/no_topics
- **진단**: `GET /api/publish-errors?problem_id=P01` — 소스별 원인 확인. P26/P27=소스 unavailable/exhausted
- **수정**: 소스 갱신(collector 수동 실행), 데이터 재수집, 가드 완화는 별도 승인
- **검증**: 동일 blog_id 재실행 성공

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

## 부록: 긴급 대응

| 상황 | 즉시 조치 |
|---|---|
| 스케줄러 무응답 | launchctl kickstart -k com.5000.scheduler → 등록 로그 3종 확인 |
| 배포 인증 전체 실패 | env의 CLOUDFLARE_API_TOKEN 제거 확인 → dispatcher.py만 사용 |
| 광고 백지 다발 | Publisher ID↔도메인 계열 매핑 섹션 참조 (ID 혼입 = 수익 직결) |
| content.db 손상 의심 | 파괴작업 4단계 프로토콜 — 백업 없이 DELETE/UPDATE 금지 |
| 빈본문 배포(P32) | 해당 포스트 즉시 확인, 배포 롤백 판단 |

**원칙**: 조용한 실패 없음 · 수동 해결 없음 · 모든 수정 후 검증 근거 남길 것

