# AGENTS.md - 프로젝트 5000 코딩 가이드라인

## 프로젝트 개요

프로젝트 5000은 자동 콘텐츠 발행 파이프라인 시스템으로, 일일 5,000건의 콘텐츠를 생성하고 발행하는 것을 목표로 합니다. 현재 파이프라인(TAP/여행, CAP/자동차, STAP/주식, GAP/시니어, RAP/부동산)이 18개 블로그(Hugo/Blogger/WordPress)에 운영 중입니다.

## 빌드/테스트 명령어

### 가상환경 활성화
```bash
source .venv/bin/activate  # macOS/Linux
```

### 의존성 설치
```bash
pip install -r requirements.txt
```

### Hugo 사이트 빌드 (블로그 배포)
```bash
npm run build  # 또는 hugo --gc --minify
```

### Hugo 개발 서버 실행
```bash
npm run dev    # 또는 hugo server -D
```

### 테스트 실행
```bash
python test_refactor.py                    # 기본 테스트
python -m pytest                           # pytest로 실행 (설치 필요)
python test_refactor.py -v                 # 상세 출력
```

### 개별 테스트 모듈 실행
```bash
python -m pytest test_refactor.py::test_validators  # 특정 함수 테스트
python -c "from test_refactor import test_validators; test_validators()"
```

### 배포 스크립트
```bash
bash scripts/batch_push.sh    # Cloudflare Pages 배포
bash run_5000.sh              # 전체 파이프라인 실행
```

### 스케줄러 관리
```bash
launchctl load ~/Library/LaunchAgents/com.5000.scheduler.plist  # 스케줄러 시작
launchctl unload ~/Library/LaunchAgents/com.5000.scheduler.plist  # 스케줄러 정지
```

## 코드 스타일 가이드라인

### Python 버전
- Python 3.14 사용 (.venv/bin/python3.14)
- f-string 사용 권장
- 타입 힌트 적극 사용

### 임포트 순서 (PEP 8)
```python
# 1. 표준 라이브러리
import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# 2. 서드파티 라이브러리
import yaml
import sqlite3
from dotenv import load_dotenv

# 3. 로컬 모듈
from shared.publisher import publish_to_hugo
from shared.content_store import insert_article
```

### 네이밍 컨벤션
- **snake_case**: 함수, 변수, 모듈명 (`generate_article`, `content_store`)
- **PascalCase**: 클래스명 (`ArticleValidator`, `ContentPublisher`)
- **UPPER_SNAKE_CASE**: 상수 (`MAX_RETRIES`, `DEFAULT_QUOTA`)
- **접두사**: `_`로 시작하는 이름은 내부용 (`_validate_content`, `_cache`)

### 에러 처리 패턴
```python
try:
    result = some_operation()
except ValueError as e:
    logger.error(f"Validation failed: {e}")
    return False, str(e)
except ConnectionError as e:
    logger.error(f"Network error: {e}")
    raise  # 중요 에러는 재전파
else:
    return True, result
finally:
    cleanup_resources()
```

### 함수 반환값 패턴
```python
def process_content(content):
    """성공시 (True, result), 실패시 (False, error_message) 반환"""
    if not content:
        return False, "Content is empty"
    
    # 처리 로직
    processed = content.upper()
    return True, processed
```

### 로깅
```python
import logging
logger = logging.getLogger(__name__)

# 레벨별 사용
logger.debug("디버그 정보")      # 상세 디버깅
logger.info("정상 동작")         # 일반 정보
logger.warning("경고 상황")      # 문제 가능성
logger.error("에러 발생")        # 처리 실패
logger.critical("심각한 오류")   # 시스템 장애
```

### 데이터베이스 접근 패턴
```python
import sqlite3
from contextlib import closing

def query_database(db_path, query, params=()):
    """컨텍스트 매니저를 사용한 안전한 DB 접근"""
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row  # 딕셔너리 스타일 접근
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()
```

### 설정 파일 처리
```python
import yaml
from pathlib import Path

CONFIG_DIR = Path(__file__).parent / "config"

def load_config(filename):
    """YAML 설정 파일 로드"""
    with open(CONFIG_DIR / filename, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
```

### 파이프라인 인터페이스
```python
# 모든 파이프라인은 run(cfg) 함수를 구현해야 함
def run(cfg):
    """
    Args:
        cfg: blog configuration dict from blogs.yaml
    
    Returns:
        tuple: (success: bool, message: str, data: dict or None)
    """
    try:
        # 1. 데이터 수집
        # 2. 콘텐츠 생성  
        # 3. 발행
        return True, "Published successfully", {"article_id": 123}
    except Exception as e:
        logger.exception(f"Pipeline failed: {e}")
        return False, str(e), None
```

### 프롬프트 파일 구조
```
prompts/
├── travel/          # 여행 파이프라인 프롬프트
├── car/             # 자동차 파이프라인 프롬프트  
├── stock/           # 주식 파이프라인 프롬프트
└── gap/             # 시니어/생활정보 프롬프트
```

## 파일 구조 컨벤션

### 공유 모듈 (shared/)
```
shared/
├── publisher.py          # 플랫폼별 발행 (Hugo/Blogger/WordPress)
├── content_store.py      # DB 작업 (articles, used_images)
├── ai_writer.py          # OpenAI API 래퍼
├── telegram_notifier.py  # 에러 알림
└── validators.py         # 콘텐츠 검증
```

### 파이프라인 구조
```
pipelines/
├── travel/               # TAP - 여행 콘텐츠
│   ├── fetcher.py        # TourAPI 데이터 수집
│   ├── writer.py         # 콘텐츠 생성
│   └── __init__.py
├── car/                  # CAP - 자동차 콘텐츠
│   ├── daily_refresh.py  # carisyou 스크래핑
│   ├── data_builder.py   # AI 입력 데이터 조립
│   └── __init__.py
└── stock/                # STAP - 주식 콘텐츠
    ├── pipeline.py       # 메인 파이프라인
    ├── fetcher.py        # DART API 수집
    └── writer.py         # 공시 분석 글 생성
```

### 설정 파일 구조
```
config/
├── blogs.yaml           # 블로그 정의 (18개)
├── models.yaml          # AI 모델 설정
├── api_keys.yaml        # API 키 관리
└── prompts.yaml         # 프롬프트 매핑
```

### 데이터베이스
```
data/
├── content.db           # 중앙 콘텐츠 DB
├── car.db              # CAP 전용 DB
├── stock.db            # STAP 전용 DB
└── gap.db              # GAP 키워드 DB
```

## 코딩 원칙

1. **실패 허용 설계**: 모든 외부 API 호출은 재시도 로직 포함
2. **중복 방지**: 이미지, 장소, 콘텐츠 중복 체크 필수
3. **할당량 준수**: daily_quota 초과 발행 방지
4. **플랫폼 독립성**: Hugo/Blogger/WordPress 일관된 인터페이스
5. **에러 전파**: 로깅과 알림으로 문제 즉시 파악

## 자동화 및 CI/CD

### 자동 배포
- 매일 22:45에 `scripts/batch_push.sh` 실행
- Cloudflare Pages에 Hugo 사이트 배포
- Wrangler CLI 사용

### 스케줄러
- 5분 간격 catchup 실행으로 누락 발행 방지
- Telegram 알림으로 실시간 모니터링

### 모니터링 지표
- 일일 발행 건수
- API 호출 성공률
- 데이터베이스 크기
- 에러 발생 빈도

## 주의사항

1. **API 키 보안**: `.env` 파일 커밋 금지, `api_keys.yaml` 보안 유지
2. **할당량 관리**: 블로그별 daily_quota 초과 방지
3. **데이터 무결성**: SQLite 트랜잭션 사용 권장
4. **리소스 관리**: 대용량 DB 작업시 메모리 모니터링
5. **로깅 레벨**: production에서는 INFO 이상만 출력

## 문제 해결

### 일반적인 문제
- **데이터베이스 잠금**: 트랜잭션 타임아웃 설정
- **API 할당량 초과**: 요청 간 지연 추가
- **이미지 중복**: `is_image_used()` 함수로 확인
- **장소 중복**: `used_places` 테이블 활용

### 디버깅
```bash
tail -f logs/scheduler.log          # 실시간 로그 모니터링
python -c "import sys; print(sys.path)"  # Python 경로 확인
sqlite3 data/content.db "SELECT * FROM articles LIMIT 5;"  # DB 확인
```

이 가이드라인은 프로젝트 5000의 일관된 코드 품질과 유지보수성을 보장합니다.

## 리팩토링 원칙

1. **except Exception 금지 → 구체적 예외 타입 + logger.error 필수**
   ```python
   # 나쁜 예시
   try:
       result = api_call()
   except Exception as e:
       print(f"Error: {e}")
   
   # 좋은 예시
   try:
       result = api_call()
   except requests.exceptions.Timeout as e:
       logger.error(f"[API_TIMEOUT] url={api_url}, timeout={timeout}s")
       return False, "API timeout"
   except sqlite3.OperationalError as e:
       logger.error(f"[DB_ERROR] query={query}, error={str(e)}")
       raise
   ```

2. **함수 50줄 초과 금지 → 하나의 함수는 하나의 역할**
   ```python
   # 나쁜 예시 (70줄 함수)
   def process_everything(data):
       # 데이터 검증 (20줄)
       # 데이터 변환 (30줄)
       # API 호출 (20줄)
       pass
   
   # 좋은 예시
   def validate_data(data):
       """데이터 검증 (20줄)"""
       pass
   
   def transform_data(data):
       """데이터 변환 (20줄)"""
       pass
   
   def call_api(transformed_data):
       """API 호출 (15줄)"""
       pass
   
   def process_everything(data):
       """메인 함수 - 역할 위임"""
       validated = validate_data(data)
       transformed = transform_data(validated)
       return call_api(transformed)
   ```

3. **매직넘버 금지 → 파일 상단 상수 또는 config로 분리**
   ```python
   # 나쁜 예시
   def calculate_quota():
       return daily_count * 5  # 5가 무엇인지?
   
   # 좋은 예시
   MAX_POSTS_PER_RUN = 5
   RETRY_LIMIT = 3
   TIMEOUT_SECONDS = 30
   
   def calculate_quota():
       return daily_count * MAX_POSTS_PER_RUN
   ```

4. **로그는 검색 가능하게 → [태그] key=value 형식**
   ```python
   # 나쁜 예시
   logger.info("Published article about car")
   
   # 좋은 예시
   logger.info("[PUBLISH_SUCCESS] blog_id=car-blog, article_id=123, pipeline=CAP")
   logger.error("[API_FAILURE] service=TourAPI, endpoint=/places, status_code=429")
   logger.debug("[DB_QUERY] table=used_images, action=insert, count=1")
   ```

5. **핵심 함수에 pytest 테스트 필수**
   ```python
   # tests/test_publisher.py
   import pytest
   from shared.publisher import publish_to_hugo
   
   def test_publish_to_hugo_success():
       """성공적인 Hugo 발행 테스트"""
       result = publish_to_hugo(
           title="테스트 글",
           content="# 테스트 콘텐츠",
           slug="test-post"
       )
       assert result[0] is True
       assert "test-post" in result[1]
   
   def test_publish_to_hugo_empty_title():
       """제목이 빈 경우 실패 테스트"""
       result = publish_to_hugo(title="", content="# 내용", slug="test")
       assert result[0] is False
       assert "title" in result[1].lower()
   ```

### 테스트 작성 가이드라인
- **단위 테스트**: 함수 하나당 하나의 테스트 파일
- **통합 테스트**: 파이프라인 전체 흐름 테스트
- **모의 객체**: 외부 API는 `unittest.mock`으로 모킹
- **테스트 데이터**: `tests/fixtures/` 디렉토리에 샘플 데이터 보관

```bash
# 테스트 구조 예시
tests/
├── unit/
│   ├── test_publisher.py
│   ├── test_content_store.py
│   └── test_validators.py
├── integration/
│   ├── test_tap_pipeline.py
│   └── test_cap_pipeline.py
└── fixtures/
    ├── sample_article.json
    └── sample_api_response.json
```

이 리팩토링 원칙은 코드 품질을 지속적으로 향상시키고 기술 부채를 방지합니다.
```

## 데이터 필드 매핑 규칙

새 데이터 소스 추가 시 반드시 아래 절차를 따릅니다.

1. 설정 파일 우선: API 필드 -> 표준 키 매핑은 config/field_mapping.yaml에 정의 (TAP)
2. 표준 키 사용: ai_writer가 읽는 키는 standard_keys만 사용
3. 필수 필드 체크: required 필드가 비면 AI에 전달하지 않음
4. 폴백 키 지원: overview: intro|lineIntro 형태로 pipe 구분

새 데이터 소스 추가 체크리스트:
- config/field_mapping.yaml에 소스 추가
- standard_keys에 매핑 확인
- required 필드 정의
- ai_writer에서 item.get() 매칭 확인
- content_generator에서 item dict에 필드 포함 확인

흔한 실수 방지:
- 필드명 불일치: API sbrsCl vs ai_writer facilities -> 양쪽 키 모두 전달
- 주소 키 차이: camping addr1, tour addr -> 폴백 처리 필수
- competitor 없을 때 AI가 임의 생성 -> 경쟁 모델 없음 명시 블록 필수


## 데이터 필드 매핑 규칙

새 데이터 소스 추가 시 반드시 아래 절차를 따릅니다.

1. 설정 파일 우선: API 필드 -> 표준 키 매핑은 config/field_mapping.yaml에 정의 (TAP)
2. 표준 키 사용: ai_writer가 읽는 키는 standard_keys만 사용
3. 필수 필드 체크: required 필드가 비면 AI에 전달하지 않음
4. 폴백 키 지원: overview: intro|lineIntro 형태로 pipe 구분

새 데이터 소스 추가 체크리스트:
- config/field_mapping.yaml에 소스 추가
- standard_keys에 매핑 확인
- required 필드 정의
- ai_writer에서 item.get() 매칭 확인
- content_generator에서 item dict에 필드 포함 확인

흔한 실수 방지:
- 필드명 불일치: API sbrsCl vs ai_writer facilities -> 양쪽 키 모두 전달
- 주소 키 차이: camping addr1, tour addr -> 폴백 처리 필수
- competitor 없을 때 AI가 임의 생성 -> 경쟁 모델 없음 명시 블록 필수
