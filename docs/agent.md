# Agent.md — 5000 프로젝트 세션 기록

## 세션: 2026-06-30T12:00+09:00

### 발견된 문제

- **증상**: 2026-06-27 ~ 06-30 (4일간) 전 블로그 발행 중단
- **로그**: `shared/validators.py` line 156 `IndentationError: expected an indented block after 'if' statement on line 155`
- **원인**: `_check_naver_map()` 함수 내 `if not has_map:` 뒤에 본문 블록 누락. `def is_korean_content()`가 실수로 `if` 블록 body로 들여쓰기되어 Python 구문 오류 발생

### 조치

1. `shared/validators.py:155` — `if not has_map:` 아래 `return issues` 추가
2. `shared/validators.py:156` — `def is_korean_content` 들여쓰기 해제 → 모듈 레벨로 복원
3. `scheduler.py:104` — `_check_python_syntax()` 함수 추가 (전체 `.py` `ast.parse()` 구문 검증)
4. 스케줄러 재시작 (`launchctl stop/start com.5000.scheduler`)

### 재발방지

`_check_python_syntax()`가 scheduler 시작 시 전체 `.py` 파일의 `SyntaxError`/`IndentationError`를 검증. 발견 시 `sys.exit(1)`로 즉시 실패 처리.

---

## 세션: 2026-07-22T00:00+09:00

### AdSense Publisher ID 매핑 (확정)

| Publisher ID | 사이트 계열 |
|---|---|
| `ca-pub-8772455780561463` | rotcha.kr, techpawz.com, farmsolutionint.com |
| `ca-pub-6677996696534146` | informationhot.kr (및 *.informationhot.kr) |

**절대 규칙**: 한 HTML 페이지 = 하나의 AdSense Publisher ID. `adsbygoogle.js?client=`와 `<ins data-ad-client>`는 반드시 동일 계정.

### 썸네일 R2 업로드 버그 (수정 완료)

- **원인**: `mde2/app/services/r2_uploader.py:113` `upload_all_images()`가 오직 `thumbnail.webp`만 찾았으나,新一代 thumbnail 파일명은 `thumb_pexels_*.webp`, `thumb_unsplash_*.webp` 형태
- **수정**: `thumb_*.webp` 패턴(assets/ 하위)도 함께 업로드하도록 변경 (2026-07-22)

### Cloudflare Pages 배포 시 프로필

Hugo 빌드 + `wrangler pages deploy` 전, 항상 다음을 unset 후 실행:
```bash
unset CLOUDFLARE_API_TOKEN CLOUDFLARE_ACCOUNT_ID CF_DNS_TOKEN CLOUDFLARE_WORKERS_AI_API_TOKEN R2_ENDPOINT
```
- 활성 프로필: `hugh79757` (토큰 위치: `~/.wrangler/config/hugh79757.toml`)
- wrangler 토큰에는 `zone:read`, `pages:write`, `workers:write` 포함 (DNS 쓰기 권한 없음)
- account: `fac9808c757df31d797190c529aaa71a` (hugh79757@gmail.com)

### img.techpawz.com 도메인 상태 (미해결)

- 현재: DNS → Cloudflare IP (104.21.31.45) → Pages 404
- 원인: `img.techpawz.com`이 `techpawz-hugo` Pages 프로젝트의 커스텀 도메인으로 연결되어 있지 않음
- 해결 필요: Cloudflare Dashboard → Pages → techpawz-hugo → 도메인에 `img.techpawz.com` 추가
  - 또는 DNS에서 CNAME `img → techpawz-hugo.pages.dev` 설정 후 Pages에서 연결 인식
  - *자동 설정 실패 원인: hugh79757 API key에 `dns_records:write` 권한 없음*

### 필요한 작업
1. Cloudflare Dashboard에서 `img.techpawz.com` → Pages `techpawz-hugo`에 연결
2. 연결 후 해당 도메인 통과 확인

### 세션 종료 시 문서 업데이트 규칙

- `agent.md`: 현재 세션에서 발견된 문제/조치/재발방지 기록
- `tech.md`: 시스템 구조/설계 결정사항 변경 시 업데이트
- `status.md`: 발행 현황/블로그 상태 변경 시 업데이트
