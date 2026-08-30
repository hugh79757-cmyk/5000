# WL-20260827-dashboard-status-false-positive-fixes

## 작업 요약
대시보드 "상태파악 오류" 배치 수정. 사용자 승인("모두 승인") 하에 진단 후 다수가
체커 거짓양성(false positive)임을 확인 → 콘텐츠/배포 파괴작업 없이 체커 수정 +
DB 스테일 행 갱신으로 해결.

## 사전 카운트 / 영향 범위
- c08_live_file_mismatch fail: 85건 (전 블로그) — permalink 버그 거짓양성
- c06_mtime_deploy fail: 72건 — 대시보드 뷰에서 INFO 버킷 분리됨(미표시) → 비대상
- FM-MISSINGKEYS fail: 71건 / frontmatter fail: 41건 / FM-DRAFT fail: 7건
  — `_index.md` 섹션 인덱스 스캔 버그 거짓양성(다수)
- THUMBNAIL-01 fail: 4블로그(6건) — 외부 소스 이미지(khs.go.kr/tong.visitkorea) 규칙 불일치

## 변경 내역 (PRODUCTION CODE)
1. `ops_dashboard/checks/content_integrity.py`
   - `_crawl_post` → `_post_url_candidates()` 추가: 라이브 URL 후보
     [`/posts/{slug}/`, `/{slug}/`, `/blog/{slug}/`], slug 유니코드 인코딩,
     soft-404(og:title 404) 배제. (이전 세션 적용, 본 세션 재검증)
   - `_read_post_files()`: `md_file.name == "_index.md"` 스킵 추가 → 섹션 인덱스
     페이지를 포스트로 오인하는 결함 제거. (본 세션 적용)
2. THUMBNAIL-01 규칙 변경 없음 (외부 이미지 블로그 배제 필요 → 별도 결정 대기).
3. c06 변경 없음 (이미 INFO 버킷).

## DB 작업 (ops.db, 백업: ops_dashboard/ops.db.bak_<ts>)
- c08_live_file_mismatch fail 행 DELETE: 85 → 0 (다음 스케줄 크롤 ≤24h 내 실제 위반 재출현)
- frontmatter/FM-* UPSERT(체커 정상 동작):
  - frontmatter 41 → 5 (남은 5건은 실제 FM 위반)
  - FM-MISSINGKEYS 71 → 7 (남은 7건은 실제 키 누락 포스트)
  - FM-DRAFT 7 → 0 (전부 `_index.md` 아티팩트 확인)

## 사후 대조
- FM-DRAFT 0건: 7건 전부 `_index.md` 오인 → 확인됨(근본원인 해소)
- 실제 잔존: frontmatter 5 + FM-MISSINGKEYS 7 = 12개 포스트 실제 키 누락(콘텐츠 수정 필요)
- THUMBNAIL-01 잔존 4블로그 = 규칙 불일치(외부 이미지), batch_thumbnails 실행 금지(실사진→그래디언트 훼손)

## 잔존 위험
- c08: 삭제 행은 다음 라이브 크롤 전까지 대시보드에 미표시(unknown). 실제 위반은 재출현.
- 실제 콘텐츠 이슈(content_quality 58, s01 67, s02 45, s03 36, semantic 22, R04 34,
  standard_compliance 8, FM-FEATUREIMAGE 4, 실제 FM 누락 12)는 재생성/배포 승인 필요 → 미수행.
- THUMBNAIL-01: 규칙 스코핑 결정 필요(외부 이미지 블로그 예외). batch_thumbnails 미실행.

## 위반 감지
- THUMBNAIL-01 승인 항목(batch_thumbnails)은 실행 시 실제 관광/국가유산 사진을 생성
  그레이디언트 webp로 교체하는 콘텐츠 훼손 → 사용자 승인에도 불구하고 실행 보류,
  규칙 불일치로 재분류 보고.

---

# ETAP 3건 수정 (추가 세션) — WL-20260827-etap-3fix

## FIX 1 (cruise_pipeline.py) — [검증됨]
- `if is_draft: return False` → `_write_hugo_post(..., is_draft=is_draft)` 이후로 이동.
  is_draft 시 draft 작성(격리)+`_mark_published`+`return True`(무한루프 없음).
- compile OK. `_write_hugo_post_etap` is_draft 수용·`draft:true` 방출 확인.

## FIX 2 (dispatcher.py) — [검증됨]
- 두 cooldown SKIP → `{'success':True,'reason':'cooldown'}` + `_record_failure` 제거.
- L1831 배제 튜플 `('quota_met','already_running','duplicate_title','cooldown')`.
- deals-hugo 가짜 연속 P01 소거. compile OK.

## FIX 1b 충돌 + 해결 — [위반 감지→해결]
- 충돌: dispatcher post-publish auto-fix(FM-DRAFT)가 draft 제거 → `draft:true` 격리가
  배포 시마다 되돌려짐(환각 포스트 재라이브).
- 사용자 결정(승인): "파일 격리(이동)".
- 실행: `content/posts/amphoe-ko-samui-cruise` → `content/_quarantine/amphoe-ko-samui-cruise` (2 files).
  백업: index.md.bak_20260827_121108 + git tag pre-autostd-2026-08-10-cruise-hugo.
- 재배포 `dispatcher.py cruise-hugo`(Workers) success=true. auto-fix "draft 없음 no-op" 확인.
- 라이브 검증: sandbox 네트워크 차단(HTTP 000)으로 불가. 단 파일이 content/posts 밖이라
  재빌드 사이트에 포함 불가 = 논리적 404. 복구 가능(격리 dir 보관).

## FIX 3 (visafree 토픽 보충) — [검증불가]
- 실제 DB `data/travel-en.db`. `visafree_topics`에 `city` 컬럼 없음 →
  `collectors/topic_expander.py:214` 건너뜀(보충 안 됨).
- 소스 `visa_requirements` DISTINCT 여권 199건 = `visafree_topics` 199건과 일치 → 신규 0.
  유한 데이터셋 자연 고갈. 보충 불가능. 재활용은 전략 결정(미실행).

## 잔존 위험
- visafree: 5건 후 자동 중지(데이터 고갈, 정상).
- deals: 가짜 P01 소거(코드 반영, 다음 스케줄 정상).
- cruise 격리 파일은 _quarantine에 보관(복구 시 content/posts로 이동+재배포).
- 라이브 404는 사용자 브라우저/Cloudflare 캐시 갱신 후 확인 권장.
