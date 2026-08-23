# WL-20260823 — HARVESTER_FULL_INTEGRATION 커밋 + 스케줄러 재기동

## 작업 단위
- 커밋: `90fb025f6` feat: keyword_harvester full integration (10 files, 755+/5-)
- 파괴적 작업: launchd scheduler unload/load (PID 99774 → 15626)

## 4단계 프로토콜 이행
1. **사전**: 대상 diff 전수 확인, 테스트 19/19 PASS 직후 커밋
2. **백업**: git 히스토리 자체(커밋), plist 재로드로 스케줄러 즉시 복구 가능
3. **실행**: git add(사용자 지정 10파일) → commit → launchctl unload+load
4. **사후 대조**:
   - 커밋 stat 출력 확인 (10 files changed)
   - 신규 PID 15626 단일 프로세스 확인
   - job 등록 검증: `.venv/bin/python -c "scheduler.register_schedules(); ..."` → `HARVEST_JOBS: ['_run_cuap_harvest@03:00:00']`

## 보존 확인
- KEYWORD_MAP fallback 유지 (get_keywords pool-first, 실패 시 fallback)
- auto_collector.py 수정 없음
- 실발행 행(content.db) 미건드림 — DB 쓰기 작업 없음

## 혼입 명시 (커밋에 포함된 타 작업 변경)
- keywords.py: KEYWORD_MAP "2026-08-22 소진 대응 확장" (homeappliance/golf 등 키워드 추가)
- pipeline.py: CATEGORY_FILTERS allowed 확장 + `_run_inner` publish_error 사유 전파
- 사용자가 파일 리스트를 지정하여 전체 커밋 지시 → 그대로 포함됨

## 잔존 위험
- /var/log/harvest.log ≠ 실제 경로 `/var/log/harvest_YYYYMMDD.log` (run_harvest LOG_DIR 패턴) — 내일 검증 시 날짜 붙은 파일 확인할 것
- /tmp/5000-scheduler.log의 "scheduled" 라인은 키워드 필터 print로 묻힘 — job 등록은 별도 스크립트로 검증 완료
- conftest ops.db 가드 순서 결함(사전 존재) 미수정 — OPS_TEST_MODE=1 필요
- tests/curation 사전 존재 실패 18건 — 타 작업 영역

## 사고 후속 (2026-08-23 07:00+07)
- 첫 실행(현지 03:00) 미발화 원인: run_harvest logging.basicConfig가 /var/log/harvest_YYYYMMDD.log FileHandler 생성 시 PermissionError(/var/log root:wheel 755) → harvest 본체 진행 전 예외 → keyword_pool/api_call_log 흔적 없음. 스케줄러 루프 자체는 정상(/usr/bin/sample로 sleep 대기 확인, 수집기 :50 정상 — api_call_log는 UTC 저장이라 이전 판단 수정).
- 픽스: commit 8ef2ef083 — LOG_DIR FileHandler OSError 시 프로젝트 logs/ 폴백. mock E2E로 폴백 파일 생성 + api_call_log 1:1 기록 검증(19/19 테스트 유지).
- 다음 실전 발화: 현지 03:00 (=KST 04:00, 윈도우 내). 아침 체크 경로 변경: logs/harvest_YYYYMMDD.log (프로젝트 루트).
