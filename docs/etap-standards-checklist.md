# ETAP 규격 체크리스트 (Phase 3 재생성 합격 기준)

> **목적**: ETAP 파이프라인으로 생성된 글이 라이브 발행되기 전에 충족해야 하는 최소 규격.
> Phase 3에서 force_topic_id로 재생성 시 이 체크리스트를 통과해야 배포 가능.

## 1. 단어 수

| 항목 | 기준 | 검사 방법 |
|------|------|-----------|
| 본문 단어 수 | **≥ 400 단어** | `len(content.split())` ≥ 400 |
| 권장 | 800~1,500 단어 | 너무 짧으면 보충 필요 |

**실패 시**: postprocess_content에서 `is_draft=True` → 발행 차단

## 2. H2 섹션

| 항목 | 기준 | 검사 방법 |
|------|------|-----------|
| H2 개수 | **≥ 3개** | `len(re.findall(r"^## ", content, re.MULTILINE))` ≥ 3 |
| H2 구조 | 규격 H2 사용 | 프롬프트에서 지정한 H2 구조 준수 |

**실패 시**: postprocess_content에서 `is_draft=True` → 발행 차단

## 3. 필수 요소

### 3.1 Disclaimer

| 항목 | 기준 | 검사 방법 |
|------|------|-----------|
| Disclaimer 카드 | **필수** | `<div class="etap-disclaimer-card">` 포함 |

- postprocess_content에서 자동 추가됨 (quality_guard.py:468-478)
- 이미 존재하면 추가하지 않음

### 3.2 Product Cards / Comparison Table

| 항목 | 기준 | 검사 방법 |
|------|------|-----------|
| Product cards | tours 데이터 있을 때 권장 | `insert_product_cards()` 호출 결과 |
| Comparison table | tours 데이터 있을 때 권장 | `insert_comparison_table()` 호출 결과 |

- `_add_product_cards()`에서 tours 기반 카드/비교 테이블 생성
- tours 없으면 빈 요소로 남을 수 있음 (데이터 부족)

### 3.3 AdSense

| 항목 | 기준 | 검사 방법 |
|------|------|-----------|
| AdSense 삽입 | **본문 규격 통과 시 자동** | `insert_adsense()` 성공 |
| 실패 조건 | 본문 `\n\n` 부족 시 실패 가능 | 본문 정상(H2≥3, ≥400단어)일 때만 통과하므로 자동 해소 |

**참고**: insert_adsense 실패는 본문 규격이 정상이면 자동 해소됨. 별도 강제 삽입 불필요.

## 4. TOC (목차)

| 항목 | 기준 | 검사 방법 |
|------|------|-----------|
| showTableOfContents | **false** | hugo.toml `[params]` `showTableOfContents = false` |

- techpawz-hugo 표준 (R01)
- ETAP도 동일하게 적용

## 5. 포스트 메타

| 항목 | 기준 | 검사 방법 |
|------|------|-----------|
| title (H1) | 첫 줄 `# 제목` 형식 | regex `^\#\s+(.+)` 매치 |
| slug | URL-safe | alpha-numeric + hyphen |
| tags | 카테고리 태그 포함 | city, country, topic category, Travel |
| featureimage | Cover 이미지 URL | fetch_city_image 결과 |

## 6. Content Quality

| 항목 | 기준 | 검사 방법 |
|------|------|-----------|
| Banned phrases | 없음 | postprocess_content에서 자동 치환 |
| Suspicious prices | $0, $50,000+ 없음 | postprocess_content 검사 |
| Hallucinated prices | 소스 데이터 외 가격 없음 | postprocess_content 검사 (data_prices 기반) |
| Fabricated URLs | 허용 도메인 외 URL 없음 | postprocess_content 검사 |
| Fake relative links | /posts/ 링크 없음 | postprocess_content 검사 |

## 7. 발행 게이트 (파이프라인 레벨)

| 단계 | 검사 | 실패 시 |
|------|------|---------|
| 데이터 수집 | tours/routes 존재 | `no_data` → exhausted 처리 |
| Dedup | threshold=0.85 | 생존 투어 ≥3 권장 (미만 시 경고) |
| Summary | 길이 ≥300자 | `no_data` → AI 호출 전 실패 |
| AI 생성 | GPT 호출 성공 | 실패 시 exhausted |
| Post-process | content ≥200자, H2≥3, ≥400단어, suspicious price 없음 | `is_draft=True` → 발행 차단 |
| Write Hugo post | `_write_hugo_post` 성공 | 실패 시 `write_failed` → 발행 차단 |

## 8. Dry-Run 검증 (Phase 3)

Phase 3 재생성 시 각 토픽에 대해:

1. **데이터 단계**: dedup 후 생존 투어 수, summary 길이 확인
2. **AI 단계**: 단어 수, H2 수, 제목 형식 확인
3. **Post-process**: is_draft=False, post_issues 없음 확인
4. **Write**: `_write_hugo_post` 반환값 `{"success": True}` 확인

**합격 기준**:
- [ ] dedup 후 생존 투어 ≥ 3
- [ ] summary 길이 ≥ 300자
- [ ] AI 본문 단어 수 ≥ 400
- [ ] H2 개수 ≥ 3
- [ ] is_draft = False
- [ ] post_issues 없거나 경미 (auto-replace만)
- [ ] `_write_hugo_post` success = True

## 9. 레퍼런스

- `pipelines/etap/quality_guard.py` — postprocess_content, H2/word count 검사
- `pipelines/etap/cruise_writer.py` — _deduplicate_tours, _build_summary, generate_cruise_guide
- `pipelines/etap/daytrips_writer.py` — 동일 구조
- `pipelines/etap/cruise_pipeline.py` — _run_impl, 발행 게이트
- `shared/publishers/hugo_writer.py` — _write_hugo_post_etap
