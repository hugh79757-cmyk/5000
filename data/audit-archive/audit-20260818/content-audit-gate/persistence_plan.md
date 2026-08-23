# Persistence Plan — Content Audit Artifacts

## 원본 보존 (Task 1)
- /tmp/5000-content-audit/ 전체는 원본 그대로 유지 (수정·삭제 금지)
- manifest 체크섬 3종 일치 확인 완료 (mechanical_all.jsonl 6cd85551…, post_inventory.jsonl 4179c4e6…, post_audit_results.jsonl a532beca…)
- 민감정보 포함 파일 0건 (refresh_token/client_secret/access_token/api_key/Bearer 스캔)

## private durable archive 후보
- 대상: /tmp/5000-content-audit/ (24.9K+ lines, ~40MB 예상)
- 위치 후보: /Users/twinssn/Projects/5000/data/audit-archive/ (gitignore 대상) 또는 별도 아카이브 디렉토리
- 크기: mechanical_all.jsonl 4.0MB + post_inventory.jsonl + post_audit_results.jsonl + 산출물 12종 + sitemaps/ 캐시
- 경로·크기 확정 후 사용자 승인 필요 — 실제 복사는 승인 후

## Git용 sanitized summary
- git 커밋 대상: audit_summary.md + audit_verdict.json (요약만, 원본 JSONL 대량 파일 제외)
- 원문 전체·긴 인용문 커밋 금지 (지시 준수)

## 보존 규칙
- /tmp 원본 무수정 (QA overlay는 /tmp/5000-content-audit-gate/에만 기록)
- 개인 아카이브 이동 전 경로·크기 보고
