# STAGE 2 — RAP 근본원인 매핑 (위반 → 원인, 코드 라인 확정)

> Phase 57 / Task 3. 작성일: 2026-08-03. 읽기 전용 스테이지 (코드/설정/배포 변경 없음).
> 모든 화살표는 파일:라인 + Yes/No + 근거 1문장. 추측 금지 — 실측/로그/DB로만 확정.
> 검증 명령: scheduler.log(219,796줄) grep, data/rap.db + data/content.db + data/stap_content.db SQL, 라이브 HTTP, git reflog.

---

## 0. CONTEXT.md 가설 vs 실측 대조 (핵심 정정 2건)

| CONTEXT.md 주장 | 실측 | 판정 |
|---|---|---|
| P1: 8/3 rap2 "음성군" 12:26/12:41 2회 연속 발행 (publish_ledger source_id 근거) | **기록 아티팩트**. `_record_ledger`(dispatcher.py:229-307)가 RAP 경로에서 **stale content.db articles 마지막 행(rap2 = 음성군 4/21)** 을 읽어 publish_ledger에 같은 행 반복 기록. 실제 8/3 발행(stap_content.db)은 전부 고유 키워드 (rap2: 보은이평/경남거창군/충주시). 8/3 ledger 행 3건은 실제 발행 3건과 count 일치 (quota는 정상 동작). | **증거 오류** |
| P1: publish_log UNIQUE 제약 없음 (일반 인덱스만) | 라이브 `PRAGMA index_list(publish_log)` → `sqlite_autoindex_publish_log_1 unique=1 origin=u` = **UNIQUE(blog_id, data_key) 존재**. `INSERT OR IGNORE`(pipeline.py:1028)가 **같은 키워드 재선택 시 새 행을 조용히 삼킴** (기존 4/21 행 유지, timestamp 미갱신). | **오류 — 원인은 INSERT 실패가 아니라 OR IGNORE 삼킴** |
| P7: depth_next/funnel 코드 구현 0건 | 구현 존재 (hugo_writer.py:826-889 `_build_funnel_cards_md`, wiring :961). "라이브 0건"의 실제 원인은 `_resolve_funnel_card_post`:719-740의 `row.get()` AttributeError. | **오류 — 원인 다름** |

---

## 1. 위반 → 근본원인 매핑표

### P1: 동일 키워드 재발행 (실제 중복 확인)

| # | 근본원인 | 파일:라인 | Yes/No | 근거 (1문장) |
|---|---|---|---|---|
| P1-1 | publish_log INSERT OR IGNORE가 재발행 시 갱신을 삼킴 | pipelines/rap/pipeline.py:1027-1036 | **Yes** | `INSERT OR IGNORE ... (blog_id, data_type, data_key, title)` — UNIQUE(blog_id,data_key)로 이미 있는 키워드는 새 행 안 만들어 timestamp 갱신 안 됨; `RAP publish_log 기록 실패` 로그는 0건 (scheduler.log 전체 grep) = 실패가 아니라 삼킴 |
| P1-2 | `_pick_keyword` 7일 제외가 최초 기록만 봄 → 7일 경과 후 무한 재선택 | pipelines/rap/pipeline.py:111-121 | **Yes** | `SELECT data_key FROM publish_log WHERE blog_id=? AND published_at > datetime('now','-7 days')` — 음성군 행은 4/21 기록 유지 → 5/18, 6/26에 재선택 허용됨 (실측: stap_content.db 음성군 글 2건 라이브, 5/18+6/26) |
| P1-3 | 실측: 동일 키워드 반복 발행 존재 | data/stap_content.db articles.source_id prefix | **Yes** | `강남구 실거래가 종합` 4회 (7/29~8/3), `2026년 청년 전세임대 1순위` 3회 (5/4~7/24), 음성군 2건 등 — source_id = `{keyword}_{YYYYMMDD}`라 prefix=키워드 |
| P1-4 | 2차 방어 무력화: source_id에 날짜 포함 | pipeline.py:1014 (source_id=f"{keyword}_{날짜}") | **Yes** | 같은 키워드라도 날짜가 다르면 source_exists(publisher.py:866) 통과; duplicate_slug는 slug가 다르면 통과 — 5/18 vs 6/26은 slug가 달라 둘 다 통과 |

**결론**: P1의 근본원인은 "publish_log가 최초 1회만 기록하고 재발행 타임스탬프를 갱신하지 않는 구조 + 7일 제외가 최초 기록 기준"이다. CONTEXT의 "8/3 당일 3회" 증거는 아티팩트였으나, **7일 이상 간격의 실제 재발행은 실측으로 존재** (음성군 라이브 2건 등).

### P2: publish_log/ledger 기록 (기록 누락 vs 오염)

| # | 근본원인 | 파일:라인 | Yes/No | 근거 |
|---|---|---|---|---|
| P2-1 | **publish_ledger 오염 (아티팩트 생성)** — RAP 발행 성공마다 stale content.db articles 행 반복 기록 | dispatcher.py:229-307 (특히 291-300) | **Yes** | RAP 블로그는 STAP/CAP/travel 분기 미해당 → `else`(291)에서 `content.db articles ORDER BY rowid DESC LIMIT 1` — content.db articles는 전 블로그 4/21에 멈춤 (max(published_at)=4/21) → rap2는 매번 "음성군" 행 기록 (8/1~8/3 ledger 13행 중 10행이 동일 음성군) |
| P2-2 | **content.db articles가 4/21 이후 전역 미기록** — `insert_article`이 ARTICLES_DB(stap_content.db)에만 쓰고 PUBLISH_LEDGER_DB(content.db) articles는 안 씀 | shared/content_store.py:12-19 (get_conn→ARTICLES_DB), shared/db_paths.py:11-15 | **Yes** | content.db articles max=6451(4/21) vs stap_content.db rap2 id=10685(8/3) — 두 DB 분리 후 ledger-sync가 content.db articles를 갱신하지 않음 (sync는 publish_ledger만 INSERT, ledger_sync.py:117) |
| P2-3 | **publish_log 기록은 되지만 재발행 갱신 안 됨** (P1-1과 동일 결함) | pipeline.py:1027-1036 | **Yes** | 위 P1-1과 동일 |

**결론**: "publish_log INSERT 실패(기록 누락)"는 **사실이 아님** (실패 로그 0건). 실제 결함은 ① 재발행 시 OR IGNORE 삼킴(P2-3/P1-1), ② `_record_ledger`의 stale read로 publish_ledger 오염(P2-1), ③ content.db articles vs stap_content.db 분리(P2-2).

### P3: ai_writer tier (KeyError)

| # | 근본원인 | 파일:라인 | Yes/No | 근거 |
|---|---|---|---|---|
| P3-1 | 브랜치 TIER_ORDER(fallback1~3) vs models.yaml(3개 키) 불일치 → KeyError | 브랜치 `1dff13638:shared/ai_writer.py:94` = `TIER_ORDER = ["default","fallback1","fallback2","fallback3","economy"]` / config/models.yaml 키 = default/fallback/economy | **Yes** | `git show 1dff13638:shared/ai_writer.py:94`로 확정; `config[attempt_tier]`(ai_writer.py:130)에서 'fallback1' KeyError |
| P3-2 | **라이브 사고 발생 확정** — 8/3 10:53 rap3, 11:03 rap5 | logs/scheduler.log:219307, 219321, 219377, 219379 | **Yes** | `KeyError: 'fallback1'` 실제 로그 4건; 8/3 10:23 스케줄러 기동 ~ 12:17 `pull --rebase origin main`(reflog dbfac7bb5) 사이 사용자가 fix/rap-subscription-backfill checkout 상태로 scheduler 실행 → write_failed |
| P3-3 | main은 안전 | shared/ai_writer.py:64 (HEAD 541da9912) | **Yes** | HEAD `TIER_ORDER = ["default", "fallback", "economy"]`; `git diff main..origin/main shared/ai_writer.py` = 0건 |

**결론**: P3는 "잠복 위험"이 아니라 **8/3 실발생 사고**. 브랜치 체크아웃 중 스케줄러 실행이 트리거. 병합 시 확정 재발 → 병합 전 C2 방어 커밋 필요.

### P4: CATCHUP 폭주 / write_failed

| # | 근본원인 | 파일:라인 | Yes/No | 근거 |
|---|---|---|---|---|
| P4-1 | 8/3 10:23~12:17 write_failed 다발의 직접 원인 = P3 KeyError | logs/scheduler.log:219307(rap3 10:53), 219379(rap5 11:03) | **Yes** | 같은 시각 CATCHUP 보충 실패 로그 연동 확인 (rap3 10:53, rap5 11:03) |
| P4-2 | rap4 13:03 timeout(600s) — dispatcher subprocess 상한 | scheduler.py:262 (timeout=600) | **Yes** | Stage 0 실측: rap4 13:03 `timeout (600s)` |
| P4-3 | **maybe_alert RAP 미호출 (알림 결함)** | shared/alert_thresholds.py:93-143 (정의) / 호출은 :40 pet-hugo 데모뿐 | **Yes** | `grep -rn "maybe_alert" --include="*.py" scheduler.py dispatcher.py pipelines/rap/ shared/` → 호출 1건(alert_thresholds.py:40 pet-hugo 데모). RAP 파이프라인은 alert_thresholds 경유 알림 경로가 없음 |
| P4-4 | scheduler 자체 3연속 알림은 동작 | scheduler.py:713-745 `_track_publish_result` | **Yes** | `_FAILURE_THRESHOLD=3`, count>=3 시 Telegram, 발송 후 카운터 리셋(:734) — 별도로 동작 |

**결론**: CATCHUP write_failed는 ① P3 브랜치 사고(8/3)가 직접 원인. ② 알림 관점에서 alert_thresholds.maybe_alert이 RAP에 배선 안 됨 (체크리스트 (6) Yes).

### P5: 키워드 풀 불균형 + 오염

| # | 근본원인 | 파일:라인 | Yes/No | 근거 |
|---|---|---|---|---|
| P5-1 | 풀 불균형 (rap2 218, rap5 395 vs rap3 2068, rap4 2324, rap 2183) | data/rap.db keywords | **Yes** | `SELECT blog_target, count(*) ... GROUP BY` 실측 (Stage 0과 동일) |
| P5-2 | 중국어 오염 없음 | data/rap.db keywords 전수 스캔 | **Yes** | python 스캔: rap2/rap5 중국어 0건 — cuap 체크리스트 (7) 오염은 RAP에 해당 없음 |
| P5-3 | 영문 포함 키워드 일부 (rap2 16/218=7.3%, rap5 51/395=12.9%) | data/rap.db keywords | **Yes** | 정규식 스캔; LH/applyhome 등 고유명사 포함 가능 — 별도 실사 필요 (경미) |
| P5-4 | 공고명 통짜 키워드 (rap2 다수) → 공고 갱신과 무관 반복 위험 | keywords 샘플 (예: "음성군 지역 국민임대주택 예비입주자 모집 공고 [2026.03.23.] 청약 정보") | **Yes** | P1-2와 결합 시 7일마다 동일 공고 재발행 구조 (음성군 2건 라이브가 실증) |

### P6: refresh 신선도

| # | 근본원인 | 파일:라인 | Yes/No | 근거 |
|---|---|---|---|---|
| P6-1 | 07-19~07-27 9일간 trades/subs 0건 — **외부 API 실패 구간** | refresh_log 129~140행 (trades_added=0, duration 27~118s) | **Yes** | duration < 90s(deadline) → 타임아웃 컷이 아님; fetch_apt_trade(fetcher.py:66-68)가 예외 시 `logger.exception` + `[]` 반환 = **조용한 실패** |
| P6-2 | 07-28부터 9584건 복구 = API 복구 | refresh_log 142행(9584), trades 테이블 202607=7699건 존재 | **Yes** | trades에 202607 데이터 존재 → "수집 자체 실패"가 아니라 7/19~27 구간 API 오류로 해석 (로그 레벨만 확인 가능, 원 응답은 미보존) |
| P6-3 | 재시도 로직 없음 — 1일 1회 실패 시 그대로 기록 | rap_data_sync.py:397-449 daily_refresh | **Yes** | try/except 3개 sync 각각 1회 시도, 재시도/backoff 없음, 실패를 refresh_log에 error로 남기지 않음 |

### P7: 퍼널 카드 (구현 존재 vs 라이브 0건)

| # | 근본원인 | 파일:라인 | Yes/No | 근거 |
|---|---|---|---|---|
| P7-1 | **`row.get("thumbnail_url")` — sqlite3.Row에 .get 없음 → AttributeError → except가 삼켜 None 반환** | shared/publishers/hugo_writer.py:719-740 (`_resolve_funnel_card_post`) | **Yes** | read-only probe 실측: `_resolve_funnel_card_post('rap-hugo')` → None; 직접 `row.get()` 실행 → `AttributeError: 'sqlite3.Row' object has no attribute 'get'` |
| P7-2 | 이로 인해 depth/bridge resolve 전부 실패 → 카드 0건 | hugo_writer.py:848-862 (resolve 실패 시 skip) | **Yes** | `[FUNNEL]` 로그 count 0, 라이브 RAP 전체 `funnel-card` grep 0건 |
| P7-3 | 피해 규모: 7/19(v2 커밋 `5c705ab51`) 이후 카드 없이 발행된 landing 글 | git log 5c705ab51 (7/19 v2 funnel cards) + find mtime | **Yes** | rap-hugo 73 + rap5-hugo 73 = **146건 라이브 글에 퍼널 카드 미삽입** |
| P7-4 | (후보 검증) `_keywords_overlap_check` 전량 drop 아님 | hugo_writer.py:806-823 | **No** | threshold=0.0 → `overlap >= 0` 항상 True (필터 비활성) — bridge drop 원인 아님 |
| P7-5 | (후보 검증) landing+bridge_to 억제 아님 | hugo_writer.py:838-841 | **No** | rap-hugo는 depth_next만, rap5도 bridge_to 없음 — 억제 조건 미충족 |
| P7-6 | (후보 검증) wiring 미도달 아님 | hugo_writer.py:961 (`_build_funnel_cards_md(blog_cfg, body_md)`) | **No** | 발행 경로에 호출 존재; Stage 1 probe에서 (0,0) 반환은 resolve 실패 때문 |
| P7-7 | v1 카드 3건 라이브 (7/18) = `pending://rap3-hugo/...` 미해결 href | RAP content/posts (7/18 발행분) + content.db published_url | **Yes** | `pending://` href 그대로 노출 (Stage 1 실측) — v1 유산 |

### b3: CoT 노출 — 2층 분리 (사용자 지시 1)

**층 A — 생성 혼입 (모델/프롬프트 레이어):**

| # | 근본원인 | 파일:라인 | Yes/No | 근거 |
|---|---|---|---|---|
| A-1 | RAP default tier = deepseek-v4-flash (DeepSeek 계열 — cuap과 동일 모델군) | config/models.yaml (default: model: deepseek-v4-flash) | **Yes** | models.yaml 실측 |
| A-2 | ai_writer(HEAD)는 `message.content`만 사용 — reasoning_content 미처리/미검사 | shared/ai_writer.py:115 (`content = response.choices[0].message.content`) | **Yes** | `grep reasoning_content` → HEAD 0건. DeepSeek의 reasoning_content는 별도 필드라 content에 직접 섞이지는 않으나, **모델이 content 안에 자기 서술을 생성**함 (탐지 필요) |
| A-3 | **rap2 프롬프트가 "1단계/2단계/3단계/4단계" 구조를 명시적으로 요구** | pipelines/rap/writer.py:674-677 (`generate_subscription_article` 프롬프트 "[청약 신청 절차 안내 (반드시 포함)] 1단계: 청약홈... 2단계: ...") | **Yes** | Stage 1 CoT 인용(rap2 "1단계에서 … 2단계에서 …")의 직접 출처 — 프롬프트가 단계 구조를 가르침 |
| A-4 | rap3/rap5 CoT("정리하면 다음과 같습니다", "핵심 요약을 세 줄로") — 프롬프트에 없는 모델 자기 서술 | trade 프롬프트(`_build_trade_system_prompt` 322-628) — "단계/다음과 같/추론" 지시 없음 | **Yes** | trade 프롬프트 grep: 단계 구조 지시 없음 → 모델이 자발적으로 생성 |

**층 B — 탐지 실패 (게이트 레이어):**

| # | 근본원인 | 파일:라인 | Yes/No | 근거 |
|---|---|---|---|---|
| B-1 | validate_post에 CoT/추론 노출 패턴 규칙 **없음** | shared/validators.py:291-377 | **Yes** | _AI_RESIDUES(:15)는 제목용 마크다운 잔여물만("다듬은 제목","```","##","title:" 등) — 본문 "1단계에서/다음과 같습니다/정리하면" 미검사 |
| B-2 | **RAP은 force_draft 미지원 → CoT 글 라이브 직행** (cuap은 draft-first로 격리) | pipelines/rap/pipeline.py:991-1005 (`_is_draft = False` 하드코딩, validator issues만 draft) vs pipelines/curation/pipeline.py:1080 (`cfg.get("force_draft", False)`) | **Yes** | RAP에 force_draft 개념 없음; 6/25 위반 중 b3 CoT 6건 전부 라이브 발행 (draft 아님) — cuap보다 노출 위험 큼 |

**결론**: b3는 ① 생성 레이어(rap2 프롬프트 강제 + 모델 자기 서술)와 ② 탐지 레이어(본문 CoT 규칙 부재 + draft 방어 부재)의 복합. cuap와 다른 점: cuap은 draft-first로 차단 중, **RAP은 라이브 노출 중** = 더 급함.

### P9 (신규): 음성군 라이브 중복 1건 (사용자 지시 3)

| # | 근본원인 | 파일:라인 | Yes/No | 근거 |
|---|---|---|---|---|
| P9-1 | 음성군 키워드 라이브 2건 (5/18 + 6/26) — 서로 다른 slug | /RAP/rap2-hugo/content/posts/음성군-지역-국민임대주택-예비입주자-모집-공고-20260323-청약-정보/ (date 5/18), 음성군-국민임대주택-예비입주자-모집-공고-안내/ (date 6/26) | **Yes** | 두 dir 모두 index.md 존재, draft:false; 내용 유사도 0.319 (SequenceMatcher) — 서로 다른 생성이지만 동일 주제 |
| P9-2 | cuap slug 중복 publish_error 계열 **아님** | — | **Yes** | slug가 달라 duplicate_slug 발동 안 함; 발행 성공(에러 없음). 계열 = **P1의 조용한 재발행 발현형** |

### P10 (신규): publish_log INSERT "누락" 정리 + 추가 발견 (사용자 지시 3)

| # | 근본원인 | 파일:라인 | Yes/No | 근거 |
|---|---|---|---|---|
| P10-1 | "발행 OK but 기록 누락" = **재발행 삼킴**(P1-1/P2-3) + **ledger 오염**(P2-1)의 합성 — 별도 INSERT 실패 아님 | pipeline.py:1027-1036, dispatcher.py:291-300 | **Yes** | `RAP publish_log 기록 실패` 0건; 8/3 ledger 3행이 실제 3건과 count 일치 → 발행은 정상 기록됨 |
| P10-2 | **추가 결함: 72시간 제목 중복 게이트 전 블로그 데드** — `SELECT title, keyword FROM publish_ledger`인데 publish_ledger에 keyword 컬럼 없음 → 예외 → [] 반환 | shared/validators.py:128-134, content.db publish_ledger 스키마 | **Yes** | 직접 실행: `no such column: keyword` 예외 확인; `_get_recent_titles`가 항상 [] → validate_post 3단계(Jaccard 0.7 제목 중복)가 전 블로그 무력 |

---

## 2. cuap 체크리스트 (1)~(7) 대조

| # | 항목 | RAP 실측 | Yes/No |
|---|---|---|---|
| (1) | 프롬프트 자기모순 (1인칭/후기 유도) | writer.py 전체 grep: 1인칭/후기 유도 0건. **단, rap2 청약 절차 프롬프트가 단계 구조를 강제**(A-3) — CoT 유사 구조 생성 유도 | **부분 Yes** (1인칭 No / 단계 강제 Yes) |
| (2) | 관련성 검증 부재/우회 | validate_post는 Jaccard 제목 유사만, keyword 동일 시 continue(:305-307) — 본문/공고 관련성 검증 없음 | **Yes** |
| (3) | 게이트 "평균" 희석 | RAP은 스코어 게이트 없음(이슈 리스트 방식) — 희석 개념 자체가 N/A. 대신 검증이 이슈 유무 이진이라 CoT 같은 미규칙 패턴 통과 | **N/A (부분)** |
| (4) | 제목 폴백 우회/옛 리터럴 | rap2 "제목" 아티팩트는 **draft:true** — 라이브 404 확인(curl), Hugo 미빌드. 폴백이 draft로 격리됨 | **No (draft 격리 확인)** |
| (5) | 자기주제 하드차단 회귀 | RAP_EXCLUDE(pipeline.py:23) + BLOG_KEYWORD_FILTER(pipeline.py:93) 존재; 중국어 0건, 영문 rap5 12.9% (경미) | **No (경미)** |
| (6) | 알림/카운터 결함 | alert_thresholds.maybe_alert RAP 미배선 (P4-3). scheduler 3연속 알림만 존재 | **Yes** |
| (7) | 키워드 풀 오염 | 중국어 0건. 공고명 통짜 키워드 반복 위험 (P5-4) | **부분 Yes** |

---

## 3. 근본원인 우선순위 (Stage 3 수정 후보)

| 순위 | 원인 | 파급 | 수정 난이도 |
|---|---|---|---|
| 1 | **P7-1 `.get()` 버그** — 라인 1개 수정으로 퍼널 카드 즉시 복구, 146건 피해 중단 | 라이브 퍼널 0건 | 최하 (1줄) |
| 2 | **P1-1/P2-3 INSERT OR IGNORE 삼킴** — 재발행 timestamp 갱신 → 7일 제외 복원 | 라이브 중복 발행 | 하 |
| 3 | **P2-1 ledger stale read** — `_record_ledger`가 stap_content.db를 읽도록 | ledger 오염/모니터 왜곡 | 하 |
| 4 | **P10-2 keyword 컬럼 게이트 데드** — publish_ledger에 keyword 기록 또는 SELECT 수정 | 전 블로그 제목 중복 게이트 복원 | 하 |
| 5 | **B-2 force_draft 부재** — RAP에 force_draft 추가 (cuap 패턴) | CoT/불량 라이브 노출 차단 | 중 |
| 6 | **P3 브랜치 TIER_ORDER** — 병합 전 C2 방어 (tier 키 유효성 + 폴백) | 브랜치 병합 시 전 분기 write_failed | 중 |
| 7 | **P4-3 maybe_alert 배선** — RAP 실패 reason별 임계값 알림 | 조용한 실패 알림 | 중 |
| 8 | **A-3 rap2 프롬프트 단계 구조 완화 + B-1 CoT 패턴 규칙** | CoT 노출 원천 차단 | 중 |

## 4. 잔존 위험 (Stage 2 종료 시점)

- P6 refresh: 외부 API 실패 구간의 원 응답/status 코드가 로그 레벨(exception traceback)에만 남아 **API 측 원인(키/서버 오류)은 확정 불가** — fetcher 응답 보존 로깅 추가 필요 (Stage 3 후보).
- P5-3 영문 키워드 51건 실사 미완 — 발행 품질 영향 여부 확인 필요.
- v1 퍼널 카드 3건(pending:// href)의 라이브 교체는 별도 작업 (Stage 4+에서 검토).
- 72h 제목 중복 게이트(P10-2)는 전 블로그 영향 — RAP 수정 시 공용 validators 변경이므로 회귀 테스트 필요.

## 5. 자가 점검

- [x] 모든 화살표에 파일:라인 + Yes/No + 근거 1문장
- [x] 추측 항목 없음 — 전부 실측/로그/DB/git으로 확정
- [x] "증상 vs 근본원인" 혼동 없음 — publish_error(증상)와 원인(P3/P4) 구분
- [x] CONTEXT.md 오류 2건(아티팩트 증거, UNIQUE 부재) 정정 반영
- [x] 사용자 지시 3건 반영: b3 2층 분리(생성/탐지) + P7 .get() 실측 + P9/P10 추가
- [x] cuap 체크리스트 (1)~(7) 대조 완료
