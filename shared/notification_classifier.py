"""
Notification classifier for problem IDs (P-codes).

Classifies problems into two notification channels:
- "realtime": Immediate Telegram push (actual failures requiring human intervention)
- "summary": Daily summary digest (quality gate blocks, normal operations, noise minimization)

Classification principle (Phase 60 Part 3 correction):
- "실제실패" (actual failure/crash): pipeline failed unexpectedly, needs human action → realtime
- "정상차단" (quality gate block): pipeline working correctly, gate rejected content → summary
- Ambiguous cases default to summary (noise minimization bias)
"""

# 실제 실패·크래시·미분류 — 사람의 즉시 조치가 필요한 경우
REALTIME_PUSH_PROBLEMS = frozenset({
    "P01",   # no_result — 파이프라인 데이터 수집 자체 실패
    "P02",   # no_content — LLM 콘텐츠 생성 실패
    "P04",   # deploy_error — Wrangler 배포 실패 (사이트 장애)
    "P05",   # hugo_build_failed — Hugo 빌드 실패 (사이트 장애)
    "P06",   # broken_featureimage — 썸네일 404 (사용자 노출)
    "unknown_failure",  # 미등록 에러 — 원인 파악 필요
})


def classify(problem_id: str) -> str:
    if problem_id in REALTIME_PUSH_PROBLEMS:
        return "realtime"
    return "summary"


def is_realtime(problem_id: str) -> bool:
    return problem_id in REALTIME_PUSH_PROBLEMS


def get_realtime_problems() -> frozenset:
    return REALTIME_PUSH_PROBLEMS
