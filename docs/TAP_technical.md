# TAP (Travel Auto Publisher) 기술문서

> 마지막 업데이트: 2026-05-31 (5차 세션)

---

## 3. fetcher.py — 데이터 수집

### 3.1 fetch_food()

**sigungu 선택 방식 (5차 세션 변경)**:
기존의 areaCode(광역)만 전달 → Counter 최빈값 방식에서,
`area_codes.py`의 `FOOD_AREA_SIGUNGU_WEIGHTED`(229개 시군구, 3등급 가중치)에서
`get_weighted_random_sigungu(exclude=최근14일_발행_시군구)`로 선택 후
`sigunguCode`를 API 파라미터로 직접 전달하는 방식으로 변경.

---

## 11. 알려진 이슈 (Known Issues)

### 11.4 Resolved

| 이슈 | 해결 | 조치 |
|------|------|------|
| 강릉 맛집 고정 반복 | ✅ 5차 세션 해결 | sigunguCode 직접 지정 + 가중치 랜덤 |
| 주제 중복 발행 차단 | ✅ 5차 세션 해결 | sigungu 컬럼 + 3중 방어 레이어 |
| INSTR 오탐 | ✅ 5차 세션 해결 | 구분자 감싸기 방식으로 교체 |

---

## 12. 세션 조치 이력

### 5차 세션 (2026-05-31)

| # | 문제 | 원인 | 조치 |
|---|------|------|------|
| 1 | 강릉 맛집 반복 발행 | sigunguCode 미지정 → 광역 전체 데이터 → Counter 최빈값이 강릉으로 수렴 | area_codes.py 239개 시군구 신규 생성 + sigunguCode 직접 파라미터 전달 |
| 2 | 주제 중복 발행 차단 불가 | title 문자열 비교만 존재, sigungu+category 조합 체크 없음 | sigungu 컬럼 추가 + 3중 방어 레이어 구현 (fetcher/pipeline/DB) |
| 3 | 소도시 0건 fallback 빈발 우려 | 229개 시군구 uniform random → 군 단위 음식점 0건 선택 빈발 | 가중치 3등급 시스템 적용 (TIER_A=3, TIER_B=2, TIER_C=1) |
| 4 | sigungu 중복 체크 DB 불일치 | publisher → stap_content.db 쓰기, pipeline → content.db 읽기 → 최신 발행 데이터 감지 불가 | shared/db_paths.py 생성 (ARTICLES_DB / PUBLISH_LEDGER_DB 분리 상수) + 전체 참조 교체 |
| 5 | INSTR 오탐 | INSTR(source_id, ?) 가 '1234'를 '12345'에서도 매칭 | INSTR(','\|\|source_id\|\|',', ','\|\|?\|\|',') 로 교체 |

---

## 15. 다음 세션 체크리스트

### 완료 항목
- [x] 강릉 맛집 고정 — sigunguCode 직접 지정 + 229개 시군구 가중치 랜덤
- [x] 주제 중복 발행 — sigungu 컬럼 + 3중 방어 레이어 + DB 경로 단일화
- [x] INSTR 오탐 방지 — 구분자 감싸기

### 잔여 항목
- [ ] title 파싱 fallback 제거
      조건: stap_content.db articles 테이블의 sigungu NULL 건이 0이 되는 시점
      확인 쿼리:
      SELECT COUNT(*) FROM articles
      WHERE blog_id='travel3-hugo'
        AND sigungu IS NULL
        AND status='published';
      결과가 0이면 _travel_sigungu_recently_published()의 2순위 fallback 블록 삭제
- [ ] fetch_food() 0건 시군구 자동 제외
      TIER_C 시군구 중 TourAPI 실제 응답 0건인 시군구를 area_codes.py에서 weight=0으로 표시
      확인 방법: dry-run 중 FETCH_FAIL 3회 이상 발생 시 해당 sigungu 로그 분석
