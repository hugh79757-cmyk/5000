# Phase 58 Task 1 — deploy_error 전파 경로 및 reason 전수 인벤토리

> 작성일: 2026-08-06
> 대상: 5000 repo (dispatcher.py / shared/ / pipelines/)
> 목적: Task 2 (PROBLEM_REGISTRY reason_keys) 및 검증 게이트의 완전성 기준 입력 자료
> 성격: READ-ONLY 조사 결과. 소스 코드 수정 없음.

---

## 재현 가능 grep 카운트 (검증 근거)

아래 카운트는 커밋 시점에 재현되는 값이다. Task 지시의 grep은 `reason: "` 형태지만
실제 코드는 `"reason": "` 형태이므로, 지시형 커맨드 결과 0과 실제 패턴 결과를 함께 기록한다.

| 커맨드 | 결과 |
| --- | --- |
| `grep -rn "deploy_error" --include="*.py" dispatcher.py shared/ pipelines/ scripts/ 2>/dev/null \| wc -l` | **6** |
| `grep -rn 'reason: "' dispatcher.py pipelines/curation/pipeline.py \| wc -l` (Task 지시형) | **0** (형식 불일치 — 실제 코드는 `"reason": "`) |
| `grep -rn '"reason": "' dispatcher.py pipelines/curation/pipeline.py \| wc -l` (실제 패턴) | **40** = dispatcher 17 + curation 23(코드 21 + 주석 2) |

`deploy_error` 6건 상세:

| file:line | 분류 | 역할 |
| --- | --- | --- |
| shared/publisher.py:1074 | 발생지(발신) | `result["deploy_error"] = str(e)` — Pages-CAP deploy 실패 병합 |
| dispatcher.py:694 | 소비지(수신) | `deploy_err = result.get("deploy_error")` — ledger 기록 + 텔레그램 |
| pipelines/stock/pipeline.py:263 | 소비지(수신·1차 알림) | STAP — `tg_error(blog_id, "deploy", ...)` |
| pipelines/stock/pipeline.py:264 | 소비지(수신·1차 알림) | STAP — 전송 메시지 구성 |
| pipelines/rap/pipeline.py:1242 | 소비지(수신·1차 알림) | RAP — `tg_error(blog_id, "deploy", ...)` |
| pipelines/rap/pipeline.py:1243 | 소비지(수신·1차 알림) | RAP — 전송 메시지 구성 |

`hugo_build_failed|build_failed` grep: **0건** (해당 리터럴 없음. 실패 문구는
"hugo build failed" 형식으로 소문자 표기, 섹션 B 참조).

---

## Section A — deploy_error 전파 경로 4종

결과 반영 키 분류 기준:
- **"result dict에 병합"** = 예외가 try/except에서 삼켜지고 결과 dict의 `deploy_error` 키로 반영
- **"exception 전파"** = 예외가 상위 호출자로 올라감
- **"swallow"** = 예외/실패가 처리 없이 삼켜짐 (반영 흔적 없음)

| 경로 | 결과 반영 키 | 침묵 여부 | 근거 (file:line) |
| --- | --- | --- | --- |
| **Pages-CAP** (car/senior/gap/rap/curation/travel → `shared.publisher.publish()`) | **result dict `deploy_error` 병합** (예외는 swallow, 전파 안 됨) | **이중 알림** — 1차 publisher.py:1076, 2차 dispatcher.py:697 | publisher.py:1063-1076; dispatcher.py:694-700 |
| **Pages-TAP** (tap-blogger → TAP subprocess) | TAP은 Blogger 전용(`core.blogger_publisher`)이라 Hugo deploy 경로 **없음** → `deploy_error` 키 생성 안 됨 | — (deploy 알림 없음, 실패 시 tap_* reason만) | TAP/app.py:608; dispatcher.py:449-492, 486 |
| **Workers-ETAP** (`dispatcher.py:_build_and_deploy_central`) | **exception 아님, return False만** — 그리고 호출부 dispatcher.py:692에서 **반환값 캡처 안 함 (무시)** | **침묵** — `logger.error`만, ledger 기록·텔레그램 없음 | dispatcher.py:692, 557-559, 613-615 |
| **STAP** (`pipelines/stock/pipeline.py` → subprocess) | **result dict `deploy_error` 병합** 후 JSON으로 dispatcher까지 전달 → dispatcher가 다시 소비 | **이중 알림** — 1차 stock/pipeline.py:264, 2차 dispatcher.py:697 | stock/pipeline.py:250, 263-264; dispatcher.py:352, 372, 694-700 |

보충 관찰 (조사 중 발견, 미확정):
- `dispatcher.py:530` `car-hugo`가 `WORKERS_BLOGS`에 포함됨. car/pipeline.py:304는
  `publish()` → `deploy_site()`를 실행하므로 **car-hugo는 publish() 경로와
  `_build_and_deploy_central()` 경로 양쪽에서 배포가 시도될 가능성**이 있음.
  cf_project/site_path 존재 여부와 실제 실행 순서는 이 조사로 확정하지 못함
  → "미확정 — 잔존 위험 1".

### Pages-CAP 상세 (Q1 답변 근거)

```python
# shared/publisher.py
1059:    if result.get("success"):
1060:        update_published(article_id, result.get("url", ""))
1061:        cf_project = blog_cfg.get("cf_project", "")
1062:        site_path = blog_cfg.get("site_path", "")
1063:        if cf_project and site_path:
1064:            try:
1065:                deploy_site(site_path, cf_project)
1066:                result["deployed"] = True
1067:                # 발행 품질 검증
1068:                try:
1069:                    _run_validation(site_path, slug, blog_id, title, result)
1070:                except Exception as _ve:
1071:                    logger.warning(f"[VALIDATE] 검증 실패 (무시): {_ve}")
1072:            except Exception as e:
1073:                result["deployed"] = False
1074:                result["deploy_error"] = str(e)
1075:                from shared.telegram_notifier import send_error as _tg_err
1076:                _tg_err(blog_id, "deploy", "Hugo빌드/Wrangler배포 실패: " + str(e)[:200])
```

- deploy 예외는 L1072 catch에서 **swallow됨** (상위로 전파 안 함)
- 실패는 L1074 `result["deploy_error"]`로 병합, L1073 `result["deployed"]=False`
- L1076에서 **즉시 텔레그램 1차 알림** (`send_error`, dispatcher의 `_tg_error`와 동일 함수)
- 성공 시에도 `result["deployed"]=True` 만 설정 → deploy 성공은 ledger에 별도 기록 없음

### dispatcher 소비부 (이중 알림 유발 지점)

```python
# dispatcher.py
688:    if result.get("success"):
689:        _record_ledger(blog_id)
690:        _reset_failure_count(blog_id)
691:        if blog_id in ETAP_PIPELINE_BLOGS or blog_id in WORKERS_BLOGS:
692:            _build_and_deploy_central(blog_id)     # ← 반환값 캡처 안 함 (Q2 핵심)
693:        # STAP/Hugo 배포 실패 — success=True지만 배포는 실패한 경우
694:        deploy_err = result.get("deploy_error")
695:        if deploy_err:
696:            _record_failure(blog_id, "deploy", deploy_err[:300])
697:            _tg_error(blog_id, "deploy", ...)
```

- L692 호출 후 반환값(True/False)이 **무시됨** → ETAP/Workers 배포 실패는 여기서 감지 불가
- L694-700은 result dict에 `deploy_error` 키가 있는 **Pages-CAP/STAP 결과만** 추가 처리.
  publisher.py:1076과 stock/pipeline.py:264가 이미 1차 알림을 보냈으므로 **2차 중복 알림**이 됨

---

## Section B — Hugo build failure vs wrangler failure 구분 가능성

배포 구현이 두 갈래로 존재한다. 두 갈래 모두 실패 종류를 문구로 구분 가능.

### B-1. `dispatcher.py:_build_and_deploy_central()` (ETAP/Workers 경로)

| return False 지점 | 로그 문구 | 실패 종류 |
| --- | --- | --- |
| dispatcher.py:549-550 | `[deploy] site_path 없음: {site_path}` | 환경/설정 (site_path 부재) |
| dispatcher.py:557-559 | `[deploy] Hugo 빌드 실패 {blog_id}\nSTDERR: ...` | **Hugo build** |
| dispatcher.py:576-578 | `[deploy] {blog_id} 락 대기 시간 초과 ({DEPLOY_LOCK_TIMEOUT}초)` | 직렬화 락 timeout (배포 자체 실패는 아님) |
| dispatcher.py:613-615 | `[deploy] Wrangler 배포 실패 {blog_id}\nSTDERR: ...` | **Wrangler** |
| dispatcher.py:619-621 | `logger.exception("[deploy] 예외 {blog_id}: {e}")` | 기타 예외 (미분류) |

→ **구분 가능**. Hugo(557)와 Wrangler(613)가 로그 문구로 명확히 분리됨. 단, 반환값이
호출부 L692에서 무시되므로 로그 파일을 뒤져야만 감지 가능 (자동 알림/기록 없음).

### B-2. `shared/publishers/deploy.py:_deploy_site_inner()` (Pages-CAP 경로 — publisher.py:1065에서 사용)

| raise 지점 | 예외 메시지 (deploy_error에 담김) | 실패 종류 |
| --- | --- | --- |
| deploy.py:106-107 | `Hugo build failed: see deploy.log` | **Hugo build** |
| deploy.py:18-19 | `Hugo build produced empty site: public/index.html not found` | **Hugo** 빌드 산출물 부재 |
| deploy.py:133-135 | `Wrangler deploy timed out ({_deploy_timeout}s)` | **Wrangler** timeout |
| deploy.py:167-168 | `Wrangler deploy failed: see deploy.log` | **Wrangler** |

→ **구분 가능**. `str(e)`에 포함되므로 deploy_error에서 판별 가능. `Hugo` vs `Wrangler`
프리픽스로 1차 구분되고, "empty site" 메시지로 빌드 성공-산출물 부재까지 세분화됨.
Wrangler 실패는 네트워크 오류 시 지수 백오프 2회 재시도 후 최종 실패만 raise (deploy.py:136-168).

> 주의: `shared/publisher.py` 로컬 정의(618-768)도 존재하지만, publisher.py:788에서
> `from shared.publishers.deploy import deploy_site, _deploy_site_inner`로 **재정의(override)** 됨.
> 실제 Pages-CAP 경로는 deploy.py 구현이 사용됨. (publisher.py:618 로컬 버전은 사장됨)

---

## Section C — dispatcher-exportable reason 전수 목록

### C-1. dispatcher.py 리터럴 (17건)

| reason 문자열 | 발생 위치 | 비고 |
| --- | --- | --- |
| `stap_not_found` | dispatcher.py:331 | STAP 프로젝트 경로 부재 |
| `no_result` | dispatcher.py:352 | STAP subprocess가 dict 반환 안 함 (runner 템플릿) |
| `stap_subprocess_error` | dispatcher.py:368 | STAP subprocess returncode != 0 |
| `stap_no_output` | dispatcher.py:375 | STAP JSON 출력 없음 |
| `stap_timeout` | dispatcher.py:381 | STAP 600s 타임아웃 |
| `stap_error` | dispatcher.py:384 | STAP 기타 예외 |
| `unknown_stap_blog` | dispatcher.py:434 | STAP_PIPELINE_MAP 매핑 없음 |
| `unknown_pipeline` | dispatcher.py:445 | pipeline 모듈 로드 실패 (텔레그램 전송 동반) |
| `tap_not_found` | dispatcher.py:453 | TAP 프로젝트 경로 부재 |
| `tap_subprocess_error` | dispatcher.py:479 | TAP subprocess returncode != 0 |
| `tap_timeout` | dispatcher.py:489 | TAP 600s 타임아웃 |
| `tap_error` | dispatcher.py:492 | TAP 기타 예외 |
| `duplicate_title` | dispatcher.py:659 | 발행 전 제목 중복 — **침묵 대상** (L703) |
| `no_result` | dispatcher.py:665 | 15분 cooldown |
| `no_result` | dispatcher.py:670 | daily cooldown (내일 00:00 재시작) |
| `no_result` | dispatcher.py:677 | result=None 정규화 |
| `dispatch_returned_none` | dispatcher.py:840 | main()에서 dispatch() None 반환 시 |

### C-2. dispatcher 문자열 정규화 세트 (7건) — string 반환 파이프라인(senior 등) 호환

dispatcher.py:680-681 리스트 (`result in (...)` → `{"success": False, "reason": result}`):

| reason 문자열 | 발생 위치 | 비고 |
| --- | --- | --- |
| `quota_met` | dispatcher.py:680 | **침묵 대상** (L703) |
| `fetch_error` | dispatcher.py:680 | 텔레그램 알림 대상 (L706) |
| `no_data` | dispatcher.py:680 | 텔레그램 알림 대상 (L706) |
| `write_error` | dispatcher.py:680 | — |
| `no_content` | dispatcher.py:681 | 텔레그램 알림 대상 (L706); ipo-hugo는 daily cooldown (L708) |
| `publish_error` | dispatcher.py:681 | — |
| `config_error` | dispatcher.py:681 | — |

### C-3. dispatcher 소비·분기 세트 (발생지는 아님, 알림 정책 기준)

| 세트 | 위치 | 의미 |
| --- | --- | --- |
| `("quota_met", "already_running", "duplicate_title")` | dispatcher.py:703 | **침묵** — `_record_failure`도 하지 않음 |
| `("no_result", "no_data", "fetch_error", "no_content")` | dispatcher.py:706 | 연속 실패 카운트 + 텔레그램 (L715), 임계값 시 escalation + daily cooldown (L716-719) |
| `("duplicate_slug", "duplicate_source_id")` | dispatcher.py:720 | 텔레그램 + STAP collect_all() 백그라운드 실행 |

### C-4. pipelines/curation/pipeline.py 리터럴 (21건)

| reason 문자열 | 발생 위치 | 비고 |
| --- | --- | --- |
| `title_blocked` | curation:753, 757, 1091 | 템플릿/블랙키워드 제목 차단 |
| `content_quality_gate` | curation:825, 830 | CoT 본문 차단 |
| `already_running` | curation:845 | 동시 실행 방지 — **침묵 대상** (dispatcher:703) |
| `quota_met` | curation:878 | 일일 할당 도달 — **침묵 대상** (dispatcher:703) |
| `no_keyword` | curation:885 | 사용 가능 키워드 없음 |
| `rate_limited` | curation:894 | 쿠팡 API 차단 |
| `collect_error` | curation:897 | 쿠팡 API 수집 실패 |
| `insufficient_products` | curation:924, 933 | 상품 부족 |
| `irrelevant_products` | curation:945, 969 | 재시도 후 필터 실패 |
| `low_relevance` | curation:1010, 1034 | 점수 미달 |
| `write_error` | curation:1056 | AI 글 생성 실패 |
| `language_error` | curation:1073 | 언어 검사 실패 |
| `similar_title` | curation:1109, 1128 | 유사 제목 중복 |
| `publish_error` | curation:1232 | Hugo 발행 실패 |

### C-5. curation `_record_failure` stage 문자열 (dispatcher reason과 상이한 별도 세트)

`pipelines/curation/pipeline.py:707` `_record_failure(blog_id, stage, error_msg, keyword)` —
reason이 아닌 **ledger stage 컬럼** 값으로 사용되지만, Task 2 검증에서 누락 시 혼선 가능하므로 기록:

`title_regenerate_failed`(752) / `title_blocked`(756, 1090) / `content_quality_gate`(824, 829) /
`no_keyword`(884) / `rate_limited`(893) / `collect_error`(896) / `insufficient_products`(923, 932) /
`irrelevant_products`(944, 968) / `low_relevance`(1009, 1033) / `write_error`(1055) /
`language_error`(1071) / `similar_title`(1108, 1112, 1127) / `publish_error`(1231)

### C-6. dispatcher가 reason으로 소비하는 외부 파이프라인 리터럴 (dispatcher:702 `result.get("reason")`)

`deploy` (dispatcher.py:696, publisher.py:1076, stock:264, rap:1243 — deploy_error 알림 stage) 와
`config` (dispatcher.py:649), `pipeline` (dispatcher.py:444, 266-268), `publish` (rap:1240),
`escalation` (dispatcher.py:718) 등 **stage 문자열** — reason_key와 다른 알림 stage 체계.
Task 2는 reason_key 중심이므로 이들은 별도로 관리 대상임을 명시.

---

## Section D — Open Questions 해답 및 잔존 위험

### Q1. Pages 경로에서 deploy_error는 결과 dict 병합인가, 예외 전파인가?

**답: 결과 dict에 병합됨 (exception은 swallow, 전파 안 됨).**
- 근거: shared/publisher.py:1072-1076. L1065 `deploy_site()` 호출을 L1064 try로 감싸고,
  L1072 `except Exception as e:`에서 L1073 `result["deployed"]=False`, L1074
  `result["deploy_error"] = str(e)`로 병합 후 L1076에서 즉시 텔레그램 알림.
  함수는 정상적으로 `result`를 반환하므로 호출 파이프라인(예: car:304, curation:1228,
  rap:1190, senior:270/328, stock:250, travel:340)은 deploy 실패를 예외로 받지 않음.

### Q2. Hugo build vs wrangler failure 구분 가능한가?

**답: 가능. 두 배포 구현 모두 실패 종류를 문구로 구분함.**
- ETAP/Workers (`_build_and_deploy_central`): 로그 문구 `[deploy] Hugo 빌드 실패`(557) vs
  `[deploy] Wrangler 배포 실패`(613)로 명확 분리. 단 호출부(692)에서 반환값 무시 → 로그 검색 필요.
- Pages-CAP (`shared/publishers/deploy.py`): 예외 메시지 `Hugo build failed`(107) /
  `Hugo build produced empty site`(19) / `Wrangler deploy timed out`(135) /
  `Wrangler deploy failed`(168)로 구분. deploy_error `str(e)`에 포함되어 자동 판별 가능.

### 미확정 — 잔존 위험

1. **car-hugo 이중 배포**: `car-hugo`가 WORKERS_BLOGS(dispatcher.py:530)에 있어
   `_build_and_deploy_central()`(Workers deploy)와 car/pipeline.py:304의
   `publish()` → `deploy_site()`(cf_project/site_path 존재 시) 양쪽에서 배포 시도 가능.
   cf_project/site_path 설정 존재 여부와 실행 순서는 미확인. → 복구 계획: car-hugo의
   `blogs.d` 설정에서 cf_project/site_path 키 존재를 확인하고, 존재 시 이중 배포 확정.
2. **STAP/RAP 이중 알림 실전 검증**: stock:264/rap:1243 1차 + dispatcher:697 2차 알림이
   실제로 중복 전송되는지 여부는 텔레그램 전송 로그로만 확인 가능 (이 조사로는 확정 불가).
3. **TAP 경로 deploy_error 수신 여부**: TAP app.py의 `run_publish()`는 JSON을 출력하지 않고
   (TAP/app.py:619, 646-650 return/raise), dispatcher:480-486은 stdout 마지막 라인을
   `json.loads` 시도 후 실패 시 `{"success": True}`로 대체. 따라서 TAP 결과 dict에
   deploy_error가 실려 돌아오는 경로는 사실상 없을 것으로 추정되나, TAP가 JSON을 출력하는
   다른 지점이 있는지는 미확정.

---

## 참고 — 이 문서의 커밋 범위

커밋은 `.planning/phase-58-publish-problem-telegram-alerting/DEPLOY-PATHS.md` 단일 파일만.
PLAN.md / CONTEXT.md / PLAN-CHECK.md / RESEARCH.md 는 untracked로 남겨 둠.
소스 코드는 일절 수정하지 않음.
