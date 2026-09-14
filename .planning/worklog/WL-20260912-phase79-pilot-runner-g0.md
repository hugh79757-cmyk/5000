# WL-20260912-phase79-pilot-runner-g0

> 날짜: 2026-09-12 / 연관: Phase 79 (pilot-runner-g0) / 상태: 진행중
> 상위 규약: `.planning/migration/MASTER-PLAN.md` (I1~I10)

## BUG-12 등록 못박기 (2026-09-12 사용자 승격 지시)

- **현상**: ev-hugo duplicate_source_id 6연실패 (2026-09-12 06:45~17:30, ev9_2026/tesla__3_2026). 만성 버전은 8/24 compare(bmw_ix2) 첫발, 하루 4~48건 (hotissue·compare 주범).
- **루트코스 (3층 가드 대조, file:line)**:
  1. 선택 콤보 `topic_manager.py:45-48` — (blog, car_id, post_type) 90일 ✅ post_type 스코프
  2. 발행 1번 가드 `publisher.py:828-829` — (blog, source, **prompt_id**) 90일 ✅ post_type 스코프
  3. 발행 2번 가드 `publisher.py:832` — (blog, source) **prompt_id 무시 30일 ❌ BUG-12 주범**
- **메커니즘**: post_type 리스트 블로그(ev [ev_analysis, top5_rank], hotissue 6개)에서 car_id가 다른 post_type으로 발행된 이력이 30일 가드에 걸려 차단. `content_store.py:225-227`은 prompt_id 인자 이미 지원, car pipeline은 이미 전달(pipeline.py:376) — publisher만 미전달.
- **수정 (Task 9, G1 진입 전 필수)**: `publisher.py:832` source_exists 호출에 prompt_id 인자 전달 (1줄+주석). **전 함대 회귀 테스트 조건: hotissue·ev·tco·guide 각 최소 1슬롯 정상 발행 관찰 (duplicate 0건) — 통과 전 G1 진입 금지.**
- **3층 가드 "동일 기준" 불변식**: 선택 90일 post_type · 발행 30일 post_type 스코프 · 로테이션(다양성). 수정 후 문서 1곳에 정리.
- kickstart 신규 코드 무관 (9/11 17~21시 ev 정상 5건 실증 — 실패는 9/12 post_type shuffle top5_rank 우선 픽부터).

## BUG-13 기록 (수정 안 함 — Phase 79 방해 X)

- **현상**: travel1-hugo duplicate_source_id 47건 (최근 7일 12건) — 전체 1위. travel2 9건 포함 travel 계열 공통.
- car 3층 가드와 별개 원인 — BUG-12 수정으로 해소 안 됨. G1 이관 완료 후 별도 조사 권장.

## 파괴 작업 목록 (진행 기록용 — Task 0 이후 순차 append)

| 시각 | 작업 | 사전카운트 | 백업 | 사후대조 | 보존확인 |
|------|------|-----------|------|---------|----------|
| (예정 21:15+) | tco-hugo push (dirty 295 + 미푸시 5) | tracked 272 = origin 272 | 로컬 SSOT 보존 | push 후 ls-files↔ls-tree 551 예상 | 미푸시 콘텐츠 0건 |
| (예정 21:15+) | compare-hugo push (dirty 573 + 미푸시 4) | tracked 993 = origin 993 | 로컬 SSOT 보존 | push 후 패리티 일치 | origin-only 0건 확인 (m0512 재측정) |

## 잔존 위험
- BUG-12 수정 미실행 (G1 전 필수 — Task 9 등록 완료)
- bmw_m4_2026 이미지 1장 download_fail (4장 커버로 게이트 충족, 완전 무결 아님)
- tco 후보 중 ev5_2026·benz_sl skip_no_data 이력 — 선택 시 Mac-패리티 판정 대상

## Task 0 실행 (2026-09-13 00:16~00:18, 사용자 승인 m0642)

- 사전카운트 갱신 (00:15 기준): tco dirty 298(??78+M219+D1, posts 282)+미푸시 5 / compare dirty 574(??125+M448+D1, posts 560)+미푸시 4. 21:34 tco 슬롯 성공분 신규 반영.
- 측정 교훈: git ls-tree quoting — 한글 경로가 `"`로 감싸여 `^content/posts/` 앵커 실패. `grep 'content/posts/'` 비앵커로 정정.
- tco push: origin posts 272→341 (+69 new), Mac 341=origin 341, clean. `chore(tco-hugo): Task 0 push`.
- compare push: origin posts 994→1110 (+116 new), Mac 1110=origin 1110, clean, origin-only 0건 유지.
- tco 당일(9/12) 13:36/17:33/21:34 3슬롯 전부 성공 — 콤보가드 통과·소재 건전 최신 증거 (사용자 m0642 지시 기록).
- destructive 로그: logs/destructive_2026-09-13.log (시각+12:00/00:15 이중 기준 명시).

## G-①·G-② 커밋 (00:2x)

- be7ed5db3 G-① (run_slot.py + publish.yml, jobs 래퍼·dry_run 조건식 lint 수정 포함)
- 60a53d048 → ed22a2153 G-② (scheduler 3곳 [SKIP] + dispatcher I1 진입 가드 + dry_run 표현식 강화 amend)
- 0effcfdce / d6f7fcec3 / dc85f38ba / 3a9de2c05 probe 실패 수정 4건 (아래)

## probe 5회 (00:23~01:2x, run 34708105559→34709682183)

1. #1 6s failure — peaceiris/action-hugo-setup repo 없음 → actions-hugo로 수정
2. #2 1m3s failure — cp 목적지 themes/ 부재 (depth-1 clone submodule 미초기화) → mkdir -p 추가. 수확: setup-python 3.14.7 + pip 전체 + env 25키 주입 확인 (R3 최종 실증)
3. #3 59s failure — manifest 형식 불일치 (Task 3 dict vs run_slot plain 비교) → 양식 수용. 수확: dry_run 파라미터 전개 `--dry-run` 실측 확인
4. #4 1m12s failure — R2 키 매핑 불일치 (manifest bare 키 vs STATE_FILES 경로, get은 루트에·put은 data/에서 탐색) + put_state가 빈 manifest `{}`를 R2에 덮음. → _r2_key 매핑 + 빈 manifest put 거부 가드. R2 객체 11건 무결 (bare 키 실측), manifest만 {}로 파괴 → 11객체 다운로드 md5 재생성 11/11 재앵커 (content.db 2d84a087 = #3 expect와 일치).
5. #5 success 1m44s — get 11/11 + put 10객체 + manifest 10 entries (ops.db 제외, 안 b). R2 manifest format {path,md5,size} 유지 확인.

## 잔존 위험 (Task 4~6888888 앞으로)
- probe는 dry-run — dispatcher 실발행 경로는 Task 5에서 최초 검증
- R2 객체는 Task 3 시점(9/11 14:00) 바이트 + probe dry-run put (runner가 get한 그대로 반납, 바이트 동일)
- Actions minutes 잔여 미실측 (billing API 404) — probe 1m44s/run 실측으로 역산 예정

## Task 4 플립 실행 (2026-09-13 21:45~21:55, 시나리오 A — 20:45 quota_met 스킵 확정으로 조기 개시)

- **20:45 슬롯 실측**: quota reached: 5 정시+catchup(3/3) 둘 다 `reason=quota_met` 스킵, consecutive 미집계. 17:31 마지막 발행+30분 경과 → 21:15 대기 불필요.
- **T0 소모 정합**: 오늘 tco 5/5 발행 (bmw_x6_m, renault, k9, bmw_ix1, benz_sl). dispatcher 600s 수정(371b5fe23) 반영 후 13:35/17:30 정시 슬롯 2연속 성공.
- **Step 1 최종 put**: WAL 체크포인트 전수(TRUNCATE 로그 (0,0,0)/(0,-1,-1)) → 11객체 중 10 put (ops.db 제외 — 안 b) + manifest 10 entries. R2 사후대조: 오늘 갱신 11객체 키 일치.
- **Step 2 flip 커밋**: `3fbbf7266` tco-hugo owner: mac→runner (cap.yaml 1줄+주석).
- **Step 3 push**: 10커밋 push (flip+대시보드 세션 수정분 전부), 패리티 0. destructive 로그 기록.
- **Step 4 Mac pull 불필요**: Mac 워킹카피=flip 커밋 생성 원본. 러너가 origin에서 get.
- **Step 5 가드 반대측 실측 [검증됨]**: Mac에서 `python3 dispatcher.py tco-hugo` → `[I1-GUARD] tco-hugo owner=runner vs env runner=False — 차단` + `{"success": false, "reason": "owner_mismatch"}`. 양측 대칭 가드 완결 (러너측 owner=mac 차단 (b/m0263 인용) + Mac측 owner=runner 차단).

## 다음: 내일 06:30 슬롯 [SKIP] 확인 (Mac) → Task 5 러너 실발행 (workflow_dispatch dry_run=false) → Gate G-B 5슬롯 관찰 (Task 6 cron 활성화는 G-C 승인 후)

## Task 5 러너 실발행 실행 (2026-09-13 18:05~18:12 UTC / 2026-09-14 KST, dry_run=false)

### 1차 시도 #9 (34772373825) — 발행 성공, 배포 실패: Hugo build
- 발행 OK (article_id=1, 싼타페 하이브리드, chars=3155, 품질게이트 전부 통과)
- 배포 실패: `Hugo build failed: see deploy.log`
- 근본원인: tco-hugo hugo.toml `themesDir = "/Users/twinssn/Projects/shared-themes"` Mac 절대경로. 러너에 부재. deploy.py는 로컬 테마(site/themes/blowfish) 존재 시 HUGO_THEMESDIR env 미세팅 → hugo.toml 절대경로 그대로 → 테마 로드 실패.
- 수정: `ff48d7ae9` — deploy.py: 로컬 테마 존재해도 hugo.toml themesDir이 해당 머신에 부재하면 `HUGO_THEMESDIR=site/themes` override. 단위+종단간 hugo 빌드 검증 통과.

### 2차 시도 (34773062833) — 발행 성공, 배포 실패: wrangler rc=1 (2.0s fast-fail)
- 발행 OK (마이바흐 GLS 잔존가치, chars=3396). Hugo 빌드는 수정으로 통과 — 1차 원인 해결 확인.
- 배포 실패: `Authentication error [code: 10000]` — GH Secret CLOUDFLARE_API_TOKEN(cfut_p2c... .env.common 것)이 hugh79757 계정 스코프 아님 (계정 API 실측: code 9109 Unauthorized).
- 보조 수정: `191cd1a3a` — deploy.py wrangler 실패 시 tail 6줄만 로깅하던 것을 stderr 전체 라인 로깅으로 확대 (원인 파악용).
- 수정: GH Secret CLOUDFLARE_API_TOKEN ← wrangler OAuth profile(hugh79757) 토큰(93자)으로 갱신 (PyNaCl 암호화 PUT, HTTP 204).

### 3차 시도 (34773754514) — 완전 성공 [검증됨]
- 발행 OK: "신차 Z4 10,090만원, 취등록세탁송비보험 더하면 실제 출고비용은 얼마?" (article_id=1, chars=3041, coupang=OK)
- 배포 OK: wrangler rc=0 dur=8.1s, `deployed: true, pipeline_status: SUCCESS`
- 라이브 확인: https://tco.rotcha.kr/posts/신차-z4-10090만원-취등록세탁송비보험-더하면-실제-출고비용은-얼마/ HTTP 200
- Round-trip: get_state 11/11 + put_state 11 객체 + ops.db 보존 OK

### 상태
- tco-hugo 러너 파이프라인 종단간 (R2 상태 → 발행 → Hugo 빌드 → wrangler 배포 → 라이브) 전부 검증 완료.
- 다음: Task 6 (cron 5슬롯) — G-C 게이트 승인 후 활성화. Task 7 minutes/킬스위치, Task 9 BUG-12 (G1 진입 전 필수).

## 갭A/B 긴급 수정 (2026-09-14 03:00 KST — 사용자 지시 m0467 D/F/V 시퀀스)

### 진단 확정
- **D-1 원격 car.db**: 러너 발행 4행 존재 (santafe 17:43, maybach 17:57, q8 18:04, z4 18:11 UTC). Mac→원격 put 정상 (sl 17:30 포함, 351행 = 맥 347 + 러너 4).
- **D-2 BUG-14 확정**: 원격·맥 모두 santafe 8/27행 존재 → 러너가 17일 전 발행 차량 재발행. 원인 2단: (1) dup-precheck SQL이 `-14 days` 윈도우(주석은 30일) — 8/27은 9/13 기준 17일 전이라 precheck 통과. (2) publisher 가드(source_exists)는 ARTICLES_DB=stap_content.db 조회인데 **stap_content.db가 STATE_FILES/R2에 부재(NoSuchKey)** → 러너는 빈 articles로 가드 통과. → santafe/maybach/q8 팬텀 재발행(중복). z4는 5/24 마지막 발행이라 정상 신규.
- **D-3**: run_slot put/get은 boto3+R2_ENDPOINT(원격)만 — local 함정 없음. npx wrangler CLI에 CLOUDFLARE_API_TOKEN env 함정 재확인(env -u 필수).
- **D-4**: 러너 발행 3+1건 슬러그 origin 부재 (z4/maybach/q8/santafe 전부 git ls-tree 0) — 갭A 확정.

### 수정 완료
- **F-1 갭B**: `shared/runner_state.py` STATE_FILES에 `data/stap_content.db` 추가 + 모듈 docstring 정정 (5000/data 쪽이 articles 원장 실체, 콤보가드 실소스 — 외부 ../STAP 경로만 제외).
- **F-2 갭A**: `scripts/run_slot.py` push_back_site() 추가 — dispatcher 성공 후 sites/{group}/{blog} content/posts만 commit→pull --rebase→push(CAP_PAT). nothing-to-commit 정상통과, push 실패=exit 4(G-B 러너 귀속 실패). CAP_PAT 권한 실측: tco-hugo admin/push OK. publish.yml clone depth 1→50 (rebase 안정).
- **F-3 갭A 백필**: 맥 9/13 발행 5건 origin push (baccd5f) — 346 파일(341+5) 정합 확인.
- **F-4 맥 권위 병합-재시딩**: 원격 러너 4행(publish_log 상세칼럼 포함) 맥 로컬 병합 + WAL 체크포인트 전수 + **12객체 전량 원격 put(stap 최초 포함, 129MB)** + manifest 12 entries 갱신 + **원격 get 12/12 md5 재검증 통과**. blind put 아닌 병합-재시딩 (G1 재시딩 프로토타입).
- **F-5 Z4 회수 안 함**: z4는 5/24 마지막 발행(4개월+)이라 정상 신규 발행 — 원격 origin에 push-back 예정(러너 재실행 시). santafe/maybach/q8 팬텀 재발행 — live에는 각 2개 포스트 존재하나 콘텐츠 상이(다른 제목/슬러그)로 SEO 중복도 낮음. 라이브 삭제는 사용자 판단 사항으로 남김.

### 검증 → G-B 재개 조건
- V-1: dry-run probe 재실행 — get 12/12(stap 포함) → push-back no-op → put 12+manifest.
- V-2: 통과 시 G-B 재개 — 기존 3회(귀속실패 2+상태공백 1) 카운트 리셋 후 5연속 관찰.
- V-3: Task 6 cron 금지 유지 (G-B 통과 전까지).

## Task 5 실발행 2회 — push_back 실증 + G-B 1/5 (2026-09-14 09:45~09:56 KST)

### 실행 창
- 09:45 dispatch (run 34800267076): Mac 슬롯 회피 창(car계열 전무, luxury 발행 완료 직후 큐 빈 시점)
- 09:53 dispatch (run 34800729631): 토큰 갱신 직후

### 1차 (run 34800267076) — 4종 중 3통과, 배포만 실패
- ① 발행: article 13999 "2026년 X5 구매 고민 중이라면 총비용 8336만원 시뮬레이션으로 결정하세요" (coupang=OK)
- ② 배포 실패: wrangler rc=1 2.9s — `Authentication error [code: 10000]` / `Invalid access token [code: 9109]`
- ③ push-back OK: X5 슬러그 origin/main 실재 (content/posts 347 = 346+1 정합)
- ④ round-trip 12/12 OK
- 원인: GH Secret CLOUDFLARE_API_TOKEN(wrangler OAuth 토큰, 9/13 18:41 추출)이 ~15h 만료. wrangler OAuth access token 수명 짧음 — 로컬은 refresh 자동갱신, GH Secret 정적 저장은 갱신 안 됨.
- X5 글 origin 커밋됐으나 라이브 미배포(deployed:false FAILED_TRANSIENT) — 다음 러너 실행 시 catchup 재배포 예정

### 토큰 갱신
- fresh 토큰: `env -u CLOUDFLARE_API_TOKEN wrangler auth token` → CF API /accounts 실측 유효(hugh79757)
- GH Secret PUT 422(키 로테이션) → repo public-key 재조회 → SealedBox+key_id → PUT 204

### 2차 (run 34800729631) — 4종 전부 통과 [G-B 1/5 카운트]
- ① 발행: article 14000 "마이바흐 S클래스를 사면 매달 얼마가 빠질까? 유지비 총정리 [2026년 9월]" (chars=3149, coupang=OK)
- ② 배포: wrangler rc=0 8.2s deployed:true SUCCESS
- ③ push-back OK: 마이바흐 슬러그 origin/main 실재 (content/posts 348 = 347+1 정합)
- ④ round-trip: get_state 12/12 + put_state 12 + ops.db 제외 True
- 라이브 HTTP 200 확인 (tco.rotcha.kr/posts/마이바흐-s클래스를-사면-...)
- 후보 가드: EV4/일렉트리파이드 G80/EX30/EV5/LX 연비 데이터 없음 차단 = 정상 데이터 가드

### 구조 리스크 기록 (Task 6 cron 전 해결 필요)
- wrangler OAuth 토큰 ~15h 수명 → GH Secret 정적 저장은 매일 만료. cron 전 구조 대안: (a) 매 dispatch 전 Mac에서 Secret 갱신 (b) 장수명 CF API 토큰 발급(배포 스코프 한정)
- tco 9/14 UTC 발행: 러너 2건(X5 13999 미배포, 마이바흐 14000 배포) — quota 2/5
