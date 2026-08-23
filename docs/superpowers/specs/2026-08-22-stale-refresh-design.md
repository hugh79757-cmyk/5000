# Stale check_results 일괄 갱신 설계 (DESIGN_ONLY)

> 상태: 설계안. 실행 금지 — 코드 구현/DB UPDATE는 별도 승인 후.
> 작성: 2026-08-22 (Exp1 Round 2 후속)

## 1. 목적

`check_results`에 잔존하는 stale `status=fail` 행(소스는 이미 반영됨)을
재검사 기반으로 일괄 갱신해 대시보드 정확도를 즉시 회복.

## 2. 배경 (Exp1 Round 1/2에서 확인된 stale 규모)

- FM-DRAFT 30블로그 중 실제 위반 1건(issue-techpawz), 나머지 29건은 소스에서 draft 이미 제거 → stale.
- FM-MISSINGKEYS 77블로그: 블록스타일 YAML 파서 버그(Exp2 수정 대상)로 인한 FALSE-POSITIVE — 본 갱신 대상 아님.
- 기타 위반(THUMBNAIL-01 10건 등)은 실제 위반일 가능성 높음 → 유지.

## 3. 범위

- 대상: `check_results` 전체 `status='fail'` 행.
- 제외:
  - FM-MISSINGKEYS (파서 버그 false-positive, Exp2까지 제외)
  - GATE_FILTERED(hotel/airport/restaurant) 블로그
  - PARSER_BUG_BLOGS(adventure-hugo 등 확정 false-positive)

## 4. 갱신 로직

```
1. SELECT status='fail' FROM check_results
     WHERE check_name NOT IN ('FM-MISSINGKEYS')
       AND blog_id NOT IN (PARSER_BUG_BLOGS)
       AND blog_id NOT LIKE '%hotel%' AND ... (GATE_FILTERED)
2. 행별 targeted_recheck(blog_id, post_path, check_name)  # READ_ONLY
   - post_path 부재 → check_results에 post_path 컬럼 없음 → site 열거 후 매칭
3. passed=True  → UPDATE 후보 목록에 추가 (status='pass' 예정)
4. passed=False → 유지 (실제 위반)
5. UPDATE 후보를 /tmp/stale_refresh_candidates.json 으로 출력
6. 실제 DB UPDATE는 --apply 플래그 명시 시에만 (별도 승인)
```

## 5. 안전장치 (safeguards)

- 배치 크기 제한: 50건/회 (대규모는 청크 분할)
- dry-run 기본: `--apply` 미지정 시 DB 갱신 0건, 후보 목록만 출력
- 갱신 전/후 카운트 보고 (before: N fail, after: M fail)
- 트랜잭션 래핑 + 실패 시 롤백
- FM-MISSINGKEYS 제외 (Exp2 parser 수정 후 별도 트라이지)
- 실행 전 라이브 스케줄러 정지 확인 (프로덕션 DB 기록 방지 — 파괴적 작업 규칙 준수)

## 6. 예상 영향

- stale 29건(FM-DRAFT) 즉시 소거 → 대시보드 위반 카운트 정확도 개선
- 추가 미확인 stale 건(다른 check_name)도 같은 로직으로 청소 가능
- FALSE-POSITIVE(FM-MISSINGKEYS)는 건드리지 않음 → 오히려 카운트 왜곡 유지 → Exp2 필수

## 7. 실행 승인 요건

- [ ] 라이브 스케줄러 정지 확인
- [ ] DB 백업 (content.db 아님, ops.db 백업)
- [ ] --apply 플래그 명시 실행 + before/after 카운트 보고
- [ ] 실행 후 재확인 쿼리

## 8. 연계

- Exp2: `content_integrity._parse_frontmatter` → python-frontmatter 채택 (격리 테스트 동반)
  → FM-MISSINGKEYS false-positive 근본 해결 후 해당 블로그 갱신 트리거.
- `ops_dashboard/exp1_selector.py` 의 stale/FP 가드를 본 갱신 배치에 재사용 권장.
