# PLAN: sector/etf/pick-hugo no_content 해결

## 1. 개요

3개 블로그의 `no_content`/`no_data` 연속 실패를 해결한다.

| 블로그 | 연속 실패 | 실제 원인 | 파이프라인 | 위치 |
|--------|----------|-----------|-----------|------|
| **sector-hugo** | 24 | 가드 체크 과잉 차단 + failure count 리셋 버그 | STAP `pipelines/sector/` | STAP 프로젝트 |
| **etf-hugo** | 15 | 3회 시도 제한(5개 토픽 중 3회), `beginner` 토픽 0회 성공 | STAP `pipelines/etf/` | STAP 프로젝트 |
| **pick-hugo** | 11 | 트림 193건 `단종` 변경 + MAX_RETRY=6 부족 + failure count 리셋 버그 | 5000 `pipelines/car/` | 5000 프로젝트 |

## 2. 공통 버그: `_reset_failure_count` 위치 오류

### 문제
`dispatcher.py` line 720-722: `_reset_failure_count()`가 `else` (실패 분기) 안에 있어서 **성공 시 리셋되지 않음**. `quota_met`/`already_running`/`duplicate_title` 상황에서만 리셋됨.

### 해결
`_reset_failure_count(blog_id)`를 `if result.get("success"):` 블록 내로 이동.

### 영향
모든 블로그에 적용됨. failure_count가 성공 시 정상 리셋 → 일시적 장애 후에도 카운트 리셋 → `_ESCALATION_THRESHOLD=3` 데드 스파이럴 방지.

---

## 3. pick-hugo (5000 `pipelines/car/`)

### 3.1 문제
- **18/26 pending topics dead**: car.db trims 193건이 `status='단종'`으로 bulk 변경됨
- `build_persona_pick_input()`이 `status='시판'` 필터로 조회 → 0건 → None 반환
- `MAX_RETRY=6`으로 26개 중 1개 viable 토픽 찾을 확률 ~23%

### 3.2 해결
**A. trim `단종` → `시판` 복구 (데이터):**
```sql
UPDATE trims SET status='시판', updated_at=datetime('now') 
WHERE car_id IN (
  SELECT t.car_id FROM topics t 
  WHERE t.site_id='pick' AND t.status='pending' AND t.post_type='persona_pick'
) AND status='단종';
```
→ 18개 dead 토픽 중 일부(또는 전부) 복구

**B. `MAX_RETRY` 증가 (pipeline.py line 86):**
`MAX_RETRY = 6` → `MAX_RETRY = 26` (또는 `len(all_topics)`)

---

## 4. sector-hugo (STAP `pipelines/sector/`)

### 4.1 문제
- 330개 기발행 article 중 많은 sector 키워드가 최근 3일 내 사용됨 → `_sector_recently_published()` 차단
- `title_similar_exists()` (STAP 버전) threshold=0.6, 전체 article 비교 → 매우 공격적
- `rotation` 토픽만 6회 성공 (2%), 나머지 4개 토픽이 324회 성공 (98%)
- `_try_generate()`가 5개 토픽 모두 소진 후 `collect_all()` 실행 → 재시도 → 실패 → `no_content`

### 4.2 해결
**A. `_try_generate()` 루프 개선 (STAP `pipelines/sector/pipeline.py`):**
- 현재: `_pick_topic()`이 `random.choice(all_topics)`로 중복 선택 가능
- 수정: 선택한 토픽을 `_tried` set에 추가하여 중복 방지, 최대 5개 토픽 모두 시도

**B. `_sector_recently_published()` 룩백 단축:**
- 현재: `lookback_days=3`
- 수정: `lookback_days=2` 또는 1 (AI가 충분히 다양한 title 생성 가능)

---

## 5. etf-hugo (STAP `pipelines/etf/`)

### 5.1 문제
- **3 attempts only** (`range(3)`)지만 `_all_topics`는 5개 — 2개 토픽은 시도조차 안 함
- `beginner` 토픽: **0회 성공** (전체 history 통틀어) — AI가 제목 생성 실패 또는 slug 중복
- ETF 데이터는 21,400건 unused → 충분

### 5.2 해결
**A. 시도 횟수 증가 (STAP `pipelines/etf/pipeline.py` line 121):**
`range(3)` → `range(len(_all_topics))` (모든 토픽 시도)

**B. `beginner` 토픽 문제 진단:**
- `beginner` slug 중복 여부 확인 (기존 0건 → slug 중복 가능성 낮음)
- AI 응답 파싱 실패 가능성 높음 → `_parse_response()`에서 `beginner` 프롬프트 출력 확인

---

## 6. 실행 순서

### Wave 1 (5000 프로젝트 — dispatcher.py, pipeline.py)
1. `dispatcher.py`: `_reset_failure_count()` 버그 수정 (line 720→668)
2. `pipelines/car/pipeline.py`: `MAX_RETRY 6→26`
3. SQL: pick-hugo pending topics 트림 `단종→시판` 복구

### Wave 2 (STAP 프로젝트 — sector, etf)
4. `STAP/pipelines/sector/pipeline.py`: `_try_generate()` 중복 토픽 방지, 룩백 3→2일
5. `STAP/pipelines/etf/pipeline.py`: 시도 횟수 `3→5`, `beginner` 토픽 진단

### Wave 3 (검증)
6. `failure_count.json` 3개 블로그 0으로 리셋
7. cooldown.json daily 키 정리
