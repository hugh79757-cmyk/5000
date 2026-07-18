# STAP (Stock Auto Publisher) — 기술 문서

> **브랜치**: STAP | **경로**: `/Users/twinssn/Projects/STAP` | **최종 수정**: 2026-07-11

## 프로젝트 개요
STAP은 주식/금융 콘텐츠 자동 발행 시스템입니다. DART 공시, 배당, ETF, 섹터, IPO, 금융(예적금) 데이터를 수집하고 AI로 분석 글을 생성하여 Hugo 블로그에 발행합니다.

- **Python**: 3.14 (.venv)
- **발행 플랫폼**: Hugo + Cloudflare Pages (6개 사이트)
- **DB**: `data/stap.db`, `data/stap_content.db`

## 사이트 목록
| 사이트 | 도메인 | 테마 | 비고 |
|--------|--------|------|------|
| stock | stock.informationhot.kr | Congo | 주식 공시 분석 |
| dividend | dividend.techpawz.com | Blowfish | 배당주 분석 |
| etf | etf.techpawz.com | Blowfish | ETF 비교 분석 |
| sector | sector.techpawz.com | Blowfish | 섹터 분석 |
| ipo | ipo.techpawz.com | Blowfish | IPO/공모주 분석 |
| finance | finance.techpawz.com | Blowfish | 예적금 금리 비교 |

## 빌드/배포 명령어
```bash
# 가상환경
cd /Users/twinssn/Projects/STAP && source .venv/bin/activate

# Hugo 빌드
hugo --minify

# 배포
wrangler pages deploy ./public --project-name=X --commit-dirty=true
```

## 데이터 흐름
```
수집 (pipelines/X/pipeline.py)
  → AI 글 생성 (pipelines/X/writer.py)
  → 발행 (shared/publisher.py)
  → Hugo 빌드/배포
```

## 파일 구조
| 디렉토리/파일 | 역할 |
|---------------|------|
| `pipelines/stock/` | 주식 공시 분석 |
| `pipelines/dividend/` | 배당주 분석 |
| `pipelines/etf/` | ETF 비교 분석 |
| `pipelines/sector/` | 섹터 분석 |
| `pipelines/ipo/` | IPO/공모주 분석 |
| `pipelines/finance/` | 예적금 금리 비교 |
| `shared/publisher.py` | Hugo 글 생성 + front-matter |
| `shared/r2_uploader.py` | R2 이미지 업로드 |
| `pipelines/thumbnail_factory.py` | 블로그별 썸네일 생성 |

## AI 프롬프트 규칙
- **temperature**: 0.4 (system/user 역할 분리)
- **system**: 페르소나 + 절대 규칙
- **user**: 데이터 + 출력 형식
- **날짜**: `datetime.now()` 동적 삽입 (하드코딩 금지)
- **금지어**: 과연, 놀랍게도, 바랍니다, 알아보겠습니다

## 데이터 전달 규칙
- writer.py 파싱: `re.sub(r'^\*+\s*', '', line)` 사용 (lstrip 금지)
- publisher.py: AI 생성 "함께 읽어보기" 제거 후 DB 기반 관련글 삽입
- DEFAULT_THUMBNAILS: 블로그별 개별 기본 썸네일
- front-matter: Blowfish는 `featureimage`, Congo/PaperMod는 `image`
- 경쟁 모델 없을 때: 단독 분석 (AI 임의 비교 금지)

## 코딩 원칙
1. .venv 사용
2. 절대경로 사용
3. 수정 전 .bak 백업
4. Hugo 빌드 후 wrangler 배포
5. git commit 메시지에 변경 사항 상세 기록

## 5000 통합 관련
- STAP은 5000에서 `_run_stap()`으로 서브프로세스 실행
- sector-hugo는 STAP의 `pipelines/sector/pipeline.py` 사용
- dispatcher.py에서 `_resolve_pipeline("sector")` → STAP 호출
- `data/stap_content.db`에서 콘텐츠 관리

## known issues
- `sector-hugo`: 23회 연속 `no_content` 실패 (토픽 순환 소진 + 중복 가드)
- `dividend-hugo`: `duplicate_source_id` → UUID 적용 완료
- `etf-hugo`: transient `no_result` → 자체 해소됨
