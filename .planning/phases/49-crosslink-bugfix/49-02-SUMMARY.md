# 49-02 SUMMARY — Batch Fix (Wave 2)

**Phase:** 49-crosslink-bugfix | **Plan:** 49-02 | **Wave:** 2 (depends on 49-01)
**Commit:** `1b249d615` — `feat(49-crosslink-bugfix): batch-fix wrong-slug entities and baked cross-link hrefs`
**Executed:** 2026-07-26 | **Verified:** 2026-08-01 (이 세션 재검증 + 잔여 정리)

---

## 목표

Wave 1은 신규 발행 방지. Wave 2는 기존에 bake된 잘못된 크로스링크와
`cuap_entities` DB의 잘못된 slug를 일괄 수정.

## 변경 내용

| 파일 | 역할 |
|------|------|
| `scripts/fix_cuap_entity_slugs.py` (신규, 125줄) | date-prefixed(`YYYYMMDD-{keyword}`) 잘못된 slug 엔티티 삭제 — `--dry-run` 지원 |
| `scripts/fix_baked_crosslink_cards.py` (신규, 310줄) | content/posts/*/index.md의 bake된 크로스링크 href 일괄 수정 — `ensure_entity_exists()` 3-tier (DB query → on-disk 검색 → 최신 엔티티 fallback), /tmp 백업, `--dry-run` 지원 |

**Wave 2 실행 결과 (커밋 메시지 기준):**
- `cuap_entities`에서 잘못된 slug 엔티티 **14건 삭제** (9개 블로그)
- bake된 크로스링크 href **143건 수정** (38개 파일 / 10개 블로그)

**추가 49-B (커밋 `045ff37d1`, 2026-07-26):**
- `scripts/scan_all_crosslinks.py` (384줄) — 전수 스캔: 3,076개 포스트, 9,840개 크로스링크
- `scripts/fix_remaining_crosslinks.py` (379줄) — 잔여 404 수정: 70건(일반) + 15건(trailing-slash 버그) = **85건**
- 최종: **9,840/9,840 정상 (0건 404)**, Hugo 빌드 10/10 블로그 0 에러

## 검증 결과 (2026-08-01 이 세션 재검증)

### [검증됨]

- `fix_cuap_entity_slugs.py --dry-run` 실행 → published=1 잘못된 slug **0건**
  (기존 14건 삭제가 유효함을 확인). 근거: DRY-RUN Summary total 0/0.
- health 블로그 콜레스테롤 포스트 4개 크로스링크 모두 **on-disk 실제 포스트와 일치**:
  - fitness `푸시업바-고민-아이언빅-방탄손목과-stam-멀티보드-실사용-느낌` → exists
  - kitchen `doma-recommend-heunhan-ohae-3gaji-2026-gijun-balojabgi` → exists
  - baby `jeojbyeong-geonjodae-recommend-mam-aenliteulbebepeullo-u-yug-a-choboleul-wihan-practical-seontaeg` → exists (CONTEXT.md의 올바른 URL 예시와 일치)
  - beauty `핸드크림-추천-엠디스픽-드-바리스타-vs-헤트라스-퍼퓸-에센스-여름철-손-보호-필수템` → exists
  근거: `ls -d /Users/twinssn/Projects/CUAP/{blog}/content/posts/{slug}` 모두 존재.
- 두 스크립트 모두 Python 문법 유효 (`ast.parse`).
- /tmp 롤백 백업 존재: `/tmp/fix_baked_crosslink_cards_before/`, `/tmp/crosslink_fix_backup/`.
- 백업은 `--dry-run` + /tmp 백업 방식이라 Hugo 빌드 방해 파일(.bak) 없음.

### [부분검증]

- 5+ 블로그 최신 포스트 검증: SCAN-REPORT(07-26)가 10개 블로그 전수 스캔
  (9,840/9,840)을 기록 — 파일시스템 ground truth 기반. 이 세션은 10개 블로그
  전수 재스캔을 재실행하지 않았고 대표 포스트(콜레스테롤)만 재검증.
- Hugo 빌드 0 에러: SCAN-REPORT가 10/10 기록(07-26). 이 세션은 빌드 재실행하지 않음.

### [검증불가] — 라이브 HTTP 200 (이 세션)

- 라이브 서버 200/404는 이 세션에서 curl로 확인하지 않음. 07-26 SCAN-REPORT가
  파일시스템 기반 정상률 100% 기록. 복구 계획: 배포 후 `curl -sIL` 4개 대상 URL 확인.

## 이 세션 추가 정리 (2026-08-01)

Wave 2 스크립트는 `published=1` 행만 대상 — **`published=0` 잘못된 slug 10건이 잔존**함을 발견.

- 대상: appliance/interior/beauty/camping(5)/health/laptop — `20260723~20260726-{keyword}` 형식,
  on-disk에 존재하지 않는 phantom 엔티티 (파이프라인은 `published=1`로만 등록하므로 pre-fix 잔재).
- 조치: 삭제 전 JSON 백업(`/tmp/cuap_stale_rows_backup_20260801-191632.json`, 10행) 후 DELETE.
- 결과: `cuap_entities` 474 → 464행. 남은 `2026%` prefix 행 5건은 모두 `published=1` +
  on-disk 실제 slug (`2026년-7월-...` 타이틀 유래) — **정상**.
- plan 성공 기준 "0 wrong slugs" 충족.

## 잔존 위험

- **라이브 재확인 필요**: 다음 배포 주기에서 콜레스테롤 포스트 4개 URL + 5개 블로그
  최신 포스트에 `curl -sIL`로 200 확인 권장 (이 세션은 파일시스템 검증만 수행).
- **"가정용 추천" 같은 모호한 link label**은 여러 포스트에 매칭 가능 — 현재 최신 post로
  연결되어 기능상 문제 없음 (SCAN-REPORT 동일 평가).
- **신규 발행 시 재발 방지는 Wave 1에 의존** — Wave 1 코드가 커밋되어 있어 방지됨.
- **uncommitted working tree**: 현재 브랜치에 phase-49 무관 변경 다수 존재.
  phase-49 관련 파일 자체는 커밋 상태와 일치.
