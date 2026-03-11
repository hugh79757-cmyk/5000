import sys
import os
import logging

sys.path.insert(0, "/Users/twinssn/Projects/5000")
sys.path.insert(0, "/Users/twinssn/Projects/tour-auto-publisher")
os.chdir("/Users/twinssn/Projects/tour-auto-publisher")

from dotenv import load_dotenv
load_dotenv("/Users/twinssn/Projects/tour-auto-publisher/.env")
load_dotenv("/Users/twinssn/Projects/5000/.env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

HUGO_BLOGS = ["travel-hugo", "travel1-hugo", "travel2-hugo", "travel3-hugo", "travel4-hugo"]


def main():
    from shared.content_store import init_db
    init_db()

    if len(sys.argv) < 2:
        print("usage: dispatcher.py <blog_id|all-hugo|report|init-db>")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "init-db":
        print("DB initialized")
        return

    if cmd == "report":
        from shared.monitor import send_daily_report
        send_daily_report()
        return

    if cmd == "all-hugo":
        from pipelines.travel.pipeline import run_all_hugo
        results = run_all_hugo(count_per_blog=1)
        print(f"all-hugo: {len(results)} published")
        return

    if cmd in HUGO_BLOGS or cmd == "travel-blogger":
        from pipelines.travel.pipeline import _run_single
        result = _run_single(cmd)
        if result:
            print(f"{cmd}: success - {result.get('url','')}")
        else:
            print(f"{cmd}: failed or quota reached")
        return

    print(f"unknown command: {cmd}")
    sys.exit(1)


if __name__ == "__main__":
    main()
