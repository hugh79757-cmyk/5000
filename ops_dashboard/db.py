"""ops_dashboard.db — SQLite 데이터 모델 + YAML sync

테이블:
  - blog_lifecycle: 블로그별 라이프사이클 상태 (진실의 단일 출처)
  - known_issues: GSD 문서에서 추출한 알려진 이슈
  - check_results: 헬스체크 실행 이력
"""
import json
import logging
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from shared.problem_registry import lookup_problem

DB_PATH = Path(__file__).parent / "ops.db"
PROJECT_ROOT = Path(__file__).parent.parent
BLOGS_D = PROJECT_ROOT / "config" / "blogs.d"

# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def _alter_columns(conn: sqlite3.Connection) -> None:
    """기존 테이블에 새 컬럼 추가 (이미 존재하면 무시)."""
    alters = [
        # blog_lifecycle 정비 컬럼
        "ALTER TABLE blog_lifecycle ADD COLUMN maintenance_status TEXT NOT NULL DEFAULT 'none'",
        "ALTER TABLE blog_lifecycle ADD COLUMN maintenance_started_at TEXT",
        "ALTER TABLE blog_lifecycle ADD COLUMN maintenance_completed_at TEXT",
        "ALTER TABLE blog_lifecycle ADD COLUMN resume_ready INTEGER NOT NULL DEFAULT 0",
    ]
    for sql in alters:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # 이미 컬럼이 있으면 무시
    conn.commit()


def get_conn(db_path: str | Path | None = None) -> sqlite3.Connection:
    p = str(db_path or DB_PATH)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """테이블 생성 (IF NOT EXISTS)."""
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS blog_lifecycle (
        blog_id TEXT PRIMARY KEY,
        brand TEXT NOT NULL,
        config_status TEXT NOT NULL DEFAULT 'inactive',
        lifecycle_status TEXT NOT NULL DEFAULT 'unknown',
        pause_reason TEXT DEFAULT '',
        paused_at TEXT,
        days_since_last_publish INTEGER,
        consecutive_failures INTEGER DEFAULT 0,
        theme TEXT DEFAULT '',
        pipeline_path TEXT DEFAULT '',
        domain TEXT DEFAULT '',
        cf_project TEXT DEFAULT '',
        site_path TEXT DEFAULT '',
        quality_grade TEXT DEFAULT '',
        domain_health TEXT DEFAULT '',
        standard_compliance TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        -- 정비·재개 프레임워크 필드 (Phase 60 Part 2)
        maintenance_status TEXT NOT NULL DEFAULT 'none',
        maintenance_started_at TEXT,
        maintenance_completed_at TEXT,
        resume_ready INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT DEFAULT (datetime('now'))
    );

    -- 정비 체크리스트 항목 추적
    CREATE TABLE IF NOT EXISTS maintenance_checklist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        blog_id TEXT NOT NULL,
        check_id TEXT NOT NULL,
        check_name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        detail TEXT DEFAULT '',
        checked_at TEXT,
        UNIQUE(blog_id, check_id)
    );

    CREATE INDEX IF NOT EXISTS idx_maint_blog ON maintenance_checklist(blog_id);

    CREATE TABLE IF NOT EXISTS known_issues (
        issue_id TEXT PRIMARY KEY,
        blog_ids TEXT DEFAULT '',
        category TEXT NOT NULL,
        symptom TEXT NOT NULL,
        recorded_date TEXT NOT NULL,
        gsd_status TEXT NOT NULL DEFAULT 'open',
        auto_detectable TEXT NOT NULL DEFAULT 'no',
        detection_method TEXT DEFAULT '',
        resolution_status TEXT NOT NULL DEFAULT 'open',
        current_detection TEXT DEFAULT 'na',
        notes TEXT DEFAULT '',
        updated_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS check_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        blog_id TEXT NOT NULL,
        check_name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'unknown',
        detail TEXT DEFAULT '',
        evidence_url TEXT DEFAULT '',
        checked_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

CREATE INDEX IF NOT EXISTS idx_check_blog ON check_results(blog_id);
CREATE INDEX IF NOT EXISTS idx_check_name ON check_results(check_name);
CREATE INDEX IF NOT EXISTS idx_check_time ON check_results(checked_at);

CREATE TABLE IF NOT EXISTS standard_rules (
    rule_id TEXT PRIMARY KEY,
    target TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'MAJOR',
    description TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_standard_rules_target ON standard_rules(target);

-- Phase 60 Part 3: 알림 재설계 테이블
CREATE TABLE IF NOT EXISTS daily_summary_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    summary_date TEXT NOT NULL,
    problem_id TEXT NOT NULL,
    blog_id TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_dse_date ON daily_summary_events(summary_date);

CREATE TABLE IF NOT EXISTS notification_debounce (
    blog_id TEXT NOT NULL,
    problem_id TEXT NOT NULL,
    push_date TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    suppressed_count INTEGER DEFAULT 0,
    PRIMARY KEY (blog_id, problem_id, push_date)
);
""")

    # Phase 60: 기존 테이블에 새 컬럼 추가 (IF NOT EXISTS는 컬럼 추가 안 됨)
    _alter_columns(conn)


# ---------------------------------------------------------------------------
# YAML → blog_lifecycle sync
# ---------------------------------------------------------------------------

def _parse_yaml_file(path: Path) -> list[dict]:
    """간단한 YAML 파서 (pyyaml 없이, blogs.d 형식 전용).

    블로그 항목은 '- key:' 패턴으로 시작하는 항목을 찾아서 파싱한다.
    blog_id는 다음 키에서 추출 (우선순위): id, cf_project, blogger_blog_id,
    blog_id_env(환경변수 이름 → 값은 런타임에 확인 불가하므로 이름 기록).

    지원하는 시작 키:
      - id: compare-hugo          (cap, cuap, etap, rap, tap)
      - cf_project: compare-hugo  (cap, stap)
      - blogger_blog_id: ...      (seap)
      - domain: ...               (manual)
      - blog_id_env: ...          (tap - tvshow-blogger, ud-blogger)
    """
    blogs = []
    current = None
    in_schedule = False

    with open(path) as f:
        for line in f:
            stripped = line.rstrip()

            # 새 블로그 항목 시작: 들여쓰기 없는 '- ' 접두사
            if stripped.startswith("- ") and not stripped.startswith("  "):
                # 새 항목 시작
                if current:
                    blogs.append(current)
                current = {"blog_id": "", "source_file": path.name}
                in_schedule = False

                # 첫 키에서 ID 추출 시도
                after_dash = stripped[2:].strip()  # "- " 제거
                if ":" in after_dash:
                    key, _, val = after_dash.partition(":")
                    key = key.strip()
                    val = val.strip()
                    _assign_id_from_key(current, key, val)
                continue

            if current is None:
                continue

            # 스케줄 블록 내부
            if stripped.startswith("schedule:"):
                in_schedule = True
                continue
            if in_schedule and stripped.startswith("times:"):
                continue
            if in_schedule and stripped.startswith("- "):
                # 스케줄 항목 (무시)
                continue
            if in_schedule and not stripped.startswith(" ") and stripped:
                in_schedule = False

            # 일반 키: 값 파싱
            if ":" not in stripped:
                continue
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()

            if key == "id":
                current["blog_id"] = val
            elif key == "cf_project":
                current["cf_project"] = val
                if not current.get("blog_id"):
                    current["blog_id"] = val
            elif key == "blogger_blog_id":
                current["blog_id"] = current.get("blog_id") or val
            elif key == "blog_id_env":
                current["blog_id_env"] = val
                if not current.get("blog_id"):
                    current["blog_id"] = f"env:{val}"
            elif key == "status":
                current["config_status"] = val
            elif key == "domain":
                current["domain"] = val
            elif key == "site_path":
                current["site_path"] = val
            elif key == "theme":
                current["theme"] = val
            elif key == "pipeline":
                current["pipeline"] = val
            elif key == "daily_quota":
                current["daily_quota"] = val

    if current:
        blogs.append(current)

    return blogs


def _assign_id_from_key(blog: dict, key: str, val: str) -> None:
    """첫 '- key: val' 라인에서 blog_id를 할당."""
    if key == "id":
        blog["blog_id"] = val
    elif key == "cf_project":
        blog["cf_project"] = val
        blog["blog_id"] = val
    elif key == "blogger_blog_id":
        blog["blog_id"] = val
    elif key == "domain":
        blog["domain"] = val
        # domain에서 blog_id 유추 불가 — 나중에 보완
    elif key == "blog_id_env":
        blog["blog_id_env"] = val
        blog["blog_id"] = f"env:{val}"
    else:
        # 알 수 없는 시작 키 — 일단 빈 ID
        pass


def _detect_brand(filename: str) -> str:
    """YAML 파일명에서 계열(brand) 자동 감지 (하드코딩 없음).

    규칙: 파일명 stem의 첫 번째 세그먼트를 brand로 사용.
    예: cap.yaml → cap, cuap.yaml → cuap, manual_blog_for_backup.yaml → manual
    새 YAML 파일(ex: newbrand.yaml) 추가만으로 새 계열이 자동 등록된다.
    """
    stem = filename[:-5] if filename.endswith(".yaml") else filename
    m = re.match(r"^([a-z0-9]+)", stem)
    return m.group(1) if m else stem


def sync_blog_lifecycle(conn: sqlite3.Connection) -> int:
    """YAML 파일을 파싱하여 blog_lifecycle 테이블을 동기화.

    반환: 삽입/업데이트된 행 수.
    """
    count = 0
    for yaml_file in sorted(BLOGS_D.glob("*.yaml")):
        if yaml_file.name.endswith(".bak") or yaml_file.name.startswith("."):
            continue
        brand = _detect_brand(yaml_file.name)
        blogs = _parse_yaml_file(yaml_file)

        for b in blogs:
            blog_id = b.get("blog_id", "")
            if not blog_id:
                continue

            # 기존 레코드 확인
            existing = conn.execute(
                "SELECT blog_id FROM blog_lifecycle WHERE blog_id = ?",
                (blog_id,),
            ).fetchone()

            now = datetime.now(timezone.utc).isoformat()

            if existing:
                conn.execute("""
                    UPDATE blog_lifecycle SET
                        brand = ?,
                        config_status = ?,
                        theme = ?,
                        domain = ?,
                        cf_project = ?,
                        site_path = ?,
                        updated_at = ?
                    WHERE blog_id = ?
                """, (
                    brand,
                    b.get("config_status", b.get("status", "unknown")),
                    b.get("theme", ""),
                    b.get("domain", ""),
                    b.get("cf_project", ""),
                    b.get("site_path", ""),
                    now,
                    blog_id,
                ))
            else:
                conn.execute("""
                    INSERT INTO blog_lifecycle
                    (blog_id, brand, config_status, lifecycle_status,
                     theme, domain, cf_project, site_path, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    blog_id,
                    brand,
                    b.get("config_status", b.get("status", "unknown")),
                    "unknown",
                    b.get("theme", ""),
                    b.get("domain", ""),
                    b.get("cf_project", ""),
                    b.get("site_path", ""),
                    now,
                ))
            count += 1

    # days_since_last_publish 집계 — publish_ledger(content.db)에서 마지막 성공 발행 기준
    _sync_days_since_last_publish(conn)

    conn.commit()
    return count


def _sync_days_since_last_publish(conn: sqlite3.Connection) -> None:
    """blog_lifecycle.days_since_last_publish를 publish_ledger 실데이터로 갱신.

    이전에는 이 컬럼이 항상 NULL(미집계)이라 freshness/stale 지표가 실값을
    반영하지 못했다. 마지막 status='published' 발행일 기준 경과 일수를 기록한다.
    """
    try:
        ledger = get_publish_log_conn()
        rows = ledger.execute("""
            SELECT blog_id, MAX(created_at) AS last
            FROM publish_ledger
            WHERE status = 'published'
            GROUP BY blog_id
        """).fetchall()
        ledger.close()

        now = datetime.now()
        for row in rows:
            try:
                last_dt = datetime.fromisoformat(row["last"])
            except (ValueError, TypeError):
                continue
            days = (now - last_dt).days
            conn.execute(
                "UPDATE blog_lifecycle SET days_since_last_publish = ? WHERE blog_id = ?",
                (days, row["blog_id"]),
            )
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"[sync] days_since_last_publish 집계 실패: {e}")

    conn.commit()


# ---------------------------------------------------------------------------
# Known issues seed
# ---------------------------------------------------------------------------

SEED_ISSUES: list[dict] = [
    # Phase 58 PROBLEM_REGISTRY (24건)
    {"issue_id": "P01", "blog_ids": "", "category": "general", "symptom": "no_result — 데이터 수집 성공이나 가드 차단으로 결과 없음", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "dispatcher reason 카운트"},
    {"issue_id": "P02", "blog_ids": "", "category": "general", "symptom": "no_content — 토픽 소진/중복 가드로 콘텐츠 생성 실패", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "dispatcher reason 카운트"},
    {"issue_id": "P03", "blog_ids": "", "category": "general", "symptom": "similar_title — 유사 제목 80% 초과로 차단", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "title_similar_exists() SequenceMatcher"},
    {"issue_id": "P04", "blog_ids": "", "category": "general", "symptom": "deploy_error — 배포 실패 (Wrangler/CF 인증/Workers)", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "wrangler exit code != 0"},
    {"issue_id": "P05", "blog_ids": "", "category": "general", "symptom": "hugo_build_failed — Hugo 빌드 실패", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "hugo --gc --minify stderr 패턴 매칭"},
    {"issue_id": "P06", "blog_ids": "", "category": "cuap", "symptom": "broken_featureimage — 썸네일 URL 깨짐 (404)", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "post_publish HTTP HEAD 200 확인"},
    {"issue_id": "P07", "blog_ids": "", "category": "general", "symptom": "cjk_leak — CJK 언어 누수 (한자/일본어/중국어)", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "regex + 한글비율 0.5"},
    {"issue_id": "P08", "blog_ids": "", "category": "general", "symptom": "cot_leak — CoT/프롬프트 누수", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "ko_thinking/prompt_instruction_leak 패턴"},
    {"issue_id": "P09", "blog_ids": "", "category": "general", "symptom": "url_token_repeat — 이미지 URL 토큰 반복", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "4자+ 5회+ 반복 패턴 regex"},
    {"issue_id": "P10", "blog_ids": "", "category": "cuap", "symptom": "title_blocked — 제목 차단", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "TITLE_BLOCKED 플래그"},
    {"issue_id": "P11", "blog_ids": "", "category": "cuap", "symptom": "title_regenerate_failed — 제목 재생성 실패", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "_title_gate() return None"},
    {"issue_id": "P12", "blog_ids": "", "category": "cuap", "symptom": "content_quality_gate — 품질 게이트 실패", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "_content_quality_gate() return False"},
    {"issue_id": "P13", "blog_ids": "", "category": "general", "symptom": "rate_limited — API 속도 제한", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "HTTP 429 응답"},
    {"issue_id": "P15", "blog_ids": "", "category": "general", "symptom": "post_publish_validation — 발행 후 검증 실패", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "validate_post_extended() False"},
    {"issue_id": "P17", "blog_ids": "", "category": "general", "symptom": "quota_exceeded — 할당량 초과", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "publish_log 일일 한도"},
    {"issue_id": "P22", "blog_ids": "", "category": "general", "symptom": "llm_fallback_exhausted — LLM 폴백 전체 실패", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "17개 모델 전부 실패"},
    {"issue_id": "P23", "blog_ids": "", "category": "general", "symptom": "image_url_long — 이미지 URL 길이 초과 (255자)", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "URL 길이 > 255자"},

    # 품질 진단 (미해결)
    {"issue_id": "Q1", "blog_ids": "baby-hugo,laptop-hugo,pet-hugo,beauty-hugo", "category": "cuap", "symptom": "experience_claim — 경험/체험 허위 주장 (30%)", "recorded_date": "2026-08-05", "gsd_status": "open", "auto_detectable": "no", "detection_method": "프롬프트 1인칭 금지 지시 미적용"},
    {"issue_id": "Q2", "blog_ids": "beauty-hugo,fitness-hugo,health-hugo", "category": "cuap", "symptom": "unsource_number — 소스 불명 수치 (30%)", "recorded_date": "2026-08-05", "gsd_status": "open", "auto_detectable": "no", "detection_method": "프롬프트 퍼지 표현 필터 미적용"},
    {"issue_id": "Q3", "blog_ids": "beauty-hugo,health-hugo", "category": "cuap", "symptom": "health_efficacy — 건강 효능 단정 (20%, 법적 리스크)", "recorded_date": "2026-08-05", "gsd_status": "open", "auto_detectable": "no", "detection_method": "프롬프트 건강 효능 금지 지시 없음"},
    {"issue_id": "Q4", "blog_ids": "baby-hugo,camping-hugo,pet-hugo", "category": "cuap", "symptom": "template_h2 — 반복 H2 템플릿 구조 (30%)", "recorded_date": "2026-08-05", "gsd_status": "open", "auto_detectable": "no", "detection_method": "프롬프트가 ## N위: 제품명 고정 강제"},
    {"issue_id": "Q5", "blog_ids": "beauty-hugo", "category": "quality", "symptom": "금지어 dead config: quality_checklist.yaml global_forbidden_words 6개 정의되나 writer.py 런타임 미적용", "recorded_date": "2026-08-06", "gsd_status": "resolved", "resolution_status": "resolved", "auto_detectable": "yes", "detection_method": "re.findall(pattern, content) — 좋은(12건), 최고의(4건) 실측", "notes": "[2026-08-06 종료] finance-hugo는 STAP 파이프라인(별도 shared/ai_writer.py, dispatcher STAP_PIPELINE_MAP)이라 CUAP pipelines/curation/writer.py의 Q5 검증 대상 아님 확정. 검증: beauty-hugo dry-run(실 LLM 3,597자, 금지어 잔존 0) + 유닛(주입 6건 전부 치환/제거 ALL_PASS). 커밋 23edc896a. 공백: 실발행 검증은 CUAP 발행 재개 후."},
    {"issue_id": "Q6", "blog_ids": "beauty-hugo", "category": "quality", "symptom": "H2 검증 허점: writer.py가 H2 카운트만 하고 H2>=1 미검증. 옛 TOP5 포맷 잔존글에서 H2=0 발생", "recorded_date": "2026-08-06", "gsd_status": "resolved", "resolution_status": "resolved", "auto_detectable": "yes", "detection_method": "re.findall(r'^## ', content) — H2=0 포스트 1건 실측", "notes": "[2026-08-06 종료] _count_h2() 추가 + 시도당 H2=0 → 재생성 유도(retry) + 최종 명시적 fail(return None, 침묵 통과 방지). 실측: 화장수-추천-top5-2026년 H1=0/H2=0(H3-only). dry-run 실 LLM H2=9, len=4297. 회귀 0 (18 failed/144 passed 동일). 커밋 ed36af514. 공백: 옛 TOP5 H2=0 베이크드 포스트는 기존 발행물 — 재렌더/수동 정리 대상(발행 재개 시)."},

    # 품질 감사 (미해결)
    {"issue_id": "QA-01", "blog_ids": "travel3-hugo", "category": "tap", "symptom": "title_body_region — 제목 '계룡시' vs 본문 '서산시' 지역 불일치", "recorded_date": "2026-08-05", "gsd_status": "open", "auto_detectable": "no", "detection_method": "제목-본문 지역 검증 게이트 미구현"},
    {"issue_id": "QA-02", "blog_ids": "compare-hugo", "category": "cap", "symptom": "irrelevant_coupang — 차량 비교글에 무관 쿠팡 링크", "recorded_date": "2026-08-05", "gsd_status": "open", "auto_detectable": "no", "detection_method": "상품-주제 관련도 필터 미구현"},
    {"issue_id": "QA-03", "blog_ids": "travel2-hugo", "category": "tap", "symptom": "excessive_coupang — 문화유산 글에 쿠팡 18건 과다", "recorded_date": "2026-08-05", "gsd_status": "open", "auto_detectable": "no", "detection_method": "쿠팡 링크 상한(3건) 미설정"},
    {"issue_id": "QA-04", "blog_ids": "hotissue-hugo", "category": "cap", "symptom": "empty_body — 본문 2자 포스트 (RSS 더미)", "recorded_date": "2026-08-05", "gsd_status": "open", "auto_detectable": "yes", "detection_method": "본문 길이 < 100자 검사"},
    {"issue_id": "QA-05", "blog_ids": "travel1-hugo", "category": "tap", "symptom": "title_body_count — 제목 '5곳' vs 본문 3곳 숫자 불일치", "recorded_date": "2026-08-05", "gsd_status": "open", "auto_detectable": "no", "detection_method": "제목-본문 숫자 검증 미구현"},
    {"issue_id": "QA-06", "blog_ids": "travel1-hugo,travel3-hugo", "category": "tap", "symptom": "generic_text — 범용 문장 과다 ('이번 글에서는' 등)", "recorded_date": "2026-08-05", "gsd_status": "open", "auto_detectable": "no", "detection_method": "범용 패턴 카운트 미구현"},

    # 구조적 불균일성
    {"issue_id": "STRUCT-01", "blog_ids": "", "category": "etap", "symptom": "etap_write_hugo — _write_hugo_post() 30+ 파일 중복", "recorded_date": "2026-08-06", "gsd_status": "open", "auto_detectable": "yes", "detection_method": "ETAP *_pipeline.py별 _write_hugo_post 존재 검사"},
    {"issue_id": "STRUCT-02", "blog_ids": "", "category": "general", "symptom": "publisher_token — publisher.py CLOUDFLARE_API_TOKEN 유지 (불일치)", "recorded_date": "2026-08-06", "gsd_status": "open", "auto_detectable": "yes", "detection_method": "grep CLOUDFLARE_API_TOKEN in publisher.py"},
    {"issue_id": "STRUCT-03", "blog_ids": "hotissue-hugo", "category": "cap", "symptom": "theme_mismatch — PaperMod 테마 (Blowfish 통일 기준 위반)", "recorded_date": "2026-08-06", "gsd_status": "open", "auto_detectable": "yes", "detection_method": "YAML theme 필드 != blowfish"},
    {"issue_id": "STRUCT-04", "blog_ids": "stock-hugo", "category": "stap", "symptom": "theme_mismatch — Congo 테마 (Blowfish 통일 기준 위반)", "recorded_date": "2026-08-06", "gsd_status": "open", "auto_detectable": "yes", "detection_method": "YAML theme 필드 != blowfish"},
    {"issue_id": "STRUCT-06", "blog_ids": "flights-hugo", "category": "etap", "symptom": "flights_flight — flights-hugo(YAML/CF) vs flight-hugo(dispatcher) 불일치", "recorded_date": "2026-08-06", "gsd_status": "open", "auto_detectable": "yes", "detection_method": "grep flight-hugo in dispatcher.py vs YAML"},
    {"issue_id": "STRUCT-07", "blog_ids": "beauty-hugo", "category": "structural", "symptom": "publish_ledger title 공백: 발행 성공(published) 시 title=\"\" 45.9%(187/407). ledger 기록 누락", "recorded_date": "2026-08-06", "gsd_status": "open", "auto_detectable": "yes", "detection_method": "SELECT COUNT(*) WHERE title=\"\" AND status=\"published\" — 187/407건"},

    # Phase 60 Part 6: maintenance 체크 (2026-08-06 → 2026-08-07 정정)
    {"issue_id": "STRUCT-08", "blog_ids": "", "category": "structural", "symptom": "M01(CJK 제목) 체크는 content.db/curation.db 직접 연결형으로 이미 구현됨. maintenance_checklist에 fail 기록 가능(예: pet-hugo 과거 CJK 제목). 다만 과거 발행 이력의 CJK 제목이 남아 현재 콘텐츠와 무관하게 fail로 잡힐 수 있어, 현재 발행분 기준 재확인 필요. 초기 보고의 '항상 pass(무력)'는 조회 테이블명 오기로 인한 오보고였으나 코드/실행은 작동 중", "recorded_date": "2026-08-06", "gsd_status": "open", "auto_detectable": "yes", "detection_method": "M01 실행 시 content.db publish_ledger / curation.db publish_log에서 최근 제목 20건 조회 → CJK 정규식 검사 → fail 가능. ops.db maintenance_checklist에 결과 기록됨", "notes": "수정 완료 사항: (1) _check_cjk_in_title은 이미 콘텐츠 DB 직접 연결형. (2) STRUCT-08의 '무력/항상 pass' 설명은 2026-08-07 관측과 불일치 → 현행 동작 기준으로 정정. (3) pet-hugo M01 fail(2026-08-05 智能玩具)은 현재 콘텐츠 210건 기준 CJK 0건 → stale 기록 가능성. 재발 방지를 위해 파이프라인 _validate_title 게이트와 함께 유지."},
    {"issue_id": "STRUCT-09", "blog_ids": "", "category": "structural", "symptom": "M07(similar_title 안전) 체크는 content.db publish_ledger 직접 연결형으로 이미 구현됨. maintenance_checklist에 similar_title fail 기록 가능(예: interior-hugo 8건 등). 초기 보고의 '항상 pass(무력)'는 조회 테이블명 오기로 인한 오보고였으나 코드/실행은 작동 중", "recorded_date": "2026-08-06", "gsd_status": "open", "auto_detectable": "yes", "detection_method": "M07 실행 시 content.db publish_ledger에서 blog_id=? AND status='failed' AND stage='similar_title' AND created_at > datetime('now','-7 days') 카운트 → fail 가능. 결과 maintenance_checklist에 기록됨", "notes": "수정 완료 사항: (1) _check_similar_title_safety는 이미 콘텐츠 DB 직접 연결형. (2) STRUCT-09의 '무력/항상 pass' 설명은 2026-08-07 관측과 불일치 → 현행 동작 기준으로 정정. (3) actual fail이 여러 블로그에서 기록되므로, 해당 블로그의 similar_title 재발 여부를 계속 관찰."},
    {"issue_id": "STRUCT-10", "blog_ids": "finance-hugo", "category": "structural", "symptom": "M09 실패 — finance-hugo 최근 7일 ledger 발행 35건이지만 curation.db publish_log 0건. 기록 누락 의심", "recorded_date": "2026-08-06", "gsd_status": "open", "auto_detectable": "yes", "detection_method": "M09 실행 결과 ledger 발행 35건 vs publish_log 0건", "notes": "M09는 content.db/curation.db 직접 연결로 정상 작동 중. finance-hugo는 publish_log 기록 자체가 없음 — 발행 경로가 curation 파이프라인을 거치지 않거나 기록 로직 누락. 수정 후보: finance-hugo 발행 경로에서 curation publish_log 기록 확인. 실수정은 Part 6 이후 별도 묶음으로 보류"},
    {"issue_id": "STRUCT-11", "blog_ids": "", "category": "structural", "symptom": "idx_ledger_dedup이 non-unique — ledger_sync._ensure_schema는 UNIQUE 기대하나 실제 DB는 CREATE INDEX(비유니크)라 INSERT OR IGNORE가 중복을 못 막음 → run_sync() 호출마다 소스 전체 행 재삽입", "recorded_date": "2026-08-06", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "PRAGMA index_list(publish_ledger) 확인 — idx_ledger_dedup sql에 UNIQUE 없음. 중복 (blog_id,slug,DATE) 그룹 8,414개(선존) + run_sync 재실행 시 재삽입", "notes": "해결(2026-08-06): partial UNIQUE(source != '' 조건부)로 재생성 — CREATE UNIQUE INDEX idx_ledger_dedup ON publish_ledger(blog_id, slug, DATE(created_at), source) WHERE source != ''. source='' 은 레거시 실발행 전량 보존을 위해 인덱스에서 제외. 선존 중복 24,061행(source!='') 정리 완료, source='' 18,301행 보존. 원인은 어제 run_sync 사고가 아니라 1/7부터 non-unique 인덱스로 누적된 반년 묵은 결함이었음(선존 중복은 R2 백업 6/19 최초부터 존재). ledger_sync._ensure_schema의 기대 정의도 partial UNIQUE로 갱신됨. run_sync는 SELECT-존재확인 후 INSERT 이중 가드 유지."},
    {"issue_id": "STRUCT-12", "blog_ids": "", "category": "structural", "symptom": "source='' 실발행 행 내부에 4중 키(blog_id, slug, DATE, source) 레거시 중복 2,935그룹 / 15,177행 존재 — 과거 dispatcher._record_ledger가 같은 글을 여러 번 기록", "recorded_date": "2026-08-06", "gsd_status": "open", "auto_detectable": "yes", "detection_method": "SELECT blog_id,slug,DATE(created_at),source FROM publish_ledger WHERE source='' GROUP BY ... HAVING COUNT(*)>1 — 2,935그룹", "notes": "evidence: adventure-hugo 4/26 (blog_id,'',DATE,'') 3행, 4/27~30 매일 5행. 영향: freshness/발행 카운트 부풀 가능성. 조치 방침: 불변식상 삭제 보류(실발행 유실 0 보장), 카운트 집계 시 DISTINCT 처리 검토. partial UNIQUE(source != '')라 이 중복은 인덱스 충돌 없음 — 관찰용으로 유지."},
    {"issue_id": "STRUCT-13", "blog_ids": "", "category": "structural", "symptom": "백필 오염 — backfill_blank_titles()이 source != '' 일부 행 title을 첫 소스 제목으로 잘못 덮음. 추정 대상 966행(재발행 233 + 다른글 374 + 판정불가 359)", "recorded_date": "2026-08-06", "gsd_status": "open", "auto_detectable": "yes", "detection_method": "(blog_id, DATE, title) 그룹 반복분 조회 — 966행. published_url 비교로 분류", "notes": "evidence: stock-hugo 2026-03-31 id=791(src='5000')/26805(src='stap') 동일 URL 다른 source — 정당한 재발행일 가능성. 미해결 사유: 원본 제목 복원 근거 없음, URL 대리 지표로는 재발행/오염 구분 불완전. 향후: 백필 실행 시점 로그 기반 원본 title 식별 후 정밀 원복. 원복 보류(2026-08-06, 옵션 C). backfill_blank_titles는 run_sync에서 호출 제거됨(재발 방지)."},
    {"issue_id": "STRUCT-14", "blog_ids": "senior-hugo,tour-hugo", "category": "structural", "symptom": "라이브 Hugo 사이트가 git 미관리 — SEAP(senior-hugo)/ETAP(tour-hugo) 디렉토리가 git 저장소 아님. 백업/롤백 수단 부재 → content.db 사고와 동종 위험(되돌릴 수 없는 손실)", "recorded_date": "2026-08-06", "gsd_status": "open", "auto_detectable": "yes", "detection_method": "git -C <site_path> rev-parse --show-toplevel 실패(not a git repository)", "notes": "발견 경위(2026-08-06): R02 config 보강 시 tour-hugo/SEAP senior-hugo 커밋 시도 → git 저장소 아님 확인. CAP 블로그 5개는 각자 독립 git 저장소(정상), informationhot-hugo도 git 저장소(정상). senior-hugo는 active/재개 대상이라 우선순위 높음 — git init + 최초 백업 커밋 필요. tour-hugo(ETAP)는 비활성이라 후순위 메모만. 배포는 wrangler Pages라 파일시스템 상태가 라이브 사이트와 직접 연결 — git 미관리 시 되돌리기 불가."},

    {"issue_id": "STRUCT-15", "blog_ids": "informationhot-hugo", "category": "structural", "symptom": "Publisher ID 이중 관리 — extend-head.html 로더 JS에 ca-pub-6677996696534146 하드코딩 + params.toml(advertisement.adsense) 이중 정의. 값은 informationhot 계열에 맞아 광고 정상이나, 계열 변경 시 불일치 위험", "recorded_date": "2026-08-06", "gsd_status": "open", "auto_detectable": "yes", "detection_method": "R03 검사 — extend-head에 하드코딩 ca-pub- 감지 (standard.py)", "notes": "발견 경위(2026-08-06): R03(CRITICAL) fail — R02에서 params.toml로 처리했으나 로더 스크립트에 하드코딩 잔존. 조치 방침: 리팩토링 단계에서 로더를 site.Params 기반으로 단일화. 지금 수정 안 함(값 정상, 광고 실작동 중). AGENTS.md 섹션 1 Publisher ID 매핑 준수 확인: 6677 = informationhot 계열 정상."},
    {"issue_id": "STRUCT-16", "blog_ids": "pick-hugo,appliance-hugo,baby-hugo,beauty-hugo,bike-hugo,camping-hugo,car-hugo,fitness-hugo,golf-hugo,health-hugo,homeappliance-hugo,interior-hugo,kitchen-hugo,laptop-hugo,massage-hugo,pet-hugo,informationhot-hugo,senior-hugo,finance-hugo", "category": "structural", "symptom": "R06 조사 완료 — in-article.html data-ad-format이 대부분 auto (19개: cap7/cuap15/rap5/seap1/stap5). ADSENSE-GUIDE 표준은 fluid인데 콘솔 슬롯 형식 미확인 → 수정 시 광고 깨질 위험", "recorded_date": "2026-08-06", "gsd_status": "open", "auto_detectable": "yes", "detection_method": "R06 검사 — in-article.html data-ad-format != fluid 감지 (standard.py)", "notes": "조사 결과(2026-08-06, 커밋 C 4단계): tap 계열 5개만 fluid(정상), 나머지 19개 auto. 수정 보류 사유: 실제 AdSense 콘솔 슬롯 형식(fluid/in-article vs auto) 교차 확인 전까지 실수정 금지 — 슬롯이 auto로 생성된 경우 fluid로 바꾸면 광고 형식 불일치. 콘솔 확인 후 별건 처리(STRUCT-16 참조)."},
    {"issue_id": "STRUCT-17", "blog_ids": "pick-hugo,bike-hugo,car-hugo,golf-hugo,homeappliance-hugo,interior-hugo,massage-hugo,rotcha-blog,senior-hugo,informationhot-hugo", "category": "structural", "symptom": "R04 GA4 태그 부재 10개 — extend_head.html에 GA4(gtag) 없음. AdSense 표준이 아닌 Analytics 사안으로 정상화 게이트와 무관", "recorded_date": "2026-08-06", "gsd_status": "open", "auto_detectable": "yes", "detection_method": "R04 검사 — extend_head.html에 gtag/GA4/google-analytics 부재 감지 (standard.py)", "notes": "발견 경위(2026-08-06, 커밋 C 4단계 재실행): R04(MAJOR) fail 10개. GA4는 트래픽 분석용으로 AdSense 수익과 직접 무관. 정상화 대상 25개 중 10개에 영향(정상화 게이트에는 미반영 — 준비도는 standard_compliance pass 기준이라 사실상 fail 요인). 조치 방침: 별도 작업으로 이관, 이번 커밋 C에서 처리 안 함."},
    {"issue_id": "STRUCT-18", "blog_ids": "", "category": "structural", "symptom": "gsd_crosscheck pass↔fail 플래핑 — detected 판정 프록시가 '블로그에 fail 체크 1개라도 존재'라 일시 fail 소멸 시 전역 이슈(blog_ids='')가 미감지 처리됨. readiness fail_total 왜곡, 준비도 신뢰성 저해", "recorded_date": "2026-08-06", "gsd_status": "open", "resolution_status": "open", "auto_detectable": "no", "detection_method": "manual — travel1-hugo gsd_crosscheck 06:03 pass → 13:19 pass → 15:11 fail → 15:12 pass → 15:23 fail 플래핑 실측", "notes": "실측(2026-08-06): tap/travel1~3/tvshow/ud 6곳 일시 +fail — 본 세션 커밋(INC-CL/Q5/Q6)과 무관. 근본: crosscheck.py가 '최신 fail 체크 존재'를 detected로 판정 + STRUCT-01/02/08/09/11~13 등 blog_ids='' 전역 이슈가 모든 블로그에 적용 → 블로그의 일시 fail이 사라지면 전역 이슈 전부 '미감지' 처리 → fail. 개선: 감지 프록시를 체크명별 매핑(auto-detectable 이슈 ↔ 담당 체크명)으로 전환 필요. 구조 변경 수반이라 Q6 다음 작업 후보로 보류. auto_detectable=no — 등록해도 crosscheck 결과에 영향 없음(메모 성격)."},

    # Triage 해결 이슈 (대표적 10건)
    {"issue_id": "T-04", "blog_ids": "tap-blogger", "category": "tap", "symptom": "tap_meta_response — 메타 응답 발행 (해결됨)", "recorded_date": "2026-07-26", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "validators.py 메타 패턴 매칭"},
    {"issue_id": "T-07", "blog_ids": "kitchen-hugo", "category": "cuap", "symptom": "kitchen_blank_body — 모바일 본문 공백 (해결됨)", "recorded_date": "2026-07-21", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "모바일 뷰포트 본문 공백 확인"},
    {"issue_id": "T-14", "blog_ids": "kuta-hugo", "category": "cap", "symptom": "kuta_broken_thumbnail — WordPress 도메인 경로 404 (해결됨)", "recorded_date": "2026-07-11", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "HTTP HEAD 200 확인"},
    {"issue_id": "T-16", "blog_ids": "appliance-hugo", "category": "cuap", "symptom": "file_name_too_long — 이미지 URL 300자 초과 (해결됨)", "recorded_date": "2026-07-09", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "URL 길이 > 255자 검사"},

    # Incident (AGENTS.md)
    {"issue_id": "INC-01", "blog_ids": "travel2-hugo", "category": "tap", "symptom": "no_result_10 — 시군구 가드 연속 10회 실패 (해결됨)", "recorded_date": "2026-07-11", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "dispatcher reason 카운트"},
    {"issue_id": "INC-03", "blog_ids": "appliance-hugo", "category": "cuap", "symptom": "similar_title — 듀스핀 키워드 유사 제목 반복 (해결됨)", "recorded_date": "2026-07-11", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "SequenceMatcher 80%"},
    {"issue_id": "INC-04", "blog_ids": "laptop-hugo", "category": "cuap", "symptom": "deploy_error_image_url — 이미지 URL 255자 초과→빌드 실패 (해결됨)", "recorded_date": "2026-07-11", "gsd_status": "resolved", "auto_detectable": "yes", "detection_method": "URL 길이 검사"},

    # 무관 크로스링크 (2026-08-06) — 코드 fixed(7e2bd2312), 기존 발행 포스트 정리 대기
    {"issue_id": "INC-CL-01", "blog_ids": "camping-hugo", "category": "cuap", "symptom": "무관 크로스링크: camping→baby 15건 (funnel-header fallback). 코드 fixed(7e2bd2312) — 신규 생성 차단됨. 기존 발행 15건 잔존 → 재개 시 재렌더로 정리.", "recorded_date": "2026-08-06", "gsd_status": "open", "auto_detectable": "yes", "detection_method": "M03 crosslink_consistency: 15/795 링크가 CROSS_GRAPH 밖", "notes": "신규 생성은 필터로 차단됨. 기존 발행 포스트 무관 링크 잔존 → 해당 블로그 재개 시 재렌더로 정리."},
    {"issue_id": "INC-CL-02", "blog_ids": "health-hugo", "category": "cuap", "symptom": "무관 크로스링크: health→camping 12건 (cross-sell-card fallback). 코드 fixed(7e2bd2312) — 신규 생성 차단됨. 기존 발행 12건 잔존 → 재개 시 재렌더로 정리.", "recorded_date": "2026-08-06", "gsd_status": "open", "auto_detectable": "yes", "detection_method": "M03 crosslink_consistency: 12/838 링크가 CROSS_GRAPH 밖", "notes": "신규 생성은 필터로 차단됨. 기존 발행 포스트 무관 링크 잔존 → 해당 블로그 재개 시 재렌더로 정리."},
    {"issue_id": "INC-CL-03", "blog_ids": "laptop-hugo", "category": "cuap", "symptom": "무관 크로스링크: laptop→kitchen 32건 (funnel 30 + cross-sell 2). 코드 fixed(7e2bd2312) — 신규 생성 차단됨. 기존 발행 32건 잔존 → 재개 시 재렌더로 정리.", "recorded_date": "2026-08-06", "gsd_status": "open", "auto_detectable": "yes", "detection_method": "M03 crosslink_consistency: 32/713 링크가 CROSS_GRAPH 밖", "notes": "신규 생성은 필터로 차단됨. 기존 발행 포스트 무관 링크 잔존 → 해당 블로그 재개 시 재렌더로 정리."},
    {"issue_id": "INC-CL-04", "blog_ids": "pet-hugo", "category": "cuap", "symptom": "무관 크로스링크: pet→beauty 15건 (funnel-header fallback). 코드 fixed(7e2bd2312) — 신규 생성 차단됨. 기존 발행 15건 잔존 → 재개 시 재렌더로 정리.", "recorded_date": "2026-08-06", "gsd_status": "open", "auto_detectable": "yes", "detection_method": "M03 crosslink_consistency: 15/677 링크가 CROSS_GRAPH 밖", "notes": "신규 생성은 필터로 차단됨. 기존 발행 포스트 무관 링크 잔존 → 해당 블로그 재개 시 재렌더로 정리."},
]


def seed_known_issues(conn: sqlite3.Connection) -> int:
    """known_issues 테이블에 GSD 이슈를 시드.

    반환: 삽입된 행 수 (기존과 중복된 것은 무시).
    """
    count = 0
    now = datetime.now(timezone.utc).isoformat()
    for issue in SEED_ISSUES:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO known_issues
                (issue_id, blog_ids, category, symptom, recorded_date,
                 gsd_status, auto_detectable, detection_method,
                 resolution_status, current_detection, updated_at, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                issue["issue_id"],
                issue.get("blog_ids", ""),
                issue["category"],
                issue["symptom"],
                issue["recorded_date"],
                issue["gsd_status"],
                issue["auto_detectable"],
                issue.get("detection_method", ""),
                issue["gsd_status"],  # resolution_status = gsd_status 초기값
                "na",
                now,
                issue.get("notes", ""),
            ))
            count += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    return count


# ---------------------------------------------------------------------------
# Standard rules seed
# ---------------------------------------------------------------------------

SEED_STANDARD_RULES: list[dict] = [
    {"rule_id": "R01", "target": "hugo.toml", "severity": "CRITICAL", "description": "showTableOfContents must be false"},
    {"rule_id": "R02", "target": "hugo.toml", "severity": "CRITICAL", "description": "Advertisement section with adsense slots required"},
    {"rule_id": "R03", "target": "extend-head.html", "severity": "CRITICAL", "description": "adsbygoogle.js must use site.Params (no hardcoding)"},
    {"rule_id": "R04", "target": "extend_head.html", "severity": "MAJOR", "description": "GA4 + mobile correction CSS required"},
    {"rule_id": "R05", "target": "adsense/top.html", "severity": "MAJOR", "description": "overflow:hidden;min-height:100px wrapper + outside push div"},
    {"rule_id": "R06", "target": "adsense/in-article.html", "severity": "CRITICAL", "description": "fluid+in-article format (no auto) + outside push div"},
    {"rule_id": "R07", "target": "single.html", "severity": "MAJOR", "description": "H2 split injection + prose wrapper"},
    {"rule_id": "R08", "target": "single.html", "severity": "MAJOR", "description": "Description (lead) must be removed"},
    {"rule_id": "R09", "target": "baseof.html", "severity": "MAJOR", "description": "No custom override — use theme default"},
    {"rule_id": "R10", "target": "custom.css", "severity": "MAJOR", "description": "Unfilled space removal + dark mode + min-height rules"},
    {"rule_id": "R11", "target": "layouts/", "severity": "MAJOR", "description": "mobile-sticky.html must not be used"},
    {"rule_id": "R12", "target": "layouts/", "severity": "MAJOR", "description": "No override files beyond the allowed set"},

    # C01~C08: 콘텐츠 무결성·누수 규칙 (Phase 62)
    {"rule_id": "C01", "target": "frontmatter", "severity": "MAJOR",
     "description": "프론트매터 내 곡선따옴표(\u2018 \u2019 \u201c \u201d) 사용 금지 — YAML 값(타이틀·description·카테고리·태그 등)에 직선따옴표(' \"') 아닌 곡선따옴표 포함 시 위반"},
    {"rule_id": "C02", "target": "frontmatter", "severity": "CRITICAL",
     "description": "프론트매터 미종료 — 첫 --- 이후 두 번째 --- 존재하지 않음 (전체 --- 홀수 카운트 판정 금지, 첫--- 이후 두 번째--- 존재 여부로만 판정)"},
    {"rule_id": "C03", "target": "body", "severity": "MAJOR",
     "description": "본문에 프론트매터 키 라인 유출 — title:, og_image:, featureimage:, date:, slug: 등 프론트매터 키 라인과 유사한 라인이 본문에 존재"},
    {"rule_id": "C04", "target": "body", "severity": "CRITICAL",
     "description": "본문에 LLM 프롬프트/사고문 누수 — 'Need think', 'We need to write', 'Let's think step by step', '먼저', '생각해보자' 등 LLM 지시 복술 흔적"},
    {"rule_id": "C05", "target": "frontmatter+publish", "severity": "CRITICAL",
     "description": "draft:true 발행 대상 — frontmatter에 draft: true가 설정되어 있는데 발행 파이프라인이 이를 발행 대상으로 처리"},
    {"rule_id": "C06", "target": "file+deploy", "severity": "MAJOR",
     "description": "로컬 mtime > 배포 시각 — 로컬 파일의 mtime이 마지막 배포 시각보다 최신 (배포 후 로컬에서 파일 수정된 상태)"},
    {"rule_id": "C07", "target": "body+cross-sell", "severity": "MAJOR",
     "description": "죽은 크로스셀 링크 — 크로스셀 카드가 가리키는 대상 slug가 DB에 published=0이거나 라이브에서 HTTP 404"},
    {"rule_id": "C08", "target": "live+file", "severity": "CRITICAL",
     "description": "라이브-파일 불일치 — 라이브 프런트와 로컬 파일 간 불일치 (제목 빔, og_image 유출 등)"},
    {"rule_id": "C09", "target": "frontmatter", "severity": "CRITICAL",
     "description": "categories/tags 문자열화 — YAML 배열이 아닌 문자열 리터럴 \"['추천']\" 형태로 저장되어 Hugo range .Params.categories/tags 실패 (type=list 정상, type=str + [...] 패턴 위반)"},
]


def seed_standard_rules(conn: sqlite3.Connection) -> int:
    """standard_rules 테이블에 R01~R12 규칙을 시드.

    반환: 삽입된 행 수 (기존과 중복된 것은 무시).
    """
    count = 0
    for rule in SEED_STANDARD_RULES:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO standard_rules
                (rule_id, target, severity, description)
                VALUES (?, ?, ?, ?)
            """, (rule["rule_id"], rule["target"], rule["severity"], rule["description"]))
            count += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    return count


# ---------------------------------------------------------------------------
# Maintenance status seed — Phase 60 Part 2
# ---------------------------------------------------------------------------

MAINTENANCE_SEED_BLOGS: list[dict] = [
    # P03으로 차단된 CUAP 블로그 + SEAP/TAP 정비 대상
    # CAP 블로그(pick-hugo)는 제외 — M03/M06이 CUAP 전용이라 항상 unknown
    {"blog_id": "beauty-hugo", "maintenance_status": "awaiting"},
    {"blog_id": "interior-hugo", "maintenance_status": "awaiting"},
    {"blog_id": "kitchen-hugo", "maintenance_status": "awaiting"},
    {"blog_id": "senior-hugo", "maintenance_status": "awaiting"},
    {"blog_id": "senior-blogger", "maintenance_status": "awaiting"},
    {"blog_id": "travel4-hugo", "maintenance_status": "awaiting"},
]


def seed_maintenance_status(conn: sqlite3.Connection) -> int:
    """정비 대상 블로그에 maintenance_status를 시드.

    반환: 업데이트된 행 수.
    """
    count = 0
    for item in MAINTENANCE_SEED_BLOGS:
        try:
            conn.execute("""
                UPDATE blog_lifecycle
                SET maintenance_status = ?
                WHERE blog_id = ? AND maintenance_status = 'none'
            """, (item["maintenance_status"], item["blog_id"]))
            count += conn.total_changes
        except sqlite3.OperationalError:
            pass
    conn.commit()
    return count


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 정비 체크리스트 — Phase 60 Part 2 표준
# ---------------------------------------------------------------------------

MAINTENANCE_CHECKLIST_ITEMS: list[dict] = [
    #CUAP/RAP 정비 경험에서 추출한 표준 항목
    {"check_id": "M01", "name": "제목 CJK 없음", "description": "제목에 한자/일본어/중국어 누수 없음"},
    {"check_id": "M02", "name": "이미지 정상 (동일 반복 없음)", "description": "썸네일/본문 이미지가 동일 이미지를 반복 사용하지 않음"},
    {"check_id": "M03", "name": "크로스링크 주제 일관", "description": "내부 링크가 블로그 주제와 무관하지 않음"},
    {"check_id": "M04", "name": "본문 품질 게이트 통과", "description": "Q1~Q4 품질 이슈 없음 (허위 경험, 소스불명 수치, 건강효능 단정, 템플릿 반복)"},
    {"check_id": "M05", "name": "표준 (광고/테마) 준수", "description": "R01~R12 표준 규칙 모두 통과"},
    {"check_id": "M06", "name": "토픽/키워드 잔량 충분", "description": "active 키워드 100개 이상, 7일 내 사용 키워드 30% 미만"},
    {"check_id": "M07", "name": "P03 유사제목 안전", "description": "최근 3일 내 발행 제목과 유사한 제목이 파이프라인에서 생성되지 않음"},
    {"check_id": "M08", "name": "CoT/프롬프트 누수 없음", "description": "본문에 사고 과정(CoT)이나 프롬프트 문구 누수 없음"},
    {"check_id": "M09", "name": "publish_log 기록 정상", "description": "발행 성공 시 publish_log에 기록이 정상적으로 남음"},
    {"check_id": "M10", "name": "도메인 가용성", "description": "HTTP HEAD 200 정상 응답"},
]


def init_maintenance_checklist(conn: sqlite3.Connection, blog_id: str) -> None:
    """특정 블로그의 정비 체크리스트 항목을 초기화."""
    for item in MAINTENANCE_CHECKLIST_ITEMS:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO maintenance_checklist
                (blog_id, check_id, check_name, status)
                VALUES (?, ?, ?, 'pending')
            """, (blog_id, item["check_id"], item["name"]))
        except sqlite3.IntegrityError:
            pass
    conn.commit()


def get_maintenance_checklist(conn: sqlite3.Connection, blog_id: str) -> list[dict]:
    """특정 블로그의 정비 체크리스트 조회."""
    rows = conn.execute("""
        SELECT * FROM maintenance_checklist
        WHERE blog_id = ? ORDER BY check_id
    """, (blog_id,)).fetchall()
    return [dict(r) for r in rows]


def get_maintenance_summary(conn: sqlite3.Connection) -> dict:
    """전체 블로그별 정비 진행 상황 요약."""
    rows = conn.execute("""
        SELECT
            bl.blog_id,
            bl.brand,
            bl.maintenance_status,
            bl.resume_ready,
            bl.config_status,
            COUNT(CASE WHEN mc.status = 'pass' THEN 1 END) as pass_count,
            COUNT(CASE WHEN mc.status = 'fail' THEN 1 END) as fail_count,
            COUNT(CASE WHEN mc.status = 'pending' THEN 1 END) as pending_count,
            COUNT(*) as total_checks
        FROM blog_lifecycle bl
        LEFT JOIN maintenance_checklist mc ON bl.blog_id = mc.blog_id
        WHERE bl.maintenance_status != 'none'
        GROUP BY bl.blog_id
        ORDER BY bl.brand, bl.blog_id
    """).fetchall()
    return [dict(r) for r in rows]


def set_check_item_status(
    conn: sqlite3.Connection,
    blog_id: str,
    check_id: str,
    status: str,
    detail: str = "",
) -> None:
    """정비 체크리스트 항목 상태 업데이트."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        UPDATE maintenance_checklist
        SET status = ?, detail = ?, checked_at = ?
        WHERE blog_id = ? AND check_id = ?
    """, (status, detail, now, blog_id, check_id))
    conn.commit()


def update_maintenance_status(
    conn: sqlite3.Connection,
    blog_id: str,
    maintenance_status: str,
) -> None:
    """블로그의 정비 상태 업데이트."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    fields = {"maintenance_status": maintenance_status}
    if maintenance_status == "in_progress":
        fields["maintenance_started_at"] = now
    elif maintenance_status == "ready":
        fields["maintenance_completed_at"] = now
        fields["resume_ready"] = 1
    elif maintenance_status == "none":
        fields["resume_ready"] = 0

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [blog_id]
    conn.execute(f"UPDATE blog_lifecycle SET {set_clause} WHERE blog_id = ?", values)
    conn.commit()


def get_all_blogs(conn: sqlite3.Connection) -> list[dict]:
    """blog_lifecycle 전체 조회.

    Fleet Status 표의 소스. 표준준수 fail 정보를 후처리로 보충해
    quality_grade / quality_fail_count / failed_rule_ids 를 함께 반환한다
    (DB write 없음, 조회 단계 계산).
    """
    rows = conn.execute(
        "SELECT * FROM blog_lifecycle ORDER BY brand, blog_id"
    ).fetchall()
    blogs = [dict(r) for r in rows]

    # 최신 standard_compliance fail 행 dict(blog_id -> dict)
    sc_latest: dict[str, dict] = {}
    for row in conn.execute("""
        SELECT cr.blog_id, cr.detail, cr.checked_at
        FROM check_results cr
        INNER JOIN (
            SELECT blog_id, MAX(checked_at) as latest
            FROM check_results
            WHERE check_name = 'standard_compliance'
            GROUP BY blog_id
        ) latest ON cr.blog_id = latest.blog_id AND cr.checked_at = latest.latest
        WHERE cr.check_name = 'standard_compliance'
    """).fetchall():
        sc_latest[row["blog_id"]] = dict(row)

    for b in blogs:
        bid = b.get("blog_id")
        sc = sc_latest.get(bid)
        if not sc:
            b["quality_grade"] = ""
            b["quality_fail_count"] = 0
            b["failed_rule_ids"] = []
            continue
        rule_ids = _parse_failed_rule_ids(sc.get("detail") or "")
        b["failed_rule_ids"] = rule_ids
        b["quality_fail_count"] = len(rule_ids)
        b["quality_grade"] = _quality_grade_from_rule_ids(rule_ids)

    return blogs


_RULE_ID_RE = re.compile(r"\bR\d{2}\b(?=\()")  # R04(MAJOR) → R04
_RULES_FAILED_RE = re.compile(
    r"(\d+)/\d+\s+rules failed:\s*(.+)$", re.DOTALL
)  # "2/14 rules failed: R04(...); R12(...)"

def _parse_failed_rule_ids(detail: str) -> list[str]:
    """표준준수 aggregate detail 문자열에서 실패한 rule_id 목록을 추출.

    형식 기대값:
        "N/M rules failed: R04(MAJOR): desc; R08(MAJOR): desc; R12(MAJOR): desc"
    안전 원칙:
        - "N/M rules failed:" 패턴이 있을 때만 표준 fail 상세로 간주
        - 파싱 실패·매칭 없으면 빈 리스트 반환 (배지 없음, 기존 detail 유지)
        - 패턴에 없으면 rule_id가 존재해도 만들어내지 않음
    """
    if not detail:
        return []
    try:
        # 표준 fail 상세는 반드시 "N/M rules failed:" 구문을 포함함
        if not _RULES_FAILED_RE.search(detail):
            return []
        return _RULE_ID_RE.findall(detail)
    except Exception:
        return []


def _quality_grade_from_rule_ids(rule_ids: list[str]) -> str:
    """표준준수 fail rule_id 개수 기반 품질 등급(A/B/C)."""
    n = len(rule_ids)
    if n == 0:
        return "A"
    if n <= 2:
        return "B"
    return "C"


def get_attention_items(conn: sqlite3.Connection) -> dict:
    """주의 필요 항목: fail/stale check_results + open known_issues.

    fail_checks: 운영 블로그(config_status='active', maintenance_status!='paused')의
    최신 fail 체크만 포함.
    excluded_fail_checks: 비운영/제외 대상 블로그의 fail 체크 (별도 집계).

    반환 dict에는 표준준수 fail 행에 한해 failed_rule_ids(list[str])가 포함된다
    (UI에서 rule_id 배지 펼침을 위해 파싱한 값. 파싱 실패 시 빈 리스트).
    """
    # 1) 최근 실패한 헬스체크 (블로그 라이프사이클 정보 포함)
    rows = conn.execute("""
        SELECT cr.blog_id, cr.check_name, cr.status, cr.detail, cr.evidence_url, cr.checked_at,
               cr.rule_id, cr.problem_id, cr.severity, cr.action,
               bl.config_status, bl.maintenance_status
        FROM check_results cr
        LEFT JOIN blog_lifecycle bl ON cr.blog_id = bl.blog_id
        INNER JOIN (
            SELECT blog_id, check_name, MAX(checked_at) as latest
            FROM check_results GROUP BY blog_id, check_name
        ) latest ON cr.blog_id = latest.blog_id
            AND cr.check_name = latest.check_name
            AND cr.checked_at = latest.latest
        WHERE cr.status = 'fail'
        ORDER BY cr.checked_at DESC
    """).fetchall()

    # W6a.1 (Phase 69): aggregate+individual dual-write 중복 병합.
    # W3가 개별 규칙행(check_name=rule_id, 예: 'R06')과 aggregate 행
    # (check_name='standard_compliance')을 함께 기록하므로, 동일 블로그의
    # standard_compliance 계열이 auto_triage에서 이중 집계된다. 여기서
    # (blog, check_name) 단위로 aggregate+individual을 하나의 fail_check로
    # 병합한다 — 개별 행이 있으면 그 rule_id를 구조 필드로 채택(구조 분류),
    # 없으면 기존대로 빈 값(자유텍스트 폴백)으로 유지.
    fail_checks = []
    excluded_fail_checks = []

    # c06_mtime_deploy는 fail이 아닌 INFO/참고 버킷으로 분리 (C.6 룩북 확정)
    info_checks: list[dict] = []

    def _is_std_family(r):
        # standard_compliance 계열: aggregate(check_name='standard_compliance')
        # 또는 개별 규칙 행(check_name == rule_id, 예: 'R06').
        return r["check_name"] == "standard_compliance" or (
            bool(r["rule_id"]) and r["check_name"] == r["rule_id"]
        )

    # (blog_id → 최신 실패 행) 그룹핑 후 standard_compliance 계열 병합.
    _by_blog: dict[str, list] = {}
    for r in rows:
        _by_blog.setdefault(r["blog_id"], []).append(r)

    for blog_id, brs in _by_blog.items():
        cfg = brs[0]["config_status"]
        maint = brs[0]["maintenance_status"]
        family = [r for r in brs if _is_std_family(r)]
        others = [dict(r) for r in brs if not _is_std_family(r)]

        entries = others
        if family:
            agg = next((r for r in family if r["check_name"] == "standard_compliance"), None)
            ind = [r for r in family if r["check_name"] != "standard_compliance"]
            base = agg if agg is not None else ind[0]
            rid = ind[0]["rule_id"] if ind else None  # 개별 행이 있으면 rule_id 채택
            sev = ind[0]["severity"] if ind else base["severity"]
            act = ind[0]["action"] if ind else base["action"]
            detail = (agg["detail"] if agg is not None
                      else "; ".join(f"{i['rule_id']}: {i['detail']}" for i in ind))
            entries.append({
                "blog_id": blog_id,
                "check_name": "standard_compliance",
                "status": "fail",
                "detail": detail,
                "evidence_url": (agg or ind[0])["evidence_url"],
                "checked_at": max(r["checked_at"] for r in family),
                "rule_id": rid,
                "problem_id": (agg or ind[0])["problem_id"],
                "severity": sev,
                "action": act,
                "failed_rule_ids": _parse_failed_rule_ids(detail),
            })

        for d in entries:
            # c06_mtime_deploy는 fail이 아닌 INFO/참고 버킷으로 분리 (C.6 룩북 확정)
            if d.get("check_name") == "c06_mtime_deploy":
                info_checks.append(d)
            # 운영 중이고 paused가 아니면 fail_checks에 포함
            elif cfg == "active" and maint != "paused":
                fail_checks.append(d)
            else:
                d["config_status"] = cfg
                d["maintenance_status"] = maint
                excluded_fail_checks.append(d)

    # standard_compliance가 아닌 행에는 failed_rule_ids를 붙이지 않음 (기존 표시 유지)
    for d in fail_checks + excluded_fail_checks:
        if d.get("check_name") != "standard_compliance":
            d.pop("failed_rule_ids", None)

    # 2) 미해결 known_issues (변경 없음)
    open_issues = conn.execute("""
        SELECT * FROM known_issues
        WHERE gsd_status = 'open'
        ORDER BY category, issue_id
    """).fetchall()

    # 3) publish_error_events의 open 이벤트도 attention에 포함 (P04 등 post_deploy 오류)
    pe_rows = conn.execute("""
        SELECT pe.blog_id, pe.problem_id, pe.stage, pe.state, pe.detail_redacted, pe.occurred_at,
               bl.config_status, bl.maintenance_status
        FROM publish_error_events pe
        LEFT JOIN blog_lifecycle bl ON pe.blog_id = bl.blog_id
        INNER JOIN (
            SELECT blog_id, problem_id, MAX(occurred_at) as latest
            FROM publish_error_events
            WHERE state = 'open'
            GROUP BY blog_id, problem_id
        ) latest ON pe.blog_id = latest.blog_id
            AND pe.problem_id = latest.problem_id
            AND pe.occurred_at = latest.latest
        WHERE pe.state = 'open'
        ORDER BY pe.occurred_at DESC
    """).fetchall()

    for pe in pe_rows:
        cfg = pe["config_status"] or "active"
        maint = pe["maintenance_status"] or "none"
        entry = {
            "blog_id": pe["blog_id"],
            "check_name": "publish_error",
            "status": pe["state"],
            "detail": f"{pe['problem_id']}: {pe['stage']} — {pe['detail_redacted'] or ''}".strip(),
            "evidence_url": "",
            "checked_at": pe["occurred_at"],
            "rule_id": "",
            "problem_id": pe["problem_id"],
            "severity": "CRITICAL" if pe["problem_id"] in ("P04", "P05", "P06", "P07", "P08", "P09", "P29") else "MAJOR",
            "action": "",
            "failed_rule_ids": [],
        }
        if cfg == "active" and maint != "paused":
            fail_checks.append(entry)
        else:
            entry["config_status"] = cfg
            entry["maintenance_status"] = maint
            excluded_fail_checks.append(entry)

    # 4) stale 블로그 (active 한정, 변경 없음)
    stale = conn.execute("""
        SELECT blog_id, days_since_last_publish, lifecycle_status
        FROM blog_lifecycle
        WHERE config_status = 'active'
          AND (
              days_since_last_publish IS NULL
              OR days_since_last_publish > 3
          )
        ORDER BY days_since_last_publish DESC
    """).fetchall()

    return {
        "fail_checks": fail_checks,
        "excluded_fail_checks": excluded_fail_checks,
        "info_checks": info_checks,
        "open_issues": [dict(r) for r in open_issues],
        "stale_blogs": [dict(r) for r in stale],
    }


def get_blog_detail(conn: sqlite3.Connection, blog_id: str) -> dict | None:
    """특정 블로그의 전체 정보 + 최근 헬스체크 + 관련 이슈."""
    import sqlite3 as _sqlite3
    old_factory = conn.row_factory
    conn.row_factory = _sqlite3.Row
    try:
        blog = conn.execute(
            "SELECT * FROM blog_lifecycle WHERE blog_id = ?", (blog_id,)
        ).fetchone()
        if not blog:
            return None
        blog_dict = dict(blog)

        checks = conn.execute("""
            SELECT * FROM check_results
            WHERE blog_id = ?
            ORDER BY checked_at DESC
            LIMIT 50
        """, (blog_id,)).fetchall()
        checks_list = [dict(r) for r in checks]

        issues = conn.execute("""
            SELECT * FROM known_issues
            WHERE blog_ids LIKE ?
            ORDER BY issue_id
        """, (f"%{blog_id}%",)).fetchall()
        issues_list = [dict(r) for r in issues]

        return {
            "blog": blog_dict,
            "checks": checks_list,
            "issues": issues_list,
        }
    finally:
        conn.row_factory = old_factory


def record_check(
    conn: sqlite3.Connection,
    blog_id: str,
    check_name: str,
    status: str,
    detail: str = "",
    evidence_url: str = "",
    rule_id: str | None = None,
    problem_id: str | None = None,
    severity: str | None = None,
    action: str | None = None,
) -> None:
    """헬스체크 결과를 기록.

    Phase 69 W2: rule_id/problem_id/severity/action 선택 파라미터는 기본값 None —
    기존 호출(새 인자 없이)은 그대로 동작하고, 새 파라미터가 주어지면 해당 컬럼에 기록한다.

    UPSERT: 동일 (blog_id, check_name)의 기존 행을 먼저 삭제 후 INSERT하여
    재검사 시마다 행이 누적되는 것을 방지한다 (웨이브3).
    checked_at은 Python local time ISO 8601로 기록 (SQLite UTC 아님).
    """
    from datetime import datetime
    now_iso = datetime.now().isoformat()
    conn.execute("""
        DELETE FROM check_results WHERE blog_id = ? AND check_name = ?
    """, (blog_id, check_name))
    conn.execute("""
        INSERT INTO check_results
            (blog_id, check_name, status, detail, evidence_url,
             rule_id, problem_id, severity, action, checked_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (blog_id, check_name, status, detail, evidence_url,
          rule_id, problem_id, severity, action, now_iso))
    conn.commit()


def record_check_rule(
    conn: sqlite3.Connection,
    blog_id: str,
    rule_id: str,
    status: str,
    severity: str,
    action: str,
    detail: str = "",
    evidence_url: str = "",
) -> None:
    """개별 규칙 실패 1건을 개별 행으로 기록 (Phase 69 W3 — dual-write).

    aggregate 행(standard_compliance, rule_id NULL)과 구분되도록 check_name을 rule_id 값으로
    기록하고, rule_id/severity/action 컬럼을 채운다. 기존 aggregate·detail 자유텍스트는
    그대로 유지된다 (개별행은 추가만).
    """
    record_check(
        conn,
        blog_id,
        check_name=rule_id,      # 개별행 check_name = rule_id (aggregate와 구분)
        status=status,
        detail=detail,
        evidence_url=evidence_url,
        rule_id=rule_id,
        problem_id=None,
        severity=severity,
        action=action,
    )


def replace_triage_classifications(
    conn: sqlite3.Connection,
    run_id: str,
    rows: list[dict],
) -> None:
    """auto-triage 분류 결과를 run_id로 묶어 '최신 1회분만' 유지 (Phase 69 W4.5).

    dry-run 여부와 무관하게 DB 기록 동작은 확인 가능해야 한다는 사용자 요구를
    유지하면서, 반복 실행 시 누적되는 것을 차단한다. 기존 기록(이전 run 포함,
    run_id 미기재 레거시 행 포함)을 먼저 전부 삭제한 뒤 현재 run 행만 삽입하므로
    프로덕션 triage_classifications에는 항상 '최신 run의 1회분'만 존재한다.

    rows: [{problem_id, severity, target, action, source, detail, classification}, ...]
    실패 시 예외를 던져 조용한 실패를 방지한다 (호출부에서 텔레그램/JSON 경로와 격리).
    """
    conn.execute("DELETE FROM triage_classifications")
    for row in rows:
        conn.execute("""
            INSERT INTO triage_classifications
                (run_id, problem_id, severity, target, action, source, detail, classification)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id,
            row.get("problem_id", ""),
            row.get("severity", ""),
            row.get("target", ""),
            row.get("action", ""),
            row.get("source", ""),
            row.get("detail", ""),
            row.get("classification", ""),
        ))
    conn.commit()


def get_registry_view(conn: sqlite3.Connection, blog_id: str | None = None) -> dict:
    """단일 엔드포인트 /api/registry용 통합 뷰 (Phase 69 W5-3).

    규칙(개별 R 행 + registry 선언)과 오류분류(triage_classifications 최신 +
    registry error 선언)를 **동일 스키마**로 노출한다. B7의 6필드(id/kind/target/
    status/severity/action/evidence) 한계를 넘어 rule_id/problem_id 구조 필드까지
    포함한다.

    **경로 Y (자연어 detail 문자열만 존재)**: check_standard_compliance는 통과한
    규칙의 개별 행을 생성하지 않으므로, R01~R11 등 통과 규칙이 UI상 unknown으로
    보이는 문제가 있었다. 또한 stale fail 행이 남아있으면 실제 현재는 pass인데도
    fail로 표시된다.

    이 수정:
      1. blog_id 파라미터 지원 — 해당 블로그의 check_results만 대상으로 함.
         api_registry가 ?blog_id=xxx를 받으면 그 블로그 기준으로 필터링.
      2. 최신 standard_compliance aggregate 행의 detail을 파싱해, 통과한 규칙은
         pass로, 실패한 규칙은 fail로 표시한다. 파싱 실패·애매한 경우 현행 폴백
         (row status 또는 unknown)을 유지해 fail을 pass로 오판하지 않는다.
      3. check_results 데이터에는 write하지 않는다 (SELECT-only).

    반환:
        {"rules": [entry...], "errors": [entry...]}
    각 entry 스키마:
        id, kind, target, status, severity, action, evidence,
        rule_id, problem_id, bucket, threshold, playbook_ref
    playbook_ref: 플레이북 위치 (예: "ERROR_PLAYBOOKS.md#p01"). P 코드는
        shared/problem_registry.py의 ProblemSpec.playbook_ref를 따르고,
        R 코드는 ERROR_PLAYBOOKS.md#{rule_id 소문자}로 구성한다.
    """
    import re as _re
    from ops_dashboard.registry import by_kind

    _RULE_ID_RE = _re.compile(r"\bR\d{2}\b(?=\()")       # R04(MAJOR) → R04
    _ALL_PASS_RE = _re.compile(r"^All\s+\d+\s+rules passed$")  # All 14 rules passed
    _RULES_FAILED_RE = _re.compile(
        r"(\d+)/\d+\s+rules failed:\s*(.+)$", _re.DOTALL
    )  # "2/14 rules failed: R04(...); R12(...)"

    def _parse_failed_rule_ids(detail: str) -> set[str]:
        """detail 문자열에서 실패한 rule_id 집합 추출.

        형식: 'N/M rules failed: R04(MAJOR): desc; R12(MAJOR): desc'
        safety: 파싱 실패 시 빈 집합 반환 → 호출 측에서 pass 승격을 하지 않음.
        """
        if not detail:
            return set()
        try:
            m = _RULES_FAILED_RE.search(detail)
            if not m or not m.group(2):
                return set()
            return set(_RULE_ID_RE.findall(m.group(2)))
        except Exception:
            return set()

    def _determine_rule_status_from_aggregate(rule_id: str, sc_row: dict) -> str | None:
        """표준준수 aggregate 기준으로 특정 rule_id의 상태 결정.

        반환:
            "pass"  — aggregate가 pass이고 rule_id가 통과로 판단됨
            "fail"  — aggregate가 fail이고 rule_id가 실패 목록에 있음
            None    — 결정 불가 (폴백으로 넘김)
        """
        if not sc_row:
            return None
        status = sc_row.get("status", "")
        detail = sc_row.get("detail", "")

        # case 1: 전체 통과
        if status == "pass" and _ALL_PASS_RE.match(detail):
            return "pass"

        # case 2: 실패 있음 — rule_id가 실패 목록에 있으면 fail, 없으면 pass
        if status == "fail":
            failed_ids = _parse_failed_rule_ids(detail)
            if failed_ids:
                if rule_id in failed_ids:
                    return "fail"
                # 실패 목록에 없는 rule_id → 통과한 것으로 판단 → pass
                return "pass"
            # 파싱 실패 (failed_ids 빈 집합) → 확실하지 않음 → 폴백
            return None

        # status unknown 등 기타 → 폴백
        return None

    def _rule_evidence(rule_id: str, row: dict | None, determined: str | None) -> str:
        """rule별 evidence 문자열.

        aggregate로 상태가 결정됐으면 rule별 행이 없을 수 있으므로,
        그 경우 aggregate detail을 축약해 사용.
        """
        if row:
            return row.get("evidence_url") or row.get("detail") or ""
        # 행 없음 + aggregate 판정됨 → aggregate 정보 축약
        if determined == "pass":
            return "표준준수 aggregate 통과 (개별 행 없음)"
        return ""

    def _rule_entry(e, row, sc_row=None):
        determined = _determine_rule_status_from_aggregate(e.id, sc_row)
        playbook_ref = f"ERROR_PLAYBOOKS.md#{e.id.lower()}"
        if determined is not None:
            # aggregate 기준으로 상태 결정 (경로 Y)
            return {
                "id": e.id,
                "kind": "rule",
                "target": e.target,
                "status": determined,
                "severity": e.severity,
                "action": e.action,
                "evidence": _rule_evidence(e.id, row, determined),
                "rule_id": e.id,
                "problem_id": "",
                "bucket": e.bucket,
                "threshold": e.threshold,
                "playbook_ref": playbook_ref,
            }
        # 폴백: 기존 로직 (확정된 개별 행이 있으면 그 status, 없으면 unknown)
        return {
            "id": e.id,
            "kind": "rule",
            "target": e.target,
            "status": row["status"] if row else "unknown",
            "severity": e.severity,
            "action": e.action,
            "evidence": (row["evidence_url"] or row["detail"] or "") if row else "",
            "rule_id": e.id,
            "problem_id": "",
            "bucket": e.bucket,
            "threshold": e.threshold,
            "playbook_ref": playbook_ref,
        }

    def _error_entry(e, row, blog_id=None):
        spec = lookup_problem(e.id)
        playbook_ref = spec.playbook_ref if spec else ""
        # triage_classifications에서 classification 우선 사용
        if row and row["classification"]:
            return {
                "id": e.id,
                "kind": "error",
                "target": e.target or (row["target"] if row else ""),
                "status": row["classification"],
                "severity": row["severity"] if row and row["severity"] else e.severity,
                "action": row["action"] if row and row["action"] else e.action,
                "evidence": (row["detail"] or row["source"] or "") if row else "",
                "rule_id": "",
                "problem_id": e.id,
                "bucket": "",
                "threshold": e.threshold,
                "playbook_ref": playbook_ref,
            }
        # triage_classifications 없으면 publish_error_events에서 최신 open 이벤트 상태 사용
        pe_row = conn.execute(
            "SELECT state, detail_redacted, occurred_at FROM publish_error_events "
            "WHERE problem_id = ? AND state = 'open' "
            f"{'AND blog_id = ?' if blog_id else ''} "
            "ORDER BY occurred_at DESC LIMIT 1",
            (e.id, blog_id) if blog_id else (e.id,),
        ).fetchone()
        if pe_row:
            return {
                "id": e.id,
                "kind": "error",
                "target": e.target or "",
                "status": pe_row["state"],
                "severity": e.severity,
                "action": e.action,
                "evidence": pe_row["detail_redacted"] or "",
                "rule_id": "",
                "problem_id": e.id,
                "bucket": "",
                "threshold": e.threshold,
                "playbook_ref": playbook_ref,
            }
        return {
            "id": e.id,
            "kind": "error",
            "target": e.target or "",
            "status": "unknown",
            "severity": e.severity,
            "action": e.action,
            "evidence": "",
            "rule_id": "",
            "problem_id": e.id,
            "bucket": "",
            "threshold": e.threshold,
            "playbook_ref": playbook_ref,
        }

    # blog_id 필터용 WHERE 절 접미사
    blog_filter = ""
    if blog_id:
        blog_filter = " AND blog_id = ?"
        _blog_id_param = (blog_id,)
    else:
        _blog_id_param = ()

    def _latest_check(check_name: str) -> dict | None:
        sql = (
            f"SELECT status, detail, evidence_url FROM check_results "
            f"WHERE check_name = ?{blog_filter} "
            f"ORDER BY checked_at DESC LIMIT 1"
        )
        params = (check_name,) + _blog_id_param if blog_filter else (check_name,)
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    # standard_compliance aggregate 최신 1행 미리 조회 (모든 rule에 공통 사용)
    sc_row = _latest_check("standard_compliance")

    rules = []
    for e in by_kind("rule"):
        row = _latest_check(e.id)
        rules.append(_rule_entry(e, row, sc_row))

    errors = []
    for e in by_kind("error"):
        # triage_classifications는 blog_id 필터 대상 아님 (전역 분류 테이블)
        row = conn.execute(
            "SELECT classification, severity, action, target, source, detail "
            "FROM triage_classifications WHERE problem_id = ? "
            "ORDER BY classified_at DESC LIMIT 1",
            (e.id,),
        ).fetchone()
        errors.append(_error_entry(e, row, blog_id=blog_id))

    return {"rules": rules, "errors": errors}




def get_daily_summary(conn: sqlite3.Connection, summary_date: str | None = None) -> dict:
    """일일 알림 요약 데이터 조회 (API + 템플릿용)."""
    from datetime import datetime as _dt
    if summary_date is None:
        summary_date = _dt.now().strftime("%Y-%m-%d")

    rows = conn.execute(
        "SELECT problem_id, blog_id, SUM(count) as cnt "
        "FROM daily_summary_events WHERE summary_date = ? "
        "GROUP BY problem_id, blog_id ORDER BY cnt DESC",
        (summary_date,),
    ).fetchall()

    breakdown: dict[str, int] = {}
    blog_by_problem: dict[str, list[str]] = {}
    total = 0
    for problem_id, blog_id, cnt in rows:
        breakdown[problem_id] = breakdown.get(problem_id, 0) + cnt
        blog_by_problem.setdefault(problem_id, []).append(blog_id)
        total += cnt

    debounce_rows = conn.execute(
        "SELECT blog_id, problem_id, suppressed_count "
        "FROM notification_debounce WHERE push_date = ? "
        "ORDER BY suppressed_count DESC",
        (summary_date,),
    ).fetchall()
    suppressed = sum(r["suppressed_count"] for r in debounce_rows)

    return {
        "date": summary_date,
        "total_events": total,
        "total_suppressed": suppressed,
        "breakdown": breakdown,
        "blog_by_problem": blog_by_problem,
        "debounce_events": [dict(r) for r in debounce_rows],
    }


# ---------------------------------------------------------------------------
# Part 5: DB 접근 함수 통일 (인라인 SQL 제거)
# ---------------------------------------------------------------------------

def get_blog_count(conn: sqlite3.Connection) -> int:
    """전체 블로그 수 조회."""
    row = conn.execute("SELECT COUNT(*) FROM blog_lifecycle").fetchone()
    return row[0] if row else 0


def get_blog_by_id(conn: sqlite3.Connection, blog_id: str) -> dict | None:
    """blog_id로 블로그 상세 조회."""
    row = conn.execute(
        "SELECT * FROM blog_lifecycle WHERE blog_id = ?", (blog_id,)
    ).fetchone()
    return dict(row) if row else None


def get_blogs_by_brand(conn: sqlite3.Connection, brand: str) -> list[dict]:
    """계열(brand)별 블로그 조회."""
    rows = conn.execute(
        "SELECT * FROM blog_lifecycle WHERE brand = ? ORDER BY blog_id", (brand,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_active_blogs(conn: sqlite3.Connection) -> list[dict]:
    """active 상태 블로그만 조회."""
    rows = conn.execute(
        "SELECT * FROM blog_lifecycle WHERE config_status = 'active' ORDER BY brand, blog_id"
    ).fetchall()
    return [dict(r) for r in rows]


def get_blogs_with_site_path(conn: sqlite3.Connection) -> list[dict]:
    """site_path가 있는 블로그 조회 (체크용)."""
    rows = conn.execute(
        "SELECT * FROM blog_lifecycle WHERE site_path != '' AND site_path IS NOT NULL ORDER BY brand, blog_id"
    ).fetchall()
    return [dict(r) for r in rows]


def get_maintenance_blogs(conn: sqlite3.Connection) -> list[dict]:
    """정비 대상 블로그 조회."""
    rows = conn.execute(
        "SELECT * FROM blog_lifecycle WHERE maintenance_status != 'none' ORDER BY brand, blog_id"
    ).fetchall()
    return [dict(r) for r in rows]


def get_blog_site_path(conn: sqlite3.Connection, blog_id: str) -> str | None:
    """블로그의 site_path 조회."""
    row = conn.execute(
        "SELECT site_path FROM blog_lifecycle WHERE blog_id = ?", (blog_id,)
    ).fetchone()
    return row["site_path"] if row else None


def get_blog_domain(conn: sqlite3.Connection, blog_id: str) -> str | None:
    """블로그의 도메인 조회."""
    row = conn.execute(
        "SELECT domain FROM blog_lifecycle WHERE blog_id = ?", (blog_id,)
    ).fetchone()
    return row["domain"] if row else None


def get_blog_pipeline_path(conn: sqlite3.Connection, blog_id: str) -> str | None:
    """블로그의 pipeline_path 조회."""
    row = conn.execute(
        "SELECT pipeline_path FROM blog_lifecycle WHERE blog_id = ?", (blog_id,)
    ).fetchone()
    return row["pipeline_path"] if row else None


def get_blog_brand(conn: sqlite3.Connection, blog_id: str) -> str | None:
    """블로그의 계열(brand) 조회."""
    row = conn.execute(
        "SELECT brand FROM blog_lifecycle WHERE blog_id = ?", (blog_id,)
    ).fetchone()
    return row["brand"] if row else None


def get_blog_config_status(conn: sqlite3.Connection, blog_id: str) -> str | None:
    """블로그의 config_status 조회."""
    row = conn.execute(
        "SELECT config_status FROM blog_lifecycle WHERE blog_id = ?", (blog_id,)
    ).fetchone()
    return row["config_status"] if row else None


def get_blog_days_since_last_publish(conn: sqlite3.Connection, blog_id: str) -> int | None:
    """블로그의 마지막 발행 후 경과일 조회."""
    row = conn.execute(
        "SELECT days_since_last_publish FROM blog_lifecycle WHERE blog_id = ?", (blog_id,)
    ).fetchone()
    return row["days_since_last_publish"] if row else None


def get_blog_maintenance_status(conn: sqlite3.Connection, blog_id: str) -> str | None:
    """블로그의 정비 상태(maintenance_status) 조회."""
    row = conn.execute(
        "SELECT maintenance_status FROM blog_lifecycle WHERE blog_id = ?", (blog_id,)
    ).fetchone()
    return row["maintenance_status"] if row else None


def get_check_results_for_blog(conn: sqlite3.Connection, blog_id: str, limit: int = 50) -> list[dict]:
    """블로그별 헬스체크 결과 조회 (최신순)."""
    rows = conn.execute("""
        SELECT * FROM check_results
        WHERE blog_id = ?
        ORDER BY checked_at DESC
        LIMIT ?
    """, (blog_id, limit)).fetchall()
    return [dict(r) for r in rows]


def get_latest_check_result(conn: sqlite3.Connection, blog_id: str, check_name: str) -> dict | None:
    """블로그의 특정 체크 최신 결과 조회."""
    row = conn.execute("""
        SELECT * FROM check_results
        WHERE blog_id = ? AND check_name = ?
        ORDER BY checked_at DESC
        LIMIT 1
    """, (blog_id, check_name)).fetchone()
    return dict(row) if row else None


def get_fail_checks_for_blog(conn: sqlite3.Connection, blog_id: str) -> list[dict]:
    """블로그의 실패한 체크 조회."""
    rows = conn.execute("""
        SELECT cr.* FROM check_results cr
        INNER JOIN (
            SELECT blog_id, check_name, MAX(checked_at) as latest
            FROM check_results WHERE blog_id = ? GROUP BY blog_id, check_name
        ) latest ON cr.blog_id = latest.blog_id
            AND cr.check_name = latest.check_name
            AND cr.checked_at = latest.latest
        WHERE cr.status = 'fail'
        ORDER BY cr.checked_at DESC
    """, (blog_id,)).fetchall()
    return [dict(r) for r in rows]


def get_check_results_summary(conn: sqlite3.Connection) -> dict:
    """전체 체크 결과 요약."""
    rows = conn.execute("""
        SELECT status, COUNT(*) as cnt
        FROM check_results
        GROUP BY status
    """).fetchall()
    return {row["status"]: row["cnt"] for row in rows}


# 체크 유형별 심각도 (5-4 필터용)
CHECK_SEVERITY: dict[str, str] = {
    "standard_compliance": "CRITICAL",
    "crosslink_consistency": "CRITICAL",
    "cjk_leak": "CRITICAL",
    "gsd_crosscheck": "MAJOR",
    "freshness": "MAJOR",
    "render_health": "MAJOR",
    "maintenance_checklist": "MINOR",
}

# 심각도 우선순위 (내림차순)
_SEVERITY_ORDER = {"CRITICAL": 3, "MAJOR": 2, "MINOR": 1}


def get_attention_blogs(
    conn: sqlite3.Connection,
    brand: str | None = None,
    check_name: str | None = None,
    severity: str | None = None,
) -> list[dict]:
    """주의 필요 블로그 목록: 최신 check_results에서 fail인 블로그.

    필터:
      - brand: 계열 (cap/cuap/etap 등)
      - check_name: 체크 유형 (standard_compliance 등)
      - severity: 심각도 (CRITICAL/MAJOR/MINOR)
    반환: 각 블로그당 최신 fail 체크 목록 (블로그 중복 가능, 정렬은 심각도 우선)
    """
    sql = """
        SELECT cr.blog_id, cr.check_name, cr.status, cr.detail,
               cr.evidence_url, cr.checked_at,
               bl.brand, bl.config_status, bl.maintenance_status
        FROM check_results cr
        INNER JOIN (
            SELECT blog_id, check_name, MAX(checked_at) as latest
            FROM check_results GROUP BY blog_id, check_name
        ) latest ON cr.blog_id = latest.blog_id
            AND cr.check_name = latest.check_name
            AND cr.checked_at = latest.latest
        LEFT JOIN blog_lifecycle bl ON bl.blog_id = cr.blog_id
        WHERE cr.status = 'fail'
        AND cr.check_name != 'c06_mtime_deploy'
        AND bl.config_status = 'active'
        AND (bl.maintenance_status IS NULL OR bl.maintenance_status != 'paused')
    """
    params: list = []
    if brand:
        sql += " AND bl.brand = ?"
        params.append(brand)
    if check_name:
        sql += " AND cr.check_name = ?"
        params.append(check_name)
    if severity:
        # severity로 지정된 check_name들만
        names = [k for k, v in CHECK_SEVERITY.items() if v == severity]
        if names:
            placeholders = ",".join("?" * len(names))
            sql += f" AND cr.check_name IN ({placeholders})"
            params.extend(names)
        else:
            return []
    sql += " ORDER BY cr.checked_at DESC"

    rows = conn.execute(sql, params).fetchall()
    items = []
    for r in rows:
        d = dict(r)
        d["severity"] = CHECK_SEVERITY.get(d["check_name"], "MAJOR")
        items.append(d)
    # 심각도 우선 정렬
    items.sort(key=lambda x: _SEVERITY_ORDER.get(x["severity"], 0), reverse=True)

    # UI 배지 펼침을 위해 표준준수 fail 행에만 failed_rule_ids 보충.
    # (get_attention_items와 동일 파서·재사용, 안전 폴백 포함)
    for d in items:
        if d.get("check_name") == "standard_compliance":
            d["failed_rule_ids"] = _parse_failed_rule_ids(d.get("detail") or "")

    # Fleet Status Quality 등급용 필드 보충은 별도 함수(get_all_blogs 보강)에서 수행.
    return items


def get_attention_blogs_aggregate(
    conn: sqlite3.Connection,
) -> dict:
    """주의 필요 블로그 집계: 전체 대비 주의 블로그 수, 필터 옵션 목록."""
    items = get_attention_blogs(conn)
    blog_ids = {i["blog_id"] for i in items}

    # 브랜드 분포
    brands: dict[str, int] = {}
    for i in items:
        brand = i.get("brand") or "unknown"
        brands[brand] = brands.get(brand, 0) + 1

    # 체크 유형 분포
    check_names: dict[str, int] = {}
    for i in items:
        cn = i["check_name"]
        check_names[cn] = check_names.get(cn, 0) + 1

    # 심각도 분포
    severities: dict[str, int] = {}
    for i in items:
        sev = i["severity"]
        severities[sev] = severities.get(sev, 0) + 1

    # 전체 옵션 목록 (필터링용 드롭다운 — 전체 데이터 기준으로 표시)
    # all_brands: blog_lifecycle 기준 전체 블로그 수 per brand
    all_brands: dict[str, int] = {}
    for row in conn.execute(
        "SELECT brand, COUNT(*) as cnt FROM blog_lifecycle GROUP BY brand ORDER BY cnt DESC"
    ).fetchall():
        all_brands[row["brand"]] = row["cnt"]

    # all_check_names: check_results 전체 기준 체크 유형별 total 건수
    all_check_names: dict[str, int] = {}
    for row in conn.execute(
        "SELECT check_name, COUNT(*) as cnt FROM check_results GROUP BY check_name ORDER BY cnt DESC"
    ).fetchall():
        all_check_names[row["check_name"]] = row["cnt"]

    # all_severities: check_results 전체 fail 기준 심각도별 총 건수
    #   CHECK_SEVERITY는 check_name→severity 매핑이므로,
    #   실제 fail 결과의 severity 분포를 직접 집계한다.
    all_severities: dict[str, int] = {}
    for row in conn.execute(
        "SELECT severity, COUNT(*) as cnt FROM check_results "
        "WHERE status='fail' AND severity IS NOT NULL AND severity != '' "
        "GROUP BY severity ORDER BY cnt DESC"
    ).fetchall():
        all_severities[row["severity"]] = row["cnt"]

    return {
        "total_blogs": len(blog_ids),
        "total_items": len(items),
        "blog_ids": sorted(blog_ids),
        "brands": brands,
        "check_names": check_names,
        "severities": severities,
        "all_brands": all_brands,
        "all_check_names": all_check_names,
        "all_severities": all_severities,
    }


def get_known_issues_for_blog(conn: sqlite3.Connection, blog_id: str) -> list[dict]:
    """블로그 관련 known_issues 조회."""
    rows = conn.execute("""
        SELECT * FROM known_issues
        WHERE blog_ids LIKE ? OR blog_ids = ''
        ORDER BY category, issue_id
    """, (f"%{blog_id}%",)).fetchall()
    return [dict(r) for r in rows]


def get_auto_detectable_issues_for_blog(conn: sqlite3.Connection, blog_id: str) -> list[dict]:
    """블로그 관련 auto_detectable known_issues 조회."""
    rows = conn.execute("""
        SELECT issue_id, symptom, blog_ids
        FROM known_issues
        WHERE auto_detectable = 'yes'
          AND gsd_status = 'open'
          AND (blog_ids LIKE ? OR blog_ids = '')
        ORDER BY category, issue_id
    """, (f"%{blog_id}%",)).fetchall()
    return [dict(r) for r in rows]


def get_recent_fail_check_results(conn: sqlite3.Connection, blog_id: str, check_name: str, since_days: int = 7) -> list[dict]:
    """최근 N일간 특정 체크의 fail 결과 조회."""
    from datetime import datetime, timedelta
    since = (datetime.now() - timedelta(days=since_days)).isoformat()
    rows = conn.execute("""
        SELECT * FROM check_results
        WHERE blog_id = ? AND check_name = ? AND status = 'fail'
          AND checked_at >= ?
        ORDER BY checked_at DESC
    """, (blog_id, check_name, since)).fetchall()
    return [dict(r) for r in rows]


def get_recent_publish_logs(conn: sqlite3.Connection, blog_id: str, limit: int = 20, table: str = "publish_log") -> list[dict]:
    """최근 발행 로그 조회 (publish_log 또는 publish_ledger)."""
    try:
        rows = conn.execute(f"""
            SELECT * FROM {table}
            WHERE blog_id = ? AND title IS NOT NULL AND title != ''
            ORDER BY published_at DESC
            LIMIT ?
        """, (blog_id, limit)).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []


def get_known_issues_by_category(conn: sqlite3.Connection, category: str) -> list[dict]:
    """카테고리별 known_issues 조회."""
    rows = conn.execute("""
        SELECT * FROM known_issues
        WHERE category = ?
        ORDER BY issue_id
    """, (category,)).fetchall()
    return [dict(r) for r in rows]


def get_open_known_issues(conn: sqlite3.Connection) -> list[dict]:
    """미해결 known_issues 조회."""
    rows = conn.execute("""
        SELECT * FROM known_issues
        WHERE gsd_status = 'open'
        ORDER BY category, issue_id
    """).fetchall()
    return [dict(r) for r in rows]


def get_stale_blogs(conn: sqlite3.Connection, threshold_days: int = 3) -> list[dict]:
    """stale 블로그 조회 (active인데 오래된 발행 또는 발행 기록 없음)."""
    rows = conn.execute("""
        SELECT blog_id, days_since_last_publish, lifecycle_status
        FROM blog_lifecycle
        WHERE config_status = 'active'
          AND (
              days_since_last_publish IS NULL
              OR days_since_last_publish > ?
          )
        ORDER BY days_since_last_publish DESC
    """, (threshold_days,)).fetchall()
    return [dict(r) for r in rows]


def get_maintenance_checklist_items() -> list[dict]:
    """정비 체크리스트 항목 반환 (static)."""
    return MAINTENANCE_CHECKLIST_ITEMS


def record_check_item_status(
    conn: sqlite3.Connection,
    blog_id: str,
    check_id: str,
    status: str,
    detail: str = "",
) -> None:
    """정비 체크리스트 항목 상태 업데이트 (기존 set_check_item_status 래퍼)."""
    set_check_item_status(conn, blog_id, check_id, status, detail)


def init_check_rollups_table(conn: sqlite3.Connection) -> None:
    """check_rollups 테이블 생성 (Part 5: 롤업 정책)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS check_rollups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rollup_date TEXT NOT NULL,
            blog_id TEXT NOT NULL,
            check_name TEXT NOT NULL,
            pass_count INTEGER NOT NULL DEFAULT 0,
            fail_count INTEGER NOT NULL DEFAULT 0,
            unknown_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(rollup_date, blog_id, check_name)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rollup_date ON check_rollups(rollup_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rollup_blog ON check_rollups(blog_id)")
    conn.commit()


def rollup_check_results(conn: sqlite3.Connection, rollup_date: str | None = None) -> int:
    """일별 check_results를 check_rollups로 집계.
    
    반환: 생성/업데이트된 롤업 행 수.
    """
    from datetime import datetime as _dt
    if rollup_date is None:
        rollup_date = _dt.now().strftime("%Y-%m-%d")

    init_check_rollups_table(conn)

    rows = conn.execute("""
        SELECT blog_id, check_name,
               SUM(CASE WHEN status = 'pass' THEN 1 ELSE 0 END) as pass_count,
               SUM(CASE WHEN status = 'fail' THEN 1 ELSE 0 END) as fail_count,
               SUM(CASE WHEN status = 'unknown' THEN 1 ELSE 0 END) as unknown_count
        FROM check_results
        WHERE date(checked_at) = ?
        GROUP BY blog_id, check_name
    """, (rollup_date,)).fetchall()

    count = 0
    for r in rows:
        conn.execute("""
            INSERT OR REPLACE INTO check_rollups
            (rollup_date, blog_id, check_name, pass_count, fail_count, unknown_count)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (rollup_date, r["blog_id"], r["check_name"],
              r["pass_count"], r["fail_count"], r["unknown_count"]))
        count += 1

    conn.commit()
    return count


def cleanup_old_check_results(conn: sqlite3.Connection, keep_days: int = 30) -> int:
    """N일 이전 check_results 원시 데이터 삭제 (롤업 완료 후).
    
    반환: 삭제된 행 수.
    """
    from datetime import datetime, timedelta
    cutoff = (datetime.now() - timedelta(days=keep_days)).strftime("%Y-%m-%d")
    
    # 롤업이 존재하는 날짜만 삭제 (롤업 후 안전 삭제)
    cursor = conn.execute("""
        DELETE FROM check_results
        WHERE date(checked_at) < ?
          AND date(checked_at) IN (
              SELECT rollup_date FROM check_rollups
          )
    """, (cutoff,))
    deleted = cursor.rowcount
    conn.commit()
    return deleted


def get_check_rollups(conn: sqlite3.Connection, blog_id: str | None = None, days: int = 30) -> list[dict]:
    """롤업 데이터 조회."""
    from datetime import datetime, timedelta
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    if blog_id:
        rows = conn.execute("""
            SELECT * FROM check_rollups
            WHERE blog_id = ? AND rollup_date >= ?
            ORDER BY rollup_date DESC, check_name
        """, (blog_id, since)).fetchall()
    else:
        rows = conn.execute("""
            SELECT * FROM check_rollups
            WHERE rollup_date >= ?
            ORDER BY rollup_date DESC, blog_id, check_name
        """, (since,)).fetchall()
    return [dict(r) for r in rows]


def get_brands(conn: sqlite3.Connection) -> list[str]:
    """등록된 모든 계열(brand) 조회."""
    rows = conn.execute("""
        SELECT DISTINCT brand FROM blog_lifecycle
        ORDER BY brand
    """).fetchall()
    return [r["brand"] for r in rows]


def get_blog_ids_by_brand(conn: sqlite3.Connection, brand: str) -> list[str]:
    """계열별 blog_id 리스트 조회."""
    rows = conn.execute("""
        SELECT blog_id FROM blog_lifecycle
        WHERE brand = ? ORDER BY blog_id
    """, (brand,)).fetchall()
    return [r["blog_id"] for r in rows]


def discover_yaml_files() -> list[Path]:
    """config/blogs.d/*.yaml 파일 자동 발견."""
    return sorted(BLOGS_D.glob("*.yaml"))


def get_brand_from_yaml_filename(filename: str) -> str:
    """YAML 파일명에서 계열(brand) 자동 감지 (하드코딩 없음).

    규칙: 파일명 stem의 첫 번째 세그먼트를 brand로 사용.
    예: cap.yaml → cap, manual_blog_for_backup.yaml → manual
    새 YAML 파일 추가만으로 새 계열이 자동 등록된다.
    """
    return _detect_brand(filename)


def get_all_yaml_blog_ids(conn: sqlite3.Connection) -> list[str]:
    """YAML 파일에서 파싱된 모든 blog_id 조회."""
    blog_ids = []
    for yaml_file in discover_yaml_files():
        if yaml_file.name.endswith(".bak") or yaml_file.name.startswith("."):
            continue
        blogs = _parse_yaml_file(yaml_file)
        for b in blogs:
            blog_id = b.get("blog_id", "")
            if blog_id:
                blog_ids.append(blog_id)
    return blog_ids


# ---------------------------------------------------------------------------
# External DB access (content.db, stap_content.db, etc.)
# ---------------------------------------------------------------------------

def get_publish_log_conn():
    """publish_log DB 연결 (content.db)."""
    from shared.paths import FIVEK_ROOT
    import sqlite3
    path = str(Path(FIVEK_ROOT) / "data" / "content.db")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def get_stap_content_conn():
    """stap_content DB 연결 (stap_content.db)."""
    from shared.paths import FIVEK_ROOT
    import sqlite3
    path = str(Path(FIVEK_ROOT) / "data" / "stap_content.db")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def get_publish_ledger_blog_ids(conn) -> list[str]:
    """publish_ledger에 존재하는 모든 blog_id 조회."""
    rows = conn.execute(
        "SELECT DISTINCT blog_id FROM publish_ledger ORDER BY blog_id"
    ).fetchall()
    return [r["blog_id"] for r in rows]


def get_publish_ledger_total(conn, blog_id: str) -> int:
    """블로그의 전체 발행 기록 수."""
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM publish_ledger WHERE blog_id = ?", (blog_id,)
    ).fetchone()
    return row["cnt"]


def get_publish_ledger_last_success(conn, blog_id: str) -> str | None:
    """블로그의 마지막 성공 발행 시각."""
    row = conn.execute(
        "SELECT MAX(created_at) AS last FROM publish_ledger"
        " WHERE blog_id = ? AND status = 'published'",
        (blog_id,),
    ).fetchone()
    return row["last"]


def get_publish_ledger_counts_since(conn, blog_id: str, since: str) -> dict:
    """특정 시각 이후 published/failed 건수."""
    row = conn.execute(
        """SELECT
            SUM(CASE WHEN status='published' THEN 1 ELSE 0 END) as pub,
            SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as fail
        FROM publish_ledger WHERE blog_id = ? AND created_at >= ?""",
        (blog_id, since),
    ).fetchone()
    return {"pub": row["pub"] or 0, "fail": row["fail"] or 0}


def get_publish_ledger_fail_count(
    conn, blog_id: str, since: str, before: str | None = None
) -> int:
    """특정 기간 실패 건수."""
    if before is None:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM publish_ledger"
            " WHERE blog_id = ? AND status = 'failed' AND created_at >= ?",
            (blog_id, since),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM publish_ledger"
            " WHERE blog_id = ? AND status = 'failed'"
            " AND created_at >= ? AND created_at < ?",
            (blog_id, since, before),
        ).fetchone()
    return row["cnt"]


def get_publish_ledger_fail_reasons(conn, blog_id: str, since: str, limit: int = 3) -> list[tuple]:
    """특정 시각 이후 실패 사유 분포 (stage 기준 상위 N개)."""
    rows = conn.execute(
        """SELECT stage, COUNT(*) as cnt
        FROM publish_ledger
        WHERE blog_id = ? AND status = 'failed' AND created_at >= ?
        GROUP BY stage ORDER BY cnt DESC LIMIT ?""",
        (blog_id, since, limit),
    ).fetchall()
    return [(r["stage"], r["cnt"]) for r in rows]


def get_recent_titles_from_publish_log(conn, blog_id: str, limit: int = 20, table: str = "publish_log") -> list[str]:
    """발행 로그에서 최근 제목 조회 (content.db 또는 stap_content.db)."""
    try:
        rows = conn.execute(f"""
            SELECT title FROM {table}
            WHERE blog_id = ? AND title IS NOT NULL AND title != ''
            ORDER BY published_at DESC LIMIT ?
        """, (blog_id, limit)).fetchall()
        return [row["title"] for row in rows]
    except Exception:
        return []


def get_recent_featureimages(conn, blog_id: str, limit: int = 20) -> list[str]:
    """최근 포스트의 featureimage 수집 (Hugo 사이트용)."""
    from ops_dashboard.db import get_blog_site_path
    from pathlib import Path
    
    site_path = get_blog_site_path(get_conn(), blog_id)
    if not site_path:
        return []
    
    posts_dir = Path(site_path) / "content" / "posts"
    if not posts_dir.is_dir():
        return []

    featureimages = []
    for post_dir in sorted(posts_dir.iterdir(), reverse=True)[:limit]:
        idx = post_dir / "index.md"
        if not idx.exists():
            continue
        try:
            content = idx.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        
        # featureimage 추출 (frontmatter)
        import re
        m = re.search(r'featureimage:\s*"([^"]+)"', content)
        if m:
            featureimages.append(m.group(1))
    
    return featureimages


def sync_yaml_to_lifecycle(conn: sqlite3.Connection) -> dict:
    """YAML 파일 자동 발견 후 blog_lifecycle 동기화.

    - 추가: YAML에 있지만 DB에 없는 블로그 등록
    - 갱신: YAML에 있는 블로그 필드 갱신
    - 제거: DB에 있지만 YAML에서 삭제된 블로그 삭제 (YAML이 단일 소스)

    반환: {"added": int, "updated": int, "removed": int}
    """
    yaml_blog_ids = set(get_all_yaml_blog_ids(conn))
    db_blog_ids = set(r["blog_id"] for r in conn.execute("SELECT blog_id FROM blog_lifecycle").fetchall())

    added = yaml_blog_ids - db_blog_ids
    removed = db_blog_ids - yaml_blog_ids

    # 등록/갱신
    sync_blog_lifecycle(conn)

    # 제거: YAML에 없는 블로그만 삭제 (체크 결과/이슈는 별도 보존)
    for blog_id in removed:
        conn.execute("DELETE FROM blog_lifecycle WHERE blog_id = ?", (blog_id,))
    conn.commit()

    return {
        "added": len(added),
        "updated": len(yaml_blog_ids & db_blog_ids),
        "removed": len(removed),
    }
