# 사람 인계용 런북: 커스텀 도메인 차단

> 대상: fitness-hugo, laptop-hugo (Pages 블로그)
> 목표: 커스텀 도메인에서404 + CoT 0 확인
> 예상 소요 시간: 15~20분

## 진단 결론 (실측 근거)

**캐시 가설은 반증됨** — 캐시 버스터(`?nocache=<random>`, `Cache-Control: no-cache`) 적용 시에도 `cf-cache-status: HIT` 유지, 커스텀 도메인 vs Pages.dev 응답 해시 **서로 다름**. 커스텀 도메인이 Pages가 아닌 **다른 오리진**에서 응답.

**가장 유력한 원인**: `fitness.informationhot.kr` / `laptop.informationhot.kr`에 수동 DNS 레코드(A/CNAME)가 존재하여 Pages 커스텀 도메인 바인딩보다 우선 적용. Pages 커스텀 도메인은 별도 수동 레코드 없이 동작하므로, 잔존 레코드가 다른 오리진을 가리키는 것이 루트 원인.

## 전제 조건

- `.pages.dev` URL은 이미404 정상 (최신 배포에서 draft:true 포스트 제외됨)
- 문제: 커스텀 도메인이 수동 DNS 레코드 또는 다른 오리진을 가리킴

## 절차

### 1순위: DNS 레코드 점검 (가장 유력한 원인)

**Dashboard 경로**: Cloudflare Dashboard → informationhot.kr → DNS → Records

**확인할 레코드 2건**:

| 레코드 | 확인 항목 |
|--------|----------|
| `fitness.informationhot.kr` | Type, Target/Content, Proxy 상태 (주황색 구름 vs 회색 구름) |
| `laptop.informationhot.kr` | Type, Target/Content, Proxy 상태 |

**판정 기준**:

- 레코드가 **없으면**: Pages 커스텀 도메인 바인딩이 정상 → 2순위로
- A 레코드가 있으면: **충돌** — Pages 커스텀 도메인과 중복. 해당 레코드가 원인. **삭제 필수**
- CNAME 레코드가 있으면: 어디를 가리키는지 확인. `*.pages.dev`가 아니면 충돌 → **삭제 필수**
- **Proxy 상태가 주황색(Proxied)**이면: Cloudflare가 중간에서 응답을 캐시/수정할 수 있음

**충돌 시 조치**: 해당 DNS 레코드 삭제 → 3순위 curl 실측

### 2순위: Pages Custom Domains 제거→재추가 (DNS 정리 후에도 안 될 경우)

**Dashboard 경로**: Cloudflare Dashboard → Pages → fitness-hugo → Custom Domains

1. `fitness.informationhot.kr` **제거**
2. **30초 대기**
3. **재추가** (도메인 입력 → 확인)
4. 10분 대기 후 3순위 curl 실측

### 3순위: curl 실측

터미널에서 다음 명령어 실행:

```bash
# fitness-hugo
curl -sI "https://fitness.informationhot.kr/posts/케틀벨-하나로-전신을-태우는-20분-홈트-루틴/" | head -5
# 기대: HTTP/2 404 또는 cf-cache-status: MISS

curl -sL "https://fitness.informationhot.kr/posts/케틀벨-하나로-전신을-태우는-20분-홈트-루틴/" | grep -c "Let me"
# 기대: 0

# laptop-hugo
curl -sI "https://laptop.informationhot.kr/posts/맥북-에어-m5auusda-156인치-비교-2026년-8월-실속-선택은/" | head -5
# 기대: HTTP/2 404 또는 cf-cache-status: MISS

curl -sL "https://laptop.informationhot.kr/posts/맥북-에어-m5auusda-156인치-비교-2026년-8월-실속-선택은/" | grep -c "Let me"
# 기대: 0
```

**판정**:
- 404 + CoT 0 → ✅ 차단 완료
- 200 + CoT > 0 → ❌ 4순위로

### 4순위: 캐시 퍼지 (보조 — 실측상 캐시가 주 원인일 가능성은 낮음)

실측으로 캐시 가설은 반증되었으나, 재바인딩/DNS 정리 후 잔여 캐시 정리 차원에서 수행.

**Dashboard 경로**: Cloudflare Dashboard → informationhot.kr → Caching → Configuration

**수행**: **Purge Everything** 클릭 → 5~10분 대기 → 3순위 curl 재실측

### 5순위: 그래도 안 되면 (최후 수단)

- Cloudflare 지원팀에 문의: "Pages 프로젝트 커스텀 도메인이 이전 배포를 서빙하고 있습니다"
- 증거로 제시: `.pages.dev`는404이나 커스텀 도메인은200이라는 사실

## 체크리스트

### fitness-hugo
- [ ] DNS 레코드 확인 (`fitness.informationhot.kr`) — 충돌 레코드 삭제
- [ ] Pages Custom Domains 제거→재추가 (DNS 정리 후에도 안 될 경우)
- [ ] curl 실측 (404 + CoT 0)
- [ ] 캐시 퍼지 (보조 — 잔여 캐시 정리)

### laptop-hugo
- [ ] DNS 레코드 확인 (`laptop.informationhot.kr`) — 충돌 레코드 삭제
- [ ] Pages Custom Domains 제거→재추가 (DNS 정리 후에도 안 될 경우)
- [ ] curl 실측 (404 + CoT 0)
- [ ] 캐시 퍼지 (보조 — 잔여 캐시 정리)

### 다른 Pages 블로그도 같은 점검 필요

CUAP의 Pages 블로그 4개가 동일 커스텀 도메인 문제를 공유할 수 있음:

| 블로그 | 커스텀 도메인 | 현재 상태 | 점검 필요 |
|--------|-------------|----------|----------|
| appliance-hugo | appliance.informationhot.kr | 200 (정상 콘텐츠) | CoT 없으나 같은 Pages 문제 가능성 → 확인 권장 |
| interior-hugo | interior.informationhot.kr | 200 (정상 콘텐츠) | 동일 |
| fitness-hugo | fitness.informationhot.kr | **200 + CoT 노출** | **긴급** |
| laptop-hugo | laptop.informationhot.kr | **200 + CoT 노출** | **긴급** |

> 참고: appliance/interior는 현재 CoT가 없는 정상 콘텐츠이므로 긴급도는 낮으나, 향후 배포 시 동일 문제가 발생할 수 있으므로 점검 권장.

## 작업 규칙 재확인

이번 인시던트를 계기로 다음 규칙을 재확인:

- **삭제·배포·DNS·도메인 변경**은 예외 없이 **사전 승인 후**에만 실행
- 파괴적 작업(삭제, 도메인 재바인딩)은 **read-only 확인 후** 승인 요청
- 승인 없는 파괴적 작업은 **원칙 2 위반**으로 기록
