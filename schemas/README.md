# schemas/ — 블로그 스키마-as-code 디렉토리

스키마-as-code는 트랙C S1 설계의 산출물이다.
상세 설계: `docs/superpowers/specs/2026-08-22-schema-as-code-design.md`

## 디렉토리 구조

```text
schemas/
├── _base/default.yaml          # 공통 폴백 (모든 분기가 상속)
├── {branch}/schema.yaml        # 분기 스키마 (8개 실존 분기)
├── {branch}/blog-overrides/    # 블로그 단위 오버라이드 (선택, 미생성)
└── README.md                   # 본 파일
```

## 상속 메커니즘 (deep-merge)

로더(`ops_dashboard/schema_loader.py`)는 다음 순서로 스키마를 병합한다.

```text
1. schemas/_base/default.yaml        # 공통 필드 (폴백)
2. schemas/{branch}/schema.yaml      # 분기 고유 오버라이드
3. schemas/{branch}/blog-overrides/{blog_id}.yaml  # 블로그 단위 (선택)
```

- 병합은 **deep-merge**: 중첩 dict(list 제외)는 키 단위로 합쳐지고,
  분기/블로그 파일이 같은 키를 선언하면 상위가 덮어쓴다.
- list 필드(예: `required_frontmatter`)는 **교체**된다 (합치지 않음) — 분기에서
  전체 목록을 다시 선언해야 한다.
- blog-overrides는 이번 생성 범위에 포함되지 않는다 (분기 스키마만 생성).

## 오버라이드 우선순위

```text
blog-overrides/{blog_id}.yaml  >  {branch}/schema.yaml  >  _base/default.yaml
(최우선)                                                      (폴백)
```

## 필드 정의 레퍼런스

| 필드 | 타입 | 설명 |
|---|---|---|
| `required_frontmatter` | list[str] | 필수 frontmatter 키 목록 (빈 값은 `empty_value_policy`로 판정) |
| `allowed_og_patterns` | list[str] | og:image URL 허용 정규식 패턴 목록 |
| `title_format_rule.max_len` | int | 제목 최대 길이 (초과 시 FM-TITLE_FORMAT) |
| `title_format_rule.forbid_ellipsis` | bool | 제목에 '…' 포함 금지 여부 |
| `title_format_rule.allow_suffix` | list[str] \| null | 허용되는 제목 접미사 ('…' 등) |
| `live_og_format_rule` | enum | 라이브 og:title vs 로컬 title 정상 관계: `exact_match` / `contains` / `prefix_match` / `case_insensitive_match` |
| `empty_value_policy` | dict[str, str] | 필드별 빈 문자열 허용: `allow` / `disallow` (기본 disallow) |
| `og_rule.og_image_required` | bool | og:image 필수 여부 |
| `og_rule.og_image_source` | str | og:image가 따라야 할 로컬 frontmatter 키 (예: featureimage) |
| `directory_layout.content_root` | str | 콘텐츠 루트 디렉토리 |
| `directory_layout.post_pattern` | str | 포스트 파일 패턴 (`{slug}` 치환) |
| `disclosure_rules` | dict | 제휴문구 규칙 (required, position) |
| `rel_rules` | dict | 어필리에이트 링크 rel 규칙 |
| `template_constraints` | dict | 템플릿 제약 (R01~R12, twitter_card, thumbnail, ticker 등) |

## 분기 현황 (2026-08-22)

| 분기 | blog_id 수 | 스키마 상태 | 표본 근거 | _base와의 주요 차이 |
|---|---|---|---|---|
| etap | 36 | ✅ 완성 | tour/trains/ferry | featureimage 필수, exact_match, og_image_required |
| cap | 8 | ✅ 완성 | pick/hotissue | '…' 접미사 허용, contains, featureimage 선택 |
| cuap | 15 | ✅ 완성 | pet-hugo (기준 블로그, 2026-08-22 확정) | featureimage 선택(31~40/40), informationhot OG 패턴, GA4 services 단일주입 표준 |
| manual | 7 | ✅ 완성 (TODO 2건) | informationhot-hugo | featureimage 거의 없음(1/40), '…' 허용, contains |
| tap | 6 | ✅ 완성 (구조 통일 반영, 2026-08-22) | travel/travel1~4 (전수 5 Hugo 블로그) | featureimage 필수(전수 98~99%), ellipsis 수용, twitter_card 비표준 |
| stap | 6 | ✅ 완성 | finance/sector | '…' 허용(35/40), ticker 키 허용 |
| rap | 5 | ✅ 완성 | rap/rap3 | featureimage 필수(39~40/40), thumbnail 허용 |
| seap | 2 | ✅ 완성 | senior-hugo | featureimage 필수(40/40), '…' 허용(20/40), thumbnail 허용 |

## 분기별 표본 조사 근거 (2026-08-22)

| 분기 | 표본 blog_id | featureimage 존재율 | title 잘림율 | OG 특이점 |
|---|---|---|---|---|
| cuap | appliance(40), beauty(40), camping(40) | 31/40, 38/40, 40/40 | 0% | cover/image 키 병용 |
| manual | informationhot(40) | 1/40 | 23/40 (58%) | cover/image 키 위주 (featureimage 아님) |
| tap | travel(674), travel1(488), travel2(655), travel3(708), travel4(640) | 98~99% (629~671/블로그) | 1~14% (ellipsis는 tap 표준 타이틀 잘림 패턴) | featureimage 외부호스트(visitkorea/khs/gocamping), twitter_card <1.5% (비표준) |
| stap | finance(40), sector(40) | 40/40, 36/40 | 35/40, 16/40 | ticker 키 존재 |
| rap | rap(40), rap3(40) | 40/40, 39/40 | 2/40 | thumbnail 키 존재 |
| seap | senior(40) | 40/40 | 20/40 (50%) | thumbnail 키 존재 |

## TODO (후속 작업)

- **manual**: `og_image_source`를 featureimage vs cover/image 중 무엇으로 할지 — cover 존재율이 높아 우선순위 결정 필요
- **stap**: `ticker`를 required로 올릴지 — sector 23/40만 존재, 재검토 필요
- **seap/stap/manual**: title `'…'` 허용 정책은 기존 발행물 수용용 — 신규 발행 writer 개선 후 forbid_ellipsis로 전환 검토
- **blog-overrides/**: 80개 블로그 개별 오버라이드 (이번 범위 제외)
- **moneyfeed**: 실존 분기 아님 (대시보드 DB 8개 brand 확인) — 온보딩 시 스키마 작성
