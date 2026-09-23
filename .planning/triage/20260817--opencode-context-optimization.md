---
date: 2026-08-17
type: config
status: resolved
---

# opencode 컨텍스트 소진 최적화 (config + zshrc + 로그 정리)

## What
opencode 사용 시 컨텍스트가 순식간에 소진되는 문제 진단 및 최적화 적용.

## Why
- 시스템 프롬프트 고정 비용 ~34-44K 토큰 (스킬 카탈로그 170개 ≈ 24-28K, AGENTS.md 합 ~17K)
- 기본 모델 `nvidia-nemotron-nano-9b-v2`는 컨텍스트 128K → 압축 트리거 50%(64K) 기준 실질 작업 공간 ~19K 토큰
- `~/.local/share/opencode/log/opencode.log` 316MB 무회전 누적
- workspace(5000) 밖 경로 접근 시 external_directory 기본값 ask → 매번 승인 팝업

## Files changed
- `~/.config/opencode/opencode.json` — `model` → `opencode/deepseek-v4-flash-free` (128K→200K), `logLevel: "WARN"`, `tool_output: {"max_lines": 200, "max_bytes": 8192}`, permission에 `external_directory`(~/Projects/**, /tmp/**, ~/.config/opencode/**, ~/.local/share/opencode/**) + `doom_loop: "allow"` 추가
- `~/.zshrc` (102-105줄) — opencode 셸 함수에 `--auto` + `OPENCODE_DISABLE_EXTERNAL_SKILLS=1` 적용
- `~/.local/share/opencode/log/opencode.log` — 316MB → `opencode.log.bak-20260817` 백업 후 truncate

## How
- `open-context-check` (Sharper-Flow, 로컬 빌드)로 세션별 라이브 사용량·시스템 프롬프트 크기 정량화
- models.dev + opencode 이슈로 모델 컨텍스트 한도 확인 (deepseek-v4-flash-free 무료 티어 200K, 1M 아님)
- 바이너리 strings 검증으로 `OPENCODE_DISABLE_EXTERNAL_SKILLS` env var 실존 확인
- 백업: `opencode.json.bak-ctx`, `opencode.json.bak-perm`

## Verification
- config JSON 유효성: `python3 -m json.tool` 통과
- `zsh -n ~/.zshrc` syntax OK, `type opencode` → shell function, `opencode --version` 1.18.18
- 스킬 파일 디스크 보존 확인 (85+35+36개) — 비활성화는 스캔 중단일 뿐 삭제 아님
- 재시작 후 `/context` 재측정으로 절감량 확인 필요 (부분검증)

## Notes
- `OPENCODE_DISABLE_EXTERNAL_SKILLS=1`로 ~/.claude·~/.agents 스킬 전부 비활성화 — GSD 스킬(gsd-quick 등) 필요 시 `skills.paths`로 선택 로드 또는 env 제거
- deepseek-v4-flash-free는 200K 상한 (서버 측 제약, 1M 아님)
