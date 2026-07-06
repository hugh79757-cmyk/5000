# Travel Writer 포맷 오류 수정

## Description
travel.yaml 프롬프트 템플릿 6개에 H1/취소선/강조 포맷 규칙을 [ABSOLUTE BAN] 첫 줄에 추가하고, writer.py에 sanitize_markdown() 안전망 함수를 추가하여 마크다운 강조/취소선 짝 불일치와 중복 H1 문제를 이중 방어 구조로 해결한다.

## Files
- `config/prompts/travel.yaml` — 6개 prompt_id 포맷 규칙 강화 (+48/-21)
- `pipelines/travel/writer.py` — sanitize_markdown() 신규 (+74/-3)

## Steps
1. `git add` travel.yaml + writer.py
2. `git commit -m "fix(travel-writer): 마크다운 포맷 오류 이중 방어 — prompt 규칙 강화 + sanitize_markdown()"`
3. Update `.planning/STATE.md`에 Quick Tasks 테이블 추가
