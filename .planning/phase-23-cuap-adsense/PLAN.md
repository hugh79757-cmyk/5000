# Phase 23: CUAP AdSense 광고 미노출 수정

**Objective:** 10개 CUAP 블로그의 AdSense 광고가 노출되지 않는 문제를 수정한다.

---

## Root Cause Analysis

| 문제 | 위치 | 심각도 |
|------|------|--------|
| `adsbygoogle.push({})` 호출 없음 | `layouts/_default/single.html` | 🔴 Critical — 광고 초기화 안 됨 |
| 동일 slot ID 3개 중복 | `config/_default/params.toml` | 🟡 Medium — 정책 위반 가능 |
| `mobileStickySlot` 설정 존재 | `config/_default/params.toml` | 🟡 Medium — Auto ads 충돌 |

### 근본 원인
- Blowfish 테마에 ad 초기화 JS 없음
- `single.html`의 `<ins class="adsbygoogle lazyad">` 태그는 단순 HTML
- `(adsbygoogle = window.adsbygoogle || []).push({})` 호출하는 스크립트 없음 → 광고 렌더링 안 됨

---

## Wave 1 — single.html에 AdSense 초기화 JS 추가 (10개 블로그)

**파일:** `layouts/_default/single.html` (10개 블로그 동일)

**변경:** `</article>` 앞에 AdSense 초기화 스크립트 추가

```html
{{/* AdSense manual ad init — lazyad class handling */}}
<script>
document.addEventListener('DOMContentLoaded', function() {
  var ads = document.querySelectorAll('ins.adsbygoogle');
  ads.forEach(function(ad) {
    if (ad.getAttribute('data-adsbygoogle-status') !== 'pushed') {
      try { (adsbygoogle = window.adsbygoogle || []).push({}); }
      catch (e) { console.error('AdSense push error:', e); }
    }
  });
});
</script>
```

**대상 블로그 (10개):**
1. appliance-hugo
2. baby-hugo
3. beauty-hugo
4. camping-hugo
5. fitness-hugo
6. health-hugo
7. interior-hugo
8. kitchen-hugo
9. laptop-hugo
10. pet-hugo

**검증:**
- [ ] 모든 블로그 single.html에 스크립트 존재 확인
- [ ] Hugo build 성공

---

## Wave 2 — params.toml 정리 (10개 블로그)

**파일:** `config/_default/params.toml` (10개 블로그)

**변경:**
1. `mobileStickySlot` 라인 제거 (Auto ads 충돌 방지)
2. `inArticleSlot`과 `leaderboardSlot`을 다른 값으로 분리

> **참고:** 현재 `2195212287`은 하나의 ad unit ID. Google AdSense 대시보드에서
> 별도의 in-article / leaderboard용 ad unit을 생성하고 각각의 slot ID를 입력해야 함.
> 일단은 기존 값을 유지하되 `mobileStickySlot`만 제거.

**변경 전:**
```toml
[adsense]
  clientID = "ca-pub-6677996696534146"
  inArticleSlot = "2195212287"
  leaderboardSlot = "2195212287"
  mobileStickySlot = "2195212287"
```

**변경 후:**
```toml
[adsense]
  clientID = "ca-pub-6677996696534146"
  inArticleSlot = "2195212287"
  leaderboardSlot = "2195212287"
```

**검증:**
- [ ] 모든 블로그 params.toml에서 `mobileStickySlot` 제거 확인
- [ ] Hugo build 성공

---

## Out of Scope

- Google AdSense 대시보드 설정 (도메인 승인, Auto ads 활성화 등)
- 별도 ad unit 생성 (slot ID 분리)
- Blowfish 테마 자체 수정 (upstream 영향)

---

## Execution Order

```
Wave 1 (single.html × 10) → Wave 2 (params.toml × 10) → Verify
```

---

## Post-Execution Verification

1. `grep -r "adsbygoogle" /Users/twinssn/Projects/cuap/*/layouts/_default/single.html | wc -l` → 10
2. `grep -r "mobileStickySlot" /Users/twinssn/Projects/cuap/*/config/_default/params.toml | wc -l` → 0
3. `hugo --source /Users/twinssn/Projects/cuap/pet-hugo` → build 성공
4. `python3 dispatcher.py pet-hugo` → 배포 성공 시 광고 노출 확인
