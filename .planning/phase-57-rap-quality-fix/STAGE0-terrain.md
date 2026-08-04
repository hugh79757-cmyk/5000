# STAGE 0 — 분기별 지형도 + 실패 reason 빈도표

> Phase 57 (rap-quality-fix) — Stage 0 산출물 (읽기 전용)
> 작성: 2026-08-03 | 상태: Gate G0→1 승인 대기
> 모든 수치는 아래 "재현 명령"으로 재현 가능.

---

## 1. 분기별 블로그 지형도 (config/blogs.yaml + config/blogs.d/*.yaml status 기준)

### RAP 분기 (5개 블로그 — 전부 active)

| blog_id | status | pipeline | platform | domain | funnel_stage | theme | daily_quota | schedule times |
|---------|--------|----------|----------|--------|--------------|-------|-------------|----------------|
| rap-hugo | active | rap | hugo | apt.informationhot.kr | landing | blowfish | 5 | 07:50/10:50/13:50/16:50/20:50 |
| rap2-hugo | active | rap | hugo | apply.informationhot.kr | bridge | blowfish | 5 | 08:10/11:10/14:10/17:10/21:10 |
| rap3-hugo | active | rap | hugo | tax.informationhot.kr | bridge | blowfish | 5 | 08:30/11:30/14:30/17:30/21:30 |
| rap4-hugo | active | rap | hugo | rent.informationhot.kr | bridge | blowfish | 5 | 08:50/11:50/14:50/17:50/21:50 |
| rap5-hugo | active | rap | hugo | brand.informationhot.kr | landing | blowfish | 5 | 09:10/12:10/15:10/18:10/22:10 |

퍼널 정의 (config/blogs.d/rap.yaml):
- rap-hugo: `depth_next` → [rap3-hugo(세금), rap4-hugo(전월세), rap2-hugo(청약)]
- rap2-hugo: `bridge_to` → [finance-hugo(청약 전 금융)]
- rap3-hugo: `depth_next` → [rap4-hugo], `bridge_to` → [finance-hugo(취득세 vs 대출)]
- rap4-hugo: `bridge_to` → [finance-hugo(전세대출)]
- rap5-hugo: `depth_next` → [rap-hugo(시세), rap2-hugo(청약)]

### CAP 분기 (config/blogs.d/cap.yaml — car 파이프라인)

| blog_id | status | pipeline | platform | domain | funnel_stage |
|---------|--------|----------|----------|--------|--------------|
| compare-hugo | active | car | hugo | compare.rotcha.kr | bridge |
| hotissue-hugo | active | car | hugo | hotissue.rotcha.kr | landing |
| rank-hugo | active | car | hugo | rank.informationhot.kr | landing |
| pick-hugo | active | car | hugo | pick.informationhot.kr | monetize |
| deal-hugo | inactive | car | hugo | deal.rotcha.kr | — |
| ev-hugo | inactive | car | hugo | ev.rotcha.kr | — |
| guide-hugo | inactive | car | hugo | guide.rotcha.kr | — |
| tco-hugo | inactive | car | hugo | tco.rotcha.kr | — |

### SEAP 분기 (config/blogs.d/seap.yaml — senior 파이프라인)

| blog_id | status | pipeline | platform | domain | funnel_stage |
|---------|--------|----------|----------|--------|--------------|
| senior-hugo | active | senior | hugo | senior.informationhot.kr | landing |
| senior-blogger | active | senior | blogger | 2.techpawz.com (blogger_blog_id 5484205249958557854) | — |

→ cap/seap은 본 페이즈 범위 밖(지형 파악만 수행, Stage 5 확대 시 참고).

---

## 2. 파이프라인 진입점 흐름 (실측 다이어그램)

```
launchd (macOS)
  └─ run_5000.sh
       └─ scheduler.py (상시 루프)
            ├─ 블로그 스케줄 시간 도달 또는 CATCHUP(누락 슬롯) 감지
            │    CATCHUP: expected=2 actual=1 missed=1 quota=5 attempt=1/3 (실측 8/3)
            ├─ QUTOA CHECK: quota_met → skip (8/3 실측 존재)
            ├─ subprocess.run([.venv/bin/python3, "dispatcher.py", blog_id],
            │    cwd=PROJECT_DIR, capture_output=True, timeout=600)   ← scheduler.py:260-263
            ├─ stdout 마지막 3줄만 [OUT] 로그  ← scheduler.py:268-274 (로그 유실 구조)
            │    마지막 줄 JSON 파싱 → success → "[PUBLISH] {blog} 발행 성공"
            │                     else    → "[PUBLISH] {blog} 발행 실패 — stage={reason}"
            └─ TimeoutExpired → "[ERROR] {blog} timeout (600s)" + _tg_error
                 └─ dispatcher.py:_resolve_pipeline(blog_id, pipeline, cfg)
                      └─ pipelines.rap.pipeline.run(blog_cfg)   ← pipeline.py:784
                           ├─ (1) daily_refresh daemon 스레드 기동 (join 120s) ← pipeline.py:791-809
                           ├─ (2) _pick_keyword(blog_id)  ← pipeline.py:74-139
                           │     ① active 키워드 조회 (blog_target 필터, LIMIT 200)
                           │     ② RAP_EXCLUDE 오염 필터 + blog_id 패턴 필터
                           │     ③ publish_log 7일 조회 → 중복 키워드 제외 ← pipeline.py:111-121
                           │        (INSERT 누락 시 이 단계 무력화됨 — P1+P2)
                           │     ④ random.choice(rows[:20]) + use_count UPDATE
                           ├─ (3) _pick_strategy(keyword, blog_id)  ← pipeline.py:142
                           ├─ (4) fetcher — fetch_trade/fetch_subscription/fetch_rent 등
                           │       (fetch_* 실패 시 reason: no_trade_data / no_subscription_data)
                           ├─ (5) writer — GPT 생성 (_build_trade_system_prompt 322-628,
                           │       _parse_article 746-783), 실패 시 reason: write_failed
                           ├─ (6) _post_process(body_md, blog_id, keyword)  ← pipeline.py:502
                           │       내부링크 무작위 샘플 삽입 (동일 블로그) + 면책 + 쿠팡 카드
                           ├─ (7) 발행 전 검증  ← pipeline.py:991-1005
                           │       shared.validators.validate_post()
                           │       issues 있으면 → _is_draft=True (전용 force_draft 미지원 — P8)
                           ├─ (8) shared.publisher.publish(...)  ← pipeline.py:1008
                           │       source_id=f"{keyword}_{YYYYMMDD}" (동일 키워드 동일일 → 동일 source_id)
                           │       Hugo 발행+배포 (deploy=True) — 성공 시 article_id 반환
                           └─ (9) publish_log INSERT OR IGNORE  ← pipeline.py:1027-1036
                                  try/except → 실패 시 logger.warning만 (조용한 실패 — P1+P2)
                                  성공 후 backlink_publisher.post_publish_backlinks()
```

게이트 목록: validator(_issues→draft), assert_korean_or_reject(전처리), language_error,
RAP_EXCLUDE(오염 필터), publish_log 7일(중복 방지 — P1+P2 의존점).

---

## 3. cuap vs rap 코드 공유 판정

| 모듈 | rap 사용처 | 판정 |
|------|-----------|------|
| shared/ai_writer.py (297줄) | GPT tier 생성 | 공용 (tier 폴백 로직 — P3 대상) |
| shared/publisher.py (1070줄) | publish() ← pipeline.py:819 | 공용 (Hugo 발행+배포) |
| shared/validators.py (732줄) | validate_post / assert_korean_or_reject / sanitize_title | 공용 |
| shared/alert_thresholds.py (155줄) | (임계값 — P4 대조 대상) | 공용 |
| shared/publishers/hugo_writer.py (978줄) | _build_funnel_cards_md(826-889), _resolve_funnel_card_post(719-740), _keywords_overlap_check(806-823) | 공용 (P7 대상) |
| shared/publishers/deploy.py (169줄) | wrangler 배포 | 공용 |
| shared/content_store / coupang_travel / thumbnail_generator / backlink_publisher / telegram_notifier | 각각 호출 | 공용 |
| pipelines/rap/pipeline.py | _pick_keyword/_pick_strategy/_post_process/publish_log INSERT/daily_refresh 스레드 | 분기 전용 (복제 로직) |
| pipelines/rap/rap_data_sync.py | daily_refresh/_parallel_sync | 분기 전용 |
| pipelines/rap/writer.py | _build_trade_system_prompt/_parse_article | 분기 전용 |
| pipelines/rap/fetcher.py | API 수집 | 분기 전용 |

### curation vs rap 대조 (3줄)

1. curation은 `force_draft` 지원(pipeline.py:1080 `is_draft = cfg.get("force_draft", False) or ...`)인 반면 rap은 전용 미지원(_is_draft는 validator 위반 시에만 true) — **P8 확인**.
2. curation은 publish_log를 자체 테이블로 관리하나 rap은 rap.db publish_log를 `INSERT OR IGNORE`로 기록하며 try/except로 실패를 삼킴 — **P1+P2 확인**.
3. 둘 다 shared.validators + shared.ai_writer + shared.publisher를 공용 사용 — 나머지 분기 로직은 각자 복제.

---

## 4. 실패 reason 빈도표 (8/1~8/3)

### 4a. 전체 로그 reason 분포 (최근 2MB, 전체 블로그 — 614건)

| reason | 빈도 | 비고 |
|--------|------|------|
| no_result | 190 | |
| already_running | 100 | |
| no_content | 49 | |
| no_topics | 39 | |
| collect_error | 38 | |
| publish_error | 33 | |
| low_relevance | 24 | |
| duplicate_source_id | 23 | |
| similar_title | 22 | |
| irrelevant_products | 21 | |
| stap_subprocess_error | 21 | |
| write_failed | 13 | |
| tap_subprocess_error | 10 | |
| daily_quota_exceeded | 7 | |
| quota_met | 6 | |
| (기타) | 18 | |

### 4b. RAP 블로그 발행 실패 (전체 로그, [PUBLISH] 발행 실패 — stage=reason)

| 블로그 | 실패 stage 분포 |
|--------|-----------------|
| rap-hugo | quota_met 2, daily_quota_exceeded 2, write_failed 2, no_trade_data 1, unknown 1 |
| rap2-hugo | quota_met 4, write_failed 1, no_subscription_data 1 |
| rap3-hugo | write_failed 5, quota_met 3, daily_quota_exceeded 1, no_trade_data 1 |
| rap4-hugo | write_failed 2, daily_quota_exceeded 2 |
| rap5-hugo | write_failed 3, quota_met 1, unknown 1 |

날짜별 실패 (8/1 집중 — 15건): 8/1 rap5×4, rap3×5, rap-hugo×2, rap2×1, rap4×2 = 14건 + rap-hugo 1건.
8/3: write_failed 재시도 성공 패턴(10:49/10:53/11:03 [FAILURE] 1/3) + rap4 13:03 timeout(600s) — **P4 실측**.

### 4c. content.db publish_ledger (status != published, rap) — 실패 누적

| 블로그 | failed 건수 |
|--------|-------------|
| rap-hugo | 33 |
| rap2-hugo | 32 |
| rap3-hugo | 30 |
| rap4-hugo | 20 |
| rap5-hugo | 26 |

### 4d. P1+P2 실측 — 8/3 동일 source_id 재발행 5건 (publish_ledger 기준)

| blog_id | 동일 키워드(부분) | 1차 | 2차 | publish_log 8/3 row |
|---------|-------------------|-----|-----|---------------------|
| rap-hugo | 서울 강남구 성원대치2단지아파트 전세 | 10:45:23 | 12:22:39 | 2건 |
| rap2-hugo | 음성군 지역 국민임대주택 예비입주자 모집 공고 [2026.03.23.] | 12:26:52 | 12:41:39 | **0건** |
| rap3-hugo | 청주동남 업무시설 용지 수의계약 공고 | 12:31:27 | 12:52:58 | 2건 |
| rap4-hugo | [정정공고]경기남부권 수원시 국민임대 예비입주자 | 10:58:48 | 13:10:28 | 2건 |
| rap5-hugo | 대림아크로빌 강남구 실거래가 | 13:13:22 | 14:00:25 | **0건** |

- rap2/rap5: **8/3 publish_log row 0건** (INSERT 누락 실측) → `_pick_keyword` 3단계(7일 조회)가
  오늘 발행 키워드를 배제 못함 → 재선택 → 동일 키워드 2회 발행. **P1+P2 근본 연쇄 실증**
- rap-hugo/rap3/rap4: publish_log row는 존재하나 동일 키워드가 다시 선택됨
  (data_key vs _pick_keyword 비교 키워드 매칭 경로 확인 필요 — Stage 2)

### 4e. publish_log 기록 현황 (rap.db)

| 블로그 | 7일내 row | 전체 row |
|--------|-----------|----------|
| rap-hugo | 20 | 389 |
| rap2-hugo | **1** | 209 |
| rap3-hugo | 20 | 378 |
| rap4-hugo | 24 | 359 |
| rap5-hugo | **2** | 403 |

- 8/1~8/3 실제 발행은 블로그당 9~10건인데 publish_log 7일 기록은 rap2 1건, rap5 2건뿐 —
  **기록 누락이 체계적** (Stage 2에서 INSERT 실패 경로 확정 필요).

### 4f. 키워드 풀 (keywords, blog_target 기준)

| 블로그 | active | total |
|--------|--------|-------|
| rap-hugo | 2183 | 2566 |
| rap2-hugo | **218** | 412 |
| rap3-hugo | 2068 | 2144 |
| rap4-hugo | 2324 | 2328 |
| rap5-hugo | **395** | 421 |

- rap2(218) / rap5(395) vs 나머지(2068~2324) — **P5 불균형 실측 확인** (CONTEXT 수치와 일치)

### 4g. database is locked (write lock 경합 — P1+P2 추정 원인)

- 로그 내 `database is locked` 발생 **140회** (전체 로그)
- 5/21 `refresh_images 실패: database is locked` + sqlite3.OperationalError 4건 이상 (Traceback) —
  daily_refresh daemon 스레드와 발행 쓰기 경합 재발 이력 실증 (Stage 2에서 재현 시도)

---

## 5. 로그 유실 확인 (scheduler.py:268-274)

- scheduler는 dispatcher stdout **마지막 3줄만** `[OUT]`으로 기록 → 실패 reason이 마지막
  JSON 줄에 없으면 원인 로그가 유실됨. 8/1~8/3 RAP 실패 중 `[PUBLISH] 발행 실패 — stage=...`
  에서 reason이 확인되지만, dispatcher 내부 상세(Exception trace)는 보존되지 않음.
- Stage 3 D9(진단 로깅) 대상 구조 확인.

---

## 6. 재현 명령 (수치 재현 스크립트)

```bash
# reason 빈도 (최근 2MB)
python3 - <<'PY'
import re; from collections import Counter
c = Counter(re.findall(r'"reason":\s*"([^"]+)"', open('logs/scheduler.log',errors='replace').read()[-2_000_000:]))
print(dict(c.most_common(12)))
PY

# publish_log rows
sqlite3 data/rap.db "SELECT COUNT(*) FROM publish_log;"

# 키워드 풀 불균형
sqlite3 data/rap.db "SELECT blog_target, COUNT(*) FROM keywords WHERE status='active' GROUP BY blog_target;"

# publish_log 7일/전체
sqlite3 data/rap.db "SELECT blog_id, COUNT(*) FROM publish_log WHERE published_at > datetime('now','-7 days') GROUP BY blog_id;"

# 8/3 동일 source_id 재발행 (P1 증거)
sqlite3 data/content.db "SELECT blog_id, source_id, COUNT(*) c FROM publish_ledger WHERE blog_id LIKE 'rap%' AND created_at LIKE '2026-08-03%' GROUP BY blog_id, source_id HAVING c>1;"

# database is locked
grep -c "database is locked" logs/scheduler.log

# publish_log UNIQUE 인덱스 존재 확인 (live 스키마)
sqlite3 data/rap.db "PRAGMA index_list(publish_log);"   # sqlite_autoindex_publish_log_1 origin=u (UNIQUE)
```

---

## 7. Stage 0 결론 요약

1. RAP 5개 블로그 전부 active, 7일 쿼터 달성 중 (9~10건/3일) — **단, publish_log 기록은 rap2/rap5 누락**
2. **P1+P2 실측 확정**: 8/3 5개 블로그 전부 동일 키워드 2회 발행. publish_log INSERT 실패
   (특히 rap2/rap5 0건) → `_pick_keyword` 7일 제외 무력화 연쇄 실증
3. **P5 실측 확정**: rap2 218 / rap5 395 active 키워드 — 타 블로그 대비 1/10 수준
4. **P4 실측 확정**: 8/3 CATCHUP 구간 write_failed 재시도 패턴 + rap4 timeout 600s
5. **P7 재확인 필요**: `_build_funnel_cards_md` 코드는 존재(hugo_writer.py:826) — 라이브 0건 원인은 Stage 2에서 확정 (RESEARCH 주장과 상충)
6. **스키마 반전 발견**: live publish_log에 UNIQUE(blog_id,data_key) 존재 — PLAN/CONTEXT의
   "UNIQUE 없음" 주장과 상충. Stage 2에서 정밀 확인 필요 (CREATE TABLE 시점 vs 실제 인덱스)
7. cap/seap 지형 파악 완료 (본 페이즈 수정 범위 밖)
