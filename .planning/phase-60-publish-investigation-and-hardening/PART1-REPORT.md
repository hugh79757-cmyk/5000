# Part 1: 발행/배포 중단 원인 규명 보고서

> 작성일: 2026-08-06
> 기준: publish_ledger × pre-refactor-baseline(d85095152, 2026-08-06 10:33:52)
> 데이터: content.db 42,209건 × blog_lifecycle 85개 블로그

---

## 판정표 요약

| 원인 | 블로그 수 | 설명 |
|------|-----------|------|
| **(a) 차단 반복** | 7 | 리팩토링 전후 관계없이 실패 반복 — 원래 문제 |
| **(b) 발행 시도 중단** | 52 | 파이프라인이 아예 가동 안 됨 — 원래 문제 |
| **(d) 리팩토링 회귀** | 0 | 리팩토링으로 인한 신규 회귀 없음 |
| **정상** | 31 | 8/1 이후 성공 발행 있음 |
| **합계** | 90 | publish_ledger 기준 (blog_lifecycle 85 + ledger 전용 5) |

**핵심 발견: 리팩토링 회귀(d) 0건.** 59-01 ETAP 통합, 59-06~08 테마 마이그레이션 등이 발행 중단을 유발하지 않았음.

---

## (a) 차단 반복 — 7개 블로그

| 블로그 | 마지막 성공 | 8/1 이후 성공 | 8/1 이후 실패 | 주요 실패 사유 |
|--------|-------------|---------------|---------------|---------------|
| beauty-hugo | 08-06 | 19 | 15 | publish_error(6), write_error(4), similar_title(3) |
| interior-hugo | 08-06 | 20 | 10 | similar_title(6), write_error(2), irrelevant_products(2) |
| kitchen-hugo | 08-06 | 19 | 20 | write_error(14), publish_error(4), irrelevant_products(2) |
| pick-hugo | 07-13 | 0 | 37 | no_topics(23), no_result(9), no_data(4) |
| senior-blogger | 07-28 | 0 | 50 | publish_error(48) — Blogger API 발행 자체 실패 |
| senior-hugo | 07-29 | 0 | 49 | publish_error(47) — Blogger API 발행 자체 실패 |
| travel4-hugo | 07-28 | 0 | 29 | no_result(29) — 데이터 수집 성공이나 가드 차단 |

**판정 근거:**
- beauty/interior/kitchen: 리팩토링 전부터 있던 유사제목/쓰�기오류. 리팩토링 후에도 성공 발행이 있음 → 원래 문제
- pick-hugo: 7/13 이후 토픽 소진. 리팩토링과 무관
- senior-blogger/hugo: Blogger API 발행 실패. 파이프라인 자체 문제
- travel4-hugo: 데이터 수집 가드 차단 (no_result). 리팩토링과 무관

---

## (b) 발행 시도 중단 — 52개 블로그

### 카테고리별 분류

| 카테고리 | 블로그 수 | 마지막 성공 시기 | 원인 추정 |
|----------|-----------|------------------|-----------|
| ETAP (전체 inactive) | 31 | 2026-05 ~ 2026-04 | 파이프라인 미가동 (inactive 상태) |
| CAP (paused) | 6 | 2026-06 ~ 2026-04 | paused 상태로 스케줄 중단 |
| STAP | 1 | 2026-05-14 | tap-hugo — 파이프라인 미가동 |
| TAP (travel4) | 1 | 2026-07-28 | 가드 차단 반복으로 시도 중단 |
| manual | 8 | 없음 | 파이프라인 미연동 (수동 관리) |
| 기타 | 5 | 없음 | 파이프라인 미연동 |

**ETAP 31개:** 전부 `status: inactive` 상태. 리팩토링과 무관하게 이미 5월에 가동 중단됨.
**CAP 6개 (compare/deal/ev/guide/hotissue/tco):** `status: paused`. 리팩토링과 무관.

---

## (d) 리팩토링 회귀 — 0건

**리팩토링 59-01(ETAP 31개 통합), 59-06~08(테마 마이그레이션), 59-09(ETAP wrapper), 59-11(naming fix)로 인해 발행이 중단된 블로그는 없음.**

근거: 모든 (a) 판정 블로그는 리팩토링 전부터 이미 차단 상태였으며, 리팩토링 후에도 성공 발행이 있거나 실패 사유가 기존과 동일함.

---

## ETAP R01/R02 대량 fail 규명

### 원인
ETAP 블로그는 Hugo config를 `config/_default/hugo.toml`에 위치 (Hugo config directory 패턴).
기존 R01/R02 검사는 루트의 `hugo.toml`만 확인 → ETAP 36개 전부 "No hugo.toml/config found" CRITICAL.

### 조치
`_find_config_file()` 함수 추가: 루트 우선, 없으면 `config/_default/` 탐색.
→ ETAP R01 "No hugo.toml found" 해결.

### ETAP 현재 상태 (수정 후)
| 블로그 | R01 | R02 | R03 | R04 |
|--------|-----|-----|-----|-----|
| adventure-hugo | pass | fail (advertisement 없음) | pass | fail (GA4 없음) |
| airlines-hugo | pass | fail | pass | fail |
| flights-hugo | pass | fail | pass | fail |

**판정:** ETAP은 원래 `config/_default/` 구조로 작동. R01 위반은 **검사 규칙 결함**이었지 리팩토링 회귀가 아님. 수정 완료.

---

## 알림 소음 차단

`standard_compliance`의 CRITICAL 위반 시 실시간 텔레그램 푸시를 비활성화.
→ ops.db에 기록은 유지, 텔레그램 발송은 logger.warning으로 전환.
→ Part 3에서 일일 요약으로 재설계 예정.

기존 발행 실패(publish_error 등) 텔레그램 알림은 그대로 유지.

---

## 잔존 위험

1. **(b) 52개 블로그 중 31개 ETAP:** inactive 상태이나 YAML에는 여전히 존재. 대시보드에서 지속적으로 "발행 시도 중단"으로 표시됨. ETAP 파이프라인 재가동 여부 결정 필요.
2. **senior-blogger/hugo:** Blogger API 발행 실패가 48/47건. Blogger API 자체 문제 또는 인증 만료 가능성.
3. **pick-hugo:** 토픽 소진(no_topics 23건). 토픽 풀 확장 또는 전략 변경 필요.
4. **(c) 배포 유실 판정 불가:** publish_ledger에 "성공 기록 있는데 라이브에 없는 글"을 HTTP HEAD로 대조하는 작업은 Part 1 범위 밖 (별도 스크립트 필요).
