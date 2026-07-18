# CUAP (Curation Auto Publisher) — 기술 문서

> **브랜치**: CUAP | **경로**: `/Users/twinssn/Projects/CUAP` | **최종 수정**: 2026-07-11

## 프로젝트 개요
CUAP은 상품 큐레이션 콘텐츠 자동 발행 시스템입니다. 쿠팡 파트너스 API를 통해 상품을 수집하고, AI로 블로그 글을 생성하여 Hugo 블로그에 발행합니다.

- **Python**: 3.14
- **발행 플랫폼**: Hugo + Cloudflare Pages
- **테마**: Blowfish (공유 테마)
- **주요 블로그**: fitness, kitchen, interior, appliance, laptop, beauty, sofa, baby, pet, camping

## 빌드/배포 명령어
```bash
# Hugo 빌드
hugo --minify

# 배포
wrangler pages deploy ./public --project-name=<blog-id> --commit-dirty=true
```

## 데이터 흐름
```
쿠팡 파트너스 API
  → pipelines/curation/keywords.py (키워드 관리)
  → pipelines/curation/pipeline.py (수집 + 필터링)
  → shared/ai_writer.py (AI 글 생성)
  → shared/publishers/hugo_writer.py (Hugo 발행)
  → shared/publishers/deploy.py (빌드 + 배포)
```

## 파일 구조
| 디렉토리/파일 | 역할 |
|---------------|------|
| `pipelines/curation/pipeline.py` | 메인 파이프라인 |
| `pipelines/curation/keywords.py` | 키워드 관리 (keyword_expander) |
| `pipelines/curation/writer.py` | AI 글 생성 |
| `shared/relevance_scorer.py` | 관련성 점수 계산 |
| `shared/content_store.py` | 콘텐츠 저장/중복 체크 |
| `shared/title_templates.py` | 제목 템플릿 관리 |

## AI 프롬프트 규칙
- **temperature**: 0.7
- **금지어**: 과연, 놀랍게도, 바랍니다, 알아보겠습니다
- **가성비 금지**: 제목에서 사용 금지 → 대체: "합격점", "실속", "가격 대비"

## 콘텐츠 필터링
- **relevance_scorer**: threshold 0.55 (interior 등)
- **keyword_expander**: 키워드 확장으로 다양한 상품 수집
- **stop_words**: 34개 (연도/월/범용속성 추가)
- **title_templates**: 11개 템플릿 (myth_busting, new_release, situation_based 추가)

## 제목 생성 로직 (Phase 6 완료)
- comparison/ranking 하드코딩 제거
- 회전 윈도우 5→10
- `_classify_title()` 정규식 개선 (vs 분류 9.7% 해소)
- 블로그별 템플릿 오버라이드 10개 활성화

## known issues
- `appliance-hugo`: 듀스핀 키워드 `similar_title` 반복 (유사도 80% 초과)
- `fitness-hugo`: 고무/고무밴드 등 키워드 제거 (쿠팡 API 미반환)
- `kitchen-hugo`: 계량 키워드 제거 (쿠팡 API 미반환)

## 5000 통합 관련
- CUAP은 5000의 `pipelines/curation/pipeline.py` 사용
- 10개 블로그 모두 5000에서 관리
- `config/blogs.d/cuap.yaml`에서 스케줄 설정
- Blowfish 테마의 `.lead { font-size: 1rem; }` CSS 수정 완료

## 모니터링
```bash
# 키워드 감사
python3 scripts/maintain_keyword_pool.py --audit

# 드라이런
python3 scripts/pipeline_dryrun.py

# 테스트
source .venv/bin/activate && pytest tests/ -q
```
