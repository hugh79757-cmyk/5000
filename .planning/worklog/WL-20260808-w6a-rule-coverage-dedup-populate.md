# WL-20260808-w6a-rule-coverage-dedup-populate

> 날짜: 2026-08-08 / 연관: Phase 69 W6a.1(dedup)+W6a.2(populate) / 상태: 진행중(커밋 대기)

## 파괴적 작업 목록

| 시각 | 작업 | 명령/스크립트 | 사전카운트 | 백업 | 사후대조 | 보존확인 |
|------|------|--------------|-----------|------|---------|----------|
| 19:50 | W6a.1 ops-dashboard 재시작(dedup 코드 배포) | launchctl kickstart -k com.5000.ops-dashboard | PID 36588 | ops.db.bak_coverage_20260808 | PID 77885 | readiness 200 |
| 19:51 | W6a.2 활성 23블로그 populate(R 개별행 + aggregate) | python -c "check_standard_compliance(active)" | rule_id 행 1 | ops.db.bak_populate_20260808 | rule_id 행 34 | aggregate 715→738(추가), excluded 69 유지 |

## 4단계 프로토콜 이행
1. 사전 카운트: rule_id 개별행 1(pet-hugo/R06), check_results 4392.
2. 되돌림 수단: `ops_dashboard/ops.db.bak_coverage_20260808`, `ops_dashboard/ops.db.bak_populate_20260808`, tags `pre-coverage-expand-2026-08-08`, `pre-w6a2-populate-2026-08-08`.
3. 실행: W6a.1 dedup 병합 코드 배포(dashboard 재시작) → W6a.2 활성 블로그만 populate.
4. 사후 대조: 총량 236→234(낡은 08-06 실패 2건 교정), excluded 69 유지, standard_compliance 21→19, 구조필드 커버리지 standard_compliance 100%(fallback 0).

## 결과 / 보존 대상 확인
- aggregate(rule_id NULL) standard_compliance: 715→738 (+23 = 활성 블로그 재기록, append만, 기존 detail 무변경).
- excluded: 69 유지 (비활성 블로그 개별행 미생성 필터 적용).
- content.db: 무변경 (auto_triage는 SYNC_DB_PATH 미기록).
- 알림(telegram log): 15:56 유지 (dry-run 발송 없음).

## W6-b 추가 (같은 날, 19:56~19:58)
| 시각 | 작업 | 명령 | 사전카운트 | 백업 | 사후대조 | 보존확인 |
|------|------|------|-----------|------|---------|----------|
| 19:56 | W6-b standard 폴백 가드(auto_triage._resolve_problem_id) | dry-run | standard fallback trace n/a | ops.db.bak_w6b_20260808 + tag pre-w6b-fallback-remove | trace 0, 총량 234, 분포 diff 0 | excluded 69, telegram/content.db 무변경 |

- **제거 범위**: standard_compliance(R01-R12) 계열에 한해 `_pattern_to_problem_id`/`_check_name_to_problem_id` 자유텍스트 폴백 호출을 차단 → 구조필드(problem_id/rule_id→registry_map) 단일 경로. 구조해석 실패 시 unknown_failure 노출 + `_FALLBACK_TRACE_STD` 기록.
- **유지**: R01-R12 밖 12건(maintenance_checklist 6, crosslink_consistency 3, freshness 2, render_health 1)은 여전히 `_check_name_to_problem_id` 폴백으로 분류.
- **검증**: standard fallback trace 0, standard_compliance 19건 전부 구조필드, 총량 234 유지, 분포 diff 0, 게이트 5/5.
- 변경 파일: `scripts/auto_triage.py` (+21/-4).

## 커밋 정리 (3 자립 커밋, W6a.1 위에)
| 커밋 | 해시 | 포함 |
|------|------|------|
| feat(registry) | 2efce05e2 | registry/__init__.py·errors.py·schema.py(추적 추가) + db.py H6(record_check_rule/replace_triage_classifications/get_registry_view) |
| fix(standard) | 75ec202ed | standard.py W6a.2 활성 필터 + _record_failed_rules |
| fix(auto_triage) | d9efed829 | auto_triage.py W6-b 폴백 가드(_FALLBACK_TRACE_STD) |

- 각 커밋 후 import/파싱 검증: 2efce05e2(registry+record_check_rule import OK), 75ec202ed(standard import OK), d9efed829(auto_triage import OK).
- 커밋 후 최종 dry-run: EXIT=0, 총량 234, standard_compliance 19, excluded 69, W6-b fallback trace 0.
- W5-era db.py H1/H2/H3 스키마 hunk는 미커밋 보존 (git diff에서 확인, _alter_columns/init_db/notification_debounce).
- ahead: 63→67 (+4 = W6a.1 + 3 커밋).

## 잔존 위험
- W5-era db.py 스키마(H1/H2/H3) + dispatcher/app/curation/backfill/deploy 수정 파일은 여전히 미커밋 — 다음 파동에서 별도 처리.
- .DS_Store, .continue-here.md, force_draft/is_draft 관련 파일은 스테이지 제외 유지.
- 낡은 aggregate 행(08-06 이전)은 잔존 — 다음 재스캔에서 교정되지만, 지금 기준으로는 과거 데이터가 남아 있음.
- `_FALLBACK_TRACE_STD`는 프로세스 수명 동안만 누적 — 새 프로세스에서 재검증 필요.
