---
date: 2026-07-16
type: config
status: resolved
---

# CUAP 블로그 발행 중단

## What
CUAP 분기 10개 블로그의 자동 발행을 전면 중단.

## Why
운영 전략 변경으로 CUAP(상품 큐레이션) 블로그 발행을 중단하기로 결정.

## Files changed
- `config/blogs.d/cuap.yaml` — 10개 블로그 `status: active` → `inactive`

## How
`cuap.yaml`에서 10개 블로그(appliance, baby, fitness, interior, laptop, health, pet, kitchen, beauty, camping)의 `status` 필드를 `active`에서 `inactive`로 일괄 변경.
`scheduler.py:401`과 `dispatcher.py:636`가 `status != "active"`인 블로그를 자동 스킵.

## Verification
`grep "status:" config/blogs.d/cuap.yaml` — 10개 전부 `inactive` 확인 완료.
