# WL-20260906 — STAP 발행 에러 배치 트리아지 + `** ` 제목 오염 수정

날짜: 2026-09-06
작업 유형: 발행 에러 트리아지 (P02/P10/P14/P16) + [PRODUCTION CODE] 수정 + 콘텐츠 2건 수정 + Pages 배포 2건

## 배경

Telegram 배치 알림: escape-hugo 단어수 미달, stock-hugo SyntaxError, laptop/fitness title_blocked, kitchen duplicate_slug, camping offtopic, ipo/nature no_content·연속실패, BC 큐 소진.

## 트리아지 결과 (REAL vs transient)

| 블로그 | 코드 | 분류 | 근거 |
|---|---|---|---|
| stock-hugo | SyntaxError | REAL — FIX #1 | writer.py:962 nested quote → ast.parse 재현 |
| laptop-hugo | P10 title_blocked 3x | transient | ledger 3키워드 10:42-11:01 실패, 13:30 수동 재현 시 정상 타이틀 반환 — economy LLM 일시 불안 |
| fitness-hugo | P10 1x | transient | 11:20 실패 → 11:23 성공 |
| kitchen-hugo | P16 duplicate_slug | transient | 11:30 충돌 → 11:33 다른 포스트 성공 |
| escape-hugo | word count 372<400 | transient | 13:28:52 발행 성공 (CATCHUP 3/3) |
| camping-hugo | P14 offtopic 식기/난로 | data-quality transient | CATEGORY_FILTERS `가전` substring가 `가전디지털` 난로 제품 차단, 식기 캐시 재수집으로 자가회복. 히터 allowed 추가 여부는 별도 승인 필요 |
| ipo-hugo | P02 no_content 10:55 | transient | 같은 날 2건 발행 (10:54, 07:33) |
| nature-hugo | P02 5x pipeline_returned_false | fail-closed 정상 동작 | S01/S02/S03 게이트가 동일구조 제목 거부. 13:39 수동 실행 게이트 통과 발행. 구조 다양성 개선은 긴급 아님 |
| BC (bc-aside) | 큐 소진 10:24/10:27 | REAL — 미해결 | seed queue 비었음, bc-seed-collection 스킬로 재수집 필요 (본 worklog 미수행) |

## FIX #1 — stock writer.py SyntaxError [PRODUCTION CODE]

- 파일: `/Users/twinssn/Projects/STAP/pipelines/stock/writer.py:962`
- 원인: 커밋 안 된 편집에서 nested quote `system_prompt="system_prompt="당신은...` 유입
- 수정: stray `system_prompt=` 제거
- 검증: ast.parse OK, py_compile OK, rg bug-pattern STAP 전체 0건
- 기존 미커밋 diff(16+/70-, 이전 작업분)는 원상 유지

## FIX #2 — `** ` 제목 prefix 오염 [PRODUCTION CODE + 콘텐츠]

- 원인: `_parse_response()`가 `TITLE:` 접두 뒤 `**`를 못 걸름
- 수정(5 파일 ipo/finance/dividend/stock/etf writer): `title = re.sub(r"^\*+\s*", "", line.replace("TITLE:", "").strip()).strip().strip('"').rstrip("*").strip()`
- sector/writer.py는 기존 정리 로직 있음 — 미수정
- 검증: py_compile 5파일 OK, 파싱 직접 테스트 OK, STAP pytest 29 passed (테스트 코드 미수정)
- 콘텐츠 수정: ipo-hugo SK이노베이션 글 title, finance-hugo 애큐온저축은행 글 title+tags+categories
- 배포: ipo-hugo rc=0 16.4s, finance-hugo rc=0 19.6s (deploy_site(), Pages)
- 라이브 검증: 두 URL 200, `<title>`에 `**` 없음
- 함정 기록: 첫 빌드 시도 `-t PaperMod` 플래그가 hugo.toml `theme=blowfish`를 덮어 hero/basic.html 에러. 플래그 없이 빌드할 것

## 파괴적 작업 로그

`logs/destructive_2026-09-06.log` 2건 (ipo-hugo, finance-hugo 배포, 사전카운트/사후/live 무열 확인 기록)

## 잔존 위험

1. **BC seed 큐 소진 미해결** — bc-seed-collection 스킬 실행 필요. 복구 계획: 스킬 로드 → BC 콘솔 TOP100 재수집 → seed_bc_queue.json 갱신
2. **camping-hugo 히터 allowed 추가** — P10/P14 규칙상 사용자 승인 필요, 미적용
3. **nature-hugo 구조 다양성** — 게이트 정상. LLM이 템플릿형 제목 반복 시 재발 가능, 긴급 아님
4. **stock-hugo 다음 스케줄 실행** — subprocess가 코드 재적재하므로 재시작 불필요, 다음 실행 결과 모니터 권장
5. STAP writer.py 5파일 + 콘텐츠 2건 **미커밋** — 커밋 요청 시 별도 분리 커밋 권장 (기존 미커밋 diff와 섞이지 않게)
