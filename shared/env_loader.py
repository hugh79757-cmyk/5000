"""환경변수 중앙화 로드 — 모든 shared 모듈에서 사용"""

from dotenv import load_dotenv
import os

def load_env() -> None:
    """프로젝트 루트 .env와 공통 .env.common 로드"""
    project_root = os.path.dirname(os.path.dirname(__file__))
    load_dotenv(os.path.join(project_root, ".env"), override=True)
    load_dotenv(os.path.expanduser("~/.env.common"), override=False)

# import 시 자동 로드
load_env()