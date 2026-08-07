# WL-20260807-og-image-investigation

- 일시: 2026-08-07
- 주제: og:image 404 원인 조사
- 결과: **관찰 오류**로 종결. 실제 404 0건.
- 근거:
  - 작업 A: 동일 오브젝트(df1fc351.webp) // 버전은 200, / 단일 버전은 404 → R2는 슬래시 구분
  - 작업 B: camping 067e17f5 포스트 featureimage 원문 = `...curation-images/hash/067e17f5//2026/08/07/4c6119c0.webp` (// 포함)
  - 작업 C: R2 list → `curation-images/hash/067e17f5//2026/08/07/4c6119c0.webp` 존재, HEAD 200
  - 작업 E: CUAP 15개 블로그 실제 featureimage URL 45건 HEAD → **45건 전부 200, 404 0건**
- 판정: og:image URL(//)과 R2 키(//) 일치. 404는 내가 URL을 잘못 구성(파일명 `후기.webp` + 슬래시 `/`)해서 발생한 자가 404.
- 결정: R2 키 이동·URL 치환·커밋 538592489 revert 전부 불필요·미실행.
- 관련 커밋: 538592489 (image_handler 슬래시 방지, 신규 글부터 적용), f70137967 (cover 제거). 유지, 회귀 0.
- 상태: 종결. 미결 이슈로 재부활 금지.
