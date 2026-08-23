# OPS-RUNBOOK.md — 일상 운영 절차서

> 기반: 2026-08-18 정밀 기준 데이터
> 대상: 매일 파이프라인을 운영하는 모든 인원

---

## 목차

1. [아침 점검 (매일 09:00)](#1-아침-점검-매일-0900)
2. [배포 절차](#2-배포-절차)
3. [블로그 추가/수정](#3-블로그-추가수정)
4. [콘텐츠 품질 모니터링](#4-콘텐츠-품질-모니터링)
5. [긴급 대응](#5-긴급-대응)
6. [주간/월간 작업](#6-주간월간-작업)

---

## 1. 아침 점검 (매일 09:00)

### 1.1 스케줄러 상태 확인

```bash
# 프로세스 확인
launchctl list | grep 5000

# 예상 출력:
# com.5000.scheduler       [PID]    0
# com.5000.scheduler-watchdog [PID] 0
# com.5000.ops-dashboard   [PID]    0
```

**[❌ 실패]** 프로세스가 없으면:
```bash
launchctl load ~/Library/LaunchAgents/com.5000.scheduler.plist
```

### 1.2 어제 발행 확인

```bash
# 어제 발행 수 확인
sqlite3 data/content.db \
  "SELECT blog_id, COUNT(*) as cnt FROM publish_ledger 
   WHERE date(published_at) = date('now', '-1 day') 
   GROUP BY blog_id ORDER BY cnt DESC;"
```

**[✅ 검증]** 모든 활성 블로그가 1건 이상 발행했는지 확인
**[⚠️ 경고]** 특정 블로그가 0건이면 해당 파이프라인 로그 확인

### 1.3 오늘 예정된 작업

```bash
# 오늘 발행 예정 시간 확인
python3 -c "
import yaml
with open('config/blogs.yaml') as f:
    cfg = yaml.safe_load(f)
for b in cfg.get('blogs', []):
    times = b.get('schedule', {}).get('times', [])
    if times:
        print(f\"{b['id']}: {', '.join(times)}\")
"
```

### 1.4 대시보드 접근 확인

```bash
# 대시보드 접속 테스트
curl -s -o /dev/null -w "%{http_code}" http://localhost:5060
# 예상: 401 (인증 필요)
```

---

## 2. 배포 절차

### 2.1 단일 블로그 배포 (글 생성 + 발행 + 배포)

```bash
#Dispatcher.py 사용 — 글 생성 → 발행 → 배포 전부 수행
python3 /Users/twinssn/Projects/5000/dispatcher.py {blog_id}
```

**[✅ 검증]** 출력에서 `success: true` 확인
**[❌ 실패]** `Authentication error` → `CLOUDFLARE_API_TOKEN` 확인:
```bash
echo $CLOUDFLARE_API_TOKEN  # 비어있어야 함
```

### 2.2 배포만 필요한 경우 (이미 발행된 글)

```bash
# 1. OAuth 프로파일 토큰 추출
export CLOUDFLARE_API_TOKEN=$(env -u CLOUDFLARE_API_TOKEN wrangler auth token 2>/dev/null | tail -1)

# 2. Hugo 빌드
HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes hugo --gc --minify --source /path/to/site

# 3. 배포
python3 -c "
import sys; sys.path.insert(0, '/Users/twinssn/Projects/5000')
from shared.publishers.deploy import deploy_site
deploy_site('/path/to/site', '{blog_id}')
"
```

### 2.3 배포 확인

```bash
# Pages 프로젝트 배포 확인
wrangler pages deployment list --project-name={blog_id}

# Workers 프로젝트 배포 확인
wrangler deployments list --name={worker_name}
```

### 2.4 배포 관련 주의사항

- **절대 `--commit-dirty=true` 사용 금지** — git 커밋 → Cloudflare Pages 자동 빌드 트리거
- **배포 직렬화**: `/tmp/wrangler_deploy.lock`으로 중복 배포 방지
- **테마 경로**: 반드시 `HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes` 지정

---

## 3. 블로그 추가/수정

### 3.1 새 블로그 추가

1. **설정 파일 생성**: `config/blogs.d/{brand}.yaml`에 추가

```yaml
- id: new-blog-hugo
  pipeline: curation  # car/curation/senior/rap/etap/travel/stock
  platform: hugo
  domain: newblog.informationhot.kr
  deploy_type: pages  # pages/workers
  schedule:
    times:
      - "07:00"
      - "10:00"
      - "13:00"
      - "16:00"
      - "20:00"
  daily_quota: 5
  site_path: /path/to/new-blog-hugo
  managed_by: pipeline
  status: active
```

2. **도메인 계열 확인**: AdSense Publisher ID 매핑 참조
3. **Hugo 사이트 생성**: 테마 + 콘텐츠 디렉터리 구조 확보
4. **빌드 테스트**: `hugo --gc --minify --source /path/to/site --themesDir /Users/twinssn/Projects/shared-themes`
5. **배포 테스트**: `dispatcher.py new-blog-hugo` 실행 (dispatcher에는 `--dry-run` 옵션 없음)

### 3.2 블로그 설정 수정

```bash
# 설정 파일 편집
vim config/blogs.d/{brand}.yaml

# 변경 후 스케줄러 재로드 (선택적 — 자동 재로드 안 됨)
launchctl unload ~/Library/LaunchAgents/com.5000.scheduler.plist
launchctl load ~/Library/LaunchAgents/com.5000.scheduler.plist
```

### 3.3 블로그 일시 중지

```yaml
# blogs.d/*.yaml에서
status: paused  # active → paused
```

**[⚠️ 주의]** paused 블로그는 스케줄러가 건너뜀. 발행 재개 시 `active`로 변경 필수.

---

## 4. 콘텐츠 품질 모니터링

### 4.1 기계 감사 (전수 스캔)

```bash
# 전체 포스트 스캔
python3 /tmp/5000-content-audit/mechanical_check.py

# 결과 위치
# /tmp/5000-content-audit/mechanical_all.jsonl (24,986건)
```

### 4.2 시맨틱 평가 (표본)

```bash
# 배치별 시맨틱 평가
python3 /tmp/5000-content-audit/semantic_eval.py

# 결과 위치
# /tmp/5000-content-audit/sem_results/batch_NN.json
```

### 4.3 대시보드 실시간 검사

1. 브라우저에서 `http://localhost:5060` 접속
2. 인증: `ops_dashboard/app.py`의 `_DEFAULT_USER`/`_DEFAULT_PASSWORD` 참조
3. 콘텐츠 품질 탭에서 블로그별 상태 확인

### 4.4 템플릿 유출 검사

```bash
# 특정 포스트 검사
curl -s "https://blog.informationhot.kr/posts/{slug}/" | grep -o '{{[^}]*}}'

# 결과 없으면 정상, 있으면 템플릿 유출
```

### 4.5 내부 링크 0건 검사

```bash
# механическое 감사 결과에서 내부 링크 0건 포스트 확인
grep '"internal_links": 0' /tmp/5000-content-audit/mechanical_all.jsonl | wc -l
# 2026-08-18 기준: 18,542건 (전체의 74.2%)
```

---

## 5. 긴급 대응

### 5.1 배포 실패 시

```bash
# 1. 원인 확인
tail -50 logs/deploy_*.log

# 2. Hugo 빌드 확인
HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes hugo --gc --minify --source /path/to/site

# 3. public/index.html 존재 확인
ls -la /path/to/site/public/index.html

# 4. lock 파일 해제 (필요 시)
rm -f /tmp/wrangler_deploy.lock

# 5. 재배포
python3 dispatcher.py {blog_id}
```

### 5.2 스케줄러 멈춤 시

```bash
# 1. 프로세스 확인
ps aux | grep scheduler.py

# 2. 로그 확인
tail -100 logs/scheduler_*.log

# 3. 재시작
launchctl unload ~/Library/LaunchAgents/com.5000.scheduler.plist
launchctl load ~/Library/LaunchAgents/com.5000.scheduler.plist
```

### 5.3 DB 손상 시

```bash
# 1. 백업 확인
ls data/*.bak_*

# 2. 무결성 검사
sqlite3 data/content.db "PRAGMA integrity_check;"

# 3. 복구 (백업이 있는 경우)
cp data/content.db.bak_YYYYMMDD data/content.db
```

### 5.4 특정 블로그 발행 중단 시

```bash
# 1. 쿨다운 확인
sqlite3 data/content.db \
  "SELECT * FROM publish_ledger WHERE blog_id='{blog_id}' ORDER BY published_at DESC LIMIT 5;"

# 2. 실패 카운트 확인
cat data/failure_count.json | python3 -m json.tool

# 3. 수동 발행 시도 (cooldown 해제 후)
python3 dispatcher.py {blog_id}
```

---

## 6. 주간/월간 작업

### 6.1 주간 품질 리뷰 (매주 월요일)

```bash
# 1. 주간 발행 요약
sqlite3 data/content.db \
  "SELECT blog_id, COUNT(*) as cnt FROM publish_ledger 
   WHERE published_at >= datetime('now', '-7 days') 
   GROUP BY blog_id ORDER BY cnt DESC;"

# 2. 실패율 확인
sqlite3 data/content.db \
  "SELECT blog_id, 
   SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed,
   COUNT(*) as total,
   ROUND(100.0 * SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) / COUNT(*), 1) as fail_rate
   FROM publish_ledger 
   WHERE published_at >= datetime('now', '-7 days')
   GROUP BY blog_id HAVING failed > 0 ORDER BY fail_rate DESC;"
```

### 6.2 월간 백업 확인 (매월 1일)

```bash
# 1. DB 백업
for db in data/*.db; do
    cp "$db" "${db}.monthly_$(date +%Y%m)"
done

# 2. 설정 파일 백업
tar czf config/config_backup_$(date +%Y%m).tar.gz config/

# 3. 로그 정리 (30일 이전)
find logs/ -name "*.log" -mtime +30 -delete
```

### 6.3 Git 정리 (매월)

```bash
# 1. 미푸시 커밋 확인
git log --oneline origin/main..HEAD | wc -l

# 2. 미커밋 변경 확인
git status --short

# 3. stash 정리
git stash list
# 필요 없는 stash 삭제: git stash drop stash@{N}

# 4. 원격 브랜치 정리
git fetch --prune origin
```

---

## 7. 자주 쓰는 명령어 요약

| 명령어 | 설명 |
|--------|------|
| `python3 dispatcher.py {blog_id}` | 단일 블로그 전체 파이프라인 실행 (허용 옵션: `<blog_id>`, `report [--quality]`, `init-db`) |
| `launchctl list \| grep 5000` | 스케줄러 프로세스 확인 |
| `launchctl unload ~/Library/LaunchAgents/com.5000.scheduler.plist` | 스케줄러 중지 |
| `launchctl load ~/Library/LaunchAgents/com.5000.scheduler.plist` | 스케줄러 시작 |
| `HUGO_THEMESDIR=/Users/twinssn/Projects/shared-themes hugo --gc --minify` | Hugo 빌드 |
| `env -u CLOUDFLARE_API_TOKEN wrangler deploy` | wrangler 배포 (토큰 제거) |
| `wrangler pages deployment list --project-name={blog_id}` | 배포 이력 확인 |
| `sqlite3 data/content.db "..."` | 발행 레저 조회 |
| `curl -s http://localhost:5060` | 대시보드 접근 테스트 |

---

## 8. 연락처 & 에스컬레이션

| 상황 | 대응 |
|------|------|
| 스케줄러 멈춤 | `launchctl unload/load`로 재시작 |
| 배포 실패 3회 이상 | `logs/deploy_*.log` 확인 → 근본 원인 해결 |
| DB 손상 의심 | 백업 복구 → `PRAGMA integrity_check` |
| 대시보드 접근 불가 | `launchctl list \| grep ops-dashboard` 확인 |
| 텔레그램 알림 미수신 | `~/.env.common`의 `TELEGRAM_BOT_TOKEN` 확인 |

---

*이 문서는 2026-08-18 기준 데이터에 기반합니다. 운영 환경 변경 시 업데이트가 필요합니다.*
