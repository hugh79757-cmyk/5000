---
title: "Schema-as-Code Design — Track C S1 (File-Based Schema Declaration)"
doc_type: DESIGN
status: IMPLEMENTED
design_validity: CONFIRMED
created: 2026-08-22
updated: 2026-08-23
branch: track-c-etap-quality-overhaul
part_of: "Roadmap M5 — Track C, S1 gate"
---

# Schema-as-Code 설계 (트랙C S1)

## 0. 목적

블로그 구조 선언(schema-as-code)을 파일 기반으로 도입한다. 트랙A의
rule_id→rule_version DB 연결(G5 블로커)이 미해결이므로, **DB/레지스트리에 직접
의존하지 않는 파일 기반 스키마**로 시작하고, 추후 트랙A G5 해소 시 어댑터만
추가하면 되는 구조로 설계한다.

기존 체커 코드(frontmatter.py, content_integrity.py, standard.py,
content_quality.py)는 **수정하지 않는다.** 로더가 중간 레이어로 들어간다.

## 1. 설계 원칙

1. **파일 기반만** — 트랙A DB/레지스트리 직접 의존 금지. 스키마는 `schemas/` YAML로만 선언.
2. **체커 무수정** — 기존 체커가 하드코딩 규칙을 그대로 유지. 로더가 로드한 SchemaSpec을
   체커가 선택적으로 소비하는 중간 레이어만 추가.
3. **트랙A 어댑터는 인터페이스만** — `adapt_rule_registry()` 시그니처 선언, 구현 금지.
4. **Hugo 빌드 흐름(트랙C S0 완료)과 충돌 금지** — 스키마는 검사기용 선언일 뿐,
   Hugo 빌드 파이프라인(`shared/publishers/deploy.py`, dispatcher 배포 흐름)을 건드리지 않는다.
5. **분기별 독립** — 각 블로그 분기(etap, moneyfeed 등)는 자신의 schema.yaml을 갖는다.

## 2. 파일 구조 제안

```text
5000/
├── schemas/
│   ├── _base/
│   │   └── default.yaml          # 모든 분기가 상속하는 공통 스키마 (fallback)
│   ├── etap/
│   │   ├── schema.yaml           # ETAP 분기 공통 스키마
│   │   └── blog-overrides/
│   │       ├── trains-hugo.yaml  # blog_id 단위 오버라이드 (선택)
│   │       └── tour-hugo.yaml
│   ├── moneyfeed/
│   │   └── schema.yaml           # moneyfeed 분기 스키마 (미구현 분기 예시)
│   └── README.md                 # 스키마 작성 규칙 문서
├── ops_dashboard/
│   └── schema_loader.py          # 로더 모듈 (신규 — 체커 수정 없음)
└── scripts/
    └── validate_schema_pr.py     # CI 정합성 게이트 스크립트 (신규)
```

- `schemas/{branch}/schema.yaml` — 분기 단위 스키마.
- `schemas/{branch}/blog-overrides/{blog_id}.yaml` — 블로그 단위 오버라이드 (선택).
  오버라이드는 분기 스키마의 특정 필드를 덮어쓴다(deep-merge).
- `schemas/_base/default.yaml` — 공통 필수값(예: `title`, `description` 등 Hugo 기본)의
  폴백. 분기 스키마가 없으면 base만 사용.

## 3. SchemaSpec 정의

로더가 반환하는 공통 데이터 구조. `dataclass` 기반으로 정의하며, 체커들이
필요한 필드를 포함한다.

```python
# ops_dashboard/schema_loader.py (신규)
from dataclasses import dataclass, field

@dataclass(frozen=True)
class SchemaSpec:
    branch: str                              # 분기명 (etap, moneyfeed, ...)
    blog_id: str | None                      # blog 단위 로드 시 해당 blog_id
    required_frontmatter: list[str]          # frontmatter.py REQUIRED_KEYS 대체 후보
    allowed_og_patterns: list[str]           # og:image / og:title 허용 URL 정규식 패턴
    directory_layout: dict[str, list[str]]   # {"posts": ["{slug}/index.md"], ...}
    disclosure_rules: dict                    # {"required_count": [1,2], "position": "..."}
    rel_rules: dict                           # {"sponsored": true, "noopener": true}
    template_constraints: dict                # {"allowed_overrides": [...], "forbidden": [...]}
    featureimage_guard: dict                  # {"max_len": 200, "token_repeat": true, ...}
    rule_refs: dict[str, str]                # {"R04": "extend_head.html", ...} — 트랙A 연계용(비사용)
    # ── [신규 2026-08-22] c08 갭 보완 필드 ──────────────────────────────
    live_og_format_rule: str = "exact_match"  # enum[exact_match|contains|prefix_match|case_insensitive_match]
    empty_value_policy: dict[str, str] = field(default_factory=dict)
    #   {field_name: "allow"|"disallow"} — 기본 disallow (required 필드 빈 문자열 금지)
```

- **live_og_format_rule**: 라이브 og:title과 로컬 title의 정상 관계 정의.
  - `exact_match` — og:title == local title (문자열 완전 일치). **기본값.**
  - `contains` — og:title이 local title을 포함 (local title ⊂ og:title). cap 기존 발행물 형식 반영.
  - `prefix_match` — og:title이 local title로 시작.
  - `case_insensitive_match` — 대소문자 무시 일치.
  - 분기별 오버라이드 예: `etap: exact_match`, `cap: contains`.
- **empty_value_policy**: required_frontmatter 필드의 빈 문자열("") 허용 여부.
  - 기본 `disallow` — Stage 1에서 LOCAL_VIOLATION으로 즉시 확정.
  - 분기별 `allow` 오버라이드 가능 (예: cap 구형 포스트 description 생략 허용).

- 체커는 `SchemaSpec.required_frontmatter` 등 **필드만** 소비한다. 기존 하드코딩
  상수(`frontmatter.REQUIRED_KEYS`)는 유지되며, 스키마 도입 후 단계적으로 대체한다
  (이 설계에서 체커 수정은 하지 않음).

## 3b. c08 2단계 판정 레이어 (신규)

기존 `content_integrity.py`의 `_compare_live_vs_local`은 **무수정**. 새 staging
레이어를 `check_c08` 위에 얹는다. 판정을 2단계로 분리한다.

### Stage 1 (로컬 전용 — CI 드라이런 범위)

- **입력:** `load_schema(blog_id) → SchemaSpec` + 로컬 포스트 frontmatter (`_read_post_files`)
- **출력:** `LOCAL_VIOLATION` (위반 rule_id: FM-MISSINGKEYS / FM-EMPTY / FM-TITLE_FORMAT) | `PASS`
- **범위:** 로컬 파일만 — 라이브 크롤, HTTP 요청, DB write 없음
- **규칙:**
  1. `required_frontmatter` 필드 값이 빈 문자열/None → `empty_value_policy` 기본
     `disallow` → `LOCAL_VIOLATION (FM-EMPTY)`
  2. `title_format_rule.forbid_ellipsis=true`이고 title에 `…` 포함 → `LOCAL_VIOLATION (FM-TITLE_FORMAT)`
  3. `title_format_rule.max_len` 초과 → `LOCAL_VIOLATION (FM-TITLE_FORMAT)`
  4. 위반 없음 → `PASS` (Stage 2 진행)
- **결정:** Stage 1에서 LOCAL_VIOLATION이 나오면 **즉시 확정** — Stage 2(라이브 크롤) 생략.

### Stage 2 (라이브 비교 — 대시보드 정기 검사 범위)

- **입력:** Stage 1 PASS 결과 + 기존 `_compare_live_vs_local(local_fm, live_html)` 출력 +
  `SchemaSpec.live_og_format_rule`
- **출력:** `LIVE_DRIFT` (불일치 서브코드) | `FALSE_POSITIVE` (정상, dismiss)
- **범위:** 라이브 크롤 필요 — 대시보드 정기 검사에서만 수행 (24h 캐시 유지)
- **규칙:**
  1. og:image: 로컬 featureimage 있음 + 라이브 og:image 없음 → `LIVE_DRIFT (C08_OG_MISSING)`
  2. og:title (`live_og_format_rule` 적용):
     - `exact_match`: local title != og:title → `LIVE_DRIFT (C08_TITLE_MISMATCH)`
     - `contains`: og:title이 local title 미포함 → `LIVE_DRIFT` / 포함 → `FALSE_POSITIVE` (dismiss)
     - `prefix_match`: og:title이 local title로 시작 안 함 → `LIVE_DRIFT` / 시작 → `FALSE_POSITIVE`
  3. 기존 (b)(c)(d) (구조/COT/광고)는 `_compare_live_vs_local` 그대로 — staging은 결과 재분류만.

### CI 통합

| 검사 경로 | 수행 단계 | 비고 |
|---|---|---|
| CI 드라이런 (`validate_schema_pr.py` 역방향) | Stage 1만 | 로컬 파일 기반, 라이브 크롤 금지. 위반 delta는 Stage 1 건수만 산출 |
| 대시보드 정기 검사 (`check_c08`) | Stage 1 + Stage 2 | Stage 1 위반 블로그는 라이브 크롤 비용 절감 (24h 캐시와 병행) |

## 4. 로더 모듈

- **모듈명:** `ops_dashboard/schema_loader.py`
- **의존성:** `pyyaml`(이미 requirements.txt에 있음), `pathlib`, `dataclasses`.
  **트랙A DB/레지스트리 import 금지.**
- **함수 시그니처:**

```python
def load_schema(blog_id: str) -> SchemaSpec:
    """blog_id → 분기(branch) 자동 매핑 후 SchemaSpec 반환.

    조회 순서:
      1. schemas/{branch}/blog-overrides/{blog_id}.yaml 존재 시 deep-merge
      2. schemas/{branch}/schema.yaml
      3. schemas/_base/default.yaml (폴백)
    매핑: blog_id의 접두사(etap-*, moneyfeed-*) 또는 config/blogs.d/{brand}.yaml의
    brand 필드로 분기 결정 (파일 기반만 — DB 조회 없음).
    미매칭 시 base 스키마 반환 + warning 로그.
    """
```

- **보조 함수:** `load_schema_spec_for_checks(blog_id) -> SchemaSpec | None`
  (체커가 실패 없이 선택 소비할 수 있게 None-safe 래퍼).

## 5. CI 정합성 게이트

- **스크립트명:** `scripts/validate_schema_pr.py`
- **트리거 조건:** GitHub Actions에서 PR이 다음 경로를 포함할 때 실행:
  - `pipelines/`, `shared/publishers/`, `layouts/`, `content/` (구조 변경 PR)
  - `schemas/` (스키마 변경 PR)
- **실패 조건 (정방향):** 블로그 구조 파일 변경 시, 해당 blog_id의
  `schemas/{branch}/schema.yaml`(또는 blog-overrides)이 함께 변경되지 않으면 **fail**.
  판정 기준: 변경된 파일 경로에서 blog_id를 추론(예: `pipelines/etap/` → etap 분기)하고,
  해당 분기 schema.yaml의 mtime/hash가 PR base와 비교해 변경됐는지 확인.
- **실패 조건 (역방향):** `schemas/` 변경 시, 영향받는 체커(frontmatter,
  content_integrity, standard, content_quality)를 대상으로 **드라이런** 실행.
  드라이런 = 기존 콘텐츠(로컬 포스트 파일)에 새 스키마를 적용해 통과 여부를
  확인하는 dry-run (라이브 크롤·배포·DB 쓰기 금지).
- **통과 조건:** 정방향 검증에서 구조 변경과 스키마 변경이 함께 있고,
  역방향 드라이런에서 기존 콘텐츠의 위반 건수가 새 스키마 적용 후 증가하지 않음.
- **범위 명시 (2026-08-22 확정):**
  - CI 드라이런 = **Stage 1만** (로컬 파일 기반, 라이브 크롤/HTTP 금지).
  - 대시보드 정기 검사 = **Stage 1 + Stage 2** (§3b).
  - 드라이런 delta는 Stage 1 위반 건수만 산출 — 라이브 og:title 불일치는 CI에서 판정하지 않음.
- **주의:** 이 게이트는 로컬 dry-run만 수행. 실제 배포·발행은 기존 승인 흐름
  (dispatcher.py, 사람 승인)을 그대로 따르며, 게이트가 배포를 대체하지 않는다.

## 6. 트랙A 어댑터 인터페이스 (미래 연결점 — 구현 금지)

트랙A G5(rule_id→rule_version DB 연결) 해소 후에만 구현한다. 여기서는
**시그니처와 계약만 선언**한다.

```python
# ops_dashboard/schema_loader.py (미래 — 현재는 선언만, 구현 금지)
from typing import Protocol

class RuleRegistry(Protocol):
    """트랙A 레지스트리 (규칙 원본). 구현은 트랙A G5 해소 후."""

@dataclass(frozen=True)
class ValidatedSchema(SchemaSpec):
    rule_version_map: dict[str, str]   # {rule_id: rule_version} — 트랙A DB 연결 결과

def adapt_rule_registry(schema: SchemaSpec, registry: RuleRegistry) -> ValidatedSchema:
    """SchemaSpec에 rule_id→rule_version 매핑을 주입해 ValidatedSchema 반환.

    연결 조건:
      - 트랙A G5 블로커 해소(rule_id→rule_version DB 연결 존재)가 선행.
      - SchemaSpec.rule_refs의 key(rule_id)를 registry에서 조회해 version을 채운다.
      - registry 미조회 rule_id는 rule_version_map에 포함하지 않음(에러 아님).
    """
    raise NotImplementedError("트랙A G5 해소 후 구현 — 이 설계 단계에서는 금지")
```

- **연결 조건:** 트랙A의 `rule_id → rule_version` DB 연결이 실제로 존재해야
  구현 가능. 그 전까지는 항상 `NotImplementedError`.
- **설계상 이점:** 체커는 `SchemaSpec`만 소비하고 어댑터를 모르므로, 추후
  트랙A 연결 시에도 체커·스키마 파일은 불변. 어댑터만 추가하면 된다.

## 7. Hugo 빌드 흐름과의 관계 (충돌 확인)

- 트랙C S0에서 완료된 Hugo 빌드 검증(36/36)은 `shared/publishers/deploy.py`와
  dispatcher 배포 흐름을 사용한다. 이 설계는 **검사기용 선언**일 뿐,
  Hugo 빌드 파이프라인에 어떤 변경도 가하지 않는다.
- 스키마 파일(`schemas/`)은 Hugo가 읽는 `config/`, `content/`, `layouts/`와
  분리된 별도 디렉터리라 빌드에 영향 없음.
- CI 게이트의 역방향 드라이런도 Hugo 빌드를 호출하지 않는다 (로컬 포스트
  파일 대상 검사기 dry-run만). → S0 빌드 흐름과 충돌 없음.

## 8. 비목표 (Non-Goals)

- 체커 코드 수정 (로더 중간 레이어만 추가)
- 트랙A DB/레지스트리 직접 접근
- 트랙A 어댑터 구현 (인터페이스 선언만)
- Hugo 빌드·배포 파이프라인 변경
- 스키마 작성 규칙 자동 검증(README 가이드라인만, 별도 게이트 없음)

## 9. 구현 우선순위 (READY_FOR_IMPLEMENTATION)

| 순위 | 항목 | 산출물 |
|---|---|---|
| 1 | `schemas/` 디렉토리 + `_base/default.yaml` 생성 | 분기 스키마 뼈대 |
| 2 | `ops_dashboard/schema_loader.py` 구현 | `load_schema()` + SchemaSpec |
| 3 | `scripts/validate_schema_pr.py` 구현 | CI 정합성 게이트 (Stage 1 드라이런) |
| 4 | c08 staging 레이어 구현 | Stage 1 + Stage 2 판정 (기존 체커 무수정) |

## 9b. 구현 완료 기록 (2026-08-22 ~ 08-23)

> 설계 → 구현 전환 완료. 코드 실측 기준.

| 순위 | 항목 | 구현 상태 | 검증 |
|---|---|---|---|
| 1 | `schemas/` 8분기 + `_base/default.yaml` | ✅ `schemas/{etap,cap,cuap,manual,tap,stap,rap,seap}/schema.yaml` | YAML 파싱 OK, README에 분기별 근거 표 |
| 2 | `ops_dashboard/schema_loader.py` | ✅ TTL 300초 캐시, blogs.d 기반 `_resolve_branch`, deep-merge, mtime 무효화 | 85개 blog_id 매핑 DB 대조 불일치 0건 |
| 3 | `scripts/validate_schema_pr.py` | ✅ 정방향(구조→스키마 동반) + 역방향(드라이런) | 3 시나리오: 구조만=FAIL, 구조+스키마=PASS, schemas만=드라이런 |
| 4 | `ops_dashboard/checks/c08_staging.py` | ✅ Stage 1(로컬) / Stage 2(라이브) 분리, 기존 체커 무수정 | 표본 5건: tour/trains=LOCAL_VIOLATION, ferry=LIVE_DRIFT, pick/hotissue=FALSE_POSITIVE |

**설계 대비 변경점:**
- `moneyfeed` 분기는 실존하지 않음 (대시보드 DB brand 8개만 존재) → 스키마 미생성, README에 TODO 기록.
- `_resolve_branch`는 파일명 stem 기반 (`managed_by` 필드 사용 시 82건 오매핑 → 수정).
- c08 staging은 `content_integrity.py` 무수정으로 신규 모듈 `c08_staging.py`에 구현.


## 10. Phase 2: 자동 피드백 루프 (미착수, 별도 설계 예정)

> **PLACEHOLDER — 이 섹션은 아직 설계되지 않았다.**
> Phase 2에서는 발행 완료 이벤트 → 스키마 대조 → 위반/드리프트 분기 → 승인 PR 루프를
> 설계한다. 상세 설계는 별도 문서로 작성 예정 (트랙 소유권 판단 포함).
> 현재까지의 설계 원칙상 파일 기반 SSOT(`schemas/`)를 유지하고, 발행 파이프라인
> (dispatcher.py)에 후크 지점을 추가하는 방향이다. 구현 전까지 이 섹션은 placeholder로 남긴다.
