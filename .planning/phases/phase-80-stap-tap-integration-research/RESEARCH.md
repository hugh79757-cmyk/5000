# Phase 80 — STAP/TAP 구조 통합 가능성 조사 (읽기 전용)

**판정: 통합 비추천 — 격리 유지. 단, 원장(ledger) 문제는 별도 해결 필요.**

조사일: 2026-09-14. 실행 아님 — 판정 근거만.
범위: dispatcher.py:487-505(_run_stap), :573-594(_run_tap_subprocess), :624-634(ETAP 내부 임포트 대비).

---

## T1. 의존성 충돌 분석

**결론: 물리적 충돌은 존재하지 않음(소버전 차이만). 그러나 venv 분리는 설계 의도가 아니라 유지 관리 방치의 산물임.**

측정 방법: `pip list --format=freeze` 3개 venv 전수 (5000/.venv, STAP/.venv, TAP/venv).
- 5000: 86 패키지, STAP: 43, TAP: 76.
- 교집합: 5000∩STAP 37, 5000∩TAP 68, STAP∩TAP 37.

버전 충돌 37개 전부 **소버전(micro) 차이**(예: `anyio 4.14.2 vs 4.14.1`, `pillow 12.3.0 vs 12.2.0`). 메이저 버전 차이는 하나뿐:
- `openai`: 5000=3.3.1 / STAP=2.37.0 / TAP=2.44.0 — **유일한 실질 충돌.**

venv 분리의 원인이 의존성 충돌이었는지 판별: **아니다.** Phase 61 문서(`.planning/phases/61-pipeline-standardization-branch-renewal/61-RESEARCH.md:53`)에 "External venv isolation lives at the 5000 boundary"라지만, 이는 격리 구조를 '유지'하기로 한 결정이지 격리를 '만든' 원인이 아니다. openai 3.x 마이그레이션(5000)과 STAP/TAP 2.x 잔류가 현재 분리를 유지하는 실질 이유로 판명.

- [검증됨] 3 venv freeze 전수 대조 — 기계적 산출, 완전 커버.
- [검증불가] 과거 특정 시점 의존성 상태(분리 당시 충돌 존재 여부) — 현재 스냅샷만 존재.

## T2. 인터페이스 두께

**결론: 경계는 매우 얇다 — JSON dict 1개 왕복. 전환 난이도 낮음(기술적).**

- `dispatcher.py:487-505` `_run_stap`: `run_subprocess(project_root, venv_python, module_spec="pipelines.{stap_name}.pipeline", run_callable="run", cfg=cfg, timeout=600, prefix="stap", blog_id=cfg["id"])`.
- `dispatcher.py:573-594` `_run_tap_subprocess`: `module_spec="app", run_callable="run_publish", cfg=None` — TAP은 cfg를 받지 않는 무인자 인터페이스(autoload 방식).
- `shared/subprocess_runner.py:61-186`: tempfile runner + venv python + `json.dumps(cfg)` CLI 임베드 + stdout 마지막 JSON 라인 파싱(:168-171). 내부 객체 공유 전혀 없음. 공유되는 것: cfg JSON(5000→외부), result dict(외부→5000), env(TOKEN pop 등 규칙 상속, :103-105), 파일시스템(콘텐츠 파일은 STAP이 자체 data/에 씀).
- STAP 결과 후처리: `dispatcher.py:542-553` quality_recorder — 얇은 소프트(try/except 비치명).
- ETAP 내부 임포트 대비(`dispatcher.py:526-534`): importlib + signature inspection으로 `run(cfg)`/`run()` 자동 대응 — STAP/TAP 전환 시에도 같은 패턴 재사용 가능.

- [검증됨] 호출부 전 라인 독해(:487-505, :573-594, :536-559, runner 전체 186행) — 전수.
- [부분검증] TAP run_publish 내부(app.py:615~) — 인터페이스 계약(무인자, dict 반환)만 확인, 내부 로직 전수 미독해.

## T3. 격리 의도 규명

**결론: 격리는 설계 의도다 — Phase 61 잠긴 결정 D-04.**

- `.planning/phases/61-pipeline-standardization-branch-renewal/61-08-PLAN.md:38` 원문: "**중요 (D-04): STAP/TAP 저장소는 물리적 병합하지 않는다.** 계약 정합(subprocess 격리 + 동일 dict 반환)만 수행. 외부 프로젝트는 계속 subprocess로 격리 실행된다."
- 61-RESEARCH.md:35: "Physically merging TAP/STAP into the 5000 tree (external projects stay subprocess-isolated — only the **contract** is aligned, `shared/subprocess_runner.py`)".
- 커밋 히스토리: `da066e3fe` feat(phase-61): add shared/subprocess_runner.py (subprocess isolation runner) — 격리 로직 400줄 중복을 통합하면서도 물리 병합은 명시적으로 배제.
- STAP AGENTS.md: 격리 근거 직접 명시는 없음(venv 사용법만, :21). TAP 쪽 자기 기록도 미발견.
- 즉 격리 = "기술적 필요(openai 메이저 차이 등)"보다 "원장 소유권 분리(각자 data/에 자체 기록)"가 주된 설계 의도. 역사적 우연 아님 — 문서로 잠긴 결정.

- [검증됨] Phase 61 문서 2종 원문 + 커밋 da066e3fe 메시지 — 격리 유지 결정의 직접 근거.
- [부분검증] "왜 분리했나"의 최초 동기 — D-04 문서가 존재 결정이지 최초 이유 설명은 아님. 최초 분리 시점(Phase 61 이전)의 명시적 근거 문서는 미발견.

## T4. 원장 설계

**결론: 원장이 통합의 실질 장애물. STAP 원장은 이미 2벌(5000 124MB + STAP 19MB)이며 쓰기 주체가 분리되어 있다.**

실측(2026-09-14):
- 5000/data/stap_content.db: **124MB, 14,028행** — aikorea24 644, rap5 610, rap2 606, rap3 594, rap4 572 등 5000 계열 블로그 원장. tco 파일럿에서 articles 실체로 판명(b16).
- STAP/data/stap_content.db: **19MB, 3,281행** — dividend 726, stock 695, finance 678, etf 470, sector 394 — STAP 계열 블로그 원장. **최신 11:10:32 — 방금 STAP 파이프라인이 쓴 상주 파일.**
- 두 파일은 **서로 다른 블로그의 articles**를 담는 동명(同名) 파일. 경로 결정은 `STAP/pipelines/sector/pipeline.py:310-318` — `__file__` 기준 상대(`STAP/data/`), 즉 subprocess cwd와 무관하게 항상 STAP 쪽을 씀. 5000 쪽은 `shared/db_paths.py:ARTICLES_DB`(b3).
- **콤보가드 BUG-14 2단(b16 D-2)의 구조적 뿌리**: 5000 `shared/publisher.py:832` 콤보가드는 5000 원장(articles)을 읽는데, 러너 환경에서 STAP 원장이 R2 부재 → 빈 articles로 가드 통과 → 팬텀 재발행. 원장 2벌이 곧 가드 무력화 원인.
- TAP 원장: tap.db(19MB)가 실체 — posts 16행/publish_logs 467행/used_content_ids 1,931행/source_pool 등. `app.py:628 SourceManager('tap.db')` — 5000/data 쪽에는 TAP 관련 테이블 없음. TAP은 **통합 시 원장 이관 대상이 아니라 원장 부재 상태로 5000으로 들어옴** — entity(tap_entity.db 448KB)만 별도.

통합 시 시나리오: 5000/data/가 SSOT가 되려면 STAP 3,281행을 5000 원장에 병합(스키마 동일 — articles 테이블)해야 하고, 이후 STAP 파이프라인(내부 임포트 전환 시)이 5000 원장에 쓰도록 경로 코드 수정 필요. **`sector/pipeline.py:310-318`의 `__file__` 상대 경로는 내부 임포트 전환 시 5000 루트 기준으로 바뀜** — 수정 1곳이면 되지만, 반대로 현재 구조에서 "같은 파일명, 다른 내용" DB가 2벌 존재하는 상태는 혼동 지속 위험. Phase 79 G0(tco 러너)에서 round-trip 대상이 5000 쪽(stap 124MB)이었던 이유도 이 구조.

- [검증됨] 2벌 DB 실측(행수·blog 분포·최신 타임스탬프·쓰기 주체) + sector/pipeline.py 경로 코드 원문 + TAP tap.db 스키마/행수.
- [검증불가] 병합 시나리오의 실제 충돌(스키마 마이그레이션) — 병합을 실행하지 않는 한 실증 불가. 스키마 동일성은 테이블 명세 대조로 대체 확인 필요.

---

## 종합 판정: 통합 비추천 — 격리 유지 (예상 공수: 통합 실행 시 2-4주+리스크, 격리 유지 시 0)

격리 필수 근거(구체):
1. **Phase 61 D-04 잠긴 결정** — "물리적 병합하지 않는다"가 문서화된 계약. 뒤집으려면 별도 ADR 필요.
2. **openai 메이저 버전 분기(3.x vs 2.x)** — 5000의 ai_writer는 openai 3.x 계약 위에서 최적화됨(LLM 폴백 체인 17티어). STAP/TAP 전환은 두 프로젝트 전체 AI 호출부 검증 동반. 메이저 마이그레이션 실증 전까지 한 venv 불가.
3. **원장 소유권** — STAP 원장 2벌 구조(5000 124MB + STAP 19MB)는 각자 블로그군(brand)의 기록. 통합 = 14,028+3,281행 병합 + 쓰기 주체 전환 + G0 러너 round-trip 대상 재설계. Phase 79가 "5000 원장 SSOT" 구조를 확립 중(G-B 관찰 진행) — 지금 구조를 바꾸면 파일럿 무효화.
4. **실행 안정성** — subprocess 격리는 STAP/TAP 크래시가 5000 프로세스를 죽이지 않음(pipeline_timeout 600s 독립). 내부 임포트는 GIL 공유로 한쪽 메모리 누수/크래시가 전체 스케줄러 장애로 전이. 30+ 블로그 동시 발행 시스템에서 격리는 안정성 자산.

그러나 조사 중 발견한 **부산물 2건은 별도 처리 가치**:
- **BUG-14 원장 2벌 문제**(T4) — 통합 없이도 해결 가능: publisher 콤보가드가 5000 원장을 읽는 이상, 러너 환경의 빈 STAP 원장이 가드를 무력화. Task 9 스코프(publisher.py:832 스코프화 + precheck 14→30일)로 잡은 것이 정확한 해결점 — 통합 불필요.
- **동명 DB 2벌 혼동 위험**(T4) — `data/stap_content.db`(5000)와 `STAP/data/stap_content.db`가 다른 내용. 최소한 주석/문서화로 구분 명시 권장. (실행 phase에서 결정)

## 검증 3분법 요약
- [검증됨] T1 3-venv 의존성 전수 대조 / T2 인터페이스 전 라인 독해 / T3 Phase 61 문서+커밋 근거 / T4 2벌 원장 실측+경로 코드.
- [부분검증] T3 최초 분리 동기(D-04는 유지 결정, 최초 이유는 미기록) / T2 TAP 내부 로직(계약만 확인).
- [검증불가] T1 과거 스냅샷 / T4 병합 실측(실행 안 함).

## 잔여 위험
- 본 조사는 읽기 전용 — 코드/DB/원장 미변경. tco G-B 관찰은 별도 진행선으로 무영향.
- 판정("통합 비추천")은 사용자 최종 결정 대상 — 본 문서는 근거 제공만.
- STAP 원장 2벌 상태가 지속되는 한 BUG-14류 가드 무력화 리스크 존재 — Task 9 완료 전까지 잔존.
