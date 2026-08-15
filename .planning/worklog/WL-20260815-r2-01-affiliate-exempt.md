# WL-20260815-r2-01-affiliate-exempt

> 날짜: 2026-08-15 / 연관: phase-71c R2-01 규칙 정의 정정 / 상태: 완료

## 배경
- R2-01이 ETAP 35개 블로그에서 fail. 조사 결과 43건 위반 전부 **제3자 affiliate hotlink**(TripAdvisor/Airalo/Omio/Coupang CDN)였고, 원래 R2에 업로드된 적이 없음 → R2 마이그레이션이 불가한 정상 운영 이미지.
- 결정: R2-01 규칙 의미를 "모든 이미지 R2 필수" → "자체 콘텐츠 이미지(featureimage + 자체 본문)만 R2 강제, affiliate CDN은 예외"로 **비파괴 정정**.

## 파괴적 작업 목록
| 시각 | 작업 | 명령/스크립트 | 사전카운트 | 백업 | 사후대조 | 보존확인 |
|------|------|--------------|-----------|------|----------|----------|
| 08:46 | ops-dashboard daemon 재시작 (코드 반영) | `launchctl unload/load com.5000.ops-dashboard.plist` | trains-hugo R2-01 fail | ops.db.bak_r2exempt_20260815_084551 | trains-hugo R2-01 cleared (1/15=THUMBNAIL-01만) | affiliate 이미지 무변경 |
| 08:48 | pending_fixes R2-01 18행 proposed→resolved | `UPDATE pending_fixes SET status='resolved'...` | 22 proposed | 동일 백업 | 18 resolved + 4 proposed(travel*) | travel 4행 유지, 이미지 무변경 |

## 4단계 프로토콜 이행
1. **사전 카운트**: ops-dashboard 강제 재시작 1회 / pending_fixes R2-01 proposed 22행 중 해소 블로그 18행 대상. 대시보드 `launchd` KeepAlive라 재시작 후 자동 기동 확인.
2. **되돌림 수단**: `ops_dashboard/ops.db.bak_r2exempt_20260815_084551` (DB 백업). 코드는 `git`으로 되돌림 가능(변경 전 커밋 대비). retain invertible: pending_fixes 기존 값은 `evidence` 보존, `action`만 새 문구로 대체.
3. **실행**: daemon restart → 35개 ETAP 재검사 → pending_fixes UPDATE.
4. **사후 대조**: R2-01 fail 블로그 35 → 6 (sector/travel×4는 비-affiliate 도메인이라 정당한 잔존). pending_fixes: 22 proposed → 18 resolved + 4 proposed.

## 결과 / 보존 대상 확인
- affiliate 이미지(파일/URL) **무변경** — 예외 처리만 적용.
- 남은 R2-01 fail 6곳(unsplash, gocamping.or.kr, tong.visitkorea.or.kr, khs.go.kr, heritage.go.kr 등 비-affiliate)은 의도대로 잔존. 별도 범위(불가/이연) 아님.
- THUMBNAIL-01(webp 요구)은 이번 작업 범위 외 — 별도 rule.

## 잔존 위험
- `config/quality_checklist.yaml` `r2_exempt_domains`에 없는 새 affiliate CDN이 생기면 해당 블로그 R2-01이 다시 fail. 신규 제휴사 온보딩 시 exempt 목록 추가 필요.
- 운영 서버는 코드 변경 시 재시작 필요(모듈 로드 시점). 이후 표준 재검사는 새 코드 기준.