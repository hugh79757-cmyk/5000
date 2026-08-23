# SEAP Thumbnail Canary Result

> **Created**: 2026-08-19 23:34 KST
> **Last updated**: 2026-08-20 00:10 KST
> **Method**: Existing pipeline code (no production code changes)
> **Target**: senior-blogger (Blogger platform)

## Sector-hugo Status (2026-08-19)

| Run | Time (KST) | Result | Note |
|-----|-----------|--------|------|
| 13:28 | 13:28 | **SUCCESS** (id=3491) | Cloudflare 전파 지연 후 HTTP 200 확인 |
| 16:28 | 16:28 | **SUCCESS** (id=3494) | HTTP 200 확인 |
| 20:28 | 20:28 | **FAIL** (no_content) | LLM 호출 실패 또는 응답 비어있음 |
| **상태** | | **paused** | 2/3 성공, 현재 파이프라인 정지 |

 sector-hugo 실행·재개하지 않음. 다음 정기 run에서 재개 여부 결정.

## 1. Canary Spec

| Item | Value |
|------|-------|
| blog_id | `senior-blogger` |
| Blogger numeric ID | `5484205249958557854` |
| Blog name | 시니어 복지 혜택 정보 |
| Blog URL | https://2.techpawz.com/ |
| Pipeline | `pipelines/senior/pipeline.py` → `_make_thumbnail()` |
| Thumbnail generator | `shared/thumbnail_generator/generator.py` → `generate_image_thumbnail()` |
| Draft post_id | `6247399775709535352` |
| Draft status | **DRAFT (비공개) — 수동 카드 확인 전까지 보존, 삭제·공개·수정 금지** |

## 2. Thumbnail Verification

| Check | Result |
|-------|--------|
| Generation | `generate_image_thumbnail(site_id='senior', ...)` → R2 URL returned |
| R2 HTTP | **200** (curl GET — Python urllib HEAD returns 403 on R2) |
| Content-Type | `image/webp` |
| Content-Length | 37,760 bytes |
| Resolution | **600×600** (현재 파이프라인 기본값. 1200×630 전환은 별도 규격화 단계에서 검토) |
| SHA256 | `09372474973ec7ac61851670169cfcd1e42bf9a01c22522cc68d7612129a11d4` |
| Unique vs default | **True** (default: `685d93b96d44d8652e1a9629dcda44e830ec39f42df5f1a74d2bccc83534fb5b`) |

## 3. Draft Content Verification

```
Content length: 334 chars
First <img> at char: 51 (is first element: True)
Thumbnail URL at char: 131 (inside first img: True)
```

Full content:
```html
<div style="text-align:center;margin-bottom:20px">
<img src="https://pub-2f5c7af1c303419a933069212bc25874.r2.dev/thumbnails/senior/canary-5d7555e412.webp"
     alt="SEAP 썸네일 복구 검증 — 시니어 복지 지원금 안내 (비공개 테스트)"
     style="max-width:100%;border-radius:12px" />
</div>
<p>이 글은 SEAP 썸네일 복구 검증을 위한 비공개 draft입니다.</p>
<p>본문 첫 번째 이미지에 썸네일이 포함되어야 합니다.</p>
```

## 4. Senior-hugo Canary Cross-check

| Check | Result |
|-------|--------|
| DB record id | 11562 |
| `thumbnail_url` | `thumbnails/senior/20260819-a054965c96.webp` ✅ |
| Permalink HTTP | **200** |
| Thumbnail HTTP | **200**, image/webp, 48,222 bytes |
| SHA256 | `778539cf3c2b3c53d47764a571bded6b069ff4f55d360a8af14b3f24038c58c9` |
| Unique vs default | **True** |

## 5. Dashboard Comparison

| Source | Thumbnail Status | Detail |
|--------|-----------------|--------|
| senior-hugo DB (id=11562) | ✅ Has thumbnail | `thumbnail_url` set, HTTP 200 |
| senior-hugo permalink | ✅ Live | HTTP 200, content loads |
| senior-blogger draft (624739...) | ✅ Draft created | body_html has `<img>` as first element |

### CQ05 · THUMBNAIL-01 (ops_dashboard DB, 2026-08-19 23:51 KST 기준)

| Signal | Status | Detail | Interpretation |
|--------|--------|--------|----------------|
| `content_quality` (CQ05) | **FAIL** | "상품/썸네일 이미지 없음" | senior-hugo 본문 내 `<img>` 태그 미검출. 600×600 썸네일이 R2에 존재하나 본문 첫 이미지로 삽입되는 경로가 Hugo frontmatter `featureimage`와 다름 — **실제 경보(stale 아님)** |
| `THUMBNAIL-01` | **없음** | check_results에 THUMBNAIL-01 기록 없음 | THUMBNAIL-01 규칙이 senior-hugo에 미적용되었거나 점검 대상에서 제외됨 |

> **해석**: CQ05는 canary 이후에도 여전히 fail. 썸네일은 R2에 정상이나 Hugo 본문 구조에서 `<img>`로 직접 삽입되지 않아 검출기에서 "이미지 없음" 판정. 별도 규격화 단계에서 해결 필요.

## 6. Known Limitations

| Issue | Status | Detail |
|-------|--------|--------|
| Card thumbnail (og:image) | **NOT VERIFIED** | Draft preview requires Blogger login; curl cannot access |
| og:image meta tag | **ABSENT** | Neither senior-hugo nor senior-blogger have og:image in HTML |
| C08_SITE_UNREACHABLE | **Separate issue** | Not related to thumbnail generation |
| Python urllib HEAD on R2 | **403** | Must use curl GET for R2 HTTP checks |
| `blogger_client.py` credentials | **Missing** | `config/blogger_credentials.json` not found; used `blogger_token.pickle` directly |
| `publish_to_blogger()` draft | **Not supported** | `isDraft=False` hardcoded; had to call API directly |

## 7. 8/19 Thumbless Posts (Backfill Candidates)

5 posts on 2026-08-19 with empty `thumbnail_url` — all published before chromium install (22:07 KST):

| id | title | published_at | Reason |
|----|-------|-------------|--------|
| 11505 | 전라남도 순천시 저소득 노인 건강보험료 전액 지원 | 02:05 | No chromium |
| 11518 | 전라남도 나주시 65세 이상 독거노인 건강보험료 지원 | 04:10 | No chromium |
| 11532 | 광양시 65세 이상 노인맞춤돌봄 대상자 건강음료 안부살피기 | 07:11 | No chromium |
| 11544 | 광양시 65세 이상 저소득 어르신 건강보험료 매달 지원 | 10:10 | No chromium |
| 11556 | 광양시 만 55세 이상 가스안전장치 무상 설치 지원 | 14:10 | No chromium |

**Note**: These are on `senior-blogger` (Blogger platform). The `senior-hugo` canary (id=11562, 15:13 KST) was after chromium install and has a valid thumbnail.

## 8. Residual Risks

| Risk | Severity | Note |
|------|----------|------|
| CQ05 still FAIL (stale?) | **High — 실제 경보** | 썸네일 R2 존재하나 Hugo 본문 구조에서 검출 안 됨. 별도 규격화 단계에서 해결 |
| THUMBNAIL-01 not checked | Medium | senior-hugo에 THUMBNAIL-01 규칙 미적용 또는 제외 |
| Card thumbnail not verifiable | Medium | Draft preview requires Blogger login; no API for preview image |
| 8/19 5 thumbless posts on senior-blogger | Low | Backfill requires code change → SEAP_THUMBNAIL_BACKFILL_PLAN.md에 별도 기록 |
| `blogger_client.py` credentials | Low | `config/blogger_credentials.json` missing; pipeline uses `blogger_publisher.py` path |
| Python urllib HEAD 403 on R2 | Low | Monitor and scripts should use curl GET |
| Fallback groups not uploaded | Medium | 7 groups designed but not on R2; only `senior` group works for canary |
| Resolution 600×600 vs 1200×630 | Medium | 현재 기본값 600×600. 1200×630 전환은 별도 규격화 단계 |
