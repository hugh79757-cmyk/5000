# CUAP 블로그 현황 (배포 분류 + AdSense)

> 작성일: 2026-07-21
> 대상: `/Users/twinssn/Projects/cuap/` Hugo 블로그 10개
> 목적: 다음 세션에서 dispatcher 배포 라우팅과 AdSense 상태를 즉시 파악하기 위함

## 1. Worker / Pages 분류 (dispatcher.py 기준 — 소스 오브 트루스)

`dispatcher.py`의 `WORKERS_BLOGS` (라인 514-521)가 배포 경로를 결정:

| blog_id | 분류 | 배포 명령 |
|---|---|---|
| health-hugo, pet-hugo, kithen-hugo, beauty-hugo, camping-hugo, baby-hugo | **Worker (6)** | `wrangler deploy --config wrangler.toml` |
| appliance-hugo, fitness-hugo, interior-hugo, laptop-hugo | **Pages (4)** | `wrangler pages deploy public --project-name {blog_id}` |

### 중요 발견 — 불일치 (2026-07-21 확인)
- 10개 블로그 **전부** `wrangler.toml`을 가짐 (Worker형: `name = "*-hugo"`, `pages_build_output_dir` 없음).
- 그러나 **Pages 4개** (appliance/fitness/interior/laptop)의 `wrangler.toml`은 dispatcher가 **사용 안 함** (Pages 경로는 toml 무시).
- 해석: Pages 4개의 `wrangler.toml`은 (a) Worker→Pages 전환 시 잔존물, 또는 (b) Worker로 전환할 의도였으나 `WORKERS_BLOGS`에 누락 — 두 가지 가능성.
- **미해결 결정**: Pages 4개를 Worker로 편입(`WORKERS_BLOGS` 추가)할지, 아니면 toml 정리할지 다음 세션에서 결정 필요.

## 2. AdSense 현황 (Phase 26 결과, 2026-07-21)

- **Publisher ID**: 전 10개 `ca-pub-6677996696534146` (informationhot 계정) — 기존 rotcha(`ca-pub-8772455780561463`)에서 통일 완료
- **슬롯**: `inArticleSlot` / `leaderboardSlot` = `2195212287`
- **검증**: 라이브 10/10에서 메타 노출 + rotcha 유출 0 확인
- **baby**: 원래 Pages 프로젝트 → Worker로 전환 (stale custom domain 레코드 정리 후 `baby.informationhot.kr` 바인딩)

## 3. 다음 세션 참고

1. Worker/Pages 재분류 시 `dispatcher.py`의 `WORKERS_BLOGS` 리스트만 수정하면 됨 (배포 로직 자동 반영).
2. Pages 4개의 `wrangler.toml` 잔존 여부 점검 필요 (불일치 섹션 참고).
3. AdSense 슬롯 `2195212287`이 informationhot 계정에 실제 존재 + 도메인 승인 + Auto ads/Anchor ON 상태를 AdSense 대시보드에서 확인 (잔존 위험).
4. 배포 금지: git push로 배포 금지, 항상 `dispatcher.py {blog_id}` 또는 Worker는 `wrangler deploy --config wrangler.toml` 사용 (CLOUDFLARE_API_TOKEN env var 제거 필수 — dispatcher가 처리).
