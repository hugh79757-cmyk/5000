# RAP (Real Estate Auto Publisher) — 기술 문서

> **브랜치**: RAP | **경로**: `/Users/twinssn/Projects/RAP` | **최종 수정**: 2026-07-11 | **version**: 1.0

## 프로젝트 개요
RAP 시스템은 **AI 기반 부동산 콘텐츠 생성 → Hugo 정적 사이트 → Cloudflare Pages 배포**로 이어지는 자동화 블로그 파이프라인입니다. 5개의 Hugo 사이트가 각기 다른 부동산 주제로 운영되며, 모두 동일한 테마(Blowfish)와 커스텀 레이아웃을 공유합니다.

- **도메인 패밀리**: `*.informationhot.kr`
- **테마**: Blowfish (git submodule)

## 사이트 인벤토리
| 디렉토리 | 사이트명 | 도메인 | GA4 | 색상 |
|---------|---------|--------|-----|------|
| `rap-hugo/` | 부동산 시세 리포트 | `apt.informationhot.kr` | G-ZWGYYMYW74 | ocean |
| `rap2-hugo/` | 청약 알리미 | `apply.informationhot.kr` | G-T02JYWS566 | sapphire |
| `rap3-hugo/` | 부동산 세금 가이드 | `tax.informationhot.kr` | G-GENY3H27YE | fire |
| `rap4-hugo/` | 전세월세 리포트 | `rent.informationhot.kr` | G-MBRJG4BBNS | congo |
| `rap5-hugo/` | 브랜드 아파트 백과 | `brand.informationhot.kr` | G-KFRHWF8W70 | autumn |

**공통 설정:**
- 언어: `ko`, 타임존: `Asia/Seoul`
- 테마: Blowfish (git submodule)
- Goldmark: `unsafe = true` (인라인 HTML 허용)
- 홈페이지: `profile` 레이아웃, 최근 글 12개 표시
- 출력: `[HTML, RSS, JSON]` (홈), `[HTML, RSS]` (섹션)

## 빌드/배포 명령어
```bash
# 로컬 개발 서버
hugo server -D

# 빌드
./fix-tables.sh && hugo --minify

# 배포
./fix-tables.sh && hugo --minify && wrangler pages deploy public/

# 새 글
hugo new posts/{slug}/index.md

# 전체 재빌드
rm -rf public resources && hugo --minify
```

## 디렉토리 구조 (공통)
```
rap-hugo/
├── content/
│   └── posts/
│       └── {slug}/
│           └── index.md          ← 개별 포스트 (frontmatter + markdown)
├── layouts/
│   ├── _default/
│   │   └── single.html           ← 본문 커스텀 템플릿 (AdSense 광고 삽입)
│   └── partials/
│       ├── extend-head.html      ← <head> 주입 (AdSense, Naver, GA4)
│       └── related.html          ← 관련 글 목록
├── static/
│   └── ads.txt                   ← 구글 애드센스 인증 파일
├── themes/
│   └── blowfish/                  ← git submodule (변경 금지)
├── hugo.toml                     ← 사이트 설정
├── fix-tables.sh                 ← 빌드 전 깨진 표 수정 스크립트
└── .gitignore                    ← resources/, public/, themes/
```

> **Note**: `rap4-hugo`는 유일하게 `config/_default/languages.ko.toml` 파일이 있음 (KO 언어 설정 강제)

## 콘텐츠 파이프라인

### 콘텐츠 생성 (writer.py)
외부 AI 생성기 `writer.py`가 다음 데이터를 기반으로 마크다운 파일을 생성합니다:
- **국토교통부 실거래가 API** — 아파트 매매/전세 실거래가
- **청약홈 API** — 분양/임대 공고 정보
- **국세청 데이터** — 양도세/취득세 기준

생성된 파일은 `content/posts/{slug}/index.md` 형태로 각 사이트 디렉토리에 저장됩니다.

### frontmatter 구조
```yaml
---
title: "2026년 06월 강남구 실거래가 종합"
slug: '2026년-06월-강남구-실거래가-종합'
date: '2026-06-03T07:53:29+09:00'
draft: false
description: "- 우성4 영등포구 실거래가 2026년 05월"
tags: ['강남구', '실거래가', '부동산']
categories: ['부동산']
featureimage: "https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/rap-thumbnails/20260603-77e41f7e3f.webp"
---
```

### 마크다운 특징
- **테이블**: Hugo/Goldmark 표준 테이블 문법 (`| col | col |`)
- **내부 링크**: `/posts/{slug}/` 형태의 상대 경로
- **쿠팡 파트너스**: 문서 하단에 추천 가전 섹션 (iframe 링크)
- **함께 읽으면 좋은 글**: 본문 상단과 하단에 관련 글 링크
- **div 박스**: `📌 놓치면 아쉬운 글` 등 스타일드 프로모션 박스 (Goldmark unsafe 모드)

## 커스텀 레이아웃

### `layouts/_default/single.html`
Blowfish 기본 `single.html`을 오버라이드하여 **애드센스 인-아티클 광고**를 H2 헤딩 사이에 삽입합니다.

```hugo
{{ $parts := split $content "<h2" }}
{{ if gt (len $parts) 1 }}
  {{ range $i, $part := $parts }}
    {{ if eq $i 0 }}
      {{ $part | safeHTML }}              ← H2 이전 내용은 그대로
    {{ else }}
      {{ if or (eq $i 2) (eq $i 4) }}
        <div class="ad-in-article">        ← 2번째와 4번째 H2 뒤에 광고 삽입
          <ins class="adsbygoogle"
               data-ad-client="ca-pub-6677996696534146"
               data-ad-slot="3403350155"></ins>
        </div>
      {{ end }}
      {{ printf "<h2%s" $part | safeHTML }} ← H2 섹션 출력
    {{ end }}
  {{ end }}
{{ else }}
  {{ .Content }}                           ← H2가 1개 이하면 광고 없음
{{ end }}
```

- 광고주: `ca-pub-6677996696534146`
- 광고 슬롯: `3403350155`

### `layouts/partials/extend-head.html`
- **Google AdSense** (`adsbygoogle.js`)
- **Google Analytics 4** (gtag, 사이트별 ID 상이)
- **Naver Site Verification** (사이트별 인증코드 상이)
- **Pinterest Verification** (`a2f1f9d5f2c18d423c1d99f6c2d0247b`)

### `layouts/partials/related.html`
관련 글을 심플한 리스트로 렌더링.

## 표깨짐 방지 시스템

### 문제
AI 생성기(`writer.py`)가 마크다운 테이블 **구분자 행(separator row)** 에서 이중 파이프(`||`)를 생성:
```
 잘못됨:  |--||----|---|-----|   ← 5열 but 이중 파이프
 올바름:  |---|---|---|---|---|   ← 5열, 각 열 ---
```

### 해결: `fix-tables.sh`
각 사이트 루트에 위치한 Python 스크립트.
- `content/posts/**/index.md` 스캔
- `||` (이중 파이프)가 포함된 구분자 행 감지
- 헤더 행의 열 개수 계산
- `|` + `---|` × N 형태로 교정

## 배포 아키텍처
- **Wrangler 직접 빌드** (`wrangler pages deploy`)
- 외부 `dispatcher.sh` 또는 `deploy.sh` 스크립트가 각 사이트의 Hugo 빌드와 Wrangler 배포를 순차 실행

## git 워크플로우
- 단일 `main` 브랜치 운영
- 각 사이트가 독립적인 git 저장소

| 유형 | 예시 | 설명 |
|------|------|------|
| `publish:` | `publish: 2026-04-25 22:45 (4건)` | 자동 콘텐츠 발행 |
| `fix:` | `fix: 표 깨짐 수정 P2:43 P4:0` | 자동/수동 버그 수정 |
| `feat:` | `feat: SEO 파일 추가 및 표 수정` | 기능 추가 |
| `init:` | `init: RAP Hugo site (blowfish theme)` | 최초 설정 |

## 사이트별 유의사항
| 사이트 | 주의 |
|--------|------|
| `rap-hugo` | 가장 많은 포스트 보유 (~275+) |
| `rap2-hugo` | 청약 공고 특성상 표가 많음 |
| `rap3-hugo` | 세금 계산 로직 포함 콘텐츠 (수동 검증 필요) |
| `rap4-hugo` | `config/` 디렉토리 별도 존재, `relatedContentLimit` 설정 누락 |
| `rap5-hugo` | 브랜드 분석 콘텐츠 (시각 자료 비중 높음) |

## 알려진 이슈
| 이슈 | 상태 | 해결 |
|------|------|------|
| 표 구분자 `||` 버그 | fix-tables.sh 자동 교정 |
| `writer.py` 할루시네이션 ("특히" 과다 생성) | 1회 cleanup 완료 (정기 검토 필요) |
| GA4 이중 설정 (hugo.toml + partial) | partial 우선 (정리 가능) |
| rap4-hugo `relatedContentLimit` 누락 | 수동 추가 필요 |

## 5000 통합 관련
- RAP은 5000의 `_run_rap_subprocess()`로 실행 (또는 직접 실행)
- `pipelines/rap/` 디렉토리는 5000에 위치
- `rap-hugo`, `rap2-hugo` 등은 5000의 Hugo 사이트로 관리
