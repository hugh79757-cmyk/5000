---
date: 2026-08-03
type: fix
status: resolved
---

# CUAP 폴백 제목 안전화 + write_error 재시도 확대 + kitchen/beauty 비활성화

## What
1. writer.py: 헤딩 없는 AI 응답 시 옛 `"추천 TOP5 (연도)"` 폴백을 `pick()` 기반 안전 템플릿 + `"추천 · YYYY년 M월"` 계층적 폴백으로 교체
2. writer.py: write_error 재시도 2→3회, 시도별 temperature 다양화 (0.85/0.95/0.75)
3. cuap.yaml: kitchen-hugo, beauty-hugo inactive 복귀 (임계값 초과 알림 중단 목적)

## Why
- 옛 폴백 포맷 `".keyword 추천 TOP5 (2026년)"`이 slug 중복을 유발 → publish_error
- write_error가 2회 재시도로는 글자수 미달(800자) 충분히 회피 불가
- kitchen/beauty에서 write_error/low_relevance 연속 실패 → 임계값 초과 텔레그램 알림

## Files changed
- `pipelines/curation/writer.py` — 폴백 제목 로직 재작성 + 재시도 확대
- `config/blogs.d/cuap.yaml` — kitchen-hugo, beauty-hugo status: inactive

## How
- writer.py: `pick()` 실패 시 예외를 조용히 무시하던 것을 `logger.warning`으로 변경
- writer.py: 옛 `f"{keyword} 추천 TOP5 ({datetime.now().year}년)"` 문자열 완전 삭제
- writer.py: 최후 폴백을 `f"{keyword} 추천 · {year}년 {month}월"`로 변경 (slug 중복 회피)
- writer.py: 후기 프레임 필드(`실사용/후기/느낌/써본/리뷰`)가 폴백 제목에 포함되지 않도록 검증 추가
- cuap.yaml: kitchen-hugo, beauty-hugo를 inactive로 설정하여 스케줄러 발행 중단

## Verification
- writer.py 컴파일 확인 ✓
- pipeline.py 컴파일 확인 ✓
- _alert_checker.get_config 동작 확인 ✓
- 폴백 제목 `pick()` 생성 확인 ✓
- 임계값 체크 로직 동작 확인 ✓
- 옛 TOP5 문자열 grep 0건 확인 ✓

## Commit
- `973a6eef6` — fix(cuap): fallback title via pick() + write_error retry 2→3
- push 완료 (27530a216..973a6eef6)

## 잔존 위험
- CoT 근본 안정화(DeepSeek)는 별도 트랙
- kitchen/beauty 비주제 키워드(`가정용`, `가죽소파`, `개입`, `나노` 등) 풀 정리 필요
- publish_error(slug 중복) 3건은 옛 폴백 포맷 때문 → 이번 수정으로 해소 예상
- kitchen/beauty 재활성화는 비주제 키워드 정리 후 승인 필요
