---
date: 2026-08-26
type: fix
status: resolved
---

# P35 라벨덤프 발행시점 자동제거 + editorial_synthesis dead-code 삭제

## What
- `shared/publishers/hugo_writer.py`에 P35 라벨덤프(가격:/장점:/단점:/추천대상: 등) 라인 전체 자동제거 로직 추가 (CUAP 릭 strip 바로 아래).
- `pipelines/etap/editorial_synthesis.py`의 미사용 dead-code `_FILLER`/`_FALLBACK` 정의(12~24행) 삭제.
- STAP 9건 + TAP 2건(총 11포스트) 라벨덤프 라인 56개 소스 정화 (잔여 0).

## Why
- CUAP 프롬프트 릭은 2중 레이어(발생차단+발행제거)로 종료했으나, P35 형식/톤 위반은 탐지만 되고 생성단 차단이 없어 새 글도 라벨덤프로 발행됨.
- `_FILLER`/`_FALLBACK`는 CUAP 릭의 Part B 원인이었으나 append 코드 제거 후 미사용 상태로 남아 재추가 유인.
- STAP/TAP 기존 위반 포스트 11건이 라이브에 잔존.

## Files changed
- shared/publishers/hugo_writer.py (recurrence prevention 블록 추가)
- pipelines/etap/editorial_synthesis.py (dead-code 2건 삭제)
- STAP/etf-hugo, STAP/finance-hugo (9포스트), TAP/travel3-hugo, TAP/travel4-hugo (2포스트) content/posts/*/index.md
- logs/destructive_2026-08-26.log (STAP/TAP 정화 항목)

## How
- hugo_writer: `(?im)^\s*(?:가격|배송|쿠팡순위|장점|아쉬운점|단점|적당한대상|적합대상|추천대상|추천\s*대상|페르소나)\s*[:：].*$` 매치 라인 전체(HTML 포함) 제거.
- editorial_synthesis: `_FILLER`/`_FALLBACK` def 블록 통째 삭제 (참조 없음 확인).
- STAP/TAP: python 스크립트로 동일 정규식 라인 제거, 백업은 git(해당 repo).

## Verification
- AST parse OK (두 py 파일).
- STAP/TAP content/posts 라벨덤프 grep 잔여 0 확인.
- 커밋 d24149af5.
- STAP/TAP 라이브 갱신은 자체 scheduler 빌드 반영(수동 배포 안 함).
