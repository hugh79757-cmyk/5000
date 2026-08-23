# SECTOR_FIX_RESULT.md

> **canary 시각**: 2026-08-19 12:06~12:07 KST
> **대상**: sector-hugo _parse_response H1/H2 fallback fix + canary

---

## 1. 커밋 SHA

| 파일 | 커밋 | 내용 |
|------|------|------|
| `STAP/pipelines/sector/writer.py` | `def7fd55` | _parse_response H1/H2 fallback + heading dedup + fallback_source 로그 |
| `STAP/tests/test_sector_parse_response.py` | `def7fd55` | 16개 회귀 테스트 (Gemini 5건, TITLE: 정상, H1, H2, H3, 중간H2, 없음, 긴 heading, 빈 응답) |
| `STAP/tests/test_sector_writer_diag.py` | `50ab77e1` | ai_generate redacted 로그 mock 테스트 6건 (이전 커밋) |
| `STAP/pipelines/sector/writer.py` (redacted log) | `b5ee63c2` | ai_generate redacted 구조화 로그 (이전 커밋) |

## 2. 테스트 결과

```
22 passed in 0.33s
```

| 테스트 | 결과 |
|--------|------|
| TITLE: 정상 경로 (출력 변경 없음) | ✅ |
| H1 fallback + 본문 제거 | ✅ |
| H2 fallback + 본문 제거 | ✅ |
| H3 not H2 (미trigger) | ✅ |
| 중간 H2 (차단) | ✅ |
| Gemini 5건 (heading 없음 → title="") | ✅ 5/5 |
| 과도하게 긴 heading (차단) | ✅ |
| 빈 응답 | ✅ |

## 3. fallback 경로

| 경로 | 조건 | 동작 |
|------|------|------|
| **TITLE: (최우선)** | `TITLE:` 마커 존재 | 기존과 동일 (변경 없음) |
| **H1 fallback** | TITLE: 없음 + 첫 비어 있지 않은 블록이 `# ` | 제목 추출 + 본문에서 제거 |
| **H2 fallback** | TITLE: + H1 없음 + 첫 `## `이 길이≤50 + 업종 키워드 포함 + 문장 아님 | 제목 추출 + 본문에서 제거 |
| **title=""** | 위 전부 해당 없음 | pipeline guard에서 no_content |

## 4. canary 결과

| 항목 | 값 |
|------|-----|
| **성공 여부** | ✅ `{"success": true}` |
| **URL** | `https://sector.techpawz.com/posts/경기순환-사이클과-섹터-로테이션의-이해/` |
| **HTTP** | **200 OK** |
| **제목** | 경기순환 사이클과 섹터 로테이션의 이해 |
| **slug** | 경기순환-사이클과-섹터-로테이션의-이해 |
| **article_id** | 3488 |
| **배포** | deployed: true |
| **템플릿 마커** | 0건 |
| **중복** | 1건 (정상) |
| **Hugo 파일** | `/Users/twinssn/Projects/STAP/sector-hugo/content/posts/경기순환-사이클과-섹터-로테이션의-이해/index.md` |

### 이번 canary에서 사용된 경로

이번 LLM 호출에서 `TITLE:` 마커가 응답에 포함되어 **기존 경로(최우선)로 성공**. H1/H2 fallback은触发되지 않음 — 안전망으로 준비됨.

## 5. rollback안

| 단계 | 조치 |
|------|------|
| 1 | `git revert def7fd55` (writer.py 원복) |
| 2 | sector-hugo status: paused |
| 3 | 스케줄러가 다음 실행에서 no_content 반환 → 기존 상태로 복귀 |

## 6. 잔존 위험

1. **Gemini 응답 형식 불일치**: H1/H2 fallback은 TITLE: 없을 때만 동작. Gemini가 본문을 바로 시작하면 title="" → no_content. **근본 해결은 프롬프트 강화 또는 모델 교체**.
2. **title_similar_exists**: 새 제목이 기존 제목과 80% 이상 유사하면 차단. 첫 canary이므로 중복 없음.
3. ** sector-hugo active 유지**: 정규 스케줄(07:28, 10:28, 13:28, 16:28, 20:28)로 복귀. 추가 실행 없음.

---

> **push·모델 우선순위 변경·다른 블로그 작업은 수행하지 않았습니다.**
