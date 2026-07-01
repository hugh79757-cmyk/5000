# Phase 10: Blowfish Engagement Optimization — tour1.rotcha.kr

## 배경

**목표:** Blowfish 테마 shortcode를 활용한 체류시간 및 재방문율 개선

**대상:** tour1.rotcha.kr (캠핑·아웃도어, travel-hugo)
- 캠핑 데이터는 구조화 숫자 데이터(site 수, 화장실 수 등)와 시설 정보(sbrsCl)가 가장 풍부한 소스
- 단일 블로그 집중 → 빠른 출시 → 효과 측정 후 확산

**비대상:**
- travel1/2/4-hugo, STAP, rap 블로그 — Phase 10 이후 별도 고려
- 날씨 API 연동 — 제외 (발행 후 업데이트 문제)
- 기존 발행 글 수정 — 신규 발행 글에만 적용

## 데이터 감사 결과

| 소스 | 다중 이미지 | 구조화 숫자 | 시설 목록 | 기간/순서 |
|------|-----------|-----------|----------|---------|
| 캠핑(GoCamping) | ❌ 1장 | ✅ 사이트/화장실 수 | ✅ sbrsCl 15종 | ⚠️ 계절 |
| 관광지(TourAPI) | ❌ 1장 | ❌ 없음 | ❌ detailIntro2 필요 | ❌ |
| 음식점(TourAPI) | ❌ 1장 | ❌ 없음 | ❌ detailIntro2 필요 | ❌ |
| 축제 | ❌ 1장 | ❌ | ❌ | ✅ 일정 |
| 코스 | ✅ 하위장소多 | ❌ | ❌ | ✅ subnum |

**핵심 발견:** `detailImage2` API 1회 추가로 전 소스 다중 이미지 확보 가능. 하지만 Phase 10은 캠핑만 대상이므로 GoCamping API에서 제공하는 `firstImageUrl`의 추가 이미지 활용 방안 확인 필요.

## Blowfish Shortcode 검증 결과

Hugo 빌드(`v0.160.1`)로 6종 shortcode 렌더링 확인 완료:
- `lead`, `alert`, `figure`, `gallery`, `accordion`, `timeline`
- `_clean_body()` 정규식(`\{\{(?![<%])[^}]+\}\}`)이 `{{< ... >}}` 보존 확인

## 결정 사항

1. **적용 블로그:** tour1.rotcha.kr (travel-hugo) 단일
2. **shortcode 7종:** lead, figure, alert, badge, gallery, accordion, chart
3. **날씨 연동:** 제외
4. **신규 글만 적용:** 기존 글 수정 안 함
5. **적용 방식:** AI 프롬프트 직접 생성 + Hugo writer post-processing 혼합
6. **chart:** 캠핑 site 수 데이터로 레이더/막대 차트 구현 (AI가 아닌 post-processor에서 Chart.js config 생성)
7. **gallery:** detailImage2 또는 GoCamping 추가 이미지 활용 방안 확인 필요

## 우선순위

| Priority | Shortcode | 방식 | 예상 효과 |
|----------|-----------|------|----------|
| P0 | lead | 첫 문단 auto-wrap | 가독성 |
| P0 | figure | caption 이미지 | 시인성 |
| P1 | alert | 반려동물/시설 팁 | 시선 유도 |
| P1 | badge | 캠핑장 유형 표시 | 정보성 |
| P2 | gallery | 다중 이미지 | 이미지 소비 |
| P2 | accordion | 시설 FAQ | 정보 탐색 |
| P3 | chart | 사이트/편의시설 비교 차트 | 체류시간 ⬆ |
