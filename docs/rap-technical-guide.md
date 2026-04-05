# 5000-RAP 기술문서

**문서 버전**: 4.0
**최종 업데이트**: 2026-04-05
**프로젝트 경로**: `/Users/twinssn/Projects/5000` (파이프라인), `/Users/twinssn/Projects/RAP` (Hugo 블로그)

---

## 1. 시스템 개요

5000-RAP(Real-estate Auto Publisher)는 국토교통부 실거래가 공공데이터를 수집하여 AI 기반으로 부동산 분석 블로그 글을 자동 생성·발행하는 파이프라인 시스템이다. 하나의 파이프라인 코드베이스에서 5개의 독립적인 Hugo 블로그를 운영하며, 각 블로그는 부동산 분석의 서로 다른 영역을 전담한다.

---

## 2. 블로그 아키텍처

### 2.1 블로그 목록

| 블로그 | 도메인 | 전담 영역 | CF 프로젝트 |
|--------|--------|-----------|-------------|
| rap-hugo | apt.informationhot.kr | 매매 시세 분석 | rap-hugo |
| rap2-hugo | apply.informationhot.kr | 청약 정보 | rap2-hugo |
| rap3-hugo | tax.informationhot.kr | 세금 가이드 | rap3-hugo |
| rap4-hugo | rent.informationhot.kr | 전세·월세 리포트 | rap4-hugo |
| rap5-hugo | brand.informationhot.kr | 브랜드 아파트 분석 | rap5-hugo |

### 2.2 배포 방식

모든 RAP 블로그는 Cloudflare Pages **Direct Upload** 방식(Git Provider: No)으로 배포한다.
배포 명령: `wrangler pages deploy ./public --project-name={cf_project}`
git push는 GitHub 코드 백업 용도이며 CF 빌드 횟수를 소모하지 않는다.

### 2.3 M1/M4 역할 분리

- **M4 (MacBook Air M4)**: 코드 작성, git push, wrangler 배포 설정
- **M1 (MacBook Air M1)**: 파이프라인 실행 서버 (`ssh m1` / `m1ssh.aikorea24.kr`)
- 프로젝트: `/Users/twinssn/Projects/5000/`
- RAP 블로그: `/Users/twinssn/Projects/RAP/rap{1~5}-hugo/`
- venv: `cd ~/Projects/5000 && source .venv/bin/activate`
- M1 wrangler 인증: `~/.wrangler/config/default.toml` + `CLOUDFLARE_API_TOKEN` 환경변수 (2026-04-05 설정)

---

## 3. 데이터 파이프라인

### 3.1 rap.db 테이블 구조

| 테이블 | 설명 |
|--------|------|
| trades | 국토교통부 실거래가 (지역별 수집) |
| subscriptions | LH 청약 공고 |
| keywords | 발행 키워드 관리 |
| publish_log | 발행 이력 (중복 방지) |
| refresh_log | 데이터 갱신 이력 |

### 3.2 키워드 현황 (2026-04-05 기준)

| 블로그 | active | inactive | 비고 |
|--------|--------|----------|------|
| rap-hugo | 1,534 | 64 | trades 기반 실거래가 키워드 |
| rap2-hugo | 170 | 238 | 청약 공고 기반 |
| rap3-hugo | 1,096 | 80 | trades 기반 세금 키워드 |
| rap4-hugo | 1,351 | 9 | trades 기반 전세 키워드 |
| rap5-hugo | 221 | 70 | trades 기반 브랜드 키워드 |

### 3.3 키워드 생성 방식 (2026-04-05 확정)

`sync_keywords_from_trades()` 함수가 trades 테이블에서 단지명을 추출하여 블로그별 키워드를 자동 생성한다.

- rap-hugo: `"{단지명} {district} 실거래가"`
- rap3-hugo: `"{단지명} {district} 세금"`
- rap4-hugo: `"{단지명} {district} 전세"`
- rap5-hugo: 브랜드 단지만 `"{단지명} {district} 브랜드"`

**gap.db 의존성 완전 제거 (2026-04-05)**: `sync_keywords_from_gap()` 완전 삭제. 공공데이터 API → rap.db 단방향으로 완전 분리.

### 3.4 오염 키워드 정리 이력 (2026-04-05)

총 476개 비활성화 처리:

| 패턴 | 사유 |
|------|------|
| 상가, 토지, 업무시설, 근린생활, 용지 | 부동산 거래 부적합 |
| 어린이집, 임차운영, 관리동, 잔여세대 | 아파트 파이프라인 부적합 |
| 공급공고, 모집공고, 선정공고, 입찰 | 공공 입찰 공고 |
| [정정공고], 수의계약, 재입찰 | 행정 공고 |
| 개념어 키워드 (rap3) | 지역명 없어 법정동코드 미매칭 |
| 개념어 키워드 (rap5) | 지역명 없어 법정동코드 미매칭 |

---

## 4. 파이프라인 핵심 로직

### 4.1 _pick_keyword (2026-04-05 수정)
```python
"SELECT keyword, category FROM keywords "
"WHERE status='active' AND blog_target=? "
"ORDER BY use_count ASC, last_used_at ASC NULLS FIRST "
"LIMIT 200",
(blog_id,)
```

**핵심 수정**: `blog_target=?` 조건 추가. 기존에는 전체 keywords에서 패턴 필터만 적용하여 타 블로그 키워드가 혼용되는 버그가 있었음. 이 수정으로 각 블로그가 자신에게 할당된 키워드만 선택.

### 4.2 3중 키워드 방어 체계

1. **RAP_EXCLUDE**: 선택 단계에서 부적합 키워드 원천 차단
2. **_pick_strategy TRADE_INCOMPATIBLE**: trade→subscription 자동 전환
3. **trade 진입 직전**: 최종 검증

### 4.3 subscription 전략 버그 수정 (2026-04-05)

rap2-hugo 발행 중단 원인: `generate_subscription_article()` 호출 코드가 잘못된 들여쓰기로 실행되지 않음.
```python
# 수정 전 (들여쓰기 오류 — 실행 안 됨)
            if not subs:
                continue
                subs = sorted(...)      # 여기가 if 블록 안으로 들어가 있었음
                article = generate_subscription_article(...)

# 수정 후
            if not subs:
                continue
            subs = sorted(subs, key=lambda x: (0 if x.get("detail_url") else 1))
            article = generate_subscription_article(keyword, subs)
```

### 4.4 rap3/rap5 개념어 키워드 문제 (2026-04-05)

**증상**: "신혼부부 취득세 감면", "래미안 브랜드 프리미엄 분석" 같은 개념어 키워드가 `use_count=0`으로 우선 선택되어 `find_lawd_cd()` 법정동코드 미매칭 → 5회 연속 스킵 → `write_failed`.

**조치**: 지역명이 없는 개념어 키워드를 비활성화. rap3 73개, rap5 69개 처리.

**근본 원인**: `sync_keywords_from_trades()`와 별도로 수동 추가된 개념어 키워드가 trades 기반 키워드보다 `use_count=0, last_used_at=NULL`로 우선순위가 높아 먼저 선택됨.

---

## 5. 품질 관리

### 5.1 품질 점수 체계 (100점 만점)

발행 전 자동 감점 항목:

| 항목 | 감점 |
|------|------|
| 지역 특성 할루시네이션 (학군, 교통, 인프라) | 3~5점 |
| 더미 링크 (화이트리스트 외) | 15점 |
| 양도세 매입가 날조 | 5점 |
| 억 환산 오류 | 10점 |
| 본문 1,500자 미만 | 30점 |
| 본문 2,200자 미만 | 10점 |
| 제목 40자 초과 | 5점 |
| 키워드 토큰 본문 미포함 | 20점 |
| 함께읽기 중복 | 5점 |
| LaTeX 수식 잔존 | 5점 |

60점 미만 → draft 전환 (발행 차단)
60~80점 → 경고 로그
80점 이상 → 정상 발행

### 5.2 현재 품질 점수 (2026-04-05)

| 블로그 | 이전 점수 | 현재 점수 | 상태 |
|--------|-----------|-----------|------|
| rap-hugo | 72 → 82 | 개선 | ✅ 정상 발행 |
| rap2-hugo | 68 → 78 | 개선 | ✅ 정상 발행 (버그 수정) |
| rap3-hugo | 65 → 80 | 개선 | ✅ 정상 발행 (개념어 정리) |
| rap4-hugo | 70 | 유지 | ✅ 정상 발행 |
| rap5-hugo | 55 → 95 | 대폭 개선 | ✅ 정상 발행 (개념어 정리) |

### 5.3 네이버지도 삽입률 (2026-04-05)

| 블로그 | 전체 글 | 지도 삽입 | 삽입률 |
|--------|---------|-----------|--------|
| rap-hugo | 38 | 6 | 16% |
| rap2-hugo | 28 | 0 | 0% |
| rap3-hugo | 53 | 8 | 15% |
| rap4-hugo | 50 | 7 | 14% |
| rap5-hugo | 53 | 25 | 47% |

**과제**: 네이버지도 삽입률 전체적으로 낮음. 목표 60% 이상.

---

## 6. 스케줄러 운영

### 6.1 발행 스케줄

| 블로그 | 발행 시간 | 일일 quota |
|--------|-----------|------------|
| rap-hugo | 08:30, 11:30, 14:30, 17:30, 21:30 | 5 |
| rap2-hugo | 08:40, 11:40, 14:40, 17:40, 21:40 | 5 |
| rap3-hugo | 08:45, 11:45, 14:45, 17:45, 21:45 | 5 |
| rap4-hugo | 08:50, 11:50, 14:50, 17:50, 21:50 | 5 |
| rap5-hugo | 09:10, 12:10, 15:10, 18:10, 22:10 | 5 |

### 6.2 내일 예상 발행량 (2026-04-06)

| 블로그 | 예상 발행 | 키워드 재고 | 비고 |
|--------|-----------|-------------|------|
| rap-hugo | 5건 | 1,534개 (충분) | 정상 |
| rap2-hugo | 3~5건 | 170개 (30일분) | 소진 주의 |
| rap3-hugo | 5건 | 1,096개 (충분) | 정상 |
| rap4-hugo | 5건 | 1,351개 (충분) | 정상 |
| rap5-hugo | 5건 | 221개 (44일분) | 정상 |

---

## 7. 향후 과제 (90점 달성)

완료된 항목:
- [x] 오염 키워드 정리 (~476개)
- [x] blog_target 필터 추가
- [x] rap2 subscription 들여쓰기 버그 수정
- [x] rap3/rap5 개념어 키워드 비활성화
- [x] rap5 draft 7개 삭제
- [x] M1 wrangler 배포 설정

잔여 과제:
- [ ] 네이버지도 삽입률 개선 (현재 14~47% → 목표 60%+)
- [ ] 중복 발행 방지 로직 강화
- [ ] 썸네일 자동생성 품질 개선
- [ ] rap2-hugo 키워드 보충 (170개, 약 34일분)
- [ ] LaTeX 수식 잔존 문제 해결 (rap5 -5점)
- [ ] 기존 발행 글 네이버지도 소급 삽입

---

## 8. Git 커밋 이력 (v4.0)

- `feat: 키워드 소스 공공데이터 단일화 — gap.db 의존성 완전 제거`
- `fix: _pick_keyword에 blog_target 필터 추가 — 키워드 블로그간 혼용 차단`
- `fix: subscription 전략 들여쓰기 오류 수정 — rap2-hugo 발행 중단 원인`

---

## 9. 운영 명령어 모음

### 수동 테스트
```bash
# M1에서
cd ~/Projects/5000 && source .venv/bin/activate
python3 -c "
import sys; sys.path.insert(0, '.')
from pipelines.rap.pipeline import run
print(run({'id': 'rap-hugo', 'daily_quota': 5, 'platform': 'hugo'}))
"
```

### 키워드 동기화
```bash
# M1에서
python3 -c "
import sys; sys.path.insert(0, '.')
from pipelines.rap.rap_data_sync import sync_keywords_from_trades
import sqlite3
conn = sqlite3.connect('data/rap.db')
n = sync_keywords_from_trades(conn)
conn.commit(); conn.close()
print(f'키워드 {n}개 추가')
"
```

### 전체 배포
```bash
# M1에서
for blog in rap-hugo rap2-hugo rap3-hugo rap4-hugo rap5-hugo; do
  cd /Users/twinssn/Projects/RAP/$blog
  npx wrangler pages deploy public --project-name $blog 2>&1 | tail -2
done
```

### DB 헬스체크
```bash
sqlite3 ~/Projects/5000/data/rap.db "
SELECT blog_target, status, COUNT(*)
FROM keywords
GROUP BY blog_target, status
ORDER BY blog_target, status;"
```
