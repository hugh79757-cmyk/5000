# Phase 10 개선 제안

**작성:** 2026-07-01 (1차 배포 후 사용자 피드백 기반)
**상태:** 제안 단계, 미구현

---

## 1. Accordion 적용 범위 축소

### 문제
현재 `_apply_accordion_shortcode()`가 `체크포인트`, `준비사항`, `참고사항` H2 섹션을 전부 접음.
사용자는 중요한 정보를 보기 위해 클릭해야 하므로 **time-on-page 감소** 역효과.

### 제안
- **accordion 대상 축소**: "한눈에 비교" 섹션(비교 리스트)만 접고 나머지는 펼친 상태 유지
- 또는 3문장 이상인 섹션만 접기 (짧은 섹션은 펼침)
- Blowfish `{{< accordion >}}`은 기본이 펼쳐진 상태가 아니므로, `open` 속성 지원 여부 확인 필요

### 우선순위: P1

---

## 2. Badge 시각적 개선

### 문제
`{{< badge >}}`가 H3 제목 옆에 인라인으로 표시됨. 제목이 길면 줄바꿈 문제 발생.
Blowfish badge가 한국어 3~4글자 업종명에 최적화되어 있지 않음.

### 제안
- `{{< badge >}}` 대신 `{{< article-tag >}}` 사용 고려 (스타일 다름)
- 또는 custom badge CSS 오버라이드: `.badge` 클래스 패딩/폰트 조정
- 인라인 대신 H3 아래 별도 줄에 배치

### 우선순위: P2

---

## 3. Chart.js 로딩 검증

### 문제
Blowfish `{{< chart >}}` shortcode가 Chart.js CDN을 페이지에 포함시키는지 미확인.
Chart.js가 로드되지 않으면 차트 영역이 빈 공간으로 노출됨.

### 제안
1. Blowfish 소스 코드 확인: `themes/blowfish/layouts/shortcodes/chart.html`
   - Chart.js CDN 링크 포함 여부
   - `defer` 또는 `async` 로딩 방식
2. 실제 브라우저 테스트: 네트워크 탭에서 chart.js 요청 확인
3. CDN 장애 시 fallback: 로컬 node_modules Chart.js 번들 제안

### 우선순위: P1

---

## 4. Gallery: 이미지 부족 문제

### 문제
GoCamping API는 캠핑장당 `firstImageUrl` 1장만 제공. gallery shortcode는 2장 이상의 연속 figure가 있어야 활성화되므로, 현재 데이터로는 gallery가 생성되지 않음.

### 제안
1. **detailImage API 연동** (별도 Phase): GoCamping detail API에서 추가 이미지 수집
2. **TourAPI 연계**: 동일 위치의 TourAPI 관광 이미지 활용
3. **Cross-item gallery**: 동일 글이 3~5개 캠핑장을 다루므로, 각 캠핑장의 1장씩을 모아 gallery 구성 (post-processor로 구현)

### 우선순위: P3

---

## 5. Alert/Badge: Prompt → Post-Processor 전환

### 문제
alert와 badge는 AI prompt에 의존하므로:
- AI가 항상 같은 형식으로 생성한다는 보장 없음
- 가끔 빠뜨리거나 위치가 이상할 수 있음
- 프롬프트 변경 시 기존 발행 내역과 불일치 발생

### 제안
post-processor로 전환:
- **badge**: items 데이터에서 `induty` 필드를 읽어 H3 제목 다음 줄에 자동 삽입
- **alert**: 특정 조건(반려동물 가능, 시설 팁)에서 자동 생성. items의 `animalCmgCl`, `sbrsCl` 필드 기반

### 우선순위: P2

---

## 6. Figure Caption 길이 제한

### 문제
`_apply_figure_shortcode()`가 이미지 다음 줄을 caption으로 추출하는데, 150자 미만 조건이 있지만 너무 긴 caption이 figure 아래에 표시될 수 있음.

### 제안
- caption 최대 길이 80자로 제한
- caption이 없으면 alt text를 caption으로 사용 (현재는 alt text를 무시하고 다음 줄을 caption으로 사용)

### 우선순위: P3

---

## 7. lead shortcode 조건 강화

### 문제
`_apply_lead_shortcode()`가 첫 번째 텍스트 단락을 항상 lead로 래핑함.
첫 단락이 1문장짜리 도입문(예: "강원도의 캠핑장을 소개합니다.")이면 lead 효과가 무의미.

### 제안
- 첫 단락이 2문장 이상일 때만 lead 적용
- 또는 첫 단락 길이가 50자 미만이면 lead 스킵

### 우선순위: P3

---

## 8. shortcodes_enabled → 세분화

### 문제
현재 `shortcodes_enabled`는 boolean on/off만 지원.
특정 shortcode만 끄거나(예: chart는 끄고 lead는 켜기) 불가능.

### 제안
```yaml
shortcodes_enabled:
  lead: true
  figure: true
  alert: true
  badge: true
  gallery: true
  accordion: false  # only accordion disabled
  chart: false      # only chart disabled
```

### 우선순위: P4

---

## 우선순위 요약

| 순위 | 항목 | 영향 | 노력 |
|------|------|------|------|
| P1 | Accordion 범위 축소 | 사용성 직결 | 소 |
| P1 | Chart.js CDN 검증 | 기능 안정성 | 소 |
| P2 | Badge 시각 개선 | 외관 | 중 |
| P2 | Alert/Badge post-processor 전환 | 일관성 | 중 |
| P3 | Gallery 이미지 부족 | 기능 제한 | 대 |
| P3 | Figure caption 길이 제한 | 외관 | 소 |
| P3 | Lead 조건 강화 | 사용성 | 소 |
| P4 | shortcodes_enabled 세분화 | 설정 유연성 | 중 |
