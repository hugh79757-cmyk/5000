---
slug: etap-tags-list-fix
date: 2026-08-10
status: in-progress
scope: etap-publish-regression
---

# Quick Task: ETAP 발행 회귀 — tags list → str 정규화

## Description
ETAP 블로그(luxury/escape/extreme/nightlife/ghost/layover 등 6+)에서
`AttributeError: 'list' object has no attribute 'split'` 발생.
`_write_hugo_post_etap()`이 ETAP article의 `tags`(list)를 그대로
`_write_hugo_post()` → `_build_frontmatter_*()`에 전달하나, 빌더는
콤마 구분 문자열을 기대(`tags.split(",")`) — type mismatch 회귀.

## 원인 (2026-08-06 도입)
- commit `a64544294` (8/6): 31개 ETAP 파이프라인이 로컬 `_write_hugo_post`
  (list 직접 처리) → 공유 `_write_hugo_post_etap`으로 마이그레이션.
- `hugo_writer.py:1210` `tags = article.get("tags", [])` — list 그대로 전달.
- 기존 로컬 버전은 `chr(10).join(f'  - "{t}"' for t in article.get("tags", []))`
  로 list를 직접 처리 → 마이그레이션 전엔 정상.

## Scope (이번 작업)
- [PRODUCTION CODE] `shared/publishers/hugo_writer.py` `_write_hugo_post_etap()`
  (1210행 부근): `tags`가 list면 콤마 join str로 정규화 (str이면 그대로).
  - 수정: `if isinstance(tags, list): tags = ",".join(...)`
- 기존 str tags 호출자(CAP/CUAP 등) 동작 변경 없음 — isinstance 가드로 보존.
- `_build_frontmatter_*` 빌더 자체는 수정하지 않음 (str 계약 유지, 파괴적 변화 방지).
- pet-hugo timeout(600s)은 별개 문제 — 이번 범위 제외.

## 게이트
1. 백업: git tag `pre-etap-tags-20260810` 생성됨. (DB 미사용 — backup 불필요)
2. baseline: test_defense_layers_independent 4건 실패 — 수정 전후 동일
   (기존 실패, 이번 수정과 무관).
3. 단위 검증:
   - list tags → `_write_hugo_post_etap` 정상 호출, YAML 파싱 `tags: [...]` 확인
   - str tags → 기존 문자열 호출자 보존 (assert tag1/tag2)
   - 빈 tags → tags 라인 생략
4. 커밋: hugo_writer.py + quick 아티팩트 + STATE.md Quick Tasks 표 갱신.

## 잔존 위험
- `shared/publisher.py`의 동일 `tags.split(",")` 4곳(221/244/267/1028행)은
  list 전달 시 동일하게 터질 수 있으나 현재 문자열 호출자뿐이라 latent —
  이번 범위 제외, 추후 별도 정리.
- pet-hugo timeout은 별도 조사 필요.