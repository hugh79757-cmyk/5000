# WL-20260823-stap-seap-phase2b-db-cache

## 작업
STAP/SEAP 8개 블로그를 쿠팡 DB 캐시 수집 구조에 등록. 브랜치 track-c-stap-seap-standardization.

- 커밋 `4fe16aa27` "feat: STAP+SEAP DB cache structure — KEYWORD_MAP, CATEGORY_FILTERS, harvester mapping" — 3 files +350/-2
  - pipelines/curation/keywords.py: KEYWORD_MAP 신규 8 id (finance/stock/dividend/etf/sector/ipo-hugo 30~34kw, senior-hugo 44kw, senior-blogger 38kw)
  - pipelines/curation/pipeline.py: CATEGORY_FILTERS 신규 8 엔트리
  - pipelines/curation/run_harvest.py: bestcategories category_cycle ["","1008","1013","1015","1006"] 순환 + _save_to_pool 범용('') 규칙 docstring
- 결과 문서: /tmp/stap_seap_phase2b_result.md

## 결정 사항
- keyword_pool blog_id 배정 = 항상 범용('') 저장, 소비 시점 배정(기존 _get_from_pool 설계 유지). preassign 기각 — 결합도.
- products 테이블 blog_id 컬럼 없음 확인 → 스키마 변경 불요.
- 시니어 키워드는 shared/coupang_senior.py 검증어 재사용. senior-blogger 식품 계열(오메가3·영양제·홍삼) 허용.

## 검증 요약
- 타깃 스위트 19/19 PASS (test_keyword_pool 8 + test_run_harvest 4 + test_keyword_harvester 7)
- tests/curation 18 failed/130 passed — stash 전후 동일 카운트·동일 파일 → 신규 회귀 0
- validate_keyword 스팟체크 8/8 PASS

## 파괴적 작업
없음 (additive 코드 커밋만; DB/API 호출 없음)

## 잔존 위험
카테고리 코드 라이브 미검증(익일 harvest 로그로 확인) / test_keywords·test_pipeline "10 blogs" 고정 어설션 pre-existing 실패 / 상세는 /tmp/stap_seap_phase2b_result.md 참조.
