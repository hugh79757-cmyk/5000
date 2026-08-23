"""쿼터우회(Quota Bypass) 발행 — 전 분기 공용 진입점.

usage:
    python3 shared/quota_bypass.py {blog_id}
    python3 shared/quota_bypass.py --list

daily_quota 를 999 로 우회해 dispatcher.dispatch() 로 발행한다.
기존 `scripts/force_publish_travel.py`(travel 전용)의 로직을 전 분기로 확장한 것.
중복 가드(source_id / _used_places / similar_title)는 그대로 유지되므로
중복 콘텐츠가 발행되지는 않는다. 소스 파일을 건드리지 않는 런타임 패치라 원복 불필요.

STAP(주식 6개) / TAP(블로그) 는 subprocess 격리 분기라 지원하지 않는다.
"""
import json
import os
import sys

# 경로 설정 — dispatcher.py 와 동일하게 5000 루트를 sys.path 최우선에 추가
FIVEK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, FIVEK_ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.expanduser("~/.env.common"))
load_dotenv(os.path.join(FIVEK_ROOT, ".env"))

import dispatcher  # noqa: E402  (sys.path 주입 후 import)
import shared.publisher  # noqa: E402


def _is_isolated(cfg: dict) -> str | None:
    """subprocess 격리 분기(STAP/TAP)라면 사유 문자열, 아니면 None."""
    pipeline = cfg.get("pipeline", "")
    platform = cfg.get("platform", "")
    if pipeline == "stock":
        return "STAP 격리 분기(subprocess) — 지원 안 함"
    if pipeline == "tap" or (pipeline == "travel" and platform == "blogger"):
        return "TAP 격리 분기(subprocess) — 지원 안 함"
    return None


def _patch_quota_to_999() -> None:
    """get_blog_config(dispatcher/publisher) 와 _is_duplicate 를 런타임 패치해
    일일 쿼터만 999 로 우회한다. 중복 가드는 그대로 유지된다."""
    # 1) dispatcher.get_blog_config — dispatch() 가 쓰는 cfg.daily_quota
    _orig_gbc = dispatcher.get_blog_config

    def _patched_gbc(blog_id):
        cfg = _orig_gbc(blog_id)
        if cfg:
            cfg = dict(cfg)
            cfg["daily_quota"] = 999
        return cfg

    dispatcher.get_blog_config = _patched_gbc

    # 2) shared.publisher.get_blog_config — publish() 의 quota 가드
    _orig_pub_gbc = shared.publisher.get_blog_config

    def _patched_pub_gbc(blog_id):
        cfg = _orig_pub_gbc(blog_id)
        if isinstance(cfg, dict):
            cfg = dict(cfg)
            cfg["daily_quota"] = 999
        return cfg

    shared.publisher.get_blog_config = _patched_pub_gbc

    # 3) dispatcher._is_duplicate — ledger 기반 quota 소진 판단도 통과
    dispatcher._is_duplicate = lambda blog_id: False


def _list_supported() -> None:
    """in-process 지원 분기 blog_id 목록 출력 (실제 발행/배포 없음)."""
    blogs = dispatcher.load_blogs()
    supported, excluded = [], []
    for b in blogs:
        if b.get("status") != "active":
            continue
        reason = _is_isolated(b)
        if reason is None:
            supported.append(b["id"])
        else:
            excluded.append(f"{b['id']}  ({reason})")
    print("== 쿼터우회 지원 분기 (daily_quota=999 만 우회, 중복 가드 유지) ==")
    for bid in sorted(supported):
        print(f"  {bid}")
    print()
    print("== 제외 (subprocess 격리) ==")
    for line in sorted(excluded):
        print(f"  {line}")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    if sys.argv[1] == "--list":
        _list_supported()
        return

    blog_id = sys.argv[1]
    cfg = dispatcher.get_blog_config(blog_id)
    if not cfg:
        print(json.dumps({"success": False, "reason": "unknown_blog_id"}))
        sys.exit(1)

    reason = _is_isolated(cfg)
    if reason:
        print(json.dumps({"success": False, "reason": reason}))
        sys.exit(1)

    if cfg.get("status") != "active":
        print(json.dumps({"success": False, "reason": f"inactive ({cfg.get('status')})"}))
        sys.exit(1)

    _patch_quota_to_999()
    print(f"[quota-bypass] {blog_id} daily_quota=999 우회 (중복 가드 유지)")

    result = dispatcher.dispatch(blog_id)
    print(json.dumps(result, ensure_ascii=False))
    if not result or not result.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()
