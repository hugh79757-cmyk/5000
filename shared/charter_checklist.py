"""Operations Charter preflight checklists — thin CLI helper.

Mirrors 64-PREFLIGHT-CHECKLISTS.md §2.1-2.5.
Usage: python -m shared.charter_checklist --job {mass-mod|deploy|rule-change|rollback|scheduler}
"""
import sys

CHECKLISTS = {
    "mass-mod": [
        "1. 진본경로 확인 — 수정 대상 경로가 config/blogs.d/{blog}.yaml의 site_path와 일치하는가? 5000/CUAP/ 등 죽은 복사본 위치가 아닌가? 확인 결과: [경로] → [진본/죽은복사본/불확실]",
        "2. git tag 백업 — 작업 전 현재 git 상태를 태그로 남겼는가? (예: backup-before-{작업명}-{YYYYMMDD}) 또는 파일/DB 스냅샷을 별도 위치에 백업했는가? 백업 위치: [태그명 또는 백업 경로]",
        "3. 파일럿 1건 선행 — 전체 적용 전 1건만 먼저 수정했는가? 파일럿 대상: [파일/레코드 식별자] 파일럿 검증 결과: [규칙 통과 여부 / Hugo 빌드 결과 / 라이브 확인]",
        "4. 라이브 대조 — 수정 후 라이브 URL을 HTTP GET/HEAD로 확인했는가? (CDN 지연 고려) 확인 URL: [라이브 URL] 확인 결과: [일치/불일치/확인 불가]",
        "5. 게이트 통과 — preflight_check(blog_id)가 blocked=False를 반환했는가? blocked=True인 경우: 원인 확인 → 수정 → 재검사 후 진행 preflight 결과: [blocked=True/False]",
        "6. 사람 승인 필요 여부 — 이 작업은 10건 이상 동시 수정이므로 **사람 승인이 필요**하다. 승인 요청 내용: [무엇을/왜/어느 범위/대안/위험] 승인 여부: [대기 중/승인됨/거부됨]",
    ],
    "deploy": [
        "1. 진본경로 확인 — 배포 대상 사이트 경로가 config에 등록된 site_path와 일치하는가? 확인 결과: [사이트 경로] → [진본/불일치/불확실]",
        "2. git tag 백업 — 배포 전 현재 파일 상태를 git tag로 남겼는가? (선택 사항이나 권장) 태그명: [태그명 또는 '미태그 — 사유:']",
        "3. 파일럿 1건 선행 — 이 작업은 배포이므로 파일럿 항목 N/A. 단, 신규 파이프라인/테마/레이아웃 변경인 경우: 별도 블로그에 먼저 배포 테스트했는가? 테스트 결과: [테스트 블로그/결과 또는 '해당 없음']",
        "4. 라이브 대조 — 배포 전 현재 라이브 상태를 확인했는가? (선택 사항) 배포 후: HTTP GET으로 배포된 URL 확인했는가? 확인 URL: [배포 후 라이브 URL] 확인 결과: [정상 서빙/불일치/확인 불가]",
        "5. 게이트 통과 — preflight_check(blog_id)가 blocked=False를 반환했는가? blocked=True인 경우: 절대 배포 진행하지 않음. 원인 확인 후 재검사. preflight 결과: [blocked=True/False] CRITICAL 규칙 위반 시: C01/C02/C04/C07/C09 등 우회 금지",
        "6. 사람 승인 필요 여부 — 일반 dispatcher.py를 통한 단일 블로그 배포: 사람 승인 불필요 (자동). 단, 다음 경우는 사람 승인 필요: Workers 블로그(Pages 아님) 배포, 다수 블로그 동시 배포(배포 직렬화 락 확인), 기존 버전 롤백을 포함한 재배포. 승인 필요 여부: [불필요/필요 — 사유:]",
        "※ CLOUDFLARE_API_TOKEN 환경변수가 설정되어 있으면 wrangler가 OAuth profile을 무시하고 잘못된 계정으로 배포할 수 있다. dispatcher.py는 내부에서 이 env var를 제거하므로 dispatcher.py 사용 시에는 문제 없음. 수동 wrangler 실행 시 주의.",
        "※ --commit-dirty=true 옵션 금지: git commit 생성 → Cloudflare Pages 자동 빌드 트리거로 배포 횟수 이중 소진.",
    ],
    "rule-change": [
        "1. 진본경로 확인 — 수정 대상 파일이 프로젝트의 진본 위치인가? ops_dashboard/db.py, content_integrity.py 등 규칙 관련 파일의 실제 경로 확인. 확인 결과: [파일 경로] → [진본/불일치]",
        "2. git tag 백업 — 규칙 변경 전 현재 db.py/체크 함수의 상태를 git tag로 남겼는가? 태그명: [태그명 또는 '미태그']",
        "3. 파일럿 1건 선행 — 신규 규칙: 단계 2(관찰규칙, WARNING)으로 먼저 등록했는가? 기존 규칙 수정: 수정 후 역검증 스크립트 실행했는가? 역검증 결과: [전건탐지 100% / 오탐 0건 / 실패 — 사유]",
        "4. 라이브 대조 — 규칙이 라이브 감지를 포함하는 경우(V 카테고리 등): 라이브 비교 API/HTTP 확인 가능한가? 확인 가능 여부: [가능/불가능 — 사유]",
        "5. 게이트 통과 — 규칙 변경 자체가 preflight 게이트를 통과해야 하는 것은 아님 (규칙 정의는 게이트 이전). 단, 변경된 규칙을 적용한 후 preflight_check가 의도대로 동작하는지 확인했는가? 확인 결과: [정상 동작/이상 — 사유]",
        "6. 사람 승인 필요 여부 — **규칙의 severity 변경(WARNING↔CRITICAL↔MAJOR) 또는 승격/강등은 사람 승인 필수.** 신규 규칙 추가(관찰단계, WARNING): 사람 승인 불필요 (자동 등록 가능). 기존 규칙 완화/강화: 역검증 통과 + 사람 승인 필요. 규칙 삭제: 사람 승인 필수. 승인 필요 여부: [불필요/필요 — 변경 내용 + 역검증 결과 첨부]",
        "※ 오탐/미탐 기록은 에이전트가 자동 수행 가능 (logs/rule_feedback.jsonl)",
        "※ 오탐/미탐 기록과 달리, severity 변경이나 승격/강등은 사람의 명시적 승인 필요",
        "※ 역검증 없이 CRITICAL로 승격하면 정상 글을 막는 거짓 양성 발생 → 신뢰 하락",
    ],
    "rollback": [
        "1. 진본경로 확인 — 롤백 대상 경로/DB가 실제 영향을 미치는 진본 위치인가? 죽은 복사본이나 테스트 환경을 롤백하는 것은 아닌가? 확인 결과: [대상] → [진본/죽은복사본/불일치]",
        "2. git tag 백업 — 롤백 전 현재 상태(롤백 대상)를 git tag로 남겼는가? 롤백은 '되돌리는' 작업이지만, 롤백 자체도 변경이므로 백업 필요. 태그명: [태그명 또는 '미태그 — 사유:']",
        "3. 파일럿 1건 선행 — 롤백의 영향을 받는 범위를 1건(예: 1개 블로그/1개 테이블)으로 좁혀 테스트했는가? 테스트 결과: [롤백 후 상태 확인 결과]",
        "4. 라이브 대조 — 롤백 후 라이브 상태를 HTTP로 확인했는가? CDN 캐시로 인해 롤백 결과가 즉시 반영되지 않을 수 있음. 확인 시 지연 고려. 확인 URL: [라이브 URL] 확인 결과: [롤백 반영됨/반영 안 됨 — CDN 지연 의심/확인 불가]",
        "5. 게이트 통과 — 롤백 후 preflight_check가 통과하는가? (롤백으로 인해 새로운 위반 발생하지 않았는지) preflight 결과: [blocked=True/False]",
        "6. 사람 승인 필요 여부 — **롤백은 사람 승인이 필수다.** 롤백 사유, 영향 범위, 대안(롤백 대신 수정 등)을 문서화하여 승인 요청. 승인 여부: [대기 중/승인됨/거부됨]",
        "※ 롤백은 '이미 배포된 것'을 되돌리는 작업이므로, 라이브에 실제 영향을 미침.",
        "※ 롤백 전 현재 상태를 반드시 백업(tag/스냅샷). 롤백 실패 시 원상복구 수단 확보.",
        "※ content.db 등 발행 기록 DB의 롤백은 실발행 기록 유실 가능성 → 특히 주의.",
    ],
    "scheduler": [
        "1. 진본경로 확인 — 스케줄러 설정 파일(plist, scheduler.py)이 실제 운영 환경의 진본 위치인가? 확인 결과: [파일 경로] → [진본/불일치]",
        "2. git tag 백업 — 스케줄러 설정 변경 전 현재 설정을 git tag로 남겼는가? (scheduler.py 수정 시 특히 중요) 태그명: [태그명 또는 '설정 변경 없음 — 단순 재시작']",
        "3. 파일럿 1건 선행 — 스케줄러 변경(빈도/대상 변경 등)인 경우: 1개 블로그 또는 짧은 간격으로 먼저 테스트했는가? 테스트 결과: [테스트 대상/결과]",
        "4. 라이브 대조 — 스케줄러 재개 후 첫 발행이 정상적으로 라이브에 반영됐는가? 확인 방법: 대시보드 발행 로그 / 라이브 포스트 확인 확인 결과: [발행 성공/실패 — 로그 확인]",
        "5. 게이트 통과 — 스케줄러가 발행하는 포스트에 대해 preflight_check가 정상 동작하는가? blocked=True가 발생하면 스케줄러가 적절히 처리(스킵/알림)하는가? 확인 결과: [정상/이상 — 로그]",
        "6. 사람 승인 필요 여부 — **스케줄러/데몬 재시작은 사람 승인이 필수다.** 재시작 사유, 예상 영향(발행할 글 대기열 등), 대안(다음 자연 발행까지 대기 등) 명시. 승인 여부: [대기 중/승인됨/거부됨]",
        "※ scheduler.py는 launchd로 상시 가동 중. 재시작 시 발행 대기열이 있으면 즉시 발행 시작.",
        "※ 스케줄러 재시작 전 현재 발행 중인 글이 있는지 확인. 강제 종료 시 발행 중간 상태 남을 수 있음.",
        "※ PID 변경 시 기존 모니터링/알림 설정이 새 PID를 가리키도록 갱신 필요.",
    ],
}


def print_checklist(job_type: str) -> int:
    """Print checklist for given job type. Returns 0 on success, 1 on error."""
    if job_type not in CHECKLISTS:
        print(f"Error: unknown job type '{job_type}'. Available: {', '.join(CHECKLISTS.keys())}", file=sys.stderr)
        return 1

    items = CHECKLISTS[job_type]
    title = {
        "mass-mod": "대량 수정",
        "deploy": "배포",
        "rule-change": "규칙 변경",
        "rollback": "롤백",
        "scheduler": "스케줄러 재개",
    }[job_type]

    box_width = 78
    top = "╔" + "═" * (box_width - 2) + "╗"
    mid = "║  프리플라이트 체크리스트 — " + title + " " * (box_width - 2 - 24 - len(title)) + "║"
    bot = "╚" + "═" * (box_width - 2) + "╝"

    print(top)
    print(mid)
    print(bot)
    print()
    print("작업 전 반드시 아래 항목을 출력하고 확인한다.")
    print()

    for item in items:
        print(f"□ {item}")
        print()

    print("※ 체크리스트를 모두 확인하지 않고 작업을 시작하면 안 된다.")
    if job_type == "mass-mod":
        print("※ dry-run 먼저: 스크립트는 --dry-run/--check 모드로 실제 변경 없이 결과 출력 후 확인")

    return 0


def main():
    if len(sys.argv) < 3 or sys.argv[1] != "--job":
        print("Usage: python -m shared.charter_checklist --job {mass-mod|deploy|rule-change|rollback|scheduler}", file=sys.stderr)
        return 1
    return print_checklist(sys.argv[2])


if __name__ == "__main__":
    sys.exit(main())