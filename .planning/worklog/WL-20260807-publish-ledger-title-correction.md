# WL-20260807-publish-ledger-title-correction

> 날짜: 2026-08-07 / 연관: Phase 67 조사 (publish_ledger ↔ curation.db title 불일치) / 상태: 완료 (DB 보정 + 코드 수정)

## 배경

8/7 새벽(00:19~01:04) CUAP 확대 발행 16건 중 5건(laptop/appliance/baby/interior/fitness-hugo)의
`publish_ledger` title이 curation.db publish_log(2177~2181)와 불일치.

**판정 (A/B): B — 라이브 오염 없음. DB 기록 매핑 문제.**
- 라이브 파일 5건 전부 curation.db와 정합 (front-matter title/slug 확인)
- ledger의 잘못된 title = `content.db articles`의 3~4월 옛 레코드 복사본
  (57823 published_url = articles rowid 6063의 published_url과 문자열 완전 일치)
- 원인: `dispatcher.py:_record_ledger` else 분기가 CUAP 블로그도 먼저
  `content.db articles WHERE blog_id=? AND status='published' ORDER BY rowid DESC LIMIT 1`을
  조회 → 불일치 5건 blog_id에는 옛 레코드 존재(laptop 27, appliance 61, baby 60, interior 56, fitness 47개)
  → 조회 성공 → `if not title and not url`(CUAP curation.db 조회) 건너뜀.
  일치 10건 blog_id는 articles 레코드 0개 → CUAP branch 정상 동작.

## 파괴적 작업 목록

| 시각 | 작업 | 명령/스크립트 | 사전카운트 | 백업 | 사후대조 | 보존확인 |
|------|------|--------------|-----------|------|---------|----------|
| 23:51 | publish_ledger 5건 title/published_url/source_id 보정 | sqlite3 UPDATE (id 57823/57824/57826/57827/57828) | 5 UPDATE (DELETE 0, INSERT 0) | data/content.db.bak_20260807_2348 (43MB) | 5건 curation.db 2177~2181 title+slug+source_id=blog_id 일치, 행수 33743 불변 | source='' 실발행 행 18334건 유지 (group by diff 일치) |

## 4단계 프로토콜 이행

1. 사전 카운트: publish_ledger 5건 UPDATE (id 57823, 57824, 57826, 57827, 57828), DELETE/INSERT 없음.
   보정값: curation.db publish_log 2177~2181의 title/slug + source_id=blog_id.
2. 되돌림 수단: `data/content.db.bak_20260807_2348` (43MB, 업데이트 전 복사, 무결성 확인 33743/3845).
   라이브 스케줄러 정지 확인: heartbeat 1786023621 (8/6 20:40 정지), scheduler.py 프로세스 없음.
3. 실행: sqlite3 UPDATE 5건 → "UPDATE 완료".
4. 사후 대조: 보정 5건 curation.db와 title/slug/source_id 전부 일치. publish_ledger 행수 33743 (불변).
   source 컬럼 분포를 백업과 diff → 완전 일치. source='' 18334건 유지.

## 보정값 상세

| ledger id | blog_id | 보정 title | published_url (slug) | source_id |
|-----------|---------|-----------|----------------------|-----------|
| 57823 | laptop-hugo | 고사양 게임을 위한 가성비 게이밍노트북 핵심 비교 분석 | 20260807-게이밍노트북 | laptop-hugo |
| 57824 | appliance-hugo | 직수형 정수기 렌탈 전 꼭 확인해야 할 필터 성능 비교 | 20260807-정수기 | appliance-hugo |
| 57826 | baby-hugo | 안전한 자기주도 이유식 시작을 위한 유아식기 소재별 특징 비교 | 20260807-유아식기 | baby-hugo |
| 57827 | interior-hugo | 허리 편한 매트리스 고르는 기준과 침대 프레임 비교 | 20260807-침대 | interior-hugo |
| 57828 | fitness-hugo | 뱃살 빼기에 효과적인 다이어트 훌라후프 고르는 팁 | 20260807-훌라후프 | fitness-hugo |

## 결과 / 보존 대상 확인

- publish_ledger source='' 실발행 행: 18,334건 before/after 유지 (백업 group-by diff 일치).
- 전체 행수: 33,743 → 33,743.
- 라이브 콘텐츠/파일: 수정 없음 (읽기 전용 확인만).

## 코드 수정 (dispatcher.py `_record_ledger`)

- **변경 내용**: else 분기(non-ETAP)에서 curation pipeline 블로그는 `content.db articles`
  조회를 건너뛰고, 기존 CUAP 분기(`if not title and not url` → curation.db publish_log
  최신 건)로 흐르게 함. `_load_all_blogs()`의 해당 blog_id `pipeline == "curation"` 판별로 분기.
- **동작 변화**: curation 블로그는 항상 curation.db에서 정확한 최신 title/slug를 기록
  (source_id=blog_id). 비-curation 블로그(STAP/CAP/RAP/travel/ETAP/기타 articles 사용)는
  기존 로직 그대로.
- **검증**:
  - 드라이런(실제 DB, INSERT 없이 조회 로직만 재현): curation 5건 → curation.db 정확한
    title/slug/source_id, rap-hugo → articles 기존 동작 유지.
  - 문법: `ast.parse` OK.
  - 회귀: `tests/test_dispatcher_registry.py` 1 passed. 실패 21건(curation 17 + shared 4)은
    **내 변경 전후 동일 실패 집합** (stash 원복 후 재실행으로 확인) — 사전 존재 실패,
    본 변경과 무관.
- **참고**: dispatcher.py에 이전 세션(Phase 66-C)의 `force_draft → --buildDrafts` 변경과
  pipelines/curation/pipeline.py, scripts/backfill_cuap_entities.py, shared/cuap_entity_linker.py,
  shared/publishers/deploy.py 변경이 이미 워킹트리에 존재 — 본 작업에서 건드리지 않음.

## 잔존 위험

- `content.db articles`의 3~4월 옛 레코드(laptop 27, appliance 61, baby 60, interior 56, fitness 47개)가
  미정리 상태로 남아 있음. `_record_ledger` 수정으로 재발은 방지됐으나, 해당 레코드가
  다른 경로(ledger_sync 등)에서 참조될 수 있어 정리 여부는 별도 결정 필요.
- 과거 133건(source='' + published_url 있는 laptop-hugo 기록)도 동일 오염 패턴일 수 있으나
  이번 범위(57814~57834) 밖 — 별도 점검 대상.
- 사전 존재 테스트 실패 21건은 본 변경과 무관하나 미해결 상태.

## 참조

- 조사 상세: (Phase 67 대화 세션) — 불일치 5건 라이브 실물 front-matter, articles 옛 레코드 대조
- 로그: `logs/destructive_2026-08-07.log`
