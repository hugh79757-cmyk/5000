# PLAN: CUAP 키워드 정리 + 임계값 완충 → kitchen/beauty 재활성화

## 목표
kitchen-hugo, beauty-hugo의 write_error 반복 근본 원인(비주제 키워드 풀 오염)을 제거하고, 임계값 알림 로직을 완충하여 안정적으로 재활성화한다.

## 전제 (이미 확정)
- write_error 반복의 근본원인 = 비주제 키워드 풀 오염
- 임계값 알림은 write_error 연속 3회로 발동
- 기존 제출된 완충 수정(3)은 maybe_alert 임계값과 이중검사라 폐기
- already_running은 Dead Code (카운터 미도달)
- kitchen 134개, beauty 172개 비주제 키워드 식별됨

---

## 1단계: 확인 + 수정안 (읽기 전용 + diff 초안, 배포 금지)

### A. 키워드 풀 정리

#### kitchen-hugo 비주제 키워드 (70+건)

**핵심 키워드 (838-900):** 정상 — 주방용품 관련
**확장 키워드 (901-924):** 중국어/혼합어 다수 — 전부 비주제

| 키워드 | 비주제 사유 |
|--------|------------|
| 쌀씻이 통推荐 | 중국어 (推荐=추천) |
| 밥숟가락 세트推荐 | 중국어 |
| 국자 세트推荐 | 중국어 |
| 뒙집개 세트推荐 | 중국어 |
| 도마 플라스틱推荐 | 중국어 |
| 도마 나무推荐 | 중국어 |
| 도마 유리推荐 | 중국어 |
| 도마 대리석推荐 | 중국어 |
| 칼 집게推荐 | 중국어 |
| 식칼 세트推荐 | 중국어 |
| 和三德칼推荐 | 중국어 |
| 薄刃推荐 | 중국어 |
| Butcher knife推荐 | 혼합어 |
| 生鱼片刀推荐 | 중국어 |
| 과일칼推荐 | 중국어 |
| 과일 칼날推荐 | 중국어 |
| 그릇 세트推荐 | 중국어 |
| 밥그릇 세트推荐 | 중국어 |
| 국그릇 세트推荐 | 중국어 |
| 반찬그릇 세트推荐 | 중국어 |
| 접시 세트推荐 | 중국어 |
| 평plate 推荐 | 혼합어 |
| 深皿推荐 | 중국어 |
| sal plate推荐 | 혼합어 |
| كأس 세트推荐 | 아랍어/혼합어 |
| 텀블러保温杯推荐 | 중국어 |
| 보온壶推荐 | 중국어 |
| 冷水壶推荐 | 중국어 |
| 도시락통推荐 | 중국어 |
| 팬케이크 pan推荐 | 혼합어 |
| 계란말이 pan推荐 | 혼합어 |
| 杨枝烤肉推荐 | 중국어 |
| 鱼片烤盘推荐 | 중국어 |
| 芝士火锅推荐 | 중국어 |
| 뚝심火锅推荐 | 중국어 |
| جبنة火锅推荐 | 아랍어/중국어 |
| 철판通过网络预约 | 중국어 |
| 냉면 그릇推荐 | 혼합어 |
| 짬뽕 그릇推荐 | 혼합어 |
| 우동 그릇推荐 | 혼합어 |
| japan udon bowl推荐 | 혼합어 |
| 국수 그릇推荐 | 혼합어 |
| 접시 건조 rack推荐 | 혼합어 |
| 행주 걸이推荐 | 혼합어 |
| Kitchen towel holder推荐 | 혼합어 |
| 주방整顿用品推荐 | 중국어 |
| 调料瓶推荐 | 중국어 |
| 调味罐推荐 | 중국어 |
| 保鲜盒推荐 | 중국어 |
| 真空保鲜盒推荐 | 중국어 |
| 冰箱保鲜盒推荐 | 중국어 |
| 冷冻保鲜盒推荐 | 중국어 |
| 食品收纳盒推荐 | 중국어 |
| 밥 보관 용기推荐 | 혼합어 |
| lunch container推荐 | 혼합어 |
| meal prep container推荐 | 혼합어 |
| 오븐용 그릇推荐 | 혼합어 |
| 파이 틀推荐 | 혼합어 |
| 마카롱 틀推荐 | 혼합어 |
| 쿠키 틀推荐 | 혼합어 |
| 케이크 틀推荐 | 혼합어 |
| wine bottle rack推荐 | 혼합어 |
| 주방 발매트推荐 | 혼합어 |
| 주방rug推荐 | 혼합어 |
| 러그推荐 | 혼합어 |

** kitchen-hugo 핵심 키워드 (838-900):** 62개 — 정상 유지
** kitchen-hugo 확장 키워드 (901-924):** 86개 중 ~70개 비주제 → 제거 대상

#### beauty-hugo 비주제 키워드 (40+건)

**핵심 키워드 (925-966):** 일부 비주제 혼재
**확장 키워드 (967-1009):** 중국어/혼합어 다수 — 전부 비주제

| 키워드 | 비주제 사유 |
|--------|------------|
| 가성비 | 너무 일반적 (가성비) |
| 개월 | 제품 아님 (개월) |
| 개입 | 뷰티 아님 (개입) |
| 고농축 | 너무 일반적 (고농축) |
| 고함량 | 너무 일반적 (고함량) |
| 나노 | 뷰티 특정 아님 (나노) |
| 나이트 | 너무 일반적 (나이트) |
| 다이소 | 상점명, 제품 아님 |
| 단독 | 제품 아님 (단독) |
| 더블 | 제품 아님 (더블) |
| 듀얼 | 제품 아님 (듀얼) |
| 드롭 | 너무 일반적 (드롭) |
| 등급 | 제품 아님 (등급) |
| 리얼 | 너무 일반적 (리얼) |
| 리커버리 | 뷰티 아님 (회복) |
| 리터 | 단위, 제품 아님 (리터) |
| 리퍼 | 뷰티 아님 (리퍼) |
| 리포좀 | 너무 기술적 (리포좀) |
| 고분자 | 너무 기술적 (고분자) |
| 각질제거제 추천 | 정상 |
| 各질필링 추천 | 중국어 |
| Enzyme 피링推荐 | 혼합어 |
| 물리적 필링 추천 | 정상 |
| 보습 로션 추천 | 정상 |
| 보습 크림 추천 | 정상 |
| 보습 에센스 추천 | 정상 |
| 보습 토너 추천 | 정상 |
| 화장수 추천 | 정상 |
| 토너 추천 | 정상 (중복) |
| 앰플 추천 | 정상 (중복) |
| 세럼推荐 | 중국어 |
| 에센스推荐 | 중국어 |
| 토니크 추천 | 정상 |
| 컨디셔너 추천 | 정상 |
| 스킨케어 추천 | 정상 |
| 基础护肤品推荐 | 중국어 |
| 오일 클렌저 추천 | 정상 |
| 워터 클렌저 추천 | 정상 |
| 폼 클렌저 추천 | 정상 |
| 잘믿 클렌저 추천 | 오타/비주제 |
| 마이크로더마 브러시 추천 | 정상 |
| 클렌징 티슈 추천 | 정상 |
| 클렌징 밤 추천 | 정상 |
| 무기자극 클렌저 추천 | 정상 |
| 지성피부 클렌저 추천 | 정상 |
| 건성피부 클렌저 추천 | 정상 |
| 미백 세럼 추천 | 정상 |
| 미백 크림 추천 | 정상 |
| 미백 토너 추천 | 정상 |
| 名疮印改善推荐 | 중국어 |
| 주름 방지 추천 | 정상 |
| 주름 개선 세럼 추천 | 정상 |
| 리프팅 크림 추천 | 정상 |
| 탄력 추천 | 정상 |
| 피부결 개선 추천 | 정상 |
| 모공 축소 추천 | 정상 |
| 피부 톤 개선 추천 | 정상 |
| 색소침착 추천 | 정상 |
| 눈가 주름 개선 추천 | 정상 |
| 눈가 다크서클 추천 | 정상 |
| 눈가 뽀얍 효과 추천 | 정상 |
| 입술保湿推荐 | 중국어 |
| 입술各질제거推荐 | 중국어 |
| 립 밤推荐 | 중국어 |
| 립 gloss推荐 | 혼합어 |
| 립 라이너 추천 | 정상 |
| 립 베이스 추천 | 정상 |
| 립 프로텍터 추천 | 정상 |
| 피부诊클레어 추천 | 중국어 |
| 피부类似推荐 | 중국어 |
| 的皮肤类型推荐 | 중국어 |
| 메이크업 베이스 추천 | 정상 |
| 피부霜 추천 | 중국어 |
| 下地推荐 | 중국어 |
| 프라이머 추천 | 정상 |
| 파운데이션 추천 | 정상 |
| 쿠션推荐 | 중국어 |
| BB크림推荐 | 중국어 |
| CC크림推荐 | 중국어 |
| concealer 推荐 | 혼합어 |
| 컨실러 추천 | 정상 |
| 피부 커버 추천 | 정상 |
| 마스커라 추천 | 정상 |
| 아이라이너 추천 | 정상 |
| 아이섀도推荐 | 중국어 |
| 아이브로 추천 | 정상 |
| 아이 메이크업 추천 | 정상 |
| 블러셔 추천 | 정상 |
| 하이라이터 추천 | 정상 |
| 쉐이딩推荐 | 중국어 |
| 컨투어링 추천 | 정상 |
| 프레쉬uphorbia 推荐 | 혼합어 |
| 미용실용 파우더 | 정상 |
| 세팅 파우더 추천 | 정상 |
| 하이라이팅 파우더 추천 | 정상 |
| 브론징 파우더 추천 | 정상 |
| 블러셔 파우더 추천 | 정상 |
| 네일 베이스 코트 추천 | 정상 |
| 네일 컬러 추천 | 정상 |
| 네일 아트 추천 | 정상 |
| 네일 젤 추천 | 정상 |
| 네일软화제 추천 | 중국어 |
| 큐티클 오일 추천 | 정상 |
| 네일 건조기 추천 | 정상 |
| 손톱 깎기 추천 | 정상 |
| 발톱 정리 추천 | 정상 |
| 헤어 스프레이 추천 | 정상 |
| 헤어 미스트 추천 | 정상 |
| 헤어 왁스 추천 | 정상 |
| 헤어 젤 추천 | 정상 |
| 헤어 mousse 推荐 | 혼합어 |
| 헤어 앰플 추천 | 정상 |
| 헤어 토닉 추천 | 정상 |
| 두피scalp 추천 | 혼합어 |
| 두피 마사지 추천 | 정상 |
| 샴푸 추천 | 정상 |
| 컨디셔너 추천 | 정상 (중복) |
| 트리트먼트 추천 | 정상 |
| 헤어팩 추천 | 정상 |
| 손상모발용 샴푸 추천 | 정상 |
| 지성모발용 샴푸 추천 | 정상 |
| 건성모발용 샴푸 추천 | 정상 |
| 탈모샴푸 추천 | 정상 |
| 두피CLEANSING 추천 | 혼합어 |
| 모발 탄력 추천 | 정상 |
| 고데기 추천 | 정상 |
| 헤어 straightener 추천 | 혼합어 |
| 헤어 curling推荐 | 중국어 |
| 헤어 드라이어 추천 | 정상 |
| 헤어 아이론 추천 | 정상 |
| 헤어 브러시 추천 | 정상 |
| 헤어 Comb 推荐 | 혼합어 |
| 헤어 타월推荐 | 중국어 |
| 헤어dryer推荐 | 혼합어 |
| 바디 로션 추천 | 정상 |
| 바디 크림 추천 | 정상 |
| 바디 에멀전 추천 | 정상 |
| 바디 오일 추천 | 정상 |
| 바디 스크럽 추천 | 정상 |
| 바디 미스트 추천 | 정상 |
| 바디 케어 추천 | 정상 |
| 핸드크림 추천 | 정상 |
| 핸드 로션 추천 | 정상 |
| 핸드솝 추천 | 정상 |
| 핸드마사지 추천 | 정상 |
| 칫솔recommended | 혼합어 |
| 电动칫솔recommended | 중국어 |
| 입マリオrecommended | 중국어 |
| 치아미백 recommended | 혼합어 |
| 치아사랑 recommended | 혼합어 |
| 입소품 recommended | 혼합어 |
| 면역력화장품 | 비주제 (면역력) |
| 整肌효과 추천 | 중국어 |
| 피부免疫推荐 | 중국어 |
| 여드름処理推荐 | 중국어 |
| 트러블 처럼 | 비주제 |
| 的问题肌肤推荐 | 중국어 |
| 피지控制推荐 | 중국어 |
| 모공관리 추천 | 정상 |
| 피부タイプ判定推荐 | 중국어 |
| 피부관리 추천 | 정상 |
| 피부결护理推荐 | 중국어 |

** beauty-hugo 핵심 키워드 (925-966):** 42개 중 ~19개 비주제
** beauty-hugo 확장 키워드 (967-1009):** 100+개 중 ~80개 비주제

#### 정리 방식

**방식:** `keywords.py`에서 해당 키워드 제거 (파괴적 아님 — DB 삭제 아님)
- `KEYWORD_MAP["kitchen-hugo"]`에서 중국어/혼합어 키워드 제거
- `KEYWORD_MAP["beauty-hugo"]`에서 비주제 + 중국어/혼합어 키워드 제거
- 핵심 키워드는 유지, 확장 키워드만 정리

**기대 효과:**
- kitchen-hugo: 86개 → ~16개 (확장 키워드 70개 제거)
- beauty-hugo: 172개 → ~73개 (핵심 19개 + 확장 80개 제거)

---

### B. 임계값 완충

#### 현재 동작 분석

```python
# pipeline.py:722-724
if reason not in ("quota_met", "already_running"):
    _consecutive_failures[blog_id] = _consecutive_failures.get(blog_id, 0) + 1
    _alert_checker.maybe_alert(blog_id, reason, {"keyword": result.get("keyword", "")})
```

```python
# alert_thresholds.py:93-143
def maybe_alert(self, blog_id, reason, context=None):
    config = self.get_config(blog_id)
    if not config.get("enabled", True):
        return None
    if self._in_cooldown(blog_id):  # ← 쿨다운만 확인
        return None
    # 알림 전송 (연속 횟수 확인 없음!)
    message = f"[임계값 초과] {blog_id}: {reason}"
    self._mark_alerted(blog_id)
    _tg_error(blog_id, reason, message)
    return message
```

**문제:** `maybe_alert()`는 쿨다운만 확인하고, 연속 횟수(`consecutive_failures`)를 확인하지 않음. 즉, 쿨다운(60분)만 지나면 매 실패마다 알림 발송.

#### 완충 방식 확정: (b1) 임계값 상향 + 연속 횟수 확인 추가

**수정 위치:** `shared/alert_thresholds.py` — `maybe_alert()` 내부

**diff 초안:**
```python
def maybe_alert(self, blog_id, reason, context=None):
    config = self.get_config(blog_id)
    if not config.get("enabled", True):
        return None
    
    # 연속 횟수 확인 (새로 추가)
    consecutive = context.get("consecutive_failures", 0) if context else 0
    threshold = config.get("consecutive_failures", 3)
    if consecutive < threshold:
        logger.debug(f"[alert_threshold] 연속 {consecutive}회 < 임계값 {threshold}: {blog_id}/{reason}")
        return None
    
    if self._in_cooldown(blog_id):
        remaining = (config["cooldown_minutes"] - (time.time() - self._last_alerted[blog_id]) / 60)
        logger.info(f"[alert_threshold] 쿨다운 중: {blog_id}/{reason} (남은: {remaining:.0f}분)")
        return None
    
    # 알림 전송
    message = f"[임계값 초과] {blog_id}: {reason} (연속 {consecutive}회)"
    if context:
        ctx_str = ", ".join(f"{k}={v}" for k, v in context.items())
        message += f" ({ctx_str})"
    
    self._mark_alerted(blog_id)
    
    if config.get("dry_run", False):
        logger.info(f"[alert_threshold DRY-RUN] {message}")
    else:
        from shared.telegram_notifier import send_error as _tg_error
        logger.info(f"[alert_threshold] 알림 전송: {message}")
        _tg_error(blog_id, reason, message)
    
    return message
```

**pipeline.py 수정:**
```python
# pipeline.py:722-724
if reason not in ("quota_met", "already_running"):
    _consecutive_failures[blog_id] = _consecutive_failures.get(blog_id, 0) + 1
    _alert_checker.maybe_alert(blog_id, reason, {
        "keyword": result.get("keyword", ""),
        "consecutive_failures": _consecutive_failures[blog_id]  # 전달
    })
```

**기대 효과:**
- write_error 1회: 알림 없음 (연속 1회 < 임계값 3)
- write_error 2회: 알림 없음 (연속 2회 < 임계값 3)
- write_error 3회: 알림 발송 (연속 3회 >= 임계값 3)
- write_error 후 성공: 카운터 리셋 → 다시 0부터

---

## 2단계: 배포 + 재활성화 (1단계 승인 후에만)

### C. 배포

1. `keywords.py` 키워드 정리 커밋 (별도 커밋)
2. `alert_thresholds.py` + `pipeline.py` 완충 수정 커밋 (별도 커밋)
3. push (no force)
4. 스케줄러 재시작

### D. kitchen/beauty 재활성화 (force_draft 유지)

```yaml
# config/blogs.d/cuap.yaml
- id: kitchen-hugo
  status: active
  force_draft: true
  
- id: beauty-hugo
  status: active
  force_draft: true
```

### E. 실측 (kitchen 2건 + beauty 2건, draft)

| 항목 | 검증 방법 |
|------|----------|
| a) write_error 0건 | keyword_health 테이블에서 consecutive_failures 확인 |
| b) 임계값 알림 미발동 | 텔레그램 알림 로그 확인 |
| c) 반려동물/비주제 상품 혼입 0건 | 발행된 포스트 content 확인 |
| d) 제목 안전 형식 | 옛 TOP5 포맷 0건, 1인칭·효능 단정 0건 |
| e) 전 건 draft 유지 | frontmatter `draft: true` 확인 |

### F. 판정

- a~e 전부 통과 → kitchen/beauty [정상화 통과], active 유지
- write_error/알림 재발 → 해당 블로그 inactive 복귀 + 잔여 오염 키워드 보고

---

## 산출물 (1단계)
- A: 정리 대상 목록 (70+건 kitchen, 40+건 beauty) + 방식 (keywords.py 제거)
- B: 완충 diff 초안 (maybe_alert 연속 횟수 확인 추가)

## 산출물 (2단계)
- C: 커밋 해시 + push + 스케줄러 재시작
- D: kitchen/beauty active 변경
- E: 실측표
- F: 판정 결과

## 제약
- force push 금지
- wrangler 수동 배포 금지
- fitness/laptop 활성화 금지
- 타 블로그 활성화 금지
