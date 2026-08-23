# ETAP Adventure — Affiliate Relationship Verification

**Part of:** Track C (branch investigation — ETAP = branch 1 of N)

- **Branch**: `_rollback_test` (작성만, commit 없음)
- **상태**: VERIFICATION_ONLY (기존 Disclosure Design 수정/commit 안 함, 코드변경/writing-plans/구현 안 함)
- **대상**: `adventure.techpawz.com` (`adventure-hugo`, pipeline `etap`, SG-A raw Viator subgroup)
- **근거 원칙**: 코드·DB(SELECT)·공개 렌더링·설정파일만 사용. 비공개 계정(파트너 대시보드·계약)은 추측 금지 → 확인 항목만 사용자에게 요청. API key 값은 읽거나 기록하지 않음.

---

## 1. 검증 항목별 근거

### 1.1 Techpawz의 Viator Partner 통합 증거
- **HISTORICAL_AFFILIATE_INTEGRATION_CONFIRMED (통합 레벨)**: `viator_api.py`가 Viator Partner API(`https://api.viator.com/partner`)를 호출(`collectors/viator_api.py:17` `API_BASE`), `.env.common`에 Viator Partner API 키 설정 존재(값 기록 안 함) → Partner API 연동이 구성되어 있음.
- **과거 귀속 링크 실존**: `viator_tours.deep_link` 중 5,643행(전체 43,282행의 13%)이 `?mcid=[REDACTED_PARTNER_ID]&pid=[REDACTED_PARTNER_ID]&medium=api&api_version=2.0` 형태 보유 → **실제 Viator 파트너 ID로 과거에 귀속 링크가 생성된 사실 CONFIRMED**.
- **현재 계정/계약 상태(활성/휴면, 계약 원문)**: 비공개 대시보드 확인 불가 → **UNVERIFIED_PENDING_OWNER**.

### 1.2 PID / Partner ID 설정 존재 여부
- `VIATOR_PID` / `VIATOR_MCID` 환경변수: 코드에서 `os.getenv("VIATOR_PID","")`(`viator_api.py:63`, `pipeline.py:42`, 다수 SG-A2 모듈:70)로 참조.
- **현재 설정 위치 전수 조사**: `.env.common`(API 키만 있음, PID/MCID 없음), `~/.zshrc/~/.bashrc` 등 shell profile(0건), `~/Library/LaunchAgents/com.5000.*.plist` EnvironmentVariables(8개 plist 전부 0건) → **현재 실행 환경 어디에도 `VIATOR_PID`가 설정되어 있지 않음 CONFIRMED**.
- 과거에는 `[REDACTED_PARTNER_ID]`가 링크에 베이킹된 것으로 보아 당시 env 또는 API 응답에 파트너 ID가 존재했음(UNVERIFIED 세부).
- **값/secret 기록 금지 준수**: 위 파트너 ID는 DB에 이미 저장된 링크 문자열에서 관찰된 값이며, 신규 secret은 기록하지 않음(값은 `[REDACTED_PARTNER_ID]`로 대체).

### 1.3 `viator_tours.deep_link`에 attribution 정보가 있는지
- SELECT(읽기 전용): `viator_tours WHERE deep_link LIKE '%?%'` → 5,643행. 샘플:
  `https://www.viator.com/tours/.../d313-5562979P1?mcid=[REDACTED_PARTNER_ID]&pid=[REDACTED_PARTNER_ID]&medium=api&api_version=2.0`
- 즉 **DB 내 attribution 상태는 혼재**: 5,643행(13%)은 귀속 파라미터 보유, 37,639행(87%)은 베어 URL.
- `adventure_writer.fetch_tours`(`adventure_writer.py:30-41`)는 `viator_tours WHERE city=? ... ORDER BY price ASC`로 최저가 투어 1건을 선택 → 선택된 행에 따라 렌더 링크에 파라미터가 있거나 없음(비결정적).

### 1.4 수집·후처리 과정에서 parameter가 제거되는지
- **수집 단계**(`viator_api.py:62-66`): `pid = os.getenv("VIATOR_PID","")` → 현재 env 미설정이므로 `deep_link = product_url`(파라미터 미부착). 즉 제거가 아니라 **처음부터 미부착**.
- **후처리 단계**: `quality_guard.postprocess_content`의 URL 처리(`quality_guard.py:235-486`)는 "미인가 호스트 삭제(허용: r2.dev/techpawz.com/googlesyndication.com)"일 뿐, viator 링크의 쿼리 파라미터를 제거하는 로직은 **존재하지 않음**(grep `param|query|strip|split|parse` 0건). `post_processor`, `hugo_writer`에도 파라미터 제거 흔적 없음.
- 결론: **파라미터 제거는 발생하지 않음**. 현재 베어 URL의 원인은 "env 미설정 → 수집 시 미부착"임.

### 1.5 최종 렌더링 URL과 redirect 후 attribution 유지 여부
- **렌더링 URL**: 라이브 `adventure.techpawz.com` 최신글(kusadasi-adventure, 이전 조사 m0085) 관찰 — viator 링크 6건 모두 `?pid/?mcid/?campaign` 파라미터 **없음** CONFIRMED.
- **adventure 파이프라인**: `adventure_pipeline.py:98,107`가 `t.get("deep_link","")`를 그대로 카드 링크로 사용, runtime 주입(`_affiliate_link`) 없음 → 저장된 DB 값이 그대로 렌더.
- **redirect 후 attribution**: viator.com 링크 클릭 시 Viator 내부 리다이렉트가 발생하나, 파라미터가 원래 없으므로 리다이렉트 후에도 귀속 정보는 **유지될 수 없음**(부가 확인 필요 → UNVERIFIED, curl 추적 미수행).
- SG-A2(`pipeline.py:65-67` `_affiliate_link`)는 `if pid and "pid=" not in link` 조건부 주입 → 현재 pid env 미설정이므로 SG-A2도 베어 URL 렌더.

### 1.6 실제 commission 귀속 확인 가능한 dashboard·계약 증거
- Viator Partner 대시보드, 커미션 지급 내역, Contributor/Partner Agreement 원문 → **로컬·공개 소스로 확인 불가 = UNVERIFIED_PENDING_OWNER**.
- 간접 증거: DB에 `[REDACTED_PARTNER_ID]` 귀속 링크 5,643행 존재 → 과거에는 커미션 귀속 경로가 작동했음을 시사하나, 현재 귀속 여부는 대시보드 확인 필요.

---

## 2. 판정 (Verdicts)

### 2.1 파트너십 통합 (Integration)
**`HISTORICAL_AFFILIATE_INTEGRATION_CONFIRMED`**
- 근거: Viator Partner API 키(`.env.common`), Partner API 호출(`viator_api.py:17`), 그리고 DB에 보존된 실제 파트너 ID 귀속 링크 5,643행.
- 단, "현재 활성 파트너십인지/휴면인지/계약 유효한지"는 대시보드 미확인으로 **UNVERIFIED_PENDING_OWNER** (통합 자체는 CONFIRMED).

### 2.2 현재 렌더링 링크 귀속 상태 (Attribution of current output)
**`UNATTRIBUTED_VIATOR_LINK_CONFIRMED`**
- 근거: 현재 `VIATOR_PID` env 미설정 → 신규 수집은 베어 URL, 라이브 adventure 글 렌더 링크 6건 전부 파라미터 없음, DB 행의 87%가 베어 URL.
- 주의: 13%(5,643행)는 과거 귀속 링크가 남아 있어, `fetch_tours`가 우연히 그 행을 골라도 파라미터가 렌더될 수 있음(비결정적). 즉 "현재 출력은 귀속 정보가 없음"이 일반적 사실이나 100% 보장은 아님.

### 2.3 관계는 있으나 귀속 불명 (대안 배제)
`COMMERCIAL_RELATIONSHIP_BUT_ATTRIBUTION_UNVERIFIED`는 **채택 안 함** — 귀속 상태는 DB·라이브로 확인 가능하며, 현재는 귀속 없음이 CONFIRMED이기 때문.

### 2.4 UNKNOWN
해당 없음(모든 항목은 CONFIRMED 또는 UNVERIFIED로 분류).

---

## 3. 잔존 위험

- **귀속 불일치**: DB에 파라미터 보유 행(5,643)과 미보유 행(37,639)이 혼재 → adventure 글마다 귀속 여부가 비결정적. disclosure 관점에서 "일부 글은 귀속 링크, 일부는 무귀속"은 정책상 정합성 결함.
- **현재 코드 경로상 신규 수집 링크 무귀속**: `VIATOR_PID` 미설정으로 신규 수집은 베어 URL → 커미션 수익이 Techpawz에 귀속되지 않을 가능성(수익 직결 이슈). 단 이는 관계 검증 범위를 넘는 운영 문제이며, 전체 실행 이력 100% 증명은 아님.
- **redirect 추적**: viator.com 클릭 후 리다이렉트에서 귀속 파라미터가 전달되는지 curl 추적 미수행 → UNVERIFIED.
- **법적 관할**: techpawz 적용 관할(FTC/CMA/ASA/EU)은 이전 Disclosure Discovery에서 UNRESOLVED.

---

## 4. 사용자 확인란 (확정)

비공개 계정 확인 결과 반영 (금액·계정 식별자 제거):

- **account_active**: **YES** — Viator 파트너 계정이 현재 활성 상태.
- **recent_commission**: **YES (estimated, unpaid)** — 최근 커미션 추정 내역 있으나 미지급 상태.
- **pid_unset_intentional**: **UNKNOWN** — `VIATOR_PID`를 의도적으로 unset 한 것인지 누락된 것인지 미확정.

---

## 5. 준수 확인

- 기존 Disclosure Design 문서(`2026-08-20-etap-adventure-affiliate-disclosure-design.md`) 수정 안 함.
- commit 안 함 (작성만).
- 코드 변경 / writing-plans / 구현 안 함.
- 비공개 정보(파트너 ID 값·API key 값)는 `[REDACTED_PARTNER_ID]`로 대체하거나 기록하지 않음 (관찰된 파트너 ID는 DB 기존 저장값임).
