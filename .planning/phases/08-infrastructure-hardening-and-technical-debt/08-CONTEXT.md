# Phase 8: Infrastructure Hardening & Technical Debt

## 배경

Phase 1~7을 통해 기능 안정화, 테스트, 콘텐츠 품질 향상을 완료했다. Phase 8은 그동안 발견된 인프라 수준의 기술 부채를 해소하는 단계다. 사용자에게 visible한 기능 변경보다는 유지보수성과 안정성을 위한 내부 정리에 초점을 둔다.

## 사전 파악 완료 항목

Phase 7 분석 과정에서 아래 항목들을 이미 확인했다:

| 항목 | 상태 | 심각도 |
|------|------|--------|
| STAP/.venv 빈 폴더 (유령 venv) | 존재하나 실행 안 됨 | 🟡 Low |
| TAP venv (openai 2.44.0) ≠ 5000/.venv (openai 2.41.0) | 버전 불일치 | 🟡 Medium |
| requirements.txt 전부 `>=` loose pin | SAP만 `==` 고정 | 🔴 High |
| pydantic-core 2.47.0 충돌 (pip upgrade 시 재현 가능) | 이미 발생 | 🔴 High |
| BLOG_SITE_PATHS 6개 절대경로 하드코딩 | `/Users/twinssn` 박힘 | 🟡 Medium |
| `_inject_related_cards()` 변수 초기화 순서 버그 | cross_found NameError 위험 | 🔴 High |
| ai_writer SPOF (49곳에서 import, retry 약함) | backoff/breaker 없음 | 🔴 High |
| TAP `core/fetcher.py` 5000과 분리 | 5000에 동일 역할 함수 존재 | 🟡 Low |


## 파일 구조 참조

- `shared/publisher.py` (L396-403): BLOG_SITE_PATHS 하드코딩
- `shared/publisher.py` (L327-527): `_inject_related_cards()` 전체
- `shared/ai_writer.py` (L52-121): generate() 함수, 3-tier fallback
- `shared/db_paths.py`: DB 경로 단일 관리 (paths.py와 별도)
- `shared/paths.py`: 프로젝트 경로 단일 관리 (130+ 경로 대체 완료)
- `5000/requirements.txt`: openai>=1.30.0, pydantic 명시 없음
- `TAP/requirements.txt`: openai>=1.0.0, pydantic 명시 없음
- `SAP/requirements.txt`: openai==2.21.0, pydantic==2.12.5, pydantic_core==2.41.5

## 리스크

- requirements.txt 버전 고정 시 기존 설치된 패키지와 충돌 가능
- ai_writer 변경 시 49개 import site 모두 영향
- BLOG_SITE_PATHS 리팩토링 시 _file_exists 로직 영향
