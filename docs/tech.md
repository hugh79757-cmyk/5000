# Tech.md — 5000 시스템 기술 문서

## 아키텍처 개요

```
launchd (com.5000.scheduler)
  └─ scheduler.py (메인 루프, 30초 간격)
       ├─ schedule.run_pending() — 정기 발행
       ├─ catchup_missed() — 누락분 보충 (5분마다)
       └─ dispatcher.py subprocess — 실제 발행 실행
```

## 주요 컴포넌트

| 모듈 | 역할 |
|---|---|
| `scheduler.py` | launchd 데몬, 스케줄링/캐치업/헬스체크 |
| `dispatcher.py` | blog_id → pipeline 매핑 + 실행 + ledger 기록 |
| `shared/validators.py` | 발행 전 콘텐츠 검증 (제목, 중복, 한글 비율 등) |
| `shared/telegram_notifier.py` | 오류/리포트 텔레그램 발송 |
| `shared/publisher.py` | 공통 발행 로직 (humanize 포함) |
| `shared/humanizer.py` | AI 말투 → 자연어 변환 (한국어 전용) |
| `pipelines/` | 파이프라인별 구현 (rap, car, curation, etap, senior, gap, travel, stock) |

## 블로그 파이프라인

| 파이프라인 | config 파일 | 블로그 수 | 특징 |
|---|---|---|---|
| RAP | `rap.yaml` | 5 | 부동산 정보 |
| CUAP | `cuap.yaml` | 10 | 큐레이션 (가전/뷰티/반려동물 등) |
| STAP | `stap.yaml` | 6 | 주식/ETF/IPO/섹터 |
| TAP | `tap.yaml` | 8 | 여행/방송, Blogger 병행 |
| SEAP | `seap.yaml` | 2 | 시니어 혜택 |
| CAP | `cap.yaml` | 8 | 자동차 (6개 inactive) |
| ETAP | `etap.yaml` | 36 | 영문 여행 (전체 inactive) |
| GAP | `gap.yaml` | 2 | 키워드 갭 (inactive) |

## 데이터베이스

- `data/content.db` — `publish_ledger` + `articles` 테이블 (중앙 발행 기록)
- `data/car.db` — CAP(car) 파이프라인 전용
- `/Users/twinssn/Projects/STAP/data/stap_content.db` — STAP 파이프라인
- `senior.db` — SEAP 서비스 데이터

## 배포 방식

- **ETAP/Workers 블로그**: Hugo 빌드 → `wrangler pages deploy` 또는 `wrangler deploy`
- **STAP 블로그**: STAP 프로젝트에서 Hugo + wrangler 처리
- **CAP 블로그**: `cap/` 프로젝트에서 Hugo 빌드 + wrangler pages deploy
- **TAP Blogger**: Google Blogger API 직접 발행

## 헬스체크

Scheduler 시작 시:
1. `_check_python_syntax()` — 전체 `.py` 구문 검증 (재발방지)
2. `_check_imports()` — 필수 패키지 존재 여부
3. `_check_boto3_deep()` — boto3 서브패키지完整性 + 자동복구
4. `_check_thumbnail_health()` — R2 썸네일 생성/업로드 테스트
