# Quick Task: CUAP CJK Pipeline Fix

## Description
CUAP CJK 누수를 파이프라인 코드에서 근본 차단한다. 4관문(소스·제목정제·언어검증·slug)을 다층 방어로 실제 수정하고, 회귀 테스트로 재발 불가를 실증한 뒤, 제목 8건을 복원 재생성해 그 고친 게이트를 통과시켜 재배포한다. push는 승인 후.

## Scope
- CUAP 파이프라인 공통 모듈 (5000 repo): `pipelines/curation/collector.py`, `pipelines/curation/enricher.py`, `pipelines/curation/writer.py`, `shared/validators.py`, `shared/publisher.py`
- 제목 8건 복원 재생성: pet 4건, beauty 1건, camping 3건 + 파편
- cap/tap/stap은 스코프 밖 (코드 분리 확인됨)

## Tasks

### 1. 4관문 코드 수정 (수리 — 청소보다 먼저)
- (a) 소스: `pipelines/curation/collector.py` / `enricher.py` — 쿠팡 상품명 등 외부 텍스트 CJK 정규화
- (b) 제목 정제: `pipelines/curation/writer.py:sanitize_title()` — CJK 감지 시 재생성 트리거
- (c) 언어 검증: `shared/validators.py:assert_korean_or_reject()` — 제목 단독 한글비율/CJK 검사 추가
- (d) slug: `shared/publisher.py:slugify()` — 화이트리스트(한글·영숫자·하이픈)로 교체

### 2. 회귀 테스트 (수리가 실제 작동하는지 실증)
- CJK 입력 케이스(智能玩具, 基础护肤品推荐, 安quan 파편, 단일 한자 推 등)로 4관문 각각 차단/정화 확인
- 특히 언어검증이 "본문 긴 글 + 제목에 한자 1자" 케이스를 잡는지 필수 포함

### 3. 제목 8건 복원 재생성 (청소 — 수리된 게이트로 통과)
- 8건(pet 4, beauty 1, camping 3)+파편: CJK 삭제가 아니라 한국어 주제어로 복원 재생성
- slug 한국어 기반 재생성 + 구 slug aliases로 404 방지
- 재생성 결과가 수리된 게이트 통과 확인

### 4. 재배포 (검증 통과분만, push 승인 후)
- draft: false 후 로컬 hugo 빌드로 제목·H1·og·slug CJK 0자, aliases 동작 확인
- pet/beauty/camping 정지 해제는 검증 통과 전제

### 5. 보고
- 4관문 수정 diff, 회귀 테스트 결과, 복원 제목표, 빌드 결과 정리
- "CUAP CJK 누수가 파이프라인 레벨에서 재발 불가인가" 회귀 테스트 근거로 판정

## Constraints
- 서브에이전트 금지
- 제목 삭제만으로 마무리 금지 — 복원 재생성 필수
- 로컬 빌드 허용, 원격 push·배포는 승인 후
- 코드 수정(1)·테스트(2)·제목 복원(3) 각각 별도 커밋
- 커밋 해시·git diff --stat 보고
- 회귀 테스트 실제 미실시 시 재발불가 판정 자동 보류