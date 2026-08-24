# MAN-001 bike-hugo 활성화

## 목적
CUAP bike-hugo paused → active 전환

## 전제
- config/blogs.d/cuap.yaml `status: active` (현재 이미 active 확인 2026-08-24)
- ops_dashboard.blog_lifecycle `config_status=active` (현재 active)

## 단계
1. yaml 확인: `grep -A2 bike-hugo config/blogs.d/cuap.yaml | grep status`
2. DB 확인: `sqlite3 ops_dashboard/ops.db "SELECT blog_id, config_status FROM blog_lifecycle WHERE blog_id='bike-hugo'"`
3. 미스매치 시:
   - yaml이 paused → `sed -i '' 's/bike-hugo.*paused/bike-hugo active/'` 후 `python -m ops_dashboard.seed` or `sync` 재실행
   - DB만 paused → `sqlite3 ops_dashboard/ops.db "UPDATE blog_lifecycle SET config_status='active', lifecycle_status='unknown', pause_reason='' WHERE blog_id='bike-hugo'"`
4. 검증: `hugo --gc --minify --source /Users/twinssn/Projects/cuap/bike-hugo --themesDir /Users/twinssn/Projects/shared-themes`
5. 스케줄러 확인: `pgrep -f scheduler.py` + 다음 09:20 스케줄 대기

## 롤백
- yaml을 paused로 되돌리고 DB도 paused로 업데이트, scheduler 재기동

## 자가진단
- bike-hugo는 현재 active이므로 본 매뉴얼은 대기용, 즉시 조치 불필요
