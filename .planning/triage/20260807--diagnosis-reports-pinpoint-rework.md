---
date: 2026-08-07
type: debug
status: ongoing
---

# 진단 보고서 작성 + 핀포인트 재작업 3항목

## What

- `.planning/DIAGNOSIS-2026-08-07.md` 작성: 전 분기 지도, 콘텐츠 전수 실측(보정 이미지 기준), 텍스트 품질 스캔, 대시보드 감지력 검증, FRONTMATTER-LEAK-59 재발 스캔, 종합 판정.
- `.planning/DIAGNOSIS-PINPOINT-2026-08-07.md` 작성: 실패 3항목만 재작업(라이브 실제 대조, 내부링크 0 원인, 텍스트 품질 패턴 재설계).

## Why

- 지난 세션에서 검증 실패한 항목(이미지/내부링크/글자수 파일-라이브 불일치, 내부링크 0 원인, 생이라면/이라이/이라고 패턴 오탐)을 다시 확인해야 했음.
- 수정·발행·스케줄러 재개 전에 읽기 전용 진단만 먼저 확정하려는 목적.

## Files changed

- `.planning/DIAGNOSIS-2026-08-07.md` (생성)
- `.planning/DIAGNOSIS-PINPOINT-2026-08-07.md` (생성)

## How

- 분기 지도는 `config/blogs.yaml` + `config/blogs.d/*.yaml` 읽기 기준.
- 콘텐츠 전수 실측은 각 활성 블로그 `content/posts/**/index.md` 읽기 + frontmatter 이미지 필드 + 본문 `![](` 합산 기준.
- 내부링크/품질 스캔은 파일 본문 regex 기준.
- 라이브 대조는 실제 URL 열기 + 본문 텍스트/이미지 alt/내부링크 패턴 확인 기준(HTTP 상태만 보지 않음).

## Verification

- 분기 지도/전수 실측 수치는 파일 읽기 기반이라 재현 가능.
- 라이브 대조는 실제 URL 접근 성공 건(TAP/SEAP/pet-hugo/appliance-hugo ASCII slug)만 인용.
- CUAP 한글 슬러그 1건은 404로 확인돼 대체 샘플로 진행.

## Notes

- humanizer A/B(P1), 스케줄러 재개(P4)는 이번 세션에서 결정하지 않고 이월.
- 텍스트 품질 패턴은 “생이라면/이라이/이라고”를 자동 오류로 쓰지 않기로 정리.
- 남은 미확정: 내부링크 카운트 기준과 실제 렌더링 기준 차이 정밀 정리, 브랜드 환각 검증용 상품명 대조 수단 부재.
