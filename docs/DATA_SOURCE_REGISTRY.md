# ETAP 데이터 소스 레지스트리 (초안)

> 생성: 2026-08-23 · 근거: /tmp/etap_family_api_mapping.md + /tmp/table_origin_trace.md + /tmp/archive_recovery_feasibility.md
> DB 단일 위치: `data/travel-en.db`

| 테이블 | 원본 출처 | 수급 방법 | 최종갱신일 | 갱신주기 | 담당 |
|--------|-----------|-----------|------------|----------|------|
| omio_routes (18,349행) | Omio CSV.gz 피드(로컬 파일, data/Archive/) | collectors/omio.py 파싱 — **원본 디렉 소실, 복원 불가(git 미커밋)** | UNKNOWN(타임스탬프 컬럼 부재) | 매일 05:00 실행(실행돼도 신규 0) | 미지정 |
| airalo_esim (1,198행) | Airalo Google Shopping XML(이메일 수령) | collectors/airalo.py — **원본 XML 소실** → 피드 URL 재요청 필요(Airalo 파트넷 메일/Merchant Center) | 2026-04-05 23:34 (단발) | 중단 상태 | 미지정 |
| visa_requirements (39,601행) | UNKNOWN — repo 밖 수동 벌크 임포트 추정(passport-index류 공개 CSV) | collector 모듈 **존재한 적 없음** → 공개 CSV 신규 collector 빌드 권고 | UNKNOWN(199×199 행렬, 타임스탬프 없음) | 없음 | 미지정 |
| michelin_restaurants (18,843행) | 추정: Michelin Guide 공개 데이터셋(Kaggle) | 로더 전무 — Kaggle 재다운로드 로더 스크립트 필요(~40행) | UNKNOWN | 없음 | 미지정 |
| city_aliases (460행) | UNKNOWN — 소규모 수작업 큐레이션 추정(23행 삭제 흔적 미규명) | 로더 전무 | UNKNOWN | 없음 | 미지정 |
| viator_destinations (3,379행) | 추정: Viator destinations 피드(호출 코드 소실) | 로더 전무 — 구조 일치 확인됨 | UNKNOWN(재적재 반복 흔적) | 없음 | 미지정 |
| viator_tours 등 F1/F2/F4 | Travelpayouts deals feed | collectors/viator.py (TRAVELPAYOUTS_API_TOKEN) | 활성 | 매일 05:00 | 미지정 |
| flight/deals 가격 | Aviasales /v2/prices/latest | collectors/aviasales.py (TRAVELPAYOUTS_API_TOKEN) | 활성 | 매일 05:00 | 미지정 |
| airlines/airports reference | Travelpayouts reference (무인증) | collectors/reference.py | 활성 | 매일 05:00 | 미지정 |
| ~~viator_destinations via viator_api~~ | api.viator.com (VIATOR_PID/KEY) | **collectors/viator_api.py 삭제됨(2026-08-23)** — 미사용 코드, 유일 호출부 run_collectors.sh는 04-28 삭제됐었음 | — | — | — |

## 주석
- 타임스탬프 컬럼이 없어 최종갱신일 절대값은 [검증불가]. 백업 DB(travel-en.db.bak_20260812~14) 카운트 비교로 하한 추정만 가능.
- Time Machine 탐색은 볼륨 미마운트(/Volumes/=Macintosh HD만)로 2026-08-23 SKIP — 마운트 시 재시도 목록: data/Archive/, data/Airalo-Product-Catalog*.xml
