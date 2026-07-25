# Phase 44 Plan — 전수조사 및 전체 수정

**Phase**: 44 — 6개 블로그 전체 최종 품질 점검  
**Strategy**: 대표님 5번 항목 — 블로거1 + 휴고5(캠핑/축제/문화유산/맛집/코스) 전수조사 → 수정 → 검증  
**Priority**: 🟡 MEDIUM

---

## 44-01: 최종 품질 기준 체크리스트 정의

**Task**: Phase 40~43에서 확립된 품질 기준을 종합해 최종 체크리스트 작성

### Deliverables:
- [ ] `config/quality_checklist.yaml` 생성 — 통합 품질 기준 문서
- [ ] Phase 40~43 검증 기준 통합 (데이터 활용, 환각 없음, 빈값 미언급, 주제 적합성, 이동시간 필터링, 타이틀-본문 일관성, 구조 일관성)
- [ ] 블로그별 특화 기준 추가 (축제=일정/위치, 문화유산=시대/종목, 맛집=메뉴/가격, 코스=경로/소요시간, 캠핑=시설/장비)
- [ ] 자동화 검증 스크립트 설계 (`scripts/verify_quality.py` 골격)

### Acceptance Criteria:
- ✅ 체크리스트가 Phase 40~43 모든 검증 기준을 포함
- ✅ 블로그별 특화 기준 5개 이상 정의
- ✅ 자동화 검증 가능하도록 정량적 지표화 (임계값 포함)

### Verification:
```bash
# 체크리스트 파일 존재 및 내용 확인
cat /Users/twinssn/Projects/5000/config/quality_checklist.yaml
```

---

## 44-02: 6개 블로그 전체 전수 점검

**Task**: 6개 블로그(블로거1 + 휴고5) 전체 포스트에 대해 품질 체크리스트 적용

### Deliverables:
- [ ] `scripts/verify_quality.py` 구현 — 체크리스트 기반 자동 검증
- [ ] 각 블로그별 `content/posts/` 전체 포스트 스캔
- [ ] 검증 결과 리포트 생성: `phase-44-full-audit/QUALITY-AUDIT-REPORT.md`
- [ ] 미달 포스트 목록 추출 (PASS/FAIL/NEEDS_REVIEW 분류)

### Target Blogs:
| 블로그 | 타입 | 경로 |
|--------|------|------|
| blogger1 | 블로거 | `/Users/twinssn/Projects/5000/...` |
| travel-hugo | 캠핑 | `/Users/twinssn/Projects/CUAP/camping-hugo/content/posts/` |
| travel1-hugo | 축제 | `/Users/twinssn/Projects/CUAP/travel1-hugo/content/posts/` |
| travel2-hugo | 문화유산 | `/Users/twinssn/Projects/CUAP/travel2-hugo/content/posts/` |
| travel3-hugo | 맛집 | `/Users/twinssn/Projects/CUAP/travel3-hugo/content/posts/` |
| travel4-hugo | 여행코스 | `/Users/twinssn/Projects/CUAP/travel4-hugo/content/posts/` |

### Acceptance Criteria:
- ✅ 6개 블로그 전체 포스트 검증 완료
- ✅ PASS/FAIL/NEEDS_REVIEW 분류된 리스트 생성
- ✅ 전체 PASS율 ≥ 90% 또는 미달 항목 명확히 식별

### Verification:
```bash
# 자동 검증 실행
cd /Users/twinssn/Projects/5000
python3 scripts/verify_quality.py --all-blogs --output phase-44-full-audit/QUALITY-AUDIT-REPORT.md
```

---

## 44-03: 신규 발행 기준 통과 확인

**Task**: 개선된 파이프라인으로 신규 발행 시 품질 기준 통과하는지 검증 (dry-run)

### Deliverables:
- [ ] 각 블로그별 dry-run 3회 실행 (신규 데이터로)
- [ ] 생성된 콘텐츠가 품질 체크리스트 100% 통과 확인
- [ ] 타이틀 생성 성공률 100% 확인
- [ ] 본문 길이 ≥ 2,500자 확인
- [ ] 블로그별 특화 검증 통과 확인

### Acceptance Criteria:
- ✅ 6개 블로그 모두 dry-run 3/3 성공
- ✅ 품질 체크리스트 100% PASS (자동 검증)
- ✅ 타이틀 생성 100% 성공 (fallback 0회)
- ✅ Phase 40~43 개선사항 유지 확인

### Verification:
```bash
# 각 블로그 dry-run 실행
for blog in travel-hugo travel1-hugo travel2-hugo travel3-hugo travel4-hugo blogger1; do
  python3 -c "
import sys; sys.path.insert(0,'/Users/twinssn/Projects/5000')
from pipelines.travel.fetcher import fetch_${blog_type}
from pipelines.travel.writer import generate_content
d = fetch_${blog_type}()
r = generate_content(d, blog_id='${blog}')
print(f'${blog}: title={len(r.get(\"title\",\"\"))}, body={len(r.get(\"body_md\",\"\"))}')
"
done
```

---

## 44-04: 미달 항목 최종 수정

**Task**: 전수조사 및 dry-run에서 발견된 미달 항목 수정

### Deliverables:
- [ ] FAIL/NEEDS_REVIEW 분류된 포스트 개별 분석
- [ ] 공통 패턴 발견 시 프롬프트/파이프라인 레벨 수정
- [ ] 개별 포스트 수정 필요 시 재생성 또는 수동 보정
- [ ] 수정 후 재검증으로 PASS 전환 확인

### Acceptance Criteria:
- ✅ 모든 미달 항목 해결 (PASS율 100% 달성)
- ✅ 수정 사항이 파이프라인 레벨에 반영되어 재발 방지
- ✅ 회귀 없음 (이미 PASS였던 항목 유지)

---

## 44-05: 마무리 및 커밋

**Task**: Phase 44 완료 문서화 및 커밋

### Deliverables:
- [ ] `PHASE44-COMPLETION-REPORT.md` 작성
- [ ] `VERIFICATION-PHASE44.md` 작성
- [ ] `SUMMARY.md` 업데이트
- [ ] ROADMAP.md Phase 44 완료 상태 반영
- [ ] 관련 파일 커밋

### Acceptance Criteria:
- ✅ 모든 산출물 문서화 완료
- ✅ 품질 기준 100% 달성 입증
- ✅ 다음 단계(Phase 18+) 진행 가능 상태

---

## Execution Strategy

**순차 진행**: 44-01 → 44-02 → 44-03 → 44-04 → 44-05  
**리스크 관리**: 44-02 전수조사 결과에 따라 44-03~04 범위 조정  
**자동화 우선**: 수동 검증 최소화, 스크립트 기반 검증 확대

---

## Key Links

```yaml
key_links:
  - from: config/quality_checklist.yaml
    to: scripts/verify_quality.py
    via: "품질 기준 → 자동 검증 스크립트"
  - from: Phase 40~43 검증 결과
    to: 44-01 체크리스트
    via: "기존 기준 통합"
  - from: CUAP 블로그 5개 + 블로거1
    to: 44-02 전수조사 대상
    via: "6개 블로그 전체"
```

---

## Pattern References

- **Quality Validation**: References `shared/content_validator.py` pattern from Phase 40
- **Content Verification**: References `detect_problematic_posts.py --scan-body` from Phase 16
- **Blog Pipeline**: References `pipelines/travel/writer.py` for dry-run generation
- **Checklist Format**: YAML with quantitative thresholds for automation

---

## Verification

**gsd-plan-checker** 검증 항목:
- [ ] 각 task가 명확한 deliverables와 acceptance criteria를 가짐
- [ ] 6개 블로그 전체 커버리지 확보
- [ ] 자동화 검증 스크립트 설계 포함
- [ ] Phase 40~43 개선사항 회귀 방지 명시
- [ ] 완료 기준이 측정 가능함 (PASS율 100%)

---

**Plan 생성**: 2026-07-25  
**상태**: Ready for execution