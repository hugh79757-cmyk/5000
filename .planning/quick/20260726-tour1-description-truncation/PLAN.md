---
slug: tour1-description-truncation
date: 2026-07-26
status: in-progress
---

# Quick Task: tour1.rotcha.kr 포스트 제목 아래 설명문 잘림 버그 수정

## Problem
- URL: https://tour1.rotcha.kr/posts/%EA%B2%BD%EA%B8%B0-%EC%95%88%EC%84%B1%EC%8B%9C-%EC%97%AD%ED%96%89-%EB%B3%B4%EB%AC%BC-3%EA%B3%B3-%EC%82%AC%EC%9D%B8%EB%B9%84%EA%B5%AC-%EC%A0%9C%EC%9E%91-%EB%8F%99%EC%A2%85---%EC%95%88%EC%84%B1-%ED%8F%AC%ED%95%A8-%EB%B9%84%EA%B5%90/
- 증상: 타이틀 아래 설명문이 "경기 안성시 보물 3곳 한눈에 비"에서 잘림 (원문: "경기 안성시 보물 3곳 한눈에 비교")
- 원인 파악 필요: Hugo 템플릿, content 생성 파이프라인, 또는 빌드 과정에서 발생

## Investigation Plan
1. 해당 포스트의 Hugo content 파일 확인 (markdown frontmatter + body)
2. tour1-hugo 템플릿에서 description 렌더링 부분 확인
3. TAP/5000 파이프라인에서 description 생성 로직 확인
4. 잘림 원인 식별 후 수정

## Expected Fix
- description 전체가 잘리지 않고 정상 표시되도록 수정
- 재발 방지를 위한 검증 로직 추가 (가능한 경우)