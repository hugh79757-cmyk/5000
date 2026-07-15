# Phase 20: Hugo Build 안정화

## 핵심 내용
**이슈1 (CUAP 10 / TAP 5):** baseof.html 인라인 JS `})()`가 Hugo 0.160.1 minifier와 충돌.
- 원인: RAP/CAP 등은 JS를 별도 `lazy-loader.html` partial로 분리해서 문제 없음
- 수정: CUAP/TAP baseof.html의 사망 코드(dead code, mobile-sticky 제거로 무의미해진 JS 블록)를 제거

**이슈2 (badge):** `{{ .Inner }}`가 Hugo 0.160.1에서 미인식
- 수정: `{{ .InnerDeindent }}`로 변경

## 실행 순서
1. Wave 1: CUAP 10개 + TAP 5개 baseof.html dead code 제거
2. Wave 2: badge shortcode 수정
3. Wave 3: 검증 (`hugo --gc --minify` 빌드 + badge 렌더링)
