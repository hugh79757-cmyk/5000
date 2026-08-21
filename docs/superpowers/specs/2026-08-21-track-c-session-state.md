---
title: "Track C Session State — 2026-08-21"
status: IN_PROGRESS
---

# Track C Session State — 2026-08-21 23:00 +09:00

## [지금 멈춰 있는 지점]
- airports A그룹 64건 중 **22건 재생성·배포 완료** (STN/LIL 포함 12 + 상위10 CDG/IST/PEK/DME/DFW/LHR/JFK/EWR/LAX/CLT). 남은 **42건 대기**. 다음 명령은 "30건 배치 → 라이브 3건 확인 → 나머지 12건".
- B그룹 5건(OKN/PCV/CAT/MKC/KDL) **noindex 유지, 발행 안 함, Phase 2 이관**. KDL 357단어 미달로 재noindex 복구 완료.
- C그룹 3건(CIV/KLT/GTW) **재생성 제외, noindex 영구** (OurAirports 미수록).
- airports 스케줄러 **paused 유지**. 해제 조건: A그룹 64건 완료 + 생성 가드(`or`: `airports_writer.py:53`) 동작 확인.

## [착수 안 한 것 — 우선순위 순]
1) corpus 전수(5,381) — `scripts/etap_audit.py`, 네트워크 0, 가장 빠름
2) 주제 혼입 91건(airports) + michelin 비미슐랭 — 판정 기준 미제안, 원인(토픽 큐) 미추적
3) template/feed 모드 36건, 마스터 표 `etap-audit-matrix.md`
4) 나머지 12패밀리 딥패스 (F1-F5, F6, F8-F12)
5) michelin P1(More about 빈 제목, alt="Photo") / P2
6) deals 106일·nomad 무발행 원인
7) 광고 잔해 2,412건 Step3 이후
8) GA4 per-blog 폴백(`G-N4Q99745QT` 공유), Viator PID 22블로그 확산

## [열려 있는 결정 — 대표 승인 필요]
- D그룹 41건 과소 수치 갱신 범위(중앙값 26배, 최대 189배)
- 주제 혼입 91건: 이동 / noindex / 방치
- ODbL 해석 외부 확인 (Produced Work는 출처 표기만이라는 가정, 미확정)
- GA4 전용 속성 34개 신설 여부
- airports Phase 2 품질 개선(좌표 중복, 보일러플레이트, 교통 정보 부재) 착수 시점

## [다음 세션 첫 명령]
"docs/superpowers/specs/2026-08-21-track-c-session-state.md 를 읽고, airports 30건 배치부터 재개. 동시에 corpus 전수 실행."

