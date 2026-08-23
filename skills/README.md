# 5000 Skills Index

> 프로젝트 내 스킬 문서 색인. 에이전트 작업 시 참조.

## TAP

| 스킬 | 경로 | 설명 |
|------|------|------|
| tap-blog-spec | `skills/tap-blog-spec/SKILL.md` | TAP 블로그 본문 레이아웃 규격 (전체 구조, H2 제한, H3 이미지·네이버지도 버튼, 쿠팡, nearby, 검증 체크리스트) |
| travel-hugo-publish | `skills/travel-hugo-publish/SKILL.md` | travel-hugo(tour1.rotcha.kr) 발행 특화 스킬. 여행 파이프라인, 쿼터 우회 발행, Hugo 빌드/배포 |
| quota-bypass-publish | `skills/quota-bypass-publish/SKILL.md` | 쿼터우회 발행 공용 스킬. `shared/quota_bypass.py` 사용법, 단일 블로그 발행, 지원/제외 분기 |

## 관련 문서 (Phase 68)

TAP 본문 규격의 배경이 되는 Phase 68 문서들:

| 문서 | 경로 | 설명 |
|------|------|------|
| TAP Writer 분리 구조 | `.planning/phases/PHASE-68/TAP-WRITER-ARCHITECTURE.md` | Blogger Writer(TAP/core/) vs Hugo Writer(5000/pipelines/travel/) 구분 |
| PPM-6 작업 계획 | `.planning/phases/PHASE-68/20-PPM-6-tap-blogger-body-layout.PLAN.md` | 5000-side + TAP-side 작업 범위 및 결정 사항 |

## 탐색 명령어

```bash
# 전체 스킬 목록
find skills -name "SKILL.md" | sed 's|skills/||;s|/SKILL.md||'

# 특정 스킬
find skills -path "*tap*" -name "SKILL.md"
```

## 공용 유틸 (쿼터우회)

쿼터 우회 발행은 `scripts/force_publish_travel.py`(travel 전용, 권장)를 전 분기로
일반화한 `shared/quota_bypass.py`(쿼터우회)를 참고한다.
`python3 shared/quota_bypass.py {blog_id}` 또는 `--list` 로 지원 분기 확인.
