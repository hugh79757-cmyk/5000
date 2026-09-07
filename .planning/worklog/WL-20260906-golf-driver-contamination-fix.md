# WL-20260906-b — golf-hugo 공구 포스트 오염 방지

날짜: 2026-09-06
작업 유형: 키워드/제품 필터 방어 강화 [PRODUCTION CODE 3파일] + DB 정화 [파괴적]

## 사고

라이브 발행: `데오람 미니 드라이버 세트 추천 - 실속 있는 공구 선택` (golf.informationhot.kr, 2026-09-06 01:31, keyword `드라이버`, relevance 0.5 = threshold 통과). 골프 블로그에 공구(전동드라이버) 포스트 발행. 9/4 `드라이버골프용품`(자석 십자 비트, 역시 공구) 발행 이력도 확인 — 반복 패턴.

사용자 결정: 라이브 포스트는 유지 (SEO 트래픽 잠재력). 이후 골프 글로 자연 희석.

## 오염 경로 (5단계)

1. `keyword_expander.py` DEFAULT_SEEDS golf에 `드라이버` 단독 시드 존재
2. `keywords.py` KEYWORD_MAP golf에 `드라이버` 단독 (line 90) — keyword_pool 비어 fallback로 여기서 선택됨 (golf-hugo keyword_pool 전체 0행 — KEYWORD_MAP 경로가 실제 선택 경로)
3. Coupang 검색 `드라이버` → 공구 제품 반환
4. `pipeline.py` CATEGORY_FILTERS golf allowed에 `드라이버` 단독 포함 → `name_has_allowed` rescue로 blocked 우회 + allowed 매칭 통과
5. relevance scorer도 `드라이버` 문자열 일치로 0.5 통과

## 수정 (3파일, [PRODUCTION CODE])

| 파일 | 수정 |
|---|---|
| `pipelines/curation/pipeline.py:281-284` | golf allowed: `드라이버` 제거 (`골프드라이버` 유지). blocked: `공구`, `전동드라이버`, `드릴` 추가 |
| `pipelines/curation/keywords.py:90` | KEYWORD_MAP golf: `드라이버` → `골프드라이버` |
| `pipelines/curation/keyword_expander.py:81` | DEFAULT_SEEDS golf: `드라이버` → `골프드라이버` |

## DB 정화 [파괴적, 4단계 프로토콜 준수]

- 대상: `data/curation.db` naver_trending_keywords golf-hugo (오염: 214행 중 209 비골프 — 여성운동화/갤럭시북/게이밍/공기청정기/치발기 등)
- 사전카운트: 214행 출력
- 백업: `data/curation.db.bak_20260906_golf`
- 실행: `드라이버` 1행 + 비골프 197행 + 잔여오염 11행 DELETE
- 사후대조: 5행 잔존 (골프/골프연습/골프용품/매트/퍼팅 — 전부 골프 정상)

## 검증

- 직접 재현 테스트: 공구 제품 2종(데오람 미니 드라이버/베스빈 전동드라이버) 차단 로그 + 골프 제품 2종(캘러웨이/테일러메이드) 생존 확인
- `validate_keyword('드라이버','golf-hugo')` → `(False, "no allowed keyword")` / `골프드라이버` → `(True, '')`
- pytest `tests/test_golf_relevance_gate.py` 19 passed
- pytest curation 스위트: 19 failed / 163 passed — git stash로 수정 전 동일 19 failed 확인 → 기존 실패(title_hardening/title_regression 계열, 본 수정과 무관). 회귀 0
- `tests/ops_dashboard/test_checker_patches_20260820.py` 수집 ImportError (C06_GRACE_HOURS) — 기존 문제, 본 수정 미연관

## 잔존 위험

1. 라이브 공구 포스트 2건(9/4, 9/6) 유지 — 사용자 결정. 재발 아니며 방어 완료
2. curation 스위트 기존 19 failed (title_hardening/title_regression) — 본 worklog 범위 외, 별도 조사 필요
3. `naver_trending_keywords` 타 블로그 오염 가능성 (golf만 점검함) — 재발 알림 시 동일 방식 정화
4. 수정 3파일 미커밋
