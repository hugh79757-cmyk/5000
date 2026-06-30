# Status.md — 5000 발행 현황

> 최종 업데이트: 2026-06-30T13:30+09:00

## 전체 발행 현황

**Active 블로그**: 27개 (RAP 5 + CUAP 10 + STAP 6 + TAP 5 + SEAP 2 + CAP 2 + 기타 5)
**Inactive 블로그**: 44개 (ETAP 35 + CAP 6 + GAP 2 + TAP 3 + 기타)

## 6월 30일 발행 (catchup 진행 중)

| 블로그 | 상태 | 비고 |
|---|---|---|
| compare-hugo | ✅ 2건 | CAP catchup 완료 |
| hotissue-hugo | ✅ 2건 | CAP catchup 완료 |
| appliance-hugo | ✅ 1건 | |
| baby-hugo | ✅ 1건 | |
| fitness-hugo | ✅ 1건 | |
| interior-hugo | ✅ 1건 | |
| laptop-hugo | ✅ 1건 | |
| beauty-hugo | ✅ 1건 | |
| camping-hugo | ✅ 1건 | |
| health-hugo | ✅ 1건 | |
| kitchen-hugo | ✅ 1건 | |
| pet-hugo | ✅ 1건 | |
| rap-hugo | ✅ 1건 | |
| rap2-hugo | ✅ 1건 | |
| 🔄 RAP/STAP/TAP/SEAP | 진행 중 | catchup 지속 |

## 알려진 문제

| 문제 | 상태 | 비고 |
|---|---|---|
| `validators.py` IndentationError | ✅ 수정완료 | 2026-06-30 12:36 재시작 |
| Telegram 400 전송오류 | ✅ 해결 | IndentationError로 인한 2차 현상 |
| baby-hugo `title_blocked` | ⚠️ 지속 | 키워드 "강아지" blocked 리스트冲突 |
| sector-hugo `no_content` | ⚠️ 지속 | 데이터 부족 |
| ETAP 35개 inactive | ⏸️ 장기 | 2026-05-06 마지막 발행 |
| CAP 6개 inactive | ⏸️ 장기 | 6/4~6/5 마지막 발행 |

## 인시던트 기록

| 일자 | 내용 | 해결 |
|---|---|---|
| 2026-06-27~30 | `validators.py` IndentationError → 전면 중단 | 06-30 12:36 수정+재시작 |
