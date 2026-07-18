# CAP (Content Auto Publisher) — 기술 문서

> **브랜치**: CAP | **경로**: `/Users/twinssn/Projects/CAP` | **최종 수정**: 2026-07-11

## 프로젝트 개요
CAP은 일반 콘텐츠 자동 발행 시스템입니다. 다양한 주제의 콘텐츠를 AI로 생성하여 Hugo 블로그에 발행합니다.

- **Python**: 3.14
- **발행 플랫폼**: Hugo + Cloudflare Pages
- **테마**: Blowfish (공유 테마)

## 파일 구조
| 디렉토리/파일 | 역할 |
|---------------|------|
| `automation/generate.py` | 콘텐츠 생성 |
| `automation/prompts/` | AI 프롬프트 관리 |
| `.planning/` | 프로젝트 계획 |

## 5000 통합 관련
- CAP은 5000의 `_run_cap_subprocess()`로 실행
- `pipelines/cap/` 또는 관련 파이프라인 사용
- `config/blogs.d/cap.yaml`에서 스케줄 설정

## known issues
- 파이프라인 발행 오류 5종 수정 완료 (2026-07-10)
  - gallery.html: remote URL hotlink (filename overflow 방지)
  - camping: 네트 키워드 제거 (쿠팡 API 미반환)
  - interior: threshold 0.55 + allowed 키워드 보강

## 참고사항
- 기술 문서가 제한적이며, `.continue-here.md`에 세션 기록이 있음
- 파이프라인 실행은 자동 (하루 1회)
