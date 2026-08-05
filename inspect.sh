#!/usr/bin/env bash
# 블로그 안정화 작업 전 현황 파악용 인스펙션 스크립트
# 사용법: bash inspect.sh  (또는 chmod +x inspect.sh && ./inspect.sh)

set -uo pipefail
sep() { echo; echo "========== $1 =========="; echo; }

# 1) 전체 상태/계획 문서
sep "STATE.md";        cat STATE.md 2>/dev/null || echo "(없음)"
sep "BLOG_STATUS.md";  cat BLOG_STATUS.md 2>/dev/null || echo "(없음)"
sep "ROADMAP.md";      cat ROADMAP.md 2>/dev/null || echo "(없음)"

# 2) 발행 제어 핵심 코드
sep "scheduler.py";    cat scheduler.py 2>/dev/null || echo "(없음)"
sep "dispatcher.py";   cat dispatcher.py 2>/dev/null || echo "(없음)"

# 3) 설정
sep "config/ 목록";    ls -la config 2>/dev/null || echo "(없음)"
sep "hugo.toml (앞부분)"; head -n 60 hugo.toml 2>/dev/null || echo "(없음)"

# 4) 파이프라인 / 프롬프트 구조 (내용 말고 구조부터)
sep "pipelines/ 트리"; find pipelines -maxdepth 2 -type f 2>/dev/null | sort || echo "(없음)"
sep "prompts/ 트리";   find prompts   -maxdepth 2 -type f 2>/dev/null | sort || echo "(없음)"
sep "workers/ 트리";   find workers   -maxdepth 2 -type f 2>/dev/null | sort || echo "(없음)"
sep "shared/ 트리";    find shared    -maxdepth 2 -type f 2>/dev/null | sort || echo "(없음)"

# 5) 분기별 콘텐츠 현황 (분기 = content 하위 디렉토리로 가정)
sep "content/ 분기 목록"; ls -la content 2>/dev/null || echo "(없음)"
sep "분기별 글 개수(.md)"
if [ -d content ]; then
  for d in content/*/; do
    n=$(find "$d" -type f -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
    printf "%-40s %s개\n" "$d" "$n"
  done
else
  echo "(content 디렉토리 없음)"
fi

# 6) draft 상태 글 카운트 (숨김 처리 현황 파악)
sep "draft: true 글 개수(분기별)"
if [ -d content ]; then
  for d in content/*/; do
    n=$(grep -rl --include="*.md" -E '^draft:\s*true' "$d" 2>/dev/null | wc -l | tr -d ' ')
    printf "%-40s draft %s개\n" "$d" "$n"
  done
fi

# 7) 최근 로그 (발행/에러 흐름)
sep "logs/ 최근 파일"; ls -lat logs 2>/dev/null | head -n 15 || echo "(없음)"

# 8) cuap 안정화 회고용: 최근 커밋 로그
sep "최근 git 커밋 20개"; git log --oneline -20 2>/dev/null || echo "(git 아님/없음)"
