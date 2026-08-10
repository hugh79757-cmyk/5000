# WL-20260808-dashboard-refresh-buttons

**일자:** 2026-08-08
**작업자:** agent

## 작업 개요
대시보드(`http://localhost:5060`)에 재검사 버튼 3종 추가.

## 배경
- POST /api/run-checks, /api/run-checks?blog_id=X, /api/maintenance/checklist 엔드포인트는 존재했으나 UI 버튼 없음 → curl로만 호출 가능
- C.4.1 문서화에 "UI 버튼 없음" 명시했으나 실제 버튼은 없었음

## 변경 내용

### 커밋 1: feat(dashboard): 정비 체크리스트 재실행 버튼 + 엔드포인트 form/json 겸용 (23ec33c4a)
- `ops_dashboard/app.py`: POST /api/maintenance/checklist가 JSON과 form 데이터 모두 수용하도록 수정
  - `request.get_json(silent=True) or request.form`으로 blog_id 추출
  - 기존 JSON 호출 하위호환 유지 확인 (JSON+form 모두 200 응답)
- `ops_dashboard/templates/blog.html`: 정비 체크리스트 표 위에 '정비 체크리스트 재실행' 버튼 (#btn-refresh-maintenance) 추가

### 커밋 2: feat(dashboard): 전체·개별 재검사 버튼 추가 (마스터 갱신) (edacfd923)
- `ops_dashboard/templates/index.html`: Fleet Status 상단에 '전체 재검사 실행' 버튼 (#btn-run-all-checks) 추가
  - POST /api/run-checks(blog_id 없음) 호출 → 완료 후 페이지 reload
  - 실행 중 disable + '검사 중…' 표시로 다중 클릭 방지
- `ops_dashboard/templates/blog.html`: Recent Checks 섹션 위에 '이 블로그 재검사' 버튼 (#btn-refresh-blog) 추가
  - POST /api/run-checks?blog_id= 호출 → 완료 후 reload
- `ops_dashboard/static/app.js`: 3개 버튼 JS 핸들러 추가
  - same-origin fetch, credentials 포함
  - 클릭 시 disable → fetch → json 응답 → window.location.reload()

### 커밋 3: docs(agents): Appendix C 검증 게이트에 재검사 트리거 필수 단계 보강 (ce9b1fdcf)
- C.1.2 게이트에 '재검사 트리거 (필수, 누락 금지)' 단계 추가
- C.1.2.1 '자동 갱신 대기의 STOP 조건' 절 신설
- C.4.1 '재검사 트리거 — 수동 갱신 전제 (공통)' 절 신설
- 각 레시피 STOP 조건에 (e) 재검사 트리거 호출 전 완료 보고 금지 항목 추가

## 게이트 결과 (5/5)
1. ops-dashboard alive + readiness 200: 통과
2. 기존 엔드포인트 무영향 (/api/registry, /api/attention, /api/standards): 전부 200
3. fail_checks 총량 일관성 (3회): 28, 28, 28 — 불변
4. 정비 엔드포인트 하위호환 (JSON + form): 둘 다 정상 응답
5. 백업 존재: ops.db.bak_buttons_20260808 존재 + pre-refresh-buttons-2026-08-08 태그

## 현재 fail_checks 상태 (2026-08-08 22:45 기준)
- 총량: 28건
- R06: 7건 (pet-hugo, kitchen-hugo, laptop-hugo, fitness-hugo, camping-hugo, beauty-hugo, baby-hugo)
- R04: 9건 (senior-hugo, rotcha-blog, informationhot-hugo, massage-hugo, interior-hugo, homeappliance-hugo, golf-hugo, car-hugo, bike-hugo)
- R12: 3건
- 영향 블로그: 21개
- stale_blogs: 7개

## CSRF 관련
- CSRF 보호 미도입 — 백로그 항목
- same-origin fetch만 허용 + Basic Auth 환경으로 위험도 낮음
- 전면 CSRF 도입은 별도 작업으로 분리

## 백로그
- CSRF 보호 도입 (별도 작업)
- 정제 체크리스트 재실행 성공 후 결과 메시지 표시 (현재는 페이지 reload만)

## 백업
- git tag: pre-refresh-buttons-2026-08-08
- DB 백업: ops_dashboard/ops.db.bak_buttons_20260808
- 로그: logs/destructive_2026-08-08.log 에 한 줄 append
