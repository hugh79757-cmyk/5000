# WL-20260908-disk-full-triage-and-fixes

> 날짜: 2026-09-08~09 / 커밋: 827313eac + 6c35c31ca (push 완료) / 상태: 완료 (모니터링·별도 과제 제외)

## 배경
Telegram 발행 오류 알림 다수(travel/stock/ipo/tour/sector/camping/appliance/layover 등). 조사 결과 근본 원인은 **디스크 100% (Errno 28 No space left on device)**. 3중 원인: (1) scheduler_stderr.log 315MB 폭발(quality_guard 로그), (2) RecheckAll 매시간 실행(80~90분 소요, 상시 CPU 91%), (3) opencode Bun JIT dylib 가비지 11G.

## 파괴적 작업 목록
| 시각 | 작업 | 사전카운트 | 백업 | 사후대조 | 보존확인 |
|------|------|-----------|------|---------|----------|
| ~14:00 | 구형 .bak 삭제 1차 (travel-en 4개~586MB + curation 2개~176MB + data/backups/ 1.2GB) | avail 8.7Gi | 각 DB 최신 .bak 유지 | avail 11Gi | 라이브 DB 무손상 |
| ~15:00 | scheduler_stderr.log 316MB truncate | 316MB | 로그(무백업, append-only) | 0바이트 | lsof PID 45719 핸들 유지 |
| ~15:05 | 구형 .bak 삭제 2차 13세트 ~760MB (content 6개, travel-en 2개, curation 1개, car 3개, mc_chains 2세트, stap 1개, senior 1개) | avail 1.1Gi | 각 DB 최신 .bak 1개 유지 | avail 11Gi | 라이브 DB 무손상 |
| ~16:00 | opencode --auto 프로세스 4개 종료 (88454 4일째/3333/13670/27522) + Bun JIT dylib 가비지 3131개(11G) rm | dylib 3131개, avail 8.4Gi | N/A(가비지) | avail 24Gi (89%) | lsof 잔존 2개(정상) |
| 17:19 | scheduler 재시작 (launchctl kickstart) | PID 45719(5일) | N/A | 새 PID 70963, 6h recheck 적용 확인 | 발행 중 0건 |
| 17:28 | dylib 2차 rm (1784개/6.6G, 1시간 재축적) | 1784개 | N/A(가비지) | avail 23Gi | 라이브 무관 |
| ~21:50 | rap3-hugo Hugo 재빌드 + wrangler 재배포 (동작구 404 race 복구) | public 1글 누락 | content 원본 유지 | 164 files, slug 200 확인 | article 13429 무사 |
| 00:27 | dylib 3차 rm (3800개/14.4GB) | 3800개 | N/A(가비지) | avail 50Gi | 라이브 무관 |
| 09:20 | airlines_topics 가짜 항공사 100개 exhausted 마킹 | 116 미소진 | data/travel-en.db.bak_aero_cleanup_20260909 (172MB) | 9 미소진(전부 실존) | 라이브 글/publish_log 무변경 |

전체 로그: `logs/destructive_2026-09-08.log`

## 코드 수정 (PRODUCTION CODE)
1. `ops_dashboard/checks/content_integrity.py` — `_quiet_gate_logs()` contextmanager 추가, S01/S02/S03 체커가 게이트 호출 시 래핑. quality_guard 로그 폭발 근본 차단. **커밋 827313eac**
2. `scheduler.py` — `_run_recheck_all` 주기 hourly → 6시간. 상시 CPU 91% + 로그 폭발 해결. **커밋 827313eac**
3. `ops_dashboard/checks/disk_space.py` (신규) — `disk_space` 체커 등록. FLEET_SENTINEL='travel-hugo' 실측, WARN_GB=10.0. 디스크 만료가 대시보드에 안 잡히던 공백 해소. **커밋 827313eac**
4. `ops_dashboard/checks/__init__.py` — disk_space import 추가. **커밋 827313eac**
5. `dispatcher.py` — main() CLI 플래그 가드 (`--help`/`--blog` 등이 blog_id로 dispatch되어 P21/P02 publish_error_event로 오기록되던 결함). **커밋 827313eac**
6. `pipelines/curation/keywords.py` — fitness-hugo 강아지 키워드 2개 삭제(오염, pet 중복), 731행 콤마 누락 수정(다이어트괄약근 병합 버그), baby-hugo 그림 도구 키워드 5개 추가(사용자 요청), camping 단일 토큰 키워드 → 복합형 교체(R12), laptop '1kg 이하 초경량 노트북' → '초경량노트북' 교체(쿠팡 미매칭). **827313eac(첫 4항목) + 미커밋(laptop)**
7. `shared/validators.py` — `_check_rap` 복합 지역명 분해 매칭('수원시영통구' 붙은 표기 오탐 수정). 3케이스 검증. **커밋 6c35c31ca**
8. `pipelines/etap/topic_expander.py` — generate_airlines synthetic fill 제거(가짜 'Aero {국가} Airways' 합성 차단). **커밋 2977e4cf4**
9. 2977e4cf4 추가: ai_writer 중국어 오판(라틴 우위), aviasales +7 항공사(CM/YX/LX/HY/9E/TS/VN), keywords laptop 교체, scheduler cooldown 오판 수정 + catchup race guard(_running_publishes), prompts tour3_course H2 3→4(travel.yaml 본체 + prompts.yaml 데드카피 동기화)
10. TAP 커밋 bceceb90(remote=travel4-hugo 저장소, 기존 관행): ai_writer system_msg→generate_with_system, festival_writer LLMClient 전환, app run_publish 반환 + heritage 단일 폴백 제거
11. scheduler 재시작 2회(9/9 13:33 PID 10116) — cooldown/race guard/heritage 수정 적용

## travel4 P01 12회 근본 (최종)
- tour3_course 프롬프트(config/prompts/travel.yaml:172)가 H2 3개 구조 설계 ↔ 검증 게이트(8/12 c268f0b81, H2>=4) 불일치 → 항상 재시도 소진 → chain_timeout → 8월 중순부터 발행불능. 프롬프트에 '{region} 여행 꿀팁' H2 추가 → 초회 검증 통과(H2:4) + 발행 200 확인(2026-09-09 14:04, 창덕궁/북촌 코스, tour3.rotcha.kr) [검증됨]
- b16/b17의 'TAP subprocess' 판단 정정: travel4는 pipeline:travel(in-process), tap-blogger만 TAP subprocess. TAP 수정은 tap-blogger 광주 북구 5연속 해결에 유효

## 검증 요약
- quiet gate logs: S02/S01 게이트 정상 반환 + stderr quality_guard 로그 0건 [검증됨]
- 6h recheck: ast.parse syntax OK [검증됨]
- disk 체커: 'disk_space' in CHECKS + sentinel '디스크 여유 10.4GB' pass [검증됨]
- dispatcher 가드: `python3 dispatcher.py --help` → usage + exit 1 [검증됨]
- keywords.py: fitness 175개/강아지 0/'다이어트'+'괄약근' 분리 확인 [검증됨]
- tests/test_structural 등 22 errors: 내 수정 이전 베이스라인과 동일(conftest.py:40 사전 훼손) [검증불가]

## 오류 원인 분류 (펄트 발행 알림 → 실제 상태)
| 알림 | 실제 | 조치 |
|------|------|------|
| travel/stock/ipo/tour/sector disk I/O | 디스크 100% 여파 | 디스크 회복. sector/tour/culture 등 자가 회복 확인 |
| travel2-hugo no_result 13:04/16:04 | quota 3/3 도달 재실행 오보고 (발행 3건 완료, 13:04도 실제 배포 rc=0 성공) | 불필요 — false-positive |
| ipo-hugo P04 | 글 생성·index.md 작성은 성공, Hugo build no space 로 배포 실패 | 16:00 STAP 슬롯 자연 복구 예상 |
| camping P02/P14 (폴대/식기/페그 avg=0.50) | 단일 짧은 토큰이 상품명 1회 매칭 → 0.5 < 0.55 구조적 미달 | quarantine 자가 방어 + R12 복합형 교체 |
| appliance 물걸레 write_error | (b5 블록 참조 — R06 수정 완료) | 20:02 슬롯 재발 여부 관찰 |
| layover word count 376<400 | 9/7 이전 이슈, 오늘 발행 3건 성공 | 불필요 — 자가 회복 |
| P33 car.db refresh stalled | 대시보드 오류 데이터 — 오늘 06:30 정상 실행(refresh_log 2026-09-08행, state=success) | 불필요 — false 데이터 |
| fitness 강아지 P03/P36 | keywords.py 오염 | 수정 완료 |
| airlines-hugo 5연속 pipeline_returned_false | topic_expander 가짜 항공사 100개(합성 Aero {국가} Airways) — airline_routes 데이터 0건 | synthetic fill 제거 + 100개 exhausted 마킹 |
| already_running 4건 (massage/laptop/kitchen/golf 9/9) | catchup race 재발 — 정규 발행과 CATCHUP 병렬 충돌, 락 자가 방어 | 라이브 오염 0, 근본은 별도 과제 |
| rap-hugo 순천 2건 no_trade_data | 공공실거래가 API가 순천(46150) 202606~09 전부 0건 미제공 — 아산 202609 57건 대조 정상 | 키워드 자동 비활성화 완료 |

## 잔존 위험
- opencode Bun dylib 지속 생성(측정 ~3.2GB/h峰值) — 3차 정리(00:27)로 avail 50Gi. 주기적 정리 필요 — opencode 세션 장시간 --auto 유지가 주원인
- ~~catchup 병렬 실행 race~~ — 9/9 race guard 구현·커밋(_running_publishes). 다음 충돌 관찰로 실증 대기
- ~~scheduler cooldown=true 오판~~ — 9/9 수정·커밋(reason 검사). PID 10116 신 코드 적용
- tests 22 errors 사전 훼손(conftest.py:40) — 미복구
- ETAP pipeline.py:214 data_prices=None — 환각 가격 소스 검증 비활성 상태(daytrips draft 자가 방어로 라이브 오염은 없음)
- travel2 13:04 pipeline_timeout_300s 오보고 구조 — 미수정
- LLM 제목 재생성 → duplicate_slug (kitchen 블렌더/baby 아기모자) — quarantine 자가 방어 중, 제목 다양화 근본 미수정
- 동작구 9월 글 3개 라이브 — 지역 월중복 유사제목(Jaccard 0.75 WARNING, advisory). 근본 미수정
- 순천 지역 공공실거래가 API 미제공(202606조차 0건) — 세금/전세 키워드도 같은 경로 예상(rap4 중흥에스-클래스 전세 9/9 실증 — 자가 비활성화)
- topic_expander: 9/9 01:00 실행에서 가짜 재생성 0건 확인. 다음 01:00 재확인 권장
- TAP heritage 미사용 52건(전부 단일 시군구) — 폴백 제거로 heritage_skip 반환, camping/festival이 발행 담당. 데이터 보충 전까지 heritage 발행 0
- config/prompts.yaml 내 tour3_course 등 데드카피 — prompt_builder는 config/prompts/ 디렉터리 우선 로드. 혼동 유발, 정리 대상(선택)
