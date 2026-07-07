"""shared 패키지 초기화 — 환경변수 로드"""

from dotenv import load_dotenv
import os

# 프로젝트 루트 .env 로드
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"), override=True)
# 공통 .env.common 로드
load_dotenv(os.path.expanduser("~/.env.common"), override=False)

# env_loader 모듈 export (하위 호환성: from shared import env_loader)
from . import env_loader  # noqa: F401