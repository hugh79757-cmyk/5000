# Phase 3: Hardening — Stability & Decoupling - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.

**Date:** 2026-06-30
**Phase:** 3-Hardening — Stability & Decoupling
**Areas discussed:** Path Config Strategy, Error Audit Scope, External Dep Isolation, Binary Paths

---

## Path Config Strategy

**User's choice:** 외부 프로젝트 루트들 각각 env 변수 + 5000_ROOT
- `5000_ROOT`, `STAP_ROOT`, `TAP_ROOT`, `ETAP_ROOT`, `LAP_ROOT`, `CUAP_ROOT`
- `~/.env.common`을 fallback으로 사용 (시크릿 리보크 대비)
- `5000/.env`가 우선순위 높음

**바이너리 경로:** `HUGO_PATH`, `WRANGLER_PATH` env 변수로

---

## Error Audit Scope

**User's choice:** dispatcher + scheduler + publisher 중앙 모듈 3개 집중

**에러 패턴:** `logger.error(f"[{module_prefix}] {context}: {e}")` — 모듈명 + 맥락 + 에러

---

## External Dependency Isolation

**User's choice:** 명확한 에러 메시지 + 해당 blog만 스킵
- 시작 시 모든 외부 의존성 체크하지 않음
- 각 호출 시점에 try/except로 처리
- subprocess 방식 유지, 경로만 환경변수화

---

## Deferred Ideas

None.
