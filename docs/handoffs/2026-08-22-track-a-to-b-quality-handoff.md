# Track A → Track B Quality Data Handoff

> 상태: DRAFT (2026-08-22). Track A §11 산출물을 Track B Phase 0 공식 입력으로 연결.
> 출처: docs/superpowers/specs/2026-08-22-section7-final-amendment.md §11
> 제약: READ_ONLY 산출. 코드/DB 변경 없음. 본 문서는 핸드오프 계약 명세.

## 1. Available Metrics (§11 13지표 매핑)

| # | 지표 | 데이터 소스 (현재) | 현재 값 | Track B 활용 목적 |
|---|------|------------------|---------|------------------|
| 1 | wordCount (하한 400 / 목표 900~1400) | design spec (quality_guard) | DB 미물질화 → proxy: content_quality 55 fail | baseline 분포 정의, 개선 전후 길이 추이 |
| 2 | H2_count (≥3) | design spec | 미물질화 | 구조 충족율 측정 |
| 3 | structure_blocks (요약+비교≥5+FAQ3+H2 4고정) | design spec | 미물질화 | 구조 블록 4종 충족율 |
| 4 | item_detail_length (H3 120~180단어) | design spec | 미물질화 | 항목 상세도 밀도 |
| 5 | cta_count_position (2개, 교차금지) | design spec | 미물질화 | CTA 규칙 준수율 |
| 6 | ad_slots (2슬롯, 상단300px 금지) | design spec | 미물질화 | 광고 규칙 준수율 |
| 7 | internal_link_density (동도메인 우선) | design spec | 미물질화 | 내부링크 밀도 |
| 8 | trust_signals (author/출처/갱신일) | design spec | 미물질화 | 신뢰신호 충족율 |
| 9 | affiliate_disclosure (rel sponsored) | design spec | 미물질화 | 제휴고지 준수율 |
| 10 | adsense_render (adsbygoogle 1회) | design spec | 미물질화 | AdSense 렌더 정상율 |
| 11 | stage1_pass (c08 게이트) | check_results check_name=c08* | c08_live_file_mismatch 85 fail | Stage1 PASS율 |
| 12 | zero_hallucination | design spec (S0 CRITICAL) | 미물질화 | 허위 0 유지 |
| 13 | no_duplicate_prose | design spec | 미물질화 | 중복 산문 0 유지 |

> **핵심**: §11 13지표는 설계 spec (design doc가 source of truth). check_results에는
> 직접 컬럼으로 존재하지 않음. Track B가 이를 정량 수집하려면 별도 수집기(§11 metrics
> collector) 신규 구현 필요 — 본 핸드오프는 "입력 계약"만 정의. 현재 가용 proxy:
> `check_results` fail 분포 (TOTAL 2003 / fail 637), 특히 `content_quality` 55 fail,
> `c08_*` 85 fail, `FM-*` 71 fail 등이 구조/메타 품질 proxy.

## 2. content_quality Checker 구조

- 등록: `register_check('content_quality')`, 함수 `check_content_quality(conn, blog_id) -> {status, detail, evidence_url}`
- 분석: `_analyze(html)` → 8개 결함코드
  - `CQ01` 빈 불릿(라벨만) / 빈 리스트 항목
  - `CQ02` CTA가 리스트 항목에 갇힘
  - `CQ03` 제휴문구 누락(n==0) / 과다(n>2)
  - `CQ04` 상품별 상세 비교가 h2 아님
  - `CQ05` 상품/썸네일 이미지 없음 / 부족
  - `CQ07` 상품 설명 문단 소실(CJK 0자)
  - `CQ08` 상품 이미지 중복(상품당 >1장)
- 출력 형식: `detail = "구조 결함: [CQ05] ..., [CQ03] ..."` / 통과 시 `"발행 글 구조 정상(...)"`
- `evidence_url` = 해당 블로그 **최신 1건** post URL
- **제한**: 블로그당 **최신 1개 포스트만** 검사 (sitemap/posts). 과거 포스트는 미검사.
- 가용성: 현재 `check_results`에 `content_quality` fail **55건** → 55개 블로그 목록 + 결함유형 확보 가능.
- Track B 입력 형태: `SELECT check_name, blog_id, detail FROM check_results WHERE check_name='content_quality' AND status='fail'` → 블로그별 CQ 코드 파싱.

## 3. Data Gaps (Track B §1~§4 미제공)

| 누락 데이터 | Track B 필요 근거 | 방안 |
|------------|------------------|------|
| content_id / revision 추적 | 변경 전후 동일 콘텐츠 식별 | Track B 독자 구현 (slug+hash) — Track A 확장 불필요 |
| change_set / deploy ledger | 개선 적용 이력 | Track B 독자 구현 또는 fix_history sidecar 재활용 |
| observation snapshot | pre/post 효과 측정 | Track B 독자 구현 (DB sidecar 또는 json) |
| 전수 포스트 품질 (최신 1건만 가용) | 대표 포스트 선정 정밀도 | content_quality.py 확장(전수) 또는 샘플링 — 별도 작업 |

> 결론: Track B는 Track A에 강하게 의존하지 않음. check_results(read) + git history +
> 자체 sidecar로 §1~§4 구현 가능 (우회 방안 채택).

## 4. Handoff Contract (Track B → Track A 의존 인터페이스)

```text
READ:
  SELECT * FROM check_results
    WHERE check_name = 'content_quality'        # §11 proxy 품질 피드
    AND status = 'fail';
  schema_loader.load_schema(blog_id)            # 블로그 스키마/필수 frontmatter
  targeted_recheck(blog_id, post_path, check_name)  # 품질 재평가(Exp1 안전망)

변경 통지 규칙:
  - §11 지표 추가/임계값 변경 시: design doc 커밋 + Track B 담당자 알림
  - check_results 스키마 변경 시: 마이그레이션 + 호환 컬럼 유지
  - content_quality 결함코드(CQ0x) 추가 시: 코드표 공유 (본 문서 §2 갱신)
```

> 버전: §11은 design doc 기반, `version: absent` (Section 7 g5_stance). 변경은 커밋 로그로 추적.
