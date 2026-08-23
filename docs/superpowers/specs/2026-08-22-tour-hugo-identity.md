# tour-hugo 정체성 정의 및 전환 계획

생성일: 2026-08-22
상태: 진행중
결정자: 대표

## 배경
- tour-hugo는 F2 8개 블로그 중 유일하게 전용 파이프라인 없이 base fallback 사용
- tours-hugo와 동일 풀/프롬프트로 복제하면 SEO 중복 발생
- 기존 263건 포스트는 "도시 종합 여행 가이드" 스타일

## 정체성 정의
| 블로그 | 정체성 | 예시 타이틀 |
|--------|--------|------------|
| tours-hugo | 특정 투어 상품 리뷰/추천 | "5 Best Walking Tours in Rome" |
| tour-hugo | 도시 종합 여행 가이드 | "Malaga Travel Guide: What to See, Eat & Do" |

## 차별화 기준
- tour-hugo: 볼거리 + 먹거리 + 교통 + 실용 팁 중심. 투어 상품은 "추천" 섹션에서 보조 언급.
- tours-hugo: 투어 상품 자체가 주인공. 가격, 일정, 비교가 핵심.

## 토픽풀
- 신규 tour_topics 테이블 생성
- 씨앗 데이터: 기존 topics(2,279행) → dest_id→city 조인 어댑터

## 파이프라인 전환 계획
1. tour_topics 테이블 생성 + 씨앗
2. tour_writer.py 프롬프트 "도시 종합 가이드" 방향 재작성
3. 테스트 발행 1건 + F1 15항목 체크
4. 통과 시 dispatcher 예외 삭제 → 활성화

## 현재 상태
- tour_pipeline.py / tour_writer.py 생성 완료 (휴면)
- dispatcher 예외(`_ETAP_BLOG_EXCEPTIONS["tour-hugo"]`)로 기존 fallback 유지 중
- 활성화 대기

## 진행 로그
- 2026-08-22: 문서 작성. tour_topics 테이블 생성 + 씨앗, writer 프롬프트 재작성, TOPIC_TABLE 연결 완료.
- 2026-08-22: tour_topics 테이블 생성 (travel-en.db). topics 2,279행 전원 destinations 조인 성공(100%), 기발행 262 slug 제외 → 2,017행 시드.
- 2026-08-22: tour_writer.py 도시 가이드 프롬프트로 재작성. H2는 hugo_writer._ALLOWED_H2_PATTERNS 기존 패턴에 매칭되도록 설계(공유 파일 무수정) — 실측 6종 허용 확인. 부작용 발견: 비매칭 H2 강등 = 기존 "볼드 소제목 문단" 이슈의 근원으로 특정.
- 2026-08-22: tour_pipeline.py TOPIC_TABLE=tour_topics, CATEGORY=Travel Guide 변경. py_compile 통과, pick_topic_by_id 드라이런 성공(id=88 Manzanillo). 활성화는 여전히 dispatcher 예외로 보류 중.
