---
date: 2026-08-02
type: debug
status: resolved
---

# 커스텀 도메인 진단: 캐시 vs 오리진 판정

## What
fitness/laptop 커스텀 도메인이200+CoT를 유지하는 원인을 캐시 버스터로 판별

## Why
Pages 배포는 정상(.pages.dev에서404)이나 커스텀 도메인에서 미차단. 원인 불명.

## 캐시 버스터 실측 결과
| 테스트 | 결과 | 판정 |
|--------|------|------|
| `?nocache=<random>` | 200 + CoT 12건, cf-cache-status: HIT | 캐시 버스터 **작동 안함** |
| `?test=1/2/3` | 모두 HIT | Cloudflare가 **쿼리스트링 무시** |
| `Cache-Control: no-cache` | HIT | 캐시 헤더도 무시 |
| 커스텀 도메인 vs Pages.dev **해시 비교** | **서로 다름** | **캐시 문제가 아님** — 오리진이 다름 |
| 응답 헤더 비교 | `text/html` vs `text/html; charset=utf-8` | **완전히 다른 오리진** |

## Files changed
read-only 조사. 파일 변경 없음.

## How
캐시 버스터 쿼리스트링 + 응답 해시 비교로 캐시 가설 반증.
가장 유력한 원인: `fitness.informationhot.kr` / `laptop.informationhot.kr`에 수동 DNS 레코드 충돌

## Verification
read-only 실측 완료. Dashboard에서 DNS 레코드 확인 필요.

## 런북
`.planning/triage/20260802-phase54-custom-domain-runbook.md`
