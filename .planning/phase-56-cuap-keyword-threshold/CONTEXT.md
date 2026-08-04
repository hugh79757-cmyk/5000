# CONTEXT: Phase 56 — CUAP 키워드 정리 + 임계값 완충 → kitchen/beauty 재활성화

## 배경

kitchen-hugo, beauty-hugo가 write_error 반복으로 비활성화됨. 근본 원인은 비주제 키워드 풀 오염(중국어/혼합어 키워드)과 임계값 알림 로직 결함(maybe_alert()가 연속 횟수 미확인).

## 전제 (이미 확정)

- write_error 반복의 근본원인 = 비주제 키워드 풀 오염
- 임계값 알림은 write_error 연속 3회로 발동
- 기존 제출된 완충 수정(3)은 maybe_alert 임계값과 이중검사라 폐기
- already_running은 Dead Code (카운터 미도달)
- kitchen 134개, beauty 172개 비주제 키워드 식별됨

## 핵심 파일

| 파일 | 역할 |
|------|------|
| `pipelines/curation/keywords.py:838-924` | kitchen-hugo 키워드 맵 |
| `pipelines/curation/keywords.py:925-1009` | beauty-hugo 키워드 맵 |
| `shared/alert_thresholds.py:93-143` | maybe_alert() 함수 |
| `pipelines/curation/pipeline.py:722-724` | 연속 실패 카운터 + maybe_alert 호출 |
| `config/blogs.d/cuap.yaml` | kitchen/beauty 상태 관리 |

## 범위

- **1단계 (읽기 전용):** 키워드 정리 대상 목록 + 임계값 완충 diff 초안
- **2단계 (배포):** 키워드 정리 + 완충 수정 커밋 + kitchen/beauty 재활성화 + 실측

## 제약

- force push 금지
- wrangler 수동 배포 금지
- fitness/laptop 활성화 금지
- 타 블로그 활성화 금지
