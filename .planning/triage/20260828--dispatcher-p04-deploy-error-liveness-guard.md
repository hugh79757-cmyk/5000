---
date: 2026-08-28
type: fix
status: resolved
---

# dispatcher P04 deploy_error 오탐 페이징 가드

## What
post_deploy 배포 실패(P04)에서 사이트가 정상 서빙(HTTP 200) 중이면 CRITICAL 텔레그램 페이징을 건너뛰고 이벤트만 기록하도록 수정.

## Why
배치 경보(hiking-hugo/flights-hugo P04 deploy_error)가 오탐으로 판명됨 — 실제로는 일시적(transient) 배포 실패였고 사이트는 200으로 살아있었으며 이벤트도 나중에 closed 됨. 살아있는 사이트에 대해 CRITICAL 페이지를 보내는 것이 오탐의 원인.

## Files changed
- dispatcher.py (신규 `_is_site_live(blog_id)` 헬퍼 추가 + post_deploy P04 분기 가드)

## How
`_is_site_live()` = get_blog_config(blog_id)["domain"] 에 urllib GET(5s 타임아웃), 2xx/3xx면 True. P04 실패 분기에서 사이트가 live면 `_record_summary_event`(감사 추적)만 남기고 `_tg_error` 페이징 생략. 체크 자체 실패 시 False 반환 → 기존 페이징 경로로 폴백(fail-safe, 회귀 없음).

## Verification
- py_compile OK
- 오프라인 로직 테스트: 도메인 있음+네트웍 OK → True, 도메인 없음 → False(폴백 페이징)
- 주의: 운영 호스트에서 urllib가 네트웍에 도달 못 하면 False를 반환해 기존처럼 페이징함(회귀 없음, 개선은 환경 의존)
