# TAP (Travel Auto Publisher) 기술문서

> 마지막 업데이트: 2026-06-01 (7차 세션)

---

## 1. 프로젝트 구조

```
/Users/twinssn/Projects/5000/
├── dispatcher.py              # 중앙 라우터 — blog_id → pipeline 실행
├── scheduler.py               # 스케줄러 — 3시간 간격 발행
├── config/
│   ├── blogs.yaml             # 블로그 설정
│   ├── blogs.d/               # 추가 블로그 설정 (개별 파일)
│   ├── prompts.yaml           # AI 프롬프트 템플릿
│   └── regions.yaml           # 지역 그룹 정의
├── pipelines/
│   ├── travel/                # 여행 블로그 파이프라인 (TAP)
│   │   ├── pipeline.py        # 메인 파이프라인 (중복 체크 포함)
│   │   ├── fetcher.py         # 데이터 수집 (TourAPI, GoCamping 등)
│   │   ├── writer.py          # AI 글 생성
│   │   └── area_codes.py      # 229개 시군구 코드 + 가중치 시스템
│   ├── curation/              # curation 블로그 파이프라인
│   ├── rap/                   # tax/rap 블로그 파이프라인
│   ├── car/                   # 자동차 블로그 파이프라인
│   ├── etap/                  # etap 블로그 파이프라인
│   ├── stock/                 # stock 블로그 파이프라인
│   ├── gap/                   # gap 블로그 파이프라인
│   └── senior/                # senior 블로그 파이프라인
├── shared/
│   ├── db_paths.py            # [v5] DB 경로 단일 관리 상수
│   ├── publisher.py           # 통합 발행 (Hugo/Blogger/WordPress)
│   ├── content_store.py       # articles/used_places/used_images CRUD
│   ├── ledger_sync.py         # publish_ledger 동기화
│   ├── validators.py          # 발행 전 검증
│   └── telegram_notifier.py   # 텔레그램 알림
├── scripts/
│   ├── test_sigungu_check.py           # sigungu 중복 체크 단위 테스트
│   └── test_sigungu_distribution.py    # 시군구 분산 테스트
├── data/
│   ├── content.db             # publish_ledger (source_id/title 중복 체크용)
│   ├── stap_content.db        # articles 테이블 (최신 발행 데이터)
│   ├── festival.db            # 축제 DB
│   └── travel.db              # 여행 데이터
└── docs/
    └── TAP_technical.md       # 본 문서
```

---

## 2. DB 이중 구조

| DB 파일 | 용도 | 테이블 | 접근 주체 |
|---------|------|--------|-----------|
| `stap_content.db` | **최신 발행 데이터 (정본)** | articles, used_places, used_images | publisher (쓰기), pipeline 중복 체크 (읽기) |
| `content.db` | publish_ledger 동기화 | publish_ledger | dispatcher/ledger_sync (쓰기), pipeline source_id 체크 (읽기) |

**정본(Source of Truth)**: `stap_content.db` — publisher가 articles를 INSERT하는 DB.
`content.db`는 `used_places`가 없고 articles 데이터가 구버전(2026-04-21)이므로
sigungu 중복 체크 등 최신 데이터가 필요한 작업에는 **반드시 stap_content.db를 읽어야 함**.

### 2.1 db_paths.py 상수

```python
# shared/db_paths.py
ARTICLES_DB       = ".../data/stap_content.db"   # articles 테이블 (최신)
PUBLISH_LEDGER_DB = ".../data/content.db"         # publish_ledger (source_id 중복체크)
TAP_DB            = ".../data/tap.db"
FESTIVAL_DB       = ".../data/festival.db"
```

**규칙**:
- sigungu 중복 체크, `is_place_used()` 호출 → `ARTICLES_DB` (stap_content.db)
- source_id 중복 체크, title 유사도 체크 → `PUBLISH_LEDGER_DB` (content.db)
- 새 DB 경로 추가 시 `db_paths.py`에만 추가 (하드코딩 금지)

---

## 3. fetcher.py — 데이터 수집

### 3.1 fetch_food()

**sigungu 선택 방식 (5차 세션 변경)**:
기존의 areaCode(광역)만 전달 → Counter 최빈값 방식에서,
`area_codes.py`의 `FOOD_AREA_SIGUNGU_WEIGHTED`(229개 시군구, 3등급 가중치)에서
`get_weighted_random_sigungu(exclude=최근14일_발행_시군구)`로 선택 후
`sigunguCode`를 API 파라미터로 직접 전달하는 방식으로 변경.

**가게명 중복 방지 (6차 세션 추가)**:
- fetch_food() 내부에서 place_name을 추출
- pipeline의 `_run_single()`에서 `used_places` 테이블 ALL-TIME 조회
- 이미 발행된 가게명이 items에 포함되면 발행 차단

---

## 4. pipeline.py — 중복 체크 방어 레이어

### 4.1 중복 방어 순서 (5중 방어)

```
fetch_food() 반환
  ↓
① source_id 조합 정확 일치       → content.db.publish_ledger.source_id=?
② 개별 contentId 부분검색        → content.db.publish_ledger INSTR(','||source_id||',', ','||?||',')
③ sigungu 14일 룩백             → stap_content.db.articles WHERE sigungu=? AND created_at>14days
④ 가게명 ALL-TIME 체크           → stap_content.db.used_places is_place_used(name, blog_id)  ← [v6 추가]
  ↓
generate_content()
  ↓
⑤ title 80% 유사도 체크         → content.db.publish_ledger SequenceMatcher
  ↓
publish()
```

### 4.2 주요 함수

| 함수 | 역할 | 읽는 DB | 쿼리 방식 |
|------|------|---------|-----------|
| `_travel_source_exists()` | source_id 정확 일치 | content.db | `source_id=?` |
| `_travel_sigungu_recently_published()` | sigungu 중복 체크 | stap_content.db | `WHERE sigungu=? AND created_at>?` (1순위) / title 파싱 (2순위 fallback) |
| `_travel_title_similar_exists()` | 제목 유사도 80% | content.db | SequenceMatcher |
| `is_place_used()` (content_store) | 가게명 ALL-TIME 중복 체크 | stap_content.db | `WHERE place_name=? AND blog_id=?` |

---

## 5. area_codes.py — 시군구 가중치 시스템

### 5.1 데이터

- 총 229개 시군구 (TourAPI 공식 지역코드 기준)
- 3등급 가중치 시스템

| 등급 | 가중치 | 대상 | 개수 |
|------|--------|------|------|
| TIER_A | 3 | 특별시/광역시 전 지역, 주요 관광도시 (강릉, 경주, 여수 등) | 103개 |
| TIER_B | 2 | 시 단위 중소도시, 주요 군 | 50개 |
| TIER_C | 1 | 군 단위 소도시 (양구군, 인제군, 울릉군 등) | 76개 |

### 5.2 핵심 함수

```python
get_weighted_random_sigungu(exclude_sigungus: set | None = None) -> tuple
    # 가중치 기반 랜덤 선택
    # exclude_sigungus: 최근 14일 발행 시군구 제외
    # 반환: (areaCode, sigunguCode, display_name)
```

### 5.3 파일 위치

- `/Users/twinssn/Projects/5000/pipelines/travel/area_codes.py`
- (TAP 프로젝트의 pipelines/ 디렉토리는 namespace 충돌 방지를 위해 삭제됨)

---

## 10. CI / 테스트

### 10.1 단위 테스트

```bash
# sigungu 중복 체크 5케이스 검증
python3 scripts/test_sigungu_check.py

# 시군구 분포 검증 (500회 샘플)
python3 scripts/test_sigungu_distribution.py
```

### 10.2 테스트 케이스

| 케이스 | 입력 | 기대 | 검증 내용 |
|--------|------|------|-----------|
| 1 | blog="travel3-hugo", sigungu="속초", days=14 | True | sigungu 컬럼 직접 매칭 |
| 2 | blog="travel3-hugo", sigungu="원주", days=14 | False | 다른 시군구는 통과 |
| 3 | blog="travel3-hugo", sigungu="", days=14 | False | 빈 sigungu → skip |
| 4 | blog="travel3-hugo", sigungu="속초", days=0 | False | lookback 0일 → 과거 없음 |
| 5 | blog="travel3-hugo", sigungu="강릉", days=14 | True | sigungu=NULL 건 title fallback |

---

## 11. 알려진 이슈 (Known Issues)

### 11.4 Resolved

| 이슈 | 해결 | 조치 |
|------|------|------|
| 강릉 맛집 고정 반복 | ✅ 5차 세션 해결 | sigunguCode 직접 지정 + 가중치 랜덤 |
| 주제 중복 발행 차단 | ✅ 5차 세션 해결 | sigungu 컬럼 + 3중 방어 레이어 |
| INSTR 오탐 | ✅ 5차 세션 해결 | 구분자 감싸기 방식으로 교체 |
| 가게명 조합 재발행 (이선장+효키 3회) | ✅ 6차 세션 해결 | used_places ALL-TIME 체크 추가 |
| pipelines namespace 충돌 | ✅ 7차 세션 해결 | TAP pipelines/ 디렉토리 삭제 + area_codes 5000으로 이동 |

### 11.5 Known (미해결)

| 이슈 | 우선순위 | 영향 |
|------|---------|------|
| "~만원대" 가격 표현 후처리 누락 | Low | 발행 품질 |
| 글자수 부족 (2,200자 미달) | Low | 일부 AI 생성 글 |
| 축제 eventStartDate 필터 미구현 | Low | 축제 블로그 |

---

## 12. 세션 조치 이력

### 5차 세션 (2026-05-31)

| # | 문제 | 원인 | 조치 |
|---|------|------|------|
| 1 | 강릉 맛집 반복 발행 | sigunguCode 미지정 → 광역 전체 데이터 → Counter 최빈값이 강릉으로 수렴 | area_codes.py 229개 시군구 신규 생성 + sigunguCode 직접 파라미터 전달 |
| 2 | 주제 중복 발행 차단 불가 | title 문자열 비교만 존재, sigungu+category 조합 체크 없음 | sigungu 컬럼 추가 + 3중 방어 레이어 구현 (fetcher/pipeline/DB) |
| 3 | 소도시 0건 fallback 빈발 우려 | 229개 시군구 uniform random → 군 단위 음식점 0건 선택 빈발 | 가중치 3등급 시스템 적용 (TIER_A=3, TIER_B=2, TIER_C=1) |
| 4 | sigungu 중복 체크 DB 불일치 | publisher → stap_content.db 쓰기, pipeline → content.db 읽기 → 최신 발행 데이터 감지 불가 | shared/db_paths.py 생성 (ARTICLES_DB / PUBLISH_LEDGER_DB 분리 상수) + 전체 참조 교체 |
| 5 | INSTR 오탐 | INSTR(source_id, ?) 가 '1234'를 '12345'에서도 매칭 | INSTR(','\|\|source_id\|\|',', ','\|\|?\|\|',') 로 교체 |

### 6차 세션 (2026-06-01)

| # | 문제 | 원인 | 조치 |
|---|------|------|------|
| 1 | 가게명 조합 재발행 | contentId 순서만 다른 동일 가게(이선장+효키)가 5일 내 3회 발행 | `_run_single()`에 `is_place_used()` ALL-TIME 체크 레이어 추가 |

### 7차 세션 (2026-06-01)

| # | 문제 | 원인 | 조치 |
|---|------|------|------|
| 1 | pipelines namespace 충돌 | TAP/pipelines/__init__.py가 5000의 pipelines 패키지 가림 → `ModuleNotFoundError: pipelines.curation` | TAP pipelines/ 디렉토리 완전 삭제 + area_codes.py를 5000/pipelines/travel/로 이동 |

---

## 15. 다음 세션 체크리스트

### 완료 항목
- [x] 강릉 맛집 고정 — sigunguCode 직접 지정 + 229개 시군구 가중치 랜덤
- [x] 주제 중복 발행 — sigungu 컬럼 + 3중 방어 레이어 + DB 경로 단일화
- [x] INSTR 오탐 방지 — 구분자 감싸기
- [x] 가게명 조합 중복 차단 — used_places ALL-TIME 체크
- [x] pipelines namespace 충돌 해결 — TAP pipelines/ 삭제 + area_codes 5000 이동

### 잔여 항목
- [ ] title 파싱 fallback 제거
      조건: stap_content.db articles 테이블의 sigungu NULL 건이 0이 되는 시점
      확인 쿼리:
      ```sql
      SELECT COUNT(*) FROM articles
      WHERE blog_id='travel3-hugo'
        AND sigungu IS NULL
        AND status='published';
      ```
      결과가 0이면 `_travel_sigungu_recently_published()`의 2순위 fallback 블록 삭제
- [ ] fetch_food() 0건 시군구 자동 제외
      TIER_C 시군구 중 TourAPI 실제 응답 0건인 시군구를 area_codes.py에서 weight=0으로 표시
      확인 방법: dry-run 중 FETCH_FAIL 3회 이상 발생 시 해당 sigungu 로그 분석
- [ ] "~만원대" 가격 표현 후처리
      AI 생성 글에 포함된 모호한 가격 표현 정리
- [ ] 글자수 부족 (2,200자 미달)
      AI 생성 글의 최소 글자수 보장 로직
- [ ] 축제 eventStartDate 필터
      이미 지난 축제가 발행되지 않도록 eventStartDate 검증
