## Wave 5: ad partial 정비 (38개)

### 5-1. top.html 정비

| 작업 | 대상 | 수 |
|------|------|---|
| overflow:hidden;min-height:100px 추가 | CAP compare/pick/rank + STAP 5 + TAP 5 + RAP 4 + SEAP 1 + 개별 4 | 24 |
| top.html 신규 생성 | CAP deal/ev/guide/tco | 4 |

### 5-2. in-article.html 정비

| 작업 | 대상 | 수 |
|------|------|---|
| push script div 밖으로 이동 | TAP 5개 | 5 |
| 포맷 변경 (fluid→auto) | STAP 5개 | 5 |
| 하드코딩 → 템플릿 변수 | CAP deal/ev/guide/tco + SEAP senior | 5 |
| overflow:hidden;min-height:100px 추가 | 전체 대상 | 36 |

### 5-3. leaderboard.html → top.html 표준화

| 작업 | 대상 | 비고 |
|------|------|------|
| leaderboard.html 사용 중지 및 top.html로 통합 | 전체 대상 | 36개 블로그 |
| - leaderboard.html을 사용하는 블로그: single.html에서 top.html로 호출 변경 및 파일 삭제 |
| - 불필요한 leaderboard.html 파일: 삭제 |
| - top.html이 누락되거나 기준과 다른 블로그: Wave 5-1과 동일하게 처리 |

---