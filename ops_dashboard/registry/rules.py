"""ops_dashboard.registry.rules — 표준 준수 규칙 R01~R12 선언 (Phase 69, W1).

`ops_dashboard/checks/standard.py`의 `STANDARD_RULES`(L27~L124)를 **동일한 중립
스키마(UnifiedEntry)** 로 미러링한 순수 선언이다. 기존 STANDARD_RULES는 이 웨이브에서
수정하지 않는다 — 소비 전환은 후속 웨이브(W6)에서 이룬다.

매핑 규칙:
    rule_id   -> id
    target    -> target (그대로)
    severity  -> severity (그대로)
    description -> action (조치 문구로 변환)
    bucket    -> bucket (그대로)
    check     -> check_fn (함수명 문자열)
    threshold -> rule은 항상 검사하므로 "always"

R06 참고 (deprecate-then-split 전방 참조, W1/W3/W7 정합):
    R06은 이 웨이브에서는 그대로 `R06`으로 선언·기록하되, W7에서 R06A/R06B로 분화된다.
    이 시점에 R06A/R06B를 미리 만들지 않는다.
"""
from __future__ import annotations

from ops_dashboard.registry.schema import UnifiedEntry, validate_entry

RULES: list[UnifiedEntry] = [
    UnifiedEntry(
        id="R01",
        kind="rule",
        target="hugo.toml",
        severity="CRITICAL",
        threshold="always",
        check_fn="_check_r01",
        action="showTableOfContents를 false로 설정",
        bucket="actionable",
    ),
    UnifiedEntry(
        id="R02",
        kind="rule",
        target="hugo.toml",
        severity="CRITICAL",
        threshold="always",
        check_fn="_check_r02",
        action="Advertisement 섹션에 adsense 슬롯이 필요함",
        bucket="actionable",
    ),
    UnifiedEntry(
        id="R03",
        kind="rule",
        target="extend-head.html",
        severity="CRITICAL",
        threshold="always",
        check_fn="_check_r03",
        action="adsbygoogle.js는 site.Params 사용 (하드코딩 금지)",
        bucket="out_of_scope",
    ),
    UnifiedEntry(
        id="R04",
        kind="rule",
        target="extend_head.html",
        severity="MAJOR",
        threshold="always",
        check_fn="_check_r04",
        action="GA4 + 모바일 보정 CSS 필요",
        bucket="out_of_scope",
    ),
    UnifiedEntry(
        id="R05",
        kind="rule",
        target="adsense/top.html",
        severity="MAJOR",
        threshold="always",
        check_fn="_check_r05",
        action="overflow:hidden;min-height:100px 래퍼 + outside push div 필요",
        bucket="actionable",
    ),
    UnifiedEntry(
        id="R06",
        kind="rule",
        target="adsense/in-article.html",
        severity="CRITICAL",
        threshold="always",
        check_fn="_check_r06",
        action="fluid+in-article format (no auto) + outside push div 필요",
        bucket="deferred",
    ),
    UnifiedEntry(
        id="R07",
        kind="rule",
        target="single.html",
        severity="MAJOR",
        threshold="always",
        check_fn="_check_r07",
        action="H2 split injection + prose wrapper 필요",
        bucket="actionable",
    ),
    UnifiedEntry(
        id="R08",
        kind="rule",
        target="single.html",
        severity="MAJOR",
        threshold="always",
        check_fn="_check_r08",
        action="Description (lead) 제거 필요",
        bucket="actionable",
    ),
    UnifiedEntry(
        id="R09",
        kind="rule",
        target="baseof.html",
        severity="MAJOR",
        threshold="always",
        check_fn="_check_r09",
        action="커스텀 오버라이드 없음 — 테마 기본값 사용",
        bucket="actionable",
    ),
    UnifiedEntry(
        id="R10",
        kind="rule",
        target="custom.css",
        severity="MAJOR",
        threshold="always",
        check_fn="_check_r10",
        action="미채움 공간 제거 + 다크모드 + min-height 규칙 필요",
        bucket="actionable",
    ),
    UnifiedEntry(
        id="R11",
        kind="rule",
        target="layouts/",
        severity="MAJOR",
        threshold="always",
        check_fn="_check_r11",
        action="mobile-sticky.html 사용 금지",
        bucket="actionable",
    ),
    UnifiedEntry(
        id="R12",
        kind="rule",
        target="layouts/",
        severity="MAJOR",
        threshold="always",
        check_fn="_check_r12",
        action="허용 집합을 벗어난 오버라이드 파일 없음",
        bucket="actionable",
    ),
    # W7-b: THUMBNAIL-01 — 썸네일 존재·600×600·webp·R2 업로드 여부 검사.
    # 표준.py의 _CHECK_FUNCTIONS 및 STANDARD_RULES에는 **추가하지 않음**.
    # W7-a 보강 A/B로 registry RULES → _resolve_check_fn 동적 디스패치 경로가
    # 열렸으므로, rules.py 선언 + standard.py _check_thumbnail_01 함수만으로
    # check_standard_compliance() 순회에 자동 편입되는지 검증 대상.
    UnifiedEntry(
        id="THUMBNAIL-01",
        kind="rule",
        target="content/posts/*/index.md (frontmatter featureimage)",
        severity="MAJOR",
        threshold="always",
        check_fn="_check_thumbnail_01",
        action="featureimage를 R2(pub-<hash>.r2.dev) 호스팅 webp로 설정",
        bucket="actionable",
    ),
    # W7 확대: R2-01 — 이미지 URL R2 버킷/키 패턴 정합성 검사.
    # THUMBNAIL-01(존재+R2+webp)과 역할 분리: R2-01은 featureimage + 본문 이미지
    # 전체를 대상으로 R2 도메인(pub-<hash>.r2.dev) 호스팅 여부만 검사(webp 무관).
    # 표준.py의 _CHECK_FUNCTIONS 및 STANDARD_RULES에는 추가하지 않음 —
    # registry 선언 + _check_r2_01 함수만으로 자동편입.
    UnifiedEntry(
        id="R2-01",
        kind="rule",
        target="content/posts/*/index.md (featureimage + 본문 이미지 URL)",
        severity="MAJOR",
        threshold="always",
        check_fn="_check_r2_01",
        action="모든 이미지 URL을 승인된 R2 버킷(pub-<hash>.r2.dev)으로 설정",
        bucket="actionable",
    ),
    # Phase 71 (SC-2): C08 — 라이브-파일 불일치 실검사.
    # 콘텐츠 무결성 검사(C01~C09)의 실행 경로는 content_integrity.check_c08 가 담당.
    # 여기선 표준 준수 집계(RULES)에 편입시켜 /standards 뷰·registry 에 노출.
    # bucket="deferred": 표준준수 집계율에서는 제외하되 실제 check 는 run_all_checks 에서
    #   매 실행되어 실판정(pass/fail)을 기록. 라이브 HTTP 비용 급증 방지는
    #   content_integrity.check_c08 의 24h 저빈도 캐시로 완화.
    UnifiedEntry(
        id="C08",
        kind="rule",
        target="live vs file (title/meta/og:image/structure/CoT/ad)",
        severity="MAJOR",
        threshold="always",
        check_fn="_check_c08",
        action="라이브 페이지 대조 위반 항목별 재조정 (C08_TITLE_MISMATCH/OG_MISSING/OG_MISMATCH/STRUCTURE/COT_LEAK/AD_NOT_RENDERED)",
        bucket="deferred",
    ),
    # Phase 71 (DATA-01): data_stock — 브랜드별 콘텐츠 재고 임계 검사.
    # 실제 판정은 data_stock.py 의 등록 체크 @register_check("data_stock") 가 run_all_checks에서
    # 수행한다 (chat 아니라 conn 기반 sqlite read-only). 여기선 registry·/standards 뷰에 노출만.
    # check_fn="_check_data_stock": standard.py 에 존재하지 않음 → _resolve_check_fn 이 None
    #   반환 + 경고 로그 → check_standard_compliance 에서 skip(continue). failures/passes 에
    #   미포함되어 "All N rules passed" 총량 안 깨짐. (C08 와 달리 site 기반이 아니므로 위임 래퍼를
    #   두지 않음.)
    # bucket="deferred": 표준준수 집계율에서 제외하되 registry·attention 에는 노출된다.
    UnifiedEntry(
        id="data_stock",
        kind="rule",
        target="브랜드별 콘텐츠 재고 (content stock per brand)",
        severity="MINOR",
        threshold="always",
        check_fn="_check_data_stock",
        action="재고 부족(≤STOCK_LOW=10) 브랜드는 발행 재정비 또는 콘텐츠 소스 보충",
        bucket="deferred",
    ),
    # Phase 72 (Wave 2b, SC-3): 프론트매터 전용 안전등급 자동수정 3종.
    # 본문 미변경, git 롤백 가능, 재검사로 해결 입증 → _AUTOFIX_SAFE_ACTIONS 편입.
    # 실제 탐지 훅(checks/frontmatter.py)은 차기 웨이브에서 run_all_checks 편입 예정 —
    # 여기선 registry·/standards 뷰 노출 + rule→action 매핑(_AUTOFIX_RULE_TO_ACTION)만 선언.
    UnifiedEntry(
        id="FM-DRAFT",
        kind="rule",
        target="content/posts/*/index.md (frontmatter draft)",
        severity="MINOR",
        threshold="always",
        check_fn="_check_frontmatter",
        action="draft:true 프론트매터 키 제거",
        bucket="actionable",
    ),
    UnifiedEntry(
        id="FM-FEATUREIMAGE",
        kind="rule",
        target="content/posts/*/index.md (frontmatter featureimage)",
        severity="MINOR",
        threshold="always",
        check_fn="_check_frontmatter",
        action="featureimage URL을 IMAGE-GUARD 규칙으로 정화",
        bucket="actionable",
    ),
    UnifiedEntry(
        id="FM-MISSINGKEYS",
        kind="rule",
        target="content/posts/*/index.md (frontmatter keys)",
        severity="MINOR",
        threshold="always",
        check_fn="_check_frontmatter",
        action="title/description/date/slug/tags 누락 시 파생값으로 보강",
        bucket="actionable",
    ),
    # ── R13-R23: 2026-08-21 airports 품질 점검 규칙 ──
    UnifiedEntry(
        id="R13",
        kind="rule",
        target="content/posts/*/index.md (본문)",
        severity="MAJOR",
        threshold="always",
        check_fn="_check_r13",
        action="본문에 삽입이미지 최소 1장 추가",
        bucket="actionable",
    ),
    UnifiedEntry(
        id="R14",
        kind="rule",
        target="content/posts/*/index.md (본문)",
        severity="MAJOR",
        threshold="always",
        check_fn="_check_r14",
        action="렌더 본문 wordCount가 400자 미만 - 본문 보강 필요",
        bucket="actionable",
    ),
    UnifiedEntry(
        id="R15",
        kind="rule",
        target="content/posts/*/index.md (본문)",
        severity="MAJOR",
        threshold="always",
        check_fn="_check_r15",
        action="정직 단어수(보일러플레이트 제외) 400 미만 - 본문 보강 필요",
        bucket="actionable",
    ),
    UnifiedEntry(
        id="R16",
        kind="rule",
        target="content/posts/*/index.md (frontmatter)",
        severity="MAJOR",
        threshold="always",
        check_fn="_check_r16",
        action="og:image(featureimage 또는 og_image) 프론트매터에 존재해야 함",
        bucket="actionable",
    ),
    UnifiedEntry(
        id="R17",
        kind="rule",
        target="content/posts/*/index.md (frontmatter params)",
        severity="MINOR",
        threshold="always",
        check_fn="_check_r17",
        action="twitter:card를 summary_large_image로 설정",
        bucket="actionable",
    ),
    UnifiedEntry(
        id="R18",
        kind="rule",
        target="content/posts/*/index.md",
        severity="CRITICAL",
        threshold="always",
        check_fn="_check_r18",
        action="생성 초안과 배포본 해시 불일치 - 재승인 또는 재배포 필요",
        bucket="actionable",
    ),
    UnifiedEntry(
        id="R19",
        kind="rule",
        target="content/posts/*/index.md (본문)",
        severity="MAJOR",
        threshold="always",
        check_fn="_check_r19",
        action="금지 표현 블랙리스트 위반 - 해당 표현 제거 또는 대체",
        bucket="actionable",
    ),
    UnifiedEntry(
        id="R20",
        kind="rule",
        target="content/posts/*/index.md (본문)",
        severity="MAJOR",
        threshold="always",
        check_fn="_check_r20",
        action="분류코드 원문 노출 - 자연어 표현으로 대체",
        bucket="actionable",
    ),
    UnifiedEntry(
        id="R21",
        kind="rule",
        target="content/posts/*/index.md (본문)",
        severity="MAJOR",
        threshold="always",
        check_fn="_check_r21",
        action="동일 포스트 내 문단 중복률 상한 초과 - 중복 문단 제거 또는 병합",
        bucket="actionable",
    ),
    UnifiedEntry(
        id="R22",
        kind="rule",
        target="content/posts/*/index.md (frontmatter)",
        severity="MAJOR",
        threshold="always",
        check_fn="_check_r22",
        action="배치 내 robots 값 일관성 위반 - noindex 설정 통일",
        bucket="actionable",
    ),
    UnifiedEntry(
        id="R23",
        kind="rule",
        target="publish record",
        severity="CRITICAL",
        threshold="always",
        check_fn="_check_r23",
        action="배포 시점 사람 승인 상태 기록 존재해야 함",
        bucket="actionable",
    ),
    UnifiedEntry(
        id="CF-01",
        kind="rule",
        target="content/posts/*/index.md (본문 날짜 + festival DB)",
        severity="MAJOR",
        threshold="always",
        check_fn="check_content_freshness",
        action="본문 날짜 만료(60일) 또는 festival DB 갱신 중단 시 재생성/refresh 필요 (ERR-021/022)",
        bucket="actionable",
    ),

]

# W6-a: rule↔문제분류(problem_id) 대응 선언.
# R01~R12는 전부 표준준수(adSense/SEO/템플릿) 규칙이므로, 어느 규칙이 위반되든 문제분류
# `standard_compliance`(표준준수 실패)로 대응된다. P-family 발행오류(P01~P24)가 아님 —
# `_check_name_to_problem_id`의 `standard_compliance → standard_compliance` 매핑과 정합.
# auto_triage._build_registry_map이 이 맵을 단일 출처로 사용해 구조 필드 우선 경로를
# 발화시킨다. 폴백 파서는 W6-b 제거 전까지 그대로 유지한다.
RULE_TO_PROBLEM: dict[str, str] = {entry.id: "standard_compliance" for entry in RULES}

# W1 게이트: 모든 선언이 스키마 허용 값을 지키는지 즉시 검증.
for _entry in RULES:
    validate_entry(_entry)
