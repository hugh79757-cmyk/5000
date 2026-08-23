# WL-20260814-c-integrity-engine-fix

작업일: 2026-08-14
작업자: LLM 에이전트 (5000 ops_dashboard)
계통: Phase C-무결성 검수엔진 결함 수정 (확산 선행조건)

## 배경

- hotissue C03 거짓초록불은 전수스캔 0건으로 실재 안 함(우려 반박).
- 그러나 `_read_post_files()`의 mtime 7일 컷오프 + `check_c01` posts[0] 단건검사는
  거짓초록불/커버리지 구멍을 만드는 검수엔진 자체 결함. 확산 재개 전 고침.
- 개별 블로그 콘텐츠는 건드리지 않고 엔진(content_integrity.py)만 수정.

## 결함1 — C01 단건검사 (posts[0])

### 확증(1a)
- `check_c01`은 `posts[0]` 1건만 검사, `posts`는 rglob 비정렬 → "최신" 보장 없음.
- hotissue C01 실제 위반 5건 vs posts[0]는 무작위 1건만 검사해 왜곡.

### 수정(1b)
- C01을 전수 순회로 변경 (C02~C09 패턴과 동일), py_compile OK.

### 검증(1c)
- 서버 재기동(launchctl kickstart) → hotissue C01 5건 보고(실측과 일치).
- techpawz C01 91건 노출 — 전수 전환의 정상 결과(이전 최대 1건만 잡혔음).

## 결함2 — mtime→OR 병합 컷오프

### 확증(2a) — date 신뢰성
- frontmatter date 누락 파일 149건 존재, 전부 파일명 date도 없음(fallback 불가).
- fm date와 파일명 date 불일치 0건 → date 자체는 신뢰.
- date 단일 기준 dry-run: 검사대상 18,679→948건 붕괴(거짓초록불 대량 위험).

### 설계 결정 (사용자 승인)
- **OR 병합 채택**: 검사대상 = (mtime ≥ now-7d) OR (frontmatter date ≥ now-7d)
  OR (date 파싱 불가/없음 → 포함, 안전측).
- date 단일(948건 붕괴)·mtime 단일(touch 은닉) 각 구멍을 상호 보완.

### 수정(2b)
- `_read_post_files()` OR 병합 교체, `_frontmatter_date_ts()` 추가.
- 파싱 실패/값없음은 None → 호출부에서 "검사포함(안전측)"으로 보장.
- py_compile OK.

### dry 영향(2c)
- 총 검사대상 mtime 18,680 → OR 18,719 (+39, 소폭). date 단일 붕괴 없음.
- hotissue 879 → 879 (변동 0).

### 실증(2d)
- 임시 디렉토리 3 시나리오:
  - 회피경로(mtime만 최근): 포함 ✓ (touch 은닉 불가)
  - date 커버(mtime 오래+date 최근): 포함 ✓
  - 안전측(date 없음): 포함 ✓
- techpawz C01 위반: mtime 검사대상 790건=91, OR 791건=91 → OR은 검사대상만
  +1 추가, C01 위반 수 불변 = 타 체크 수치 급변 없음 확인.

## 정책 경계 문서화 (2, 종료 시)

**'최근분만 검수' 정책 한계 (의도된 정책으로 간주, 계획문서 62-04 근거):**

- OR 병합도 "mtime 7일 밖 **AND** date 7일 밖"인 과거 발행글의 신규 오류는 못 잡음.
- 이것이 (a) 의도된 "최근분만 검수" 정책이면 정상. 계획문서
  `62-04-preflight-gate.md`의 "최근 7일" 명시를 근거로 (a)로 간주.
- (b) 전수검사 트랙이 필요해지면 별도 작업 — 이번 범위 밖(문서화만).
- 대시보드가 "0건"이라고 해서 전수 검수가 아니므로, 과거 발행글 오류는
  주기 전수스캔(별도)으로만 확인 가능.

## 잔존 위험
- 과거 발행글 신규 오류는 OR 병합으로 못 잡음 → 전수검사 트랙 필요 시 별도.
- C01 91건(techpawz) 등 전수 전환으로 노출된 누적 위반은 콘텐츠 교정 대상
  (별도 웨이브. 엔진 수정 아님).

## 관련 파일
- `ops_dashboard/checks/content_integrity.py` — 엔진 수정(결함1+2)
- 백업: `/tmp/c_integrity_backup_20260814/content_integrity.py.c01applied`
- git 태그: `pre-c-integrity-2-engine-fix-20260814`, `pre-c-integrity-1-hotissue-fix-20260814`