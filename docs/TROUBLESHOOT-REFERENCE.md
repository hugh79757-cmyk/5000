# TROUBLESHOOT-REFERENCE.md — 팀 전용 문제 해결 참고서

> 기반: 2026-08-18 정밀 기준 데이터 (31개 파일, 10개 워커 조사 완료)
> 대상: 모든 파이프라인 운영자, 신규 온보딩 대상

---

## 1. 5000 아키텍처 개요

```
scheduler.py (launchd, 30초 폴링)
  → dispatcher.py (blog_id 라우터)
    → pipelines/{type}/pipeline.py (AI 글 생성 + QA)
      → shared/publisher.py (Hugo 콘텐츠 기록)
        → shared/publishers/deploy.py (Hugo 빌드 + wrangler 배포)
          → Cloudflare Pages/Workers
```

- **스케줄러**: `scheduler.py` — `schedule` 라이브러리, 30초 폴링, 5분마다 캐치업
- **디스패처**: `dispatcher.py` — `blog_id` → 파이프라인 동적 임포트, 쿨다운/할당량 검사
- **배포**: `deploy.py` — `CLOUDFLARE_API_TOKEN` 제거 → OAuth 프로파일 사용, `/tmp/wrangler_deploy.lock` 직렬화

---

## 2. 파이프라인별 구조도

| 파이프라인 | 디렉터리 | 블로그 수 | 출력 플랫폼 | 콘텐츠 유형 |
|-----------|---------|----------|-----------|-----------|
| **etap** | `pipelines/etap/` | 35+ | Cloudflare Pages + Hugo | 영어 여행 가이드 |
| **car** | `pipelines/car/` | 8 | Cloudflare Pages + Hugo | 자동차 |
| **senior** | `pipelines/senior/` | ~5 | Cloudflare Pages + Hugo | 시니어 복지 |
| **gap** | `pipelines/gap/` | ~3 | Cloudflare Pages + Hugo | 일반 콘텐츠 |
| **rap** | `pipelines/rap/` | ~3 | Cloudflare Pages + Hugo | 부동산 |
| **stock** | external (STAP) | 6 | Cloudflare Pages + Hugo | 주식/금융 |
| **travel** | `pipelines/travel/` | ~5 | Cloudflare Pages + Hugo | 여행 (한국어) |
| **tap** | external (TAP) | 1 | Blogger.com | 여행 |
| **curation** | `pipelines/curation/` | ~3 | Cloudflare Pages + Hugo | 큐레이션 |

---

## 3. 블로그 배포 구조

### 3.1 배포 유형

| 유형 | 블로그 목록 | 명령어 |
|------|-----------|-------|
| **Workers** (11개) | health-hugo, pet-hugo, kitchen-hugo, beauty-hugo, camping-hugo, baby-hugo, massage-hugo, car-hugo, homeappliance-hugo, golf-hugo, bike-hugo | `wrangler deploy --config wrangler.toml` |
| **Pages** (나머지 모든 Hugo) | appliance-hugo, fitness-hugo, interior-hugo, laptop-hugo, travel-hugo, rap-hugo 등 | `wrangler pages deploy public --project-name={blog_id}` |
| **Blogger** (4개) | senior-blogger, tap-blogger, tvshow-blogger, ud-blogger | `shared/blogger_publisher.py` |

### 3.2 도메인-계열 매핑

| 도메인 계열 | Publisher ID | 블로그 |
|------------|-------------|-------|
| `*.rotcha.kr` | `ca-pub-8772455780561463` | compare-hugo, deal-hugo, ev-hugo, guide-hugo, hotissue-hugo, tco-hugo |
| `*.informationhot.kr` | `ca-pub-6677996696534146` | rank-hugo, pick-hugo, appliance-hugo, baby-hugo, fitness-hugo 등 |
| `*.techpawz.com` | `ca-pub-8772455780561463` | adventure-hugo, airlines-hugo, flights-hugo 등 (ETAP 35개) |
| `*.informationhot.kr` (aikorea) | `ca-pub-5938862195544185` | (aikorea24 전용) |

---

## 4. 일반적인 문제 해결

### 4.1 배포 실패

**증상**: `wrangler deploy`가 `Authentication error code: 10000` 반환

**원인**: `CLOUDFLARE_API_TOKEN` 환경변수가 wrangler auth profile보다 우선 적용됨

**해결**:
```bash
# 절대这样做하지 말 것:
# wrangler deploy

# 올바른 방법: dispatcher.py 사용
python3 /Users/twinssn/Projects/5000/dispatcher.py {blog_id}

# 또는 수동 (토큰 제거 후)
env -u CLOUDFLARE_API_TOKEN wrangler deploy --config wrangler.toml
```

**근거**: `shared/publishers/deploy.py:13-31` — `build_wrangler_env()`가 env에서 `CLOUDFLARE_API_TOKEN` pop

### 4.2 Hugo 빌드 실패

**증상**: `hugo --gc --minify` 실행 후 `public/index.html` 없음

**가능한 원인**:
1. 테마 누락 — `HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes` 필요
2. 콘텐츠 문제 — frontmatter 형식 오류, 숏코드 미등록
3. 이미지 URL 길이 초과 (255자 macOS 파일명 제한)

**해결**:
```bash
# 테마 경로 지정 후 빌드
HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes hugo --gc --minify

# 특정 블로그 빌드 확인
hugo --gc --minify --source /path/to/site --themesDir /Users/twinssn/Projects/shared-themes
```

### 4.3 no_result / no_content 에러

| 에러 유형 | 파이프라인 | 원인 패턴 | 해결 방향 |
|----------|----------|----------|----------|
| `no_result` | travel | 데이터 수집 성공 → 가드 차단 → None 반환 | 가드 기간/임계값 조정 |
| `no_content` | sector/stock | 토픽 순환 소진 + 중복 가드 → article 생성 실패 | 토픽 다양화, 데이터 수집 빈도 |

### 4.4 유사 제목 차단 (similar_title)

**증상**: `title_similar_exists()`가 유사 제목 감지 → 발행 차단

**메커니즘**: `shared/content_store.py` — SequenceMatcher 80% 유사도 임계값

**해결**: 키워드별 제목 변형 다양화, 유사도 임계값 조정 검토

### 4.5 썸네일 깨짐 (broken_featureimage)

**증상**: `featureimage`가 존재하지 않는 URL을 가리킴 → 브라우저 404

**원인**: `batch_thumbnails.py`가 실행되지 않아 R2에 썸네일 없음

**해결**:
```bash
python3 /Users/twinssn/Projects/5000/scripts/batch_thumbnails.py --slug "20260617-212002-부산-동래구-카페-추천-핫플레이스-5곳"
```

### 4.6 템플릿 유출 (template leak)

**증상**: 렌더링된 HTML에 `{{}}` 또는 `{{% %}}` 마커 노출

**확인 방법**:
1. 브라우저에서 해당 포스트 열기
2. 페이지 소스 보기 (Ctrl+U)
3. `<script type="application/ld+json">` 내 `{{}}` 검색

**확인된 사례** (2026-08-18 기준):
- `laptop-hugo`: JSON-LD description에 `{{}}` 존재
- `beauty-hugo`: JSON-LD description에 `{{}}` 존재

**근본 원인**: AI 러ITER가 빈 Hugo 숏코드 `{{}}`를 삽입하고, Hugo 빌드 시 JSON-LD 내부를 통과

---

## 5. 데이터 구조도

### 5.1 주요 SQLite DB

| DB 파일 | 용도 | 위치 |
|--------|------|------|
| `content.db` | 중앙 발행 레저, 포스트 기록 | `data/content.db` |
| `car.db` | 자동차 파이프라인 콘텐츠 | `data/car.db` |
| `curation.db` | 큐레이션 파이프라인 | `data/curation.db` |
| `senior.db` | 시니어/복지 파이프라인 | `data/senior.db` |
| `rap.db` | 부동산 파이프라인 | `data/rap.db` |
| `stap_content.db` | 주식 콘텐츠 | `data/stap_content.db` |
| `quality.db` | 품질 스캔 결과 | `data/quality.db` |
| `scanner.db` | 스캐너 데이터 | `data/scanner.db` |
| `ops.db` | 운영 대시보드 | `ops_dashboard/ops.db` |

### 5.2 주요 설정 파일

| 파일 | 용도 |
|------|------|
| `blogs.yaml` | 마스터 스케줄 + 배포 설정 |
| `blogs.d/*.yaml` | 개별 블로그 정의 (id, pipeline, schedule, platform) |
| `prompts.yaml` | AI 글쓰기 프롬프트 + SEO 규칙 (1117줄) |
| `models.yaml` | LLM 프로바이더 모델 |
| `api_keys.yaml` | API 시크릿 (gitignored) |

---

## 6. 모니터링 & 알림

### 6.1 대시보드

- **주소**: `http://localhost:5060`
- **인증**: HTTP Basic Auth (`OPS_USER`/`OPS_PASSWORD` env vars, 기본값은 `ops_dashboard/app.py` 참조)
- **런처**: `com.5000.ops-dashboard.plist` (launchd)
- **RBAC 없음**: 단일 계정, 역할 분리 없음

### 6.2 자동 스캔

| 스캔 | 주기 | 설명 |
|------|------|------|
| P32 스캔 | 6시간마다 | 배포된 콘텐츠 빈 체크 |
| 전수 재검사 | 매시간 | Phase 71 안전 재검사 |
| 품질 스캔 | 매일 23:00 | 품질 스캔 + Telegram 리포트 |
| 일일 리포트 | 매일 23:50 | 교차 프로젝트 집계 |

### 6.3 텔레그램 알림

- **봇 토큰**: `~/.env.common`의 `TELEGRAM_BOT_TOKEN`
- **채팅 ID**: `~/.env.common`의 `TELEGRAM_CHAT_ID`
- **디바운싱**: `shared/notification_debounce.py`

---

## 7. 스케줄러 (scheduler.py)

### 7.1 메인 루프

```python
def main():
    _wait_for_network()
    cleanup_stale_slots()
    register_schedules()
    _check_thumbnail_health()
    _update_heartbeat()
    while True:
        _update_heartbeat()
        schedule.run_pending()       # 30초 폴링
        if now_ts - last_catchup >= 300:  # 5분마다
            catchup_missed()
        time.sleep(30)
```

### 7.2 등록된 작업

| 스케줄 | 작업 | 비고 |
|--------|------|------|
| 블로그별 스케줄 | `queue_publish(blog_id)` | 60초 간격 순차 큐 |
| 매일 05:00 | `_run_etap_collectors` | 서브프로세스 격리 |
| 매일 05:30 | `_run_senior_sync` | senior.db 동기화 |
| 매일 06:10 | `_run_stap_collector` | STAP 데이터 수집 |
| 매일 06:30 | `_run_car_refresh` | CAR 갱신 |
| 매일 06:45 | `_run_indexnow` | IndexNow URL 제출 |
| 매시간 :50 | `_run_cuap_collector` | CUAP 자동 수집기 |
| 매일 23:00 | `_run_quality_scan` | 품질 스캔 |
| 6시간마다 | `_run_p32_scan` | 배포 콘텐츠 빈 체크 |
| 매시간 | `_run_recheck_all` | Phase 71 안전 재검사 |

### 7.3 캐치업 메커니즘

- 5분마다 `catchup_missed()` — 예상 스케줄 슬롯 vs 실제 레저 카운트 비교
- 블로그당 최대 3회 캐치업 (`MAX_CATCHUP_PER_BLOG=3`)
- `no_topics` 증상 시 ops.db 기반 재시도 상태 관리

---

## 8. 주요 경로 참조

### 8.1 파이프라인 코드

| 경로 | 용도 |
|------|------|
| `dispatcher.py` | 메인 라우터 — 파이프라인별 분기 |
| `scheduler.py` | 스케줄러 — 루프, 작업 등록, 캐치업 |
| `pipelines/etap/pipeline.py` | ETAP 파이프라인 |
| `pipelines/car/pipeline.py` | CAR 파이프라인 |
| `pipelines/curation/pipeline.py` | 큐레이션 파이프라인 |
| `pipelines/senior/pipeline.py` | 시니어 파이프라인 |
| `pipelines/rap/pipeline.py` | 부동산 파이프라인 |
| `pipelines/travel/pipeline.py` | 여행 파이프라인 (한국어) |

### 8.2 공유 모듈

| 경로 | 용도 |
|------|------|
| `shared/ai_writer.py` | GPT 호출, 폴백 체인 |
| `shared/validators.py` | 발행 전 검증 |
| `shared/publisher.py` | Hugo 콘텐츠 기록 |
| `shared/publishers/hugo_writer.py` | Hugo 콘텐츠 정리 |
| `shared/publishers/deploy.py` | Hugo 빌드 + wrangler 배포 |
| `shared/content_store.py` | 유사 제목, 장소 중복 체크 |
| `shared/r2_uploader.py` | Cloudflare R2 이미지 업로드 |

### 8.3 대시보드

| 경로 | 용도 |
|------|------|
| `ops_dashboard/app.py` | Flask 메인 (0.0.0.0:5060) |
| `ops_dashboard/db.py` | ops.db 접근 |
| `ops_dashboard/checks/content_quality.py` | 콘텐츠 품질 검사 |

### 8.4 외부 프로젝트

| 프로젝트 | 경로 | 통합 |
|---------|------|------|
| STAP | `/Users/twinssn/Projects/STAP` | 서브프로세스 격리 (`_run_stap()`) |
| TAP | `/Users/twinssn/Projects/TAP` | 서브프로세스 + 엔티티 링크 |
| ETAP | `/Users/twinssn/Projects/ETAP` | Hugo 사이트 경로 (30+ 블로그) |
| CUAP | `/Users/twinssn/Projects/CUAP` | 관련 Hugo 프로젝트 |

---

## 9. 보안 고려사항

### 9.1 인증

- **대시보드**: HTTP Basic Auth (`OPS_USER`/`OPS_PASSWORD` env vars, 기본값은 `ops_dashboard/app.py` 참조), RBAC 없음
- **Wrangler**: OAuth 프로파일 (`hugh79757`), `CLOUDFLARE_API_TOKEN` env var 제거 필수
- **Blogger**: OAuth 2.0 (`blogger_token.pickle`)
- **OpenAI**: API 키 (`~/.env.common`)

### 9.2 시크릿 관리

- `.env` — 라이브 자격증명 포함 (`.gitignore`로 보호)
- `config/api_keys.yaml` — API 시크릿 (gitignored)
- `~/.env.common` — 공유 시크릿 (OpenAI, Telegram, R2)

### 9.3 네트워크

- 대시보드: `0.0.0.0:5060` 바인딩 (전체 인터페이스)
- launchd plist 8개 전체 목록:

| plist | 용도 |
|-------|------|
| `com.5000.scheduler.plist` | 메인 스케줄러 |
| `com.5000.scheduler-watchdog.plist` | 스케줄러 와치독 |
| `com.5000.ops-dashboard.plist` | 운영 대시보드 |
| `com.5000.analytics.plist` | 분석 |
| `com.5000.analytics.watchdog.plist` | 분석 와치독 |
| `com.5000.auto-triage.plist` | 자동 분류 |
| `com.5000.dashboard.plist` | 이전 버전 (superseded) |
| `com.5000.master-backup.plist` | 마스터 백업 |
- **위험**: 로컬 네트워크에서 접근 가능, RBAC 없음

---

## 10. 문제 해결 체크리스트

### 10.1 블로그 발행 실패 시

1. **로그 확인**: `logs/` 디렉터리에서 최근 에러 확인
2. **스케줄러 상태**: `launchctl list | grep 5000`으로 프로세스 확인
3. **DB 연결**: `sqlite3 data/content.db "SELECT COUNT(*) FROM publish_ledger WHERE blog_id='{blog_id}' AND date('published_at')=date('now')"` — 오늘 발행 수 확인
4. **배포 상태**: `wrangler pages deployment list --project-name={blog_id}` — 최근 배포 확인
5. ** testName 연동**: `dispatcher.py report`로 최근 실행 결과 확인 (dispatcher에는 `--dry-run` 옵션 없음)

### 10.2 배포 실패 시

1. **CLOUDFLARE_API_TOKEN 확인**: `echo $CLOUDFLARE_API_TOKEN` — 비어있어야 함
2. **Hugo 빌드 확인**: `hugo --gc --minify --source /path/to/site --themesDir /Users/twinssn/Projects/shared-themes`
3. **public/index.html 확인**: Hugo 빌드 후 존재해야 함
4. **lock 파일 확인**: `ls /tmp/wrangler_deploy.lock` — 잠금 해제 필요 시 `rm /tmp/wrangler_deploy.lock`

### 10.3 콘텐츠 품질 이슈 시

1. **기계 감사**: `python3 /tmp/5000-content-audit/mechanical_check.py` — 전체 포스트 스캔
2. **시맨틱 평가**: `python3 /tmp/5000-content-audit/semantic_eval.py` — 100점 만점 평가
3. **대시보드**: `http://localhost:5060` — 실시간 검사 결과 확인
4. **템플릿 유출**: 브라우저에서 포스트 열기 → 페이지 소스 보기 → `{{}}` 검색

### 10.4 블로그 추가 시

1. `config/blogs.d/{brand}.yaml`에 블로그 정의 추가
2. `site_path`가 로컬 Hugo 디렉터리를 정확히 가리키는지 확인
3. `deploy_type` (pages/workers) 지정
4. `schedule.times`에 발행 시간 지정
5. 도메인 계열에 맞는 AdSense Publisher ID 확인

---

## 11. 긴급 복구 절차

### 11.1 스케줄러 재시작

```bash
# 현재 프로세스 확인
launchctl list | grep 5000

# 스케줄러 언로드
launchctl unload ~/Library/LaunchAgents/com.5000.scheduler.plist

# 스케줄러 다시 로드
launchctl load ~/Library/LaunchAgents/com.5000.scheduler.plist
```

### 11.2 대시보드 재시작

```bash
# 대시보드 언로드
launchctl unload ~/Library/LaunchAgents/com.5000.ops-dashboard.plist

# 대시보드 다시 로드
launchctl load ~/Library/LaunchAgents/com.5000.ops-dashboard.plist
```

### 11.3 DB 백업

```bash
# content.db 백업
cp data/content.db data/content.db.bak_$(date +%Y%m%d_%H%M%S)

# 모든 DB 백업
for db in data/*.db; do
    cp "$db" "${db}.bak_$(date +%Y%m%d_%H%M%S)"
done
```

### 11.4 git 커밋 상태 확인

```bash
# 미푸시 커밋 수 확인
git log --oneline origin/main..HEAD | wc -l

# 미커밋 변경 확인
git status --short

# stash 확인
git stash list
```

---

## 12. 참고 문서

| 문서 | 경로 | 설명 |
|------|------|------|
| 대시보드 운영 런북 | `docs/DASHBOARD_OPS_RUNBOOK.md` | 4단계 워크플로우 |
| FIX 레시피북 | `docs/APPENDIX_C_FIX_RECIPES.md` | R01~R12, THUMBNAIL-01, R2-01, P01~P18, C01~C09 |
| Fleet 온보딩 런북 | `docs/APPENDIX_D_FLEET_ONBOARDING.md` | 신규 블로그·분기 추가 |
| 현재 상태 | `CURRENT_STATE.md` | 10개 영역 기준 데이터 |
| 운영 규약 | `.planning/OPERATIONS-CHARTER.md` | 콘텐츠 무결성, 링크 건강성 원칙 |
| 기계 감사 결과 | `data/audit-archive/audit-20260818/` | 24,986포스트 감사 데이터 |

---

*이 문서는 2026-08-18 기준 데이터에 기반합니다. 아키텍처 변경 시 업데이트가 필요합니다.*
