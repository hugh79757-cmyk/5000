---
slug: etap-tags-list-fix
date: 2026-08-10
status: complete
scope: etap-publish-regression
---

# Summary: ETAP 발행 회귀 — tags list → str 정규화

## 수행
- **대상 파일**: `shared/publishers/hugo_writer.py` — `_write_hugo_post_etap()`
- **수정**: `tags = article.get("tags", [])` 직후 list 정규화 추가
  ```python
  if isinstance(tags, list):
      tags = ",".join(str(t).strip() for t in tags if str(t).strip())
  ```
- list → "city,country,Luxury Tours" str 변환, str은 그대로 통과,
  빈 list → "" (빌더에서 tags 라인 생략).
- `_build_frontmatter_*` 빌더/공유 `_write_hugo_post` 계약은 변경 없음.

## 게이트
1. 백업: `git tag pre-etap-tags-20260810` 생성.
2. baseline: `test_defense_layers_independent.py` — 수정 전 4 fail / 수정 후 4 fail
   (동일 — 기존 CoT 검출 실패, 이번 수정과 무관. 11 pass).
3. 단위 검증:
   - list tags → `_write_hugo_post_etap` 정상 파일 생성,
     PyYAML 파싱 `tags: [Paris, France, Luxury Tours]` 확인.
   - str tags → `_build_frontmatter_blowfish("tag1,tag2")` 정상 ("tag1","tag2" 포함).
   - 빈 tags → `tags:` 라인 생략 (YAML 파싱 확인).
4. 커밋: `hugo_writer.py` + PLAN/SUMMARY + STATE.md Quick Tasks 표.

## 상태
- status: complete (단위 검증 완료, 배포는 스케줄러 재실행으로 자연 반영)

## 잔존 위험
- `shared/publisher.py` 동일 `tags.split(",")` 4곳(221/244/267/1028행): 현재
  문자열 호출자뿐이라 latent — list 전달 시 동일 오류 가능. 추후 별도 정리.
- pet-hugo timeout(600s)은 별개 문제 — 미조사 상태 (다음 세션 과제).