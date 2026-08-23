# SEAP Thumbnail Backfill Plan

> **Created**: 2026-08-20 00:15 KST
> **Scope**: 5건의 무이미지 senior-blogger 게시물 (2026-08-19)
> **제약**: 게시물·이미지·코드·DB·R2·대시보드 규칙 변경 없음. 비파괴 조사·계획만 포함.

## 1. 대상 게시물

| id | title | slug | published_at (KST) | URL |
|----|-------|------|-------------------|-----|
| 11505 | 전라남도 순천시 저소득 노인 건강보험료 전액 지원 조건과 방법 | `전라남도-순천시-저소득-노인-건강보험료-전액-지원-조건과-방법` | 2026-08-19 11:05 | https://2.techpawz.com/2026/08/blog-post_18.html |
| 11518 | 전라남도 나주시 65세 이상 독거노인 건강보험료 지원 조건은? | `전라남도-나주시-65세-이상-독거노인-건강보험료-지원-조건은` | 2026-08-19 13:10 | https://2.techpawz.com/2026/08/65_0357371862.html |
| 11532 | 광양시 65세 이상 노인맞춤돌봄 대상자 건강음료 안부살피기 조건 | `광양시-65세-이상-노인맞춤돌봄-대상자-건강음료-안부살피기-조건` | 2026-08-19 16:11 | https://2.techpawz.com/2026/08/65_01926752531.html |
| 11544 | 광양시 65세 이상 저소득 어르신 건강보험료 매달 지원받는 조건 | `광양시-65세-이상-저소득-어르신-건강보험료-매달-지원받는-조건` | 2026-08-19 19:10 | https://2.techpawz.com/2026/08/65_01397172365.html |
| 11556 | 광양시 만 55세 이상 가스안전장치(타이머콕) 무상 설치 지원 대상과 방법은? | `광양시-만-55세-이상-가스안전장치타이머콕-무상-설치-지원-대상과-방법은` | 2026-08-19 23:10 | https://2.techpawz.com/2026/08/55.html |

**원인**: Chromium이 2026-08-19 22:07 KST에 설치됨. 위 5건의 발행 시간(11:05~23:10 KST)은 chromium 없이 실행된 scheduler에 의해 발생.

## 2. 현재 상태

| 항목 | 상태 | 근거 |
|------|------|------|
| `thumbnail_url` | **비어있음** | stap_content.db에서 `thumbnail_url IS NULL` |
| 본문 `<img>` | **없음** | body_html에 `<img>` 태그 없음 (텍스트만) |
| 카드 썸네일 | **없음** | Blogger og:image 미지원, 본문 이미지 없음 |
| 라이브 URL | **접근 가능** | curl 200 (개별 확인 필요) |
| Chromium | **현재 설치됨** | `~/Library/Caches/ms-playwright/chromium_headless_shell-1228/` |

## 3. 비파괴 Backfill 절차 (설계)

### 3.1 사전 조건

- Chromium 설치 확인: `python -c "from playwright.sync_api import sync_playwright; pw=sync_playwright().start(); pw.chromium.launch(); pw.stop()"`
- `generate_image_thumbnail()` 동작 확인: canary 테스트로 R2 업로드 검증
- Blogger API token 유효성: `blogger_token.pickle` → token refresh 가능

### 3.2 절차 (게시물 1건 기준)

```
1. stap_content.db에서 id, title, slug, body_html 읽기 (READ ONLY)
2. generate_image_thumbnail(site_id='senior', slug=slug, title=title) 호출
3. 생성된 thumbnail_url을 R2에서 HTTP 200 확인 (curl GET)
4. body_html 앞에 <div><img src=thumbnail_url></div> 삽입하여 새 body_html 생성
5. Blogger API로 기존 게시물 업데이트 (post.update, body=new_body_html)
6. stap_content.db에 thumbnail_url 업데이트 (UPDATE articles SET thumbnail_url=? WHERE id=?)
7. 라이브 URL에서 본문 첫 <img> 존재 확인
```

### 3.3 주의사항

- **Blogger API `posts().update()`는 본문만 변경**. 제목·라벨·발행 시간은 변경 없음.
- **DB 업데이트는 `thumbnail_url` 컬럼만 변경**. 다른 컬럼 건드리지 않음.
- **R2에 새 이미지 업로드만 발생**. 기존 이미지 삭제 없음.
- **순차 실행**: 5건을 한 번에 처리하지 않고, 1건씩 확인 후 다음 건으로 진행.

## 4. Canary 계획

| 단계 | 내용 | 검증 기준 |
|------|------|----------|
| Canary 1건 | id=11556 (마지막 게시물, 영향 최소) | thumbnail R2 200, 본문 `<img>` 존재, DB `thumbnail_url` 업데이트 |
| 대기 | 24시간 | 라이브 URL 카드 미리보기 확인 (Blogger 대시보드 수동) |
| 전건 실행 | 나머지 4건 (11505, 11518, 11532, 11544) | 각각 동일 검증 |
| 최종 확인 | 전체 5건 라이브 URL `curl -s \| grep \"<img\"` | 각 URL에서 최소 1개 `<img>` 태그 |

### Canary 1건 상세 (id=11556)

- slug: `광양시-만-55세-이상-가스안전장치타이머콕-무상-설치-지원-대상과-방법은`
- 제목: `광양시 만 55세 이상 가스안전장치(타이머콕) 무상 설치 지원 대상과 방법은?`
- 예상 thumbnail: `thumbnails/senior/{slug}.webp` (R2)
- 검증: `curl -s 'https://2.techpawz.com/2026/08/55.html' | grep '<img'`

## 5. 롤백 계획

| 상황 | 롤백 방법 |
|------|----------|
| thumbnail 생성 실패 | 해당 건 skip, 나머지 계속 |
| R2 업로드 실패 | 해당 건 skip, DB 변경 없음 (3번에서 중단) |
| Blogger 업데이트 실패 | DB 변경 없음 (5번에서 중단) |
| 업데이트 후 본문 깨짐 | Blogger API로 원래 body_html 복원 (DB에서 읽은 원본 사용) |
| 전체 롤백 | 각 게시물의 원래 body_html(이미지 없음)로 복원 + DB thumbnail_url=NULL |

### 롤백 명령어 (게시물 1건)

```bash
# 원본 body_html 복원 (DB에서 읽은 원본)
python3 -c "
import sqlite3
conn = sqlite3.connect('data/stap_content.db')
row = conn.execute('SELECT body_html FROM articles WHERE id=11556').fetchone()
# row[0]은 백업 시 저장된 원본. 업데이트 전 백업 필수.
"
# Blogger API로 복원
# service.posts().update(blogId=BLOG_ID, postId=POST_ID, body={'content': original_body})
```

## 6. 잔존 위험

| 위험 | 심각도 | 비고 |
|------|--------|------|
| Blogger `posts().update()` 동작 미검증 | Medium | 현재까지 update API 사용 이력 없음. canary에서 최초 테스트 |
| 카드 썸네일 미보장 | Medium | og:image 미지원. 본문 첫 `<img>`만 삽입. 소셜 공유 시 이미지 미표시 |
| 600×600 해상도 | Low | 현재 파이프라인 기본값. 1200×630은 별도 규격화 단계 |
| DB `thumbnail_url` 업데이트 순수성 | Low | UPDATE는 `thumbnail_url` 컬럼만 변경. 다른 컬럼 영향 없음 |
| Chromium 재설치 불가 | Low | Playwright 업데이트 시 chromium 경로 변경 가능. 재설치 필요 시 `playwright install chromium` |
