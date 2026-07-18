# TAP (Travel Auto Publisher) — 기술 문서

> **브랜치**: TAP | **경로**: `/Users/twinssn/Projects/TAP` | **최종 수정**: 2026-07-11

## 프로젝트 개요
TAP은 한국 여행 콘텐츠 자동 발행 시스템입니다. 캠핑장, 관광지, 축제 등의 공공 API 데이터를 수집하고, AI로 블로그 글을 생성하여 Blogger에 발행합니다.

- **Python**: 3.14 (venv: `/Users/twinssn/Projects/TAP/venv`)
- **발행 플랫폼**: Blogger (`travel.rotcha.kr`)
- **스케줄러**: `scheduler.py` (3시간 간격)
- **DB**: `tap.db` (posts, publish_logs, region_stats)

## 배포 방식
- **CI 미사용**: GitHub으로 push하지 않음
- **실행 방식**: 로컬 launchd daemon → `run_5000.sh` / `run_tap.sh` → `scheduler.py`
- **Hugo 배포**: Cloudflare Pages (무료 플랜, 월 500빌드 제한)
- **Worker**: `rotcha-redirect` (wrangler.toml, URL 리다이렉트 전용)

## 빌드/테스트 명령어
```bash
# 가상환경
source /Users/twinssn/Projects/TAP/venv/bin/activate

# 단일 발행
python3 app.py

# 스케줄러
python3 scheduler.py

# 축제
python3 run_festival.py

# 로그
tail -f logs/app.log
```

## 데이터 흐름
```
공공 API (camping/tour/durunubi)
  → content_generator.py (item 구성)
  → ai_writer.py (AI 글 생성)
  → blogger_publisher.py (발행)

추가 모듈:
- blog_info_extractor (네이버 후기)
- nearby_info (주변 맛집/관광지)
- tripcom_affiliate (쿠팡 링크)
```

## 파일 구조
| 파일 | 역할 |
|------|------|
| `app.py` | 메인 엔트리포인트 |
| `scheduler.py` | 스케줄러 |
| `core/ai_writer.py` | AI 글 생성 (OpenAI API, temperature 0.7) |
| `core/content_generator.py` | 데이터 수집 + item 구성 |
| `core/camping_data.py` | 캠핑장 API 데이터 처리 |
| `core/tour_api.py` | 관광 API 클라이언트 |
| `core/blogger_publisher.py` | Blogger 발행 |
| `core/nearby_info.py` | 주변 맛집/관광지 (반경 5km/10km) |
| `core/blog_info_extractor.py` | 네이버 블로그 후기 추출 |
| `core/title_generator.py` | CTR 최적화 제목 생성 |
| `core/theme_selector.py` | 테마 선택 (글램핑, 카라반, 반려동물 등) |
| `core/field_mapper.py` | API 필드 → 표준 키 매핑 유틸리티 |
| `core/festival/` | 축제 전용 파이프라인 |

## 설정 파일
| 파일 | 역할 |
|------|------|
| `config/settings.yaml` | 전역 설정 |
| `config/regions.yaml` | 지역 그룹 정의 |
| `config/themes.yaml` | 테마별 필터 조건 |
| `config/field_mapping.yaml` | API 필드 매핑 |
| `config/keywords.yaml` | 검색 키워드 |
| `config/title_templates.yaml` | 제목 템플릿 |

## 데이터 필드 매핑 규칙
새 데이터 소스 추가 시 `config/field_mapping.yaml`을 먼저 업데이트합니다.

**표준 키** (ai_writer가 읽는 키):
```
title, addr, overview, image, tel, facilities, animalCmgCl, homepage
```

**새 데이터 소스 추가 체크리스트**:
1. `config/field_mapping.yaml`에 소스 정의
2. `content_generator.py`에서 item dict에 표준 키 포함 확인
3. `ai_writer.py`에서 `item.get()` 매칭 확인
4. 테스트: `python3 core/field_mapper.py`

**흔한 실수**:
- API는 `sbrsCl`, ai_writer는 `facilities` → 양쪽 키 모두 전달 필수
- camping은 `addr1`, tour는 `addr` → ai_writer에서 폴백 처리
- `animalCmgCl` 필드 누락 시 AI가 "확인 필요"로 출력

## AI 프롬프트 규칙
- **temperature**: 0.7
- **금지어**: 이모지, 바랍니다, 이번 글에서는, 즐거운
- **쿠팡 문구**: "쿠팡파트너스의 일환으로"

## 코딩 원칙
1. venv 사용: `/Users/twinssn/Projects/TAP/venv/bin/python3`
2. 로깅: `logging.getLogger(__name__)`
3. DB: `tap.db` (posts/publish_logs/region_stats)
4. 에러 시 로그 기록 후 다음 스케줄로 넘김
5. 백업: 수정 전 `.bak` 파일 생성

## 5000 통합 관련
- TAP은 5000에서 `_run_tap_subprocess()`로 서브프로세스 실행
- `pipelines/travel/` 디렉토리는 5000에 위치 (TAP에 `pipelines/` 없음)
- `fetcher.py`: `/Users/twinssn/Projects/TAP/pipelines/travel/fetcher.py`
- `pipeline.py`: `/Users/twinssn/Projects/5000/pipelines/travel/pipeline.py`
- `content.db`: `/Users/twinssn/Projects/5000/data/content.db`

## 스케줄
- 일반 발행: 07:00, 14:00, 20:00 (캠핑30% + 관광70%)
- 축제 발행: 09:00, 16:00, 22:00 (단건80% + 리스트20%)

## 중복 방지
- 일반: 3일 내 동일 지역+테마 차단
- 축제: 7일 내 동일 축제 제목 차단
