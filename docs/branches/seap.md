# SEAP (Senior Auto Publisher) — 기술 문서

> **브랜치**: SEAP | **경로**: `/Users/twinssn/Projects/SEAP` | **최종 수정**: 2026-07-11

## 프로젝트 개요
SEAP은 시니어/복지 콘텐츠 자동 발행 시스템입니다. 시니어 관련 복지, 건강, 여가 콘텐츠를 AI로 생성하여 Hugo 블로그에 발행합니다.

- **Python**: 3.14
- **발행 플랫폼**: Hugo + Cloudflare Pages
- **테마**: Blowfish (공유 테마)
- **블로그 수**: ~5개

## 데이터 흐름
```
복지/건강 데이터 수집
  → pipelines/senior/pipeline.py (수집 + 필터링)
  → shared/ai_writer.py (AI 글 생성)
  → shared/publishers/hugo_writer.py (Hugo 발행)
  → shared/publishers/deploy.py (빌드 + 배포)
```

## 5000 통합 관련
- SEAP은 5000의 `pipelines/senior/pipeline.py` 사용
- `data/senior.db`에서 콘텐츠 관리
- `config/blogs.d/seap.yaml`에서 스케줄 설정

## known issues
- 특별한 이슈 보고 없음

## 참고사항
- 기술 문서가 제한적
- 파이프라인 실행은 자동 (하루 1회)
- `senior-hugo` 블로그 운영
