# WL-20260821 — ETAP branch 1 재검증 A/B

## 개요
- 재검증: etap-auto-branches-discovery.md 35 정본/SG 분류/deploy 위반 3 병렬 read-only
- A: 문서 §1/§2/§3/§4/§5 정정 (SG-A 19→13, SG-A2 4→10, deploy 36 live→live1+dead31)
- B: dead code 31 제거 + pipeline.py fallback deploy_site 위임

## 파괴적 작업 4단계
1. 사전 카운트: dead 31 + live 1 (pipeline.py) = def 32, active 35 유지 확인
2. 백업: git diff staged 33 files (doc 1 + etap 32 중 31 dead 제거 + pipeline 1 정상화)
3. 실행: 31 파일 def _build_and_deploy 삭제, pipeline.py deploy_site 위임
4. 사후 대조: grep wrangler 0, grep def _build_and_deploy 1(pipeline.py), py_compile OK 32, active 35 보존

## 로그
- logs/destructive_2026-08-21.log append

## 잔존 위험
- 4개 파일(adventure/airlines/airports/flight)도 wrangler 없으나 subprocess import 잔존 → harmless
- 신규 {stem}_pipeline.py 없는 ETAP 블로그 추가 시 dispatcher 미등록이면 pipeline.py fallback 재확인 필요 (현재 0개)
