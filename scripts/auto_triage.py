#!/usr/bin/env python3
"""
auto_triage.py — 알림 오토트리아지 루프

대시보드 JSON(/api/attention 등)을 읽어 트리아지 규칙에 따라 알림을 자동 분류·처리.
오탐/정상은 요약으로 흡수, 실제 결함만 텔레그램 알림. 처리 결과 요약 보고서 생성.

사용법:
    python scripts/auto_triage.py              # Dry-run: 요약만 출력
    PROBLEM_ALERT_DRY_RUN=0 python scripts/auto_triage.py  # 텔레그램 발송 포함
"""

import json
import os
import sys
import base64
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from typing import Any

# ---------------------------------------------------------------------------
# 경로
# ---------------------------------------------------------------------------
FIVEK_ROOT = Path(__file__).resolve().parents[1]
# 직접 실행 시 프로젝트 루트를 sys.path에 추가 (shared/ops_dashboard import 보장).
# launchd는 PYTHONPATH로 이미 주입되며, 여기서는 중복 삽입을 방지한다.
if str(FIVEK_ROOT) not in sys.path:
    sys.path.insert(0, str(FIVEK_ROOT))
DASHBOARD_URL = "http://localhost:5060"
TRIAGE_RULES_PATH = FIVEK_ROOT / "scripts" / "auto_triage_rules.yaml"
SUMMARY_LOG = FIVEK_ROOT / "logs" / "auto_triage_summary.log"
TELEGRAM_SUMMARY_LOG = FIVEK_ROOT / "logs" / "auto_triage_telegram.log"
SYNC_DB_PATH = FIVEK_ROOT / "data" / "content.db"


# ---------------------------------------------------------------------------
# 인증 (대시보드 Basic Auth)
# ---------------------------------------------------------------------------
DASHBOARD_USER = os.environ.get("OPS_USER", "ops")
DASHBOARD_PASS = os.environ.get("OPS_PASSWORD")


# ---------------------------------------------------------------------------
# 트리아지 규칙 로드
# ---------------------------------------------------------------------------
def load_triage_rules(path: Path) -> dict[str, Any]:
    """auto_triage_rules.yaml에서 규칙 로드."""
    import yaml
    if not path.exists():
        # 파일 없으면 내장 기본 규칙 사용
        return _default_triage_rules()
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _default_triage_rules() -> dict[str, Any]:
    """규칙 파일이 없을 때 사용할 내장 기본 규칙 (auto_triage_rules.yaml의 서브셋)."""
    return {
        "triage_rules": [
            {
                "problem_id": "P09",
                "name_ko": "이미지 URL 토큰 반복",
                "판정": {"type": "actual_defect", "오탐여부": False},
                "자동조치": [
                    {"type": "log_only", "내용": "P09 감지됨 — 실제 결함, 알림 유지, 요약 기록"},
                    {"type": "summary_append", "내용": "{blog_id}: P09 {pattern} — 실제 결함 (알림 유지)"},
                ],
                "사람호출": {"조건": "항상 (실제 LLM URL stutter 결함)", "note": "이미지 URL 재생성 필요"},
            },
            {
                "problem_id": "P07",
                "name_ko": "CJK 누수",
                "판정": {"type": "actual_defect", "오탐여부": False},
                "자동조치": [
                    {"type": "log_only"},
                    {"type": "summary_append", "내용": "{blog_id}: P07 CJK 누수 — 실제 결함"},
                ],
                "사람호출": {"조건": "항상 (실제 콘텐츠 오염)"},
            },
            {
                "problem_id": "P08",
                "name_ko": "LLM/CoT 누수",
                "판정": {"type": "actual_defect", "오탐여부": False},
                "자동조치": [
                    {"type": "log_only"},
                    {"type": "summary_append", "내용": "{blog_id}: P08 CoT 누수 — 실제 결함"},
                ],
                "사람호출": {"조건": "항상 (실제 프롬프트 누수)"},
            },
            {
                "problem_id": "P04",
                "name_ko": "배포 실패 (deploy_error)",
                "판정": {"type": "actual_defect", "오탐여부": False},
                "자동조치": [
                    {"type": "log_only"},
                    {"type": "summary_append", "내용": "{blog_id}: P04 배포 실패 — 사람 확인 필요"},
                ],
                "사람호출": {"조건": "항상 (CRITICAL, 인프라 문제)"},
            },
            {
                "problem_id": "P05",
                "name_ko": "Hugo 빌드 실패",
                "판정": {"type": "actual_defect", "오탐여부": False},
                "자동조치": [
                    {"type": "log_only"},
                    {"type": "summary_append", "내용": "{blog_id}: P05 Hugo 빌드 실패"},
                ],
                "사람호출": {"조건": "항상 (CRITICAL)"},
            },
            {
                "problem_id": "P06",
                "name_ko": "썸네일 404 (broken_featureimage)",
                "판정": {"type": "actual_defect", "오탐여부": False},
                "자동조치": [
                    {"type": "log_only"},
                    {"type": "summary_append", "내용": "{blog_id}: P06 썸네일 404"},
                ],
                "사람호출": {"조건": "항상 (CRITICAL)"},
            },
            {
                "problem_id": "P14",
                "name_ko": "수집/품질 게이트 실패 (no_keyword 등)",
                "판정": {"type": "contextual"},
                "subtypes": [
                    {
                        "subtype": "informational_keyword",
                        "판정기준": [
                            "키워드가 장소·행사·개념 등 정보성",
                            "Coupang 검색 결과 0건 또는 insufficient_products",
                            "irrelevant_products / low_relevance",
                        ],
                        "자동조치": [
                            {"type": "silent_skip", "내용": "정보성 키워드 → 상품 매칭 불가 (정상). 알림 제외, 로그만."},
                            {"type": "summary_append", "내용": "info-skip: {blog_id} 키워드 '{keyword}' — 정보성, 상품 없음 (정상)"},
                        ],
                        "사람호출": {"조건": "불필요 (정보성 키워드는 상품 매칭 불가가 정상)"},
                    },
                    {
                        "subtype": "commercial_keyword_fail",
                        "판정기준": [
                            "키워드가 상품명·제품 카테고리",
                            "Coupang 검색 결과가 있음에도 insufficient_products/low_relevance",
                            "동일 commercial 키워드 연속 3회 이상 no_keyword",
                        ],
                        "자동조치": [
                            {"type": "summary_append", "내용": "commercial-fail: {blog_id} 키워드 '{keyword}' — 상품 있으나 매칭 실패"},
                        ],
                        "사람호출": {"조건": "상품 키워드 연속 실패 시만 (자동 스킵 불가)"},
                    },
                    {
                        "subtype": "collect_error",
                        "판정기준": ["collect_error (수집 자체 실패)"],
                        "자동조치": [
                            {"type": "log_only", "내용": "collect_error → 수집 파이프라인 문제 가능성"},
                        ],
                        "사람호출": {"조건": "연속 2회 이상 collect_error → API/크롤러 문제 가능성"},
                    },
                ],
            },
            {
                "problem_id": "P02",
                "name_ko": "콘텐츠 생성 실패 (no_content / publish_error)",
                "판정": {"type": "contextual"},
                "subtypes": [
                    {
                        "subtype": "leak_detected_embedded",
                        "판정기준": ["error_msg에 leak_detected 포함", "C01=True 또는 C04=True"],
                        "자동조치": [
                            {"type": "escalate", "내용": "{blog_id}: P02 — leak_detected 내포 (C01={c01}, C04={c04}) — 실제 콘텐츠 오염"},
                        ],
                        "사람호출": {"조건": "항상 (콘텐츠 오염은 자동 처리 불가)"},
                    },
                    {
                        "subtype": "transient_error",
                        "판정기준": ["timeout/network/일시Error"],
                        "자동조치": [
                            {"type": "retry_silent", "내용": "일시적 오류 → 자동 재시도 대기"},
                        ],
                        "사람호출": {"조건": "연속 3회 이상 transient 오류 → 인프라 문제"},
                    },
                    {
                        "subtype": "genuine_failure",
                        "판정기준": ["위 둘에 해당하지 않는 no_content/publish_error"],
                        "자동조치": [
                            {"type": "summary_append", "내용": "{blog_id}: P02 콘텐츠 생성 실패 ({reason})"},
                        ],
                        "사람호출": {"조건": "연속 3회 이상 → 프롬프트/모델 문제"},
                    },
                ],
            },
            {
                "problem_id": "P03",
                "name_ko": "유사 제목 중복 (similar_title)",
                "판정": {"type": "auto_skip_possible", "근거": "제목 유사도 80% 초과 → 중복 방지 기능 정상 작동"},
                "자동조치": [
                    {"type": "silent_skip", "내용": "similar_title 감지 → 제목 중복 방지 정상 작동, 알림 제외"},
                ],
                "사람호출": {"조건": "특정 키워드가 지속적 similar_title → 키워드 변형 필요"},
            },
            {
                "problem_id": "P10",
                "name_ko": "제목 템플릿 패턴 (title_blocked)",
                "판정": {"type": "auto_skip_possible", "근거": "블랙키워드/템플릿 패턴 차단 → 품질 게이트 정상 작동"},
                "자동조치": [
                    {"type": "silent_skip", "내용": "title_blocked → 블랙키워드 차단 정상, 알림 제외"},
                ],
                "사람호출": {"조건": "정상 키워드가 title_blocked → 블랙키워드 목록 확인"},
            },
            {
                "problem_id": "leak_detected",
                "name_ko": "콘텐츠 누수 (C01/C04)",
                "판정": {"type": "actual_defect", "오탐여부": False},
                "자동조치": [
                    {"type": "escalate", "내용": "{blog_id}: leak_detected C01={c01}, C04={c04} — 실제 콘텐츠 오염"},
                ],
                "사람호출": {"조건": "항상 (콘텐츠 오염은 자동 처리 불가)"},
            },
        ]
    }


# ---------------------------------------------------------------------------
# 트리아지 엔진
# ---------------------------------------------------------------------------
class TriageEngine:
    """대시보드 데이터 + 트리아지 규칙 → 알림 분류·처리·요약."""

    def __init__(self, rules: dict[str, Any]) -> None:
        self.rules = {r["problem_id"]: r for r in rules.get("triage_rules", [])}
        self.results: list[dict[str, Any]] = []
        self.summary: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "total_alerts": 0,
            "auto_handled": 0,
            "escalated": 0,
            "silent_skipped": 0,
            "by_type": defaultdict(int),
            "human_review_needed": [],
            "auto_handled_details": [],
        }

    def triage_notification(
        self,
        problem_id: str,
        blog_id: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """단일 알림 트리아지. (problem_id, blog_id, context) → 분류 결과."""
        context = context or {}
        rule = self.rules.get(problem_id)
        if rule is None:
            result = {
                "problem_id": problem_id,
                "blog_id": blog_id,
                "classification": "unknown",
                "action": "사람 호출 (미등록 reason)",
                "detail": f"미등록 problem_id: {problem_id}",
            }
            self._accumulate(result, escalated=True)
            return result

        판정 = rule.get("판정", {})
        rule_type = 판정.get("type", "unknown")

        # subtypes 처리 (P14, P02 등)
        subtypes = rule.get("subtypes", [])
        if subtypes and "keyword" in context:
            for st in subtypes:
                st_type = st["subtype"]
                criteria = st.get("판정기준", [])
                if self._matches_subtype(st_type, criteria, context, blog_id):
                    return self._apply_subtype_action(st, blog_id, context, rule["problem_id"])

        # 기본 rule 처리
        return self._apply_rule(rule, blog_id, context, rule_type)

    def _matches_subtype(self, subtype: str, criteria: list[str], context: dict, blog_id: str) -> bool:
        """서브타입 판정기준에 매칭되는지 확인."""
        keyword = context.get("keyword", "")
        error_msg = context.get("error_msg", "")
        reason = context.get("reason", "")
        c01 = context.get("c01", False)
        c04 = context.get("c04", False)

        if subtype == "commercial_keyword_fail":
            # ⚠ G3-fix: commercial을 먼저 검사 — "추천/비교/리뷰" 등 겸용 키워드가
            # informational로 먼저 매칭되어 silent_skip 되는 오삼킴 방지.
            # 상품 키워드는 정보성보다 상업성 우선.
            commercial_keywords = ["추천", "비교", "리뷰", "가격", "구매", "할인",
                                   "베스트", "TOP", "순위", "제품", "모델", "사양"]
            return any(kw in keyword for kw in commercial_keywords) or \
                   context.get("insufficient_products", False)

        if subtype == "informational_keyword":
            # 정보성 키워드 판단 (간단한 휴리스틱)
            # commercial_keyword_fail에서 이미 "추천/비교/리뷰"를 처리했으므로
            # 여기서는 순수 정보성 키워드만 남음.
            info_keywords = ["근교", "가이드", "고르는", "후기", "리스트업",
                             "방법", "조건", "신청", "지원", "혜택", "정리", "순위", "TOP",
                             "사용법", "분석", "체크리스트"]
            return any(kw in keyword for kw in info_keywords) or \
                   "no_keyword" in reason or \
                   context.get("insufficient_products", False) or \
                   context.get("irrelevant_products", False)

        if subtype == "collect_error":
            return "collect_error" in reason

        if subtype == "leak_detected_embedded":
            return "leak_detected" in error_msg or c01 or c04

        if subtype == "transient_error":
            transient_words = ["timeout", "network", "연결", "일시", "일시적"]
            return any(w in (error_msg or "").lower() for w in transient_words)

        if subtype == "genuine_failure":
            return True  # 기본값

        if subtype == "no_data genuine":
            return reason in ("no_result", "no_data") and \
                   not any(w in (error_msg or "").lower() for w in ["timeout", "network", "연결"]) \
                   or context.get("check_name", "") == "freshness"

        if subtype == "pipeline_error":
            return reason in ("fetch_error", "no_topic")

        if subtype == "keyword_issue":
            return "title_regenerate_failed" in reason

        if subtype == "timeout":
            return "timeout" in reason

        return False

    def _format_action(self, template: str, context: dict) -> str:
        """액션 템플릿에 context 값 치환.
        {blog_id}, {c01}, {c04}, {reason}, {pattern} 등 치환."""
        result = template
        for key in ["blog_id", "c01", "c04", "reason", "pattern", "keyword",
                     "error_msg", "stage", "problem_id"]:
            if key in context:
                # bool 값은 문자열로 변환
                val = context[key]
                if isinstance(val, bool):
                    val = str(val)
                result = result.replace(f"{{{key}}}", str(val))
        return result

    def _apply_subtype_action(self, st: dict, blog_id: str, context: dict, parent_problem_id: str) -> dict:
        """서브타입 행동 적용."""
        subtype_name = st["subtype"]
        actions = st.get("자동조치", [])
        사람호출 = st.get("사람호출", {}).get("조건", "")

        for action in actions:
            atype = action["type"]
            if atype == "silent_skip":
                result = {
                    "problem_id": parent_problem_id,
                    "blog_id": blog_id,
                    "classification": "auto_skipped",
                    "action": f"silent_skip: {self._format_action(action.get('내용', ''), context)}",
                    "detail": f"서브타입: {subtype_name}",
                }
                self._accumulate(result, silent=True)
                return result
            elif atype == "summary_append":
                result = {
                    "problem_id": parent_problem_id,
                    "blog_id": blog_id,
                    "classification": "auto_handled",
                    "action": f"summary_append: {self._format_action(action.get('내용', ''), context)}",
                    "detail": f"서브타입: {subtype_name}",
                }
                self._accumulate(result, handled=True)
                return result
            elif atype == "escalate":
                result = {
                    "problem_id": parent_problem_id,
                    "blog_id": blog_id,
                    "classification": "escalated",
                    "action": f"사람 호출: {self._format_action(action.get('내용', ''), context)}",
                    "detail": f"서브타입: {subtype_name}",
                }
                self._accumulate(result, escalated=True)
                return result
            elif atype == "retry_silent":
                result = {
                    "problem_id": parent_problem_id,
                    "blog_id": blog_id,
                    "classification": "auto_handled",
                    "action": f"retry_silent: {self._format_action(action.get('내용', ''), context)}",
                    "detail": f"서브타입: {subtype_name}",
                }
                self._accumulate(result, handled=True)
                return result

        # fallback
        result = {
            "problem_id": parent_problem_id,
            "blog_id": blog_id,
            "classification": "unknown_subtype",
            "action": f"서브타입 '{subtype_name}' 처리 불명확 → 사람 호출",
            "detail": f"판정기준: {st.get('판정기준', [])}",
        }
        self._accumulate(result, escalated=True)
        return result

    def _apply_rule(self, rule: dict, blog_id: str, context: dict, rule_type: str) -> dict:
        """기본 rule 적용."""
        actions = rule.get("자동조치", [])
        사람호출 = rule.get("사람호출", {}).get("조건", "")

        if rule_type in ("actual_defect",):
            # 실제 결함 → escalate 또는 log_only + summary
            for action in actions:
                atype = action["type"]
                if atype == "escalate":
                    result = {
                        "problem_id": rule["problem_id"],
                        "blog_id": blog_id,
                        "classification": "escalated",
                        "action": f"사람 호출: {self._format_action(action.get('내용', ''), context)}",
                        "detail": f"실제 결함 ({rule.get('판정', {}).get('근거', '')})",
                    }
                    self._accumulate(result, escalated=True)
                    return result
                elif atype == "log_only":
                    result = {
                        "problem_id": rule["problem_id"],
                        "blog_id": blog_id,
                        "classification": "logged",
                        "action": "로그 + 요약 기록",
                        "detail": f"실제 결함, 알림 유지 ({rule.get('name_ko', '')})",
                    }
                    self._accumulate(result, logged=True)
                    return result

        elif rule_type == "auto_skip_possible":
            for action in actions:
                if action["type"] == "silent_skip":
                    result = {
                        "problem_id": rule["problem_id"],
                        "blog_id": blog_id,
                        "classification": "auto_skipped",
                        "action": f"silent_skip: {self._format_action(action.get('내용', ''), context)}",
                        "detail": f"판정 근거: {rule.get('판정', {}).get('근거', '')}",
                    }
                    self._accumulate(result, silent=True)
                    return result

        elif rule_type == "auto_handle":
            for action in actions:
                atype = action["type"]
                if atype == "silent_skip":
                    result = {
                        "problem_id": rule["problem_id"],
                        "blog_id": blog_id,
                        "classification": "auto_skipped",
                        "action": f"silent_skip: {self._format_action(action.get('내용', ''), context)}",
                    }
                    self._accumulate(result, silent=True)
                    return result
                elif atype == "retry_schedule":
                    result = {
                        "problem_id": rule["problem_id"],
                        "blog_id": blog_id,
                        "classification": "auto_handled",
                        "action": f"retry_schedule: {action.get('내용', '')}",
                    }
                    self._accumulate(result, handled=True)
                    return result
                elif atype == "auto_recovery":
                    result = {
                        "problem_id": rule["problem_id"],
                        "blog_id": blog_id,
                        "classification": "auto_handled",
                        "action": f"auto_recovery: {action.get('내용', '')}",
                    }
                    self._accumulate(result, handled=True)
                    return result

        elif rule_type == "contextual":
            # 기본 fallback: summary_append
            for action in actions:
                if action["type"] == "summary_append":
                    result = {
                        "problem_id": rule["problem_id"],
                        "blog_id": blog_id,
                        "classification": "auto_handled",
                        "action": f"summary_append: {self._format_action(action.get('내용', ''), context)}",
                        "detail": "문맥별 분류 필요 (서브타입 매칭 시도)",
                    }
                    self._accumulate(result, handled=True)
                    return result

        # fallback: 사람 호출
        result = {
            "problem_id": rule["problem_id"],
            "blog_id": blog_id,
            "classification": "escalated",
            "action": f"사람 호출: {rule.get('name_ko', '')} ({rule_type})",
            "detail": f"규칙 타입 '{rule_type}' 처리 불명확",
        }
        self._accumulate(result, escalated=True)
        return result

    def _accumulate(self, result: dict, *, handled: bool = False, escalated: bool = False,
                    silent: bool = False, logged: bool = False) -> None:
        """트리아지 결과 누적."""
        self.results.append(result)
        self.summary["total_alerts"] += 1
        if handled:
            self.summary["auto_handled"] += 1
        if escalated:
            self.summary["escalated"] += 1
        if silent:
            self.summary["silent_skipped"] += 1
        if logged:
            self.summary["auto_handled"] += 1  # log_only도 자동 처리로 간주

        # by_type 카운트
        pid = result.get("problem_id", "?")
        self.summary["by_type"][pid] += 1

        if escalated or result["classification"] in ("escalated", "unknown", "unknown_subtype"):
            self.summary["human_review_needed"].append(result)

        if not silent:
            self.summary["auto_handled_details"].append(result)

    def generate_summary(self) -> str:
        """트리아지 결과 요약 보고서 생성."""
        s = self.summary
        lines = [
            f"\n{'='*70}",
            f"🤖 오토트리아지 요약 보고 — {s['timestamp']}",
            f"{'='*70}",
            f"\n📊 전체 통계",
            f"  총 알림: {s['total_alerts']}건",
            f"  자동 처리: {s['auto_handled']}건 (silent_skip + log_only + summary_append + retry)",
            f"  사람 호출: {s['escalated']}건",
            f"  silent skip: {s['silent_skipped']}건",
            f"\n📋 유형별 분류",
        ]
        for pid, count in sorted(s["by_type"].items(), key=lambda x: -x[1]):
            spec_name = self._pid_name(pid)
            lines.append(f"  {pid} ({spec_name}): {count}건")

        if s["human_review_needed"]:
            lines.append(f"\n🚨 사람 호출 필요 ({len(s['human_review_needed'])}건)")
            for item in s["human_review_needed"]:
                lines.append(f"  • {item['problem_id']} / {item['blog_id']}: {item['action']}")

        if s["auto_handled_details"]:
            lines.append(f"\n📝 자동 처리 상세")
            for item in s["auto_handled_details"][:20]:
                cls = item.get("classification", "?")
                action = item.get("action", "?")
                detail = item.get("detail", "")
                lines.append(f"  [{cls}] {item['problem_id']} / {item['blog_id']}: {action}")
                if detail and detail != action:
                    lines.append(f"         └ {detail}")

        if not s["total_alerts"]:
            lines.append("\n✓ 알림 없음 — 모든 정상")

        lines.append(f"\n{'='*70}\n")
        return "\n".join(lines)

    def _pid_name(self, pid: str) -> str:
        """problem_id → name_ko 매핑 (rules에서 추출)."""
        for r in self.rules.get("triage_rules", []):
            if r.get("problem_id") == pid:
                return r.get("name_ko", pid)
        # PROBLEM_REGISTRY에서 fallback
        try:
            from shared.problem_registry import PROBLEM_REGISTRY
            spec = PROBLEM_REGISTRY.get(pid)
            if spec:
                return spec.name_ko
        except Exception:
            pass
        return pid


# ---------------------------------------------------------------------------
# 대시보드 데이터 수집
# ---------------------------------------------------------------------------
def fetch_dashboard_data() -> dict[str, Any]:
    """대시보드 API에서 데이터 수집."""
    results: dict[str, Any] = {}
    endpoints = [
        ("attention", "/api/attention"),
        ("issues", "/api/issues"),
        ("fleet", "/api/fleet"),
        ("readiness", "/api/readiness"),
        ("registry", "/api/registry"),
    ]
    for name, path in endpoints:
        url = f"{DASHBOARD_URL}{path}"
        req = urllib.request.Request(url)
        auth_str = f"{DASHBOARD_USER}:{DASHBOARD_PASS}"
        req.add_header("Authorization", f"Basic {base64.b64encode(auth_str.encode()).decode()}")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                results[name] = json.loads(resp.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
            results[name] = {"error": str(e)}
    return results


def fetch_scheduler_logs() -> list[str]:
    """scheduler.error.log에서 오늘 알림 로그 추출."""
    log_path = Path("/tmp/5000-scheduler.error.log")
    if not log_path.exists():
        return []
    today = datetime.now().strftime("%Y-%m-%d")
    lines = []
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith(today):
                lines.append(line.rstrip())
    return lines


def parse_scheduler_notifications(log_lines: list[str]) -> list[dict[str, Any]]:
    """scheduler.error.log에서 알림성 로그 파싱."""
    import re
    notifications = []
    for line in log_lines:
        # [PUBLISH] 실패 로그
        if "[PUBLISH]" in line and "발행 성공" not in line:
            # 예: 2026-08-08 13:45:45,267 [ERROR] [PUBLISH] car-hugo 발행 실패 — stage=no_keyword
            # blog_id 추출 — [PUBLISH] 뒤에 blog_id가 오고 그 다음 "발행 실패"
            blog_match = re.search(r"\[PUBLISH\]\s+(\S+)\s+발행\s+실패", line)
            blog_id = blog_match.group(1) if blog_match else "unknown"

            # stage 추출
            stage_match = re.search(r"stage=(\S+)", line)
            stage = stage_match.group(1) if stage_match else ""

            # error_msg 추출 (leak_detected: C01=..., C04=...)
            error_match = re.search(r"pipeline 실패:\s*(\S+)", line)
            error_msg = error_match.group(1) if error_match else ""

            # c01/c04 추출
            c01_match = re.search(r"C01=([A-Za-z]+)", line)
            c04_match = re.search(r"C04=([A-Za-z]+)", line)
            c01 = c01_match.group(1) if c01_match else False
            c04 = c04_match.group(1) if c04_match else False

            # reason 추출 (명시적 reason= 패턴이 없으면 stage를 reason으로 사용)
            reason_match = re.search(r"reason=(\S+)", line)
            reason = reason_match.group(1) if reason_match else ""
            if not reason:
                # stage를 reason으로 사용 (예: stage=no_keyword → reason=no_keyword)
                if stage:
                    reason = stage

            # keyword 추출
            kw_match = re.search(r'"keyword":\s*"([^"]+)"', line)
            keyword = kw_match.group(1) if kw_match else ""

            notifications.append({
                "source": "scheduler",
                "blog_id": blog_id,
                "stage": stage,
                "error_msg": error_msg,
                "c01": c01,
                "c04": c04,
                "reason": reason,
                "keyword": keyword,
                "raw": line,
            })

        # problem_monitor 알림 로그
        if "[problem_monitor] 알림 발송:" in line:
            # 예: 2026-... [INFO] [problem_monitor] 알림 발송: blog_id/P09
            import re
            match = re.search(r"알림 발송:\s*(\S+)/(\S+)", line)
            if match:
                blog_id = match.group(1)
                problem_id = match.group(2)
                notifications.append({
                    "source": "problem_monitor",
                    "blog_id": blog_id,
                    "problem_id": problem_id,
                    "raw": line,
                })

        # watchdog death 알림
        if "death 알림 발송" in line or "death 감지" in line:
            notifications.append({
                "source": "watchdog",
                "blog_id": "system",
                "problem_id": "watchdog_death",
                "raw": line,
            })

    return notifications


# ---------------------------------------------------------------------------
# 트리아지 실행
# ---------------------------------------------------------------------------
def _classification_rows(engine: TriageEngine) -> list[dict]:
    """TriageEngine 누적 결과에서 DB/JSON 기록용 분류 행 추출 (Phase 69 W4).

    engine.results의 각 항목에 severity/action을 PROBLEM_REGISTRY에서 보강한다.
    기존 분류 로직·요약 생성은 건드리지 않는다 — 이 함수는 출력 경로 추가만 담당.
    """
    rows = []
    from shared.problem_registry import lookup_problem

    for r in engine.results:
        pid = r.get("problem_id", "unknown_failure")
        spec = lookup_problem(pid)
        severity = (spec.severity if spec else "") or r.get("severity", "")
        action = (r.get("action") or (spec.action if spec else "")) or ""
        rows.append({
            "problem_id": pid,
            "severity": severity,
            "target": r.get("blog_id", ""),
            "action": action,
            "source": r.get("pattern", "") or r.get("reason", "") or r.get("check_name", ""),
            "detail": r.get("detail", ""),
            "classification": r.get("classification", ""),
        })
    return rows


def _write_classifications_json(rows: list[dict]) -> str:
    """분류 결과를 JSON 파일로 덤프 (DB 접근 실패 시에도 데이터 보존 — 조용한 실패 금지).

    반환: 작성된 JSON 파일 경로.
    """
    dump_dir = SUMMARY_LOG.parent  # logs/
    dump_dir.mkdir(parents=True, exist_ok=True)
    path = dump_dir / f"triage_classifications_{datetime.now().strftime('%Y%m%d')}.json"
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"written_at": datetime.now().isoformat(timespec="seconds"),
                            "rows": rows}, ensure_ascii=False) + "\n")
    return str(path)


def _record_classifications_db(rows: list[dict]) -> None:
    """분류 결과를 ops.db triage_classifications 테이블에 기록 (Phase 69 W4).

    dry-run 여부와 무관하게 DB 실재화는 수행한다 (텔레그램 발송만 dry_run으로 억제).
    실패 시 예외를 던져 조용한 실패를 방지한다 — 호출부에서 텔레그램/JSON 경로와 격리.
    """
    from ops_dashboard import db as ops_db

    # Phase 69 W4.5: run_id로 묶어 '최신 1회분만' 유지 — 반복 실행 누적 차단.
    # 기존 기록을 삭제하고 현재 run 행만 삽입하므로 건수는 실행 간 누적되지 않는다.
    run_id = datetime.now().strftime("%Y%m%d%H%M%S")

    conn = ops_db.get_conn()
    ops_db.init_db(conn)
    try:
        ops_db.replace_triage_classifications(conn, run_id=run_id, rows=rows)
    finally:
        conn.close()


def run_triage(dry_run: bool = True) -> str:
    """트리아지 실행 → 요약 보고서 반환."""
    engine = TriageEngine(load_triage_rules(TRIAGE_RULES_PATH))

    # 1. 대시보드 data에서 attention/fail_checks 수집
    dashboard = fetch_dashboard_data()
    attention = dashboard.get("attention", {})

    # W5-2: /api/registry의 rules/errors로 rule_id→problem_id 역방향 매핑 구성.
    # 구조 필드가 있는 개별행(rule_id 채워짐)을 구조적으로 분류하기 위한 조인 안전망.
    # registry를 못 받거나 비면 {} — 폴백으로 안전 동작.
    registry_map = _build_registry_map(dashboard.get("registry"))

    # ⚠ G3-fix: 서버 장애 감지 — 데이터 취득 실패는 silent_skip이 아니라 사람 호출
    # fetch_dashboard_data()가 {"error": ...}를 반환한 엔드포인트가 전부이면
    # 데이터 소스 자체를 못 읽은 것이므로 "데이터 취득 실패"로 보고해야 함.
    # 정상적으로 데이터를 받았는데 fail_checks=[]인 경우(이슈 0)와 반드시 구분.
    endpoint_errors = {name: data for name, data in dashboard.items()
                       if isinstance(data, dict) and data.get("error")}
    총엔드포인트 = len({"attention", "issues", "fleet", "readiness"} & set(dashboard.keys()))
    오류엔드포인트 = len(endpoint_errors)
    서버장애 = (총엔드포인트 > 0 and 오류엔드포인트 == 총엔드포인트)

    if 서버장애:
        _server_failure_record = {
            "problem_id": "data_fetch_failure",
            "blog_id": "system",
            "classification": "escalated",
            "action": "사람 호출: 대시보드 데이터 취득 실패 — 서버 장애 가능성 (전원 엔드포인트 오류)",
            "detail": f"엔드포인트 {오류엔드포인트}/{총엔드포인트} 오류: " +
                      ", ".join(f"{n}={d.get('error','?')[:80]}" for n, d in endpoint_errors.items()),
        }
    else:
        _server_failure_record = None

    # W6-b: 이번 run 동안 standard 폴백 추적 초기화 (검증 관문용).
    _FALLBACK_TRACE_STD.clear()

    fail_checks = attention.get("fail_checks", [])
    open_issues = attention.get("open_issues", [])

    # ⚠ G3-fix: 서버 장애 기록이 있으면 최우선 people-call로 주입
    if _server_failure_record:
        engine._accumulate(_server_failure_record, escalated=True)

    # fail_checks 트리아지
    for item in fail_checks:
        blog_id = item.get("blog_id", "unknown")
        check_name = item.get("check_name", "")
        pattern = item.get("pattern", "")

        # W5-2: 구조 필드(problem_id/rule_id) 우선 + 자유텍스트 폴백.
        # 구조 필드가 없으면 기존 _pattern_to_problem_id/_check_name_to_problem_id로
        # 폴백하므로 분류 결과는 W5 전 baseline과 동일하게 유지된다.
        problem_id = _resolve_problem_id(item, registry_map)

        ctx = {
            "keyword": item.get("keyword", ""),
            "pattern": pattern,
            "error_msg": item.get("error_msg", ""),
            "c01": item.get("c01", False),
            "c04": item.get("c04", False),
            "reason": item.get("reason", ""),
            "insufficient_products": item.get("insufficient_products", False),
            "irrelevant_products": item.get("irrelevant_products", False),
            "check_name": check_name,
            # W5-2: 구조 필드를 engine 분류에도 실어 전달 (향후 W6에서 사용).
            "rule_id": item.get("rule_id", ""),
            "problem_id": item.get("problem_id", ""),
            "severity": item.get("severity", ""),
            "action": item.get("action", ""),
        }
        engine.triage_notification(problem_id, blog_id, ctx)

    # 2. open_issues 트리아지 (known_issues) — 구조적 문제, 사람 호출 대상이지만 요약에만 기록
    for issue in open_issues:
        issue_id = issue.get("issue_id", "unknown")
        category = issue.get("category", "")
        # known_issues는 구조적 문제 — summary에만 기록, 사람 호출 목록에서 제외
        result = {
            "problem_id": "known_issue",
            "blog_id": issue_id,
            "classification": "structural_issue",
            "action": f"알려진 구조적 이슈 ({category}): {issue_id} — 요약에만 기록",
            "detail": f"category={category}",
        }
        engine._accumulate(result, handled=True)
        # 사람 호출 목록에서 제외하기 위해 별도 처리
        # (human_review_needed에 추가하지 않음)

    # 3. excluded_fail_checks 트리아지 (비운영 블로그)
    excluded = attention.get("excluded_fail_checks", [])
    for item in excluded:
        blog_id = item.get("blog_id", "unknown")
        # 비운영 블로그의 실패는 모두 silent_skip으로 처리 (개별 분류 불필요)
        result = {
            "problem_id": "excluded",
            "blog_id": blog_id,
            "classification": "excluded_blog",
            "action": "비운영 블로그 제외 (silent_skip)",
            "detail": f"check_name={item.get('check_name', '')}, pattern={item.get('pattern', '')}",
        }
        engine._accumulate(result, silent=True)

    # 4. scheduler.log에서 실시간 알림 파싱
    log_lines = fetch_scheduler_logs()
    notifications = parse_scheduler_notifications(log_lines)
    for notif in notifications:
        if notif["source"] == "problem_monitor":
            engine.triage_notification(notif["problem_id"], notif["blog_id"], {})
        elif notif["source"] == "scheduler":
            # scheduler 실패 → reason 기준으로 트리아지
            reason = notif.get("reason", "")
            c01 = notif.get("c01", False)
            c04 = notif.get("c04", False)
            ctx = {
                "error_msg": notif.get("error_msg", ""),
                "reason": reason,
                "c01": c01,
                "c04": c04,
                "keyword": "",
            }
            # reason → problem_id 매핑
            problem_id = _reason_to_problem_id(reason)
            if problem_id:
                engine.triage_notification(problem_id, notif["blog_id"], ctx)
            else:
                engine.triage_notification("unknown_failure", notif["blog_id"], ctx)
        elif notif["source"] == "watchdog":
            engine.triage_notification("watchdog_death", "system", {})

    # 5. 요약 생성
    engine_summary = engine.summary  # dict
    summary_text = engine.generate_summary()  # string

    # Phase 69 W4: 분류 결과 DB/JSON 실재화 (기존 출력은 그대로 유지, 추가만)
    try:
        cls_rows = _classification_rows(engine)
        _record_classifications_db(cls_rows)
        json_path = _write_classifications_json(cls_rows)
        print(f"[W4] triage classifications recorded: {len(cls_rows)} rows (json={json_path})")
    except Exception as e:  # noqa: BLE001 — 실패해도 기존 알림 경로는 중단하지 않는다
        print(f"[W4] classification persist failed: {e}")

    # 로깅
    log_line = f"[{datetime.now().isoformat(timespec='seconds')}] 트라이아지 완료: 총{engine_summary['total_alerts']}건, 자동처리{engine_summary['auto_handled']}건, 사람호출{engine_summary['escalated']}건\n"
    log_line += summary_text
    SUMMARY_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(SUMMARY_LOG, "a", encoding="utf-8") as f:
        f.write(log_line + "\n")

    if not dry_run:
        # 텔레그램 발송 (요약만)
        try:
            import shared.telegram_notifier as tn
            tn.send(summary_text[:4000])
            with open(TELEGRAM_SUMMARY_LOG, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().isoformat(timespec='seconds')}] 텔레그램 발송 완료\n")
        except Exception as e:
            with open(TELEGRAM_SUMMARY_LOG, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().isoformat(timespec='seconds')}] 텔레그램 발송 실패: {e}\n")

    return summary_text


def _check_name_to_problem_id(check_name: str) -> str | None:
    """check_name → problem_id 매핑."""
    mapping = {
        "standard_compliance": "standard_compliance",  # R01~R12 표준준수 실패 (별도 분류)
        "maintenance_checklist": "P15",
        "freshness": "P01",  # freshness = stale data = no_result 계열
        "crosslink_consistency": "dead_entity_link",
        "render_health": "P06",
        "gsd_crosscheck": "unknown_failure",
    }
    return mapping.get(check_name)


def _build_registry_map(registry_data: dict | None) -> dict:
    """/api/registry 응답 → rule_id→problem_id 매핑 구성 (Phase 69 W5-2).

    fail_check item의 `rule_id`를 구조적으로 problem_id로 대응시키기 위한 역방향
    매핑. 단일 출처는 `ops_dashboard/registry/rules.py`의 **선언적 `RULE_TO_PROBLEM`**
    (W6-a) — R01~R12 규칙이 위반되면 `standard_compliance` 문제분류로 대응된다.
    이를 1차로 채우고, registry 응답의 rule/error id 동일성 매칭으로 추가 대응을
    병합한다 (안전망).

    registry 모듈을 못 읽으면 기존 id 동일성 매칭만 사용하고, 그마저 없으면 `{}`
    반환 — 폴백으로 안전 동작. 폴백 파서(_pattern_to_problem_id 등)는 W6-b 제거 전까지
    유지한다.
    """
    mapping: dict[str, str] = {}
    # W6-a: 선언적 rule↔problem 대응을 단일 출처로 사용.
    try:
        from ops_dashboard.registry.rules import RULE_TO_PROBLEM

        mapping.update(RULE_TO_PROBLEM)
    except Exception:  # noqa: BLE001 — registry 미가용 시 id 동일성 매칭으로 안전 폴백.
        pass
    # 안전망: registry 응답의 rule id가 error id와 동일하면 그대로 대응.
    if registry_data:
        rules = registry_data.get("rules") or []
        error_ids = {e.get("id") for e in (registry_data.get("errors") or [])}
        for r in rules:
            rid = r.get("id")
            if rid and rid in error_ids:
                mapping[rid] = rid
    return mapping


# W6-b: standard_compliance(R01-R12) 계열이 폴백 경로를 타는지 추적.
# 구조필드로 해석된 standard 항목은 이 집합에 들어가지 않아야 하고,
# 들어가면 W6-b 검증 관문(폴백 0)이 실패한다. (check_name, blog_id) 기록.
_FALLBACK_TRACE_STD: list[tuple[str, str]] = []


def _resolve_problem_id(item: dict, registry_map: dict) -> str:
    """fail_check item → problem_id (구조 필드 우선 + 자유텍스트 폴백, Phase 69 W5-2).

    우선순위:
      1. `item.problem_id` 가 있으면 그대로 사용.
      2. `item.rule_id` 가 있고 registry_map에 대응 problem_id가 있으면 사용.
      3. W6-b: `standard_compliance` 계열은 여기서 **구조필드 단일 경로**로 종료한다.
         구조필드로 해석되지 못하면 unknown_failure로 노출(조용한 오분류 금지)하고
         _pattern/_check_name 자유텍스트 폴백을 호출하지 않는다. 폴백 추적에 기록.
      4. R01-R12 밖 체크 타입(maintenance_checklist/freshness/render_health/
         crosslink_consistency 등)은 기존 자유텍스트 폴백 유지:
         _pattern_to_problem_id → _check_name_to_problem_id → unknown_failure.

    폴백 파서 자체는 W6-b 이후에도 R01-R12 밖 타입용으로 남긴다 (전면 삭제 금지).
    """
    pid = (item.get("problem_id") or "").strip()
    if pid:
        return pid
    rid = (item.get("rule_id") or "").strip()
    if rid and registry_map.get(rid):
        return registry_map[rid]
    # W6-b: standard_compliance 계열은 구조필드 단일 경로 — 자유텍스트 폴백 금지.
    if (item.get("check_name") or "").strip() == "standard_compliance":
        _FALLBACK_TRACE_STD.append((item.get("check_name", ""), item.get("blog_id", "")))
        return "unknown_failure"
    pid = _pattern_to_problem_id(item.get("pattern", ""))
    if pid:
        return pid
    pid = _check_name_to_problem_id(item.get("check_name", ""))
    if pid:
        return pid
    return "unknown_failure"


def _pattern_to_problem_id(pattern: str) -> str | None:
    """pattern 문자열에서 problem_id 판별."""
    if not pattern:
        return None
    p = pattern.lower()
    if "반복" in p or "repeated segment" in p or "token" in p:
        return "P09"
    if "누수" in p or "leak" in p or "cjk" in p or "c01" in p or "c04" in p:
        return "leak_detected"
    if "404" in p or "thumbnail" in p or "썸네일" in p:
        return "P06"
    if "제목" in p and ("유사" in p or "중복" in p):
        return "P03"
    if "만료" in p or "stale" in p or "old" in p:
        return "P19"
    if "품질" in p or "게이트" in p:
        return "P12"
    if "할당량" in p or "quota" in p:
        return "P17"
    return None


def _reason_to_problem_id(reason: str) -> str | None:
    """reason → problem_id 매핑."""
    mapping = {
        "leak_detected": "leak_detected",
        "publish_error": "P02",
        "no_keyword": "P14",
        "no_result": "P01",
        "no_content": "P02",
        "deploy_error": "P04",
        "build_failed": "P05",
        "broken_featureimage": "P06",
        "similar_title": "P03",
        "title_blocked": "P10",
        "title_regenerate_failed": "P11",
        "content_quality_gate": "P12",
        "language_error": "P12",
        "rate_limited": "P13",
        "validation": "P15",
        "stale": "P19",
        "duplicate_source_id": "P16",
        "duplicate_slug": "P16",
        "quota_met": "P17",
        "already_running": "P18",
        "config_error": "P21",
        "no_data": "P01",
        "fetch_error": "P01",
        "cjk_leak": "P07",
        "llm_cot_leak": "P08",
        "cot_leak": "P08",
        "image_url_repeat": "P09",
        "image_url_length": "P23",
        "escalation": "P01",
        "generation_failed": "P02",
    }
    return mapping.get(reason)


def main() -> None:
    dry_run = os.environ.get("PROBLEM_ALERT_DRY_RUN", "1") != "0"
    summary = run_triage(dry_run=dry_run)
    print(summary)
    if dry_run:
        print("\n[DRY-RUN] 텔레그램 미발송. PROBLEM_ALERT_DRY_RUN=0이면 발송.")


def generate_summary_report(engine: TriageEngine) -> str:
    """TriageEngine 결과로부터 사람-readable 요약 보고서 생성.
    
    매일 1~2회 실행해 요약만 텔레그램으로 받을 수 있는 형식.
    """
    s = engine.summary
    lines = [
        "\n" + "=" * 70,
        "🤖 오토트리아지 일일 요약",
        "=" * 70,
        "",
        f"📅 생성 시각: {s['timestamp']}",
        "",
        "📊 한 줄 요약",
        f"  총 알림 {s['total_alerts']}건 → 자동처리 {s['auto_handled']}건, 사람호출 {s['escalated']}건, silent_skip {s['silent_skipped']}건",
        "",
    ]
    
    # 사람 호출 항목 (진짜 결함만)
    if s["human_review_needed"]:
        lines.append("🚨 사람 확인 필요 (실제 결함 — 무시하면 안 됨)")
        for item in s["human_review_needed"]:
            pid = item.get("problem_id", "?")
            bid = item.get("blog_id", "?")
            action = item.get("action", "?")
            # 문제ID → 이름 매핑
            name = _pid_name(pid)
            lines.append(f"  • [{pid}] {bid}: {action}")
            if len(s["human_review_needed"]) >= 10:
                lines.append(f"  ... 외 {len(s['human_review_needed']) - 10}건")
                break
    else:
        lines.append("✅ 사람 호출 필요 없음 — 모두 자동 처리됨")
    
    lines.append("")
    lines.append("📋 유형별 통계")
    for pid, count in sorted(s["by_type"].items(), key=lambda x: -x[1]):
        name = _pid_name(pid)
        lines.append(f"  {pid} ({name}): {count}건")
    
    lines.append("")
    lines.append("📝 자동 처리 내역 (상위 15건)")
    for item in s["auto_handled_details"][:15]:
        cls = item.get("classification", "?")
        action = item.get("action", "?")
        lines.append(f"  [{cls}] {item.get('problem_id', '?')} / {item.get('blog_id', '?')}: {action}")
    
    if len(s["auto_handled_details"]) > 15:
        lines.append(f"  ... 외 {len(s['auto_handled_details']) - 15}건")
    
    lines.append("")
    lines.append(f"{'=' * 70}\n")
    return "\n".join(lines)


def _pid_name(pid: str) -> str:
    """문제ID → 이름 매핑 (rules에서 추출)."""
    for r in AUTO_TRIAGE_RULES.get("triage_rules", []):
        if r.get("problem_id") == pid:
            return r.get("name_ko", pid)
    # fallback: PROBLEM_REGISTRY
    try:
        from shared.problem_registry import PROBLEM_REGISTRY
        spec = PROBLEM_REGISTRY.get(pid)
        if spec:
            return spec.name_ko
    except Exception:
        pass
    return pid


# 로더에서 읽은 규칙을 모듈 레벨에서 캐싱
_AUTO_TRIAGE_RULES: dict[str, Any] | None = None


def get_triage_rules() -> dict[str, Any]:
    global _AUTO_TRIAGE_RULES
    if _AUTO_TRIAGE_RULES is None:
        rules_path = Path(__file__).parent / "auto_triage_rules.yaml"
        if rules_path.exists():
            import yaml
            with open(rules_path, "r", encoding="utf-8") as f:
                _AUTO_TRIAGE_RULES = yaml.safe_load(f)
        else:
            _AUTO_TRIAGE_RULES = {"triage_rules": _default_triage_rules()}
    return _AUTO_TRIAGE_RULES


def _pid_name(pid: str) -> str:
    """문제ID → 이름 매핑 (rules에서 추출)."""
    rules = get_triage_rules()
    for r in rules.get("triage_rules", []):
        if r.get("problem_id") == pid:
            return r.get("name_ko", pid)
    # fallback: PROBLEM_REGISTRY
    try:
        from shared.problem_registry import PROBLEM_REGISTRY
        spec = PROBLEM_REGISTRY.get(pid)
        if spec:
            return spec.name_ko
    except Exception:
        pass
    return pid


# ---------------------------------------------------------------------------
# 로더에서 읽은 규칙을 모듈 레벨에서 캐싱
# ---------------------------------------------------------------------------
_AUTO_TRIAGE_RULES: dict[str, Any] | None = None


def get_triage_rules() -> dict[str, Any]:
    """모듈 레벨 규칙 캐싱. 스크립트 재실행 시마다 YAML 재파싱하지 않음."""
    global _AUTO_TRIAGE_RULES
    if _AUTO_TRIAGE_RULES is None:
        rules_path = Path(__file__).parent / "auto_triage_rules.yaml"
        if rules_path.exists():
            import yaml
            with open(rules_path, "r", encoding="utf-8") as f:
                _AUTO_TRIAGE_RULES = yaml.safe_load(f)
        else:
            _AUTO_TRIAGE_RULES = {"triage_rules": _default_triage_rules()}
    return _AUTO_TRIAGE_RULES


if __name__ == "__main__":
    main()
