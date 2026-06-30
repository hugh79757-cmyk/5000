# Reasonix project memory

Notes the user pinned via the `#` prompt prefix. The whole file is
loaded into the immutable system prefix every session — keep it terse.

- 🔧 kitchen-hugo Cloudflare Pages 프로젝트 생성 및 배포 복구

## 컨텍스트
- 오류: `Project not found [code: 8000007]`
- 원인: Cloudflare Pages에 `kitchen-hugo` 프로젝트가 존재하지 않음
- 경로: `/Users/twinssn/Projects/CUAP/kitchen-hugo/`

---

## TASK 0. 현재 상태 파악

```bash
# 전체 Pages 프로젝트 목록
npx wrangler pages project list

# wrangler.toml 내용 확인
cat /Users/twinssn/Projects/CUAP/kitchen-hugo/wrangler.toml

# hugo 빌드 output 디렉토리 확인
ls /Users/twinssn/Projects/CUAP/kitchen-hugo/public/ | head -5
```

---

## TASK 1. Cloudflare Pages 프로젝트 생성

```bash
npx wrangler pages project create kitchen-hugo --production-branch=main
```

성공 메시지 확인:
```
✨ Successfully created the 'kitchen-hugo' project on Cloudflare Pages!
```

---

## TASK 2. wrangler.toml 수정

`pages_build_output_dir` 필드가 없어서 경고 발생 중. 아래 내용으로 수정:

```toml
name = "kitchen-hugo"
pages_build_output_dir = "public"
```

```bash
# 현재 toml 백업 후 수정
cp /Users/twinssn/Projects/CUAP/kitchen-hugo/wrangler.toml \
   /Users/twinssn/Projects/CUAP/kitchen-hugo/wrangler.toml.bak

# pages_build_output_dir 추가 (없는 경우)
grep -q "pages_build_output_dir" /Users/twinssn/Projects/CUAP/kitchen-hugo/wrangler.toml \
  || echo 'pages_build_output_dir = "public"' \
     >> /Users/twinssn/Projects/CUAP/kitchen-hugo/wrangler.toml

cat /Users/twinssn/Projects/CUAP/kitchen-hugo/wrangler.toml
```

---

## TASK 3. 수동 배포 테스트

```bash
cd /Users/twinssn/Projects/CUAP/kitchen-hugo

# Hugo 빌드
hugo --minify

# Wrangler 배포
npx wrangler pages deploy public \
  --project-name kitchen-hugo \
  --commit-dirty=true \
  --commit-message=init
```

성공 기준:
```
✨ Deployment complete!
https://kitchen-hugo.pages.dev
```

---

## TASK 4. 커스텀 도메인 연결 확인

```bash
npx wrangler pages project list | grep kitchen-hugo
```

Cloudflare 대시보드에서 `kitchen.informationhot.kr` 커스텀 도메인이
`kitchen-hugo` 프로젝트에 연결되어 있는지 확인.
없으면:
```bash
npx wrangler pages domain add kitchen-hugo kitchen.informationhot.kr
```

---

## TASK 5. © {year} 템플릿 오류 수정

`wrangler.toml` 또는 Hugo 테마 footer 파일에서 `{year}` → `{{ now.Year }}` 로 수정:

```bash
# footer 템플릿 파일 찾기
grep -r "{year}" /Users/twinssn/Projects/CUAP/kitchen-hugo/themes/ \
                 /Users/twinssn/Projects/CUAP/kitchen-hugo/layouts/ 2>/dev/null
```

찾은 파일에서 `{year}` → `{{ now.Year }}` 로 교체 후 Hugo 재빌드.

---

## 보고 형식
1. `wrangler pages project list` 전체 출력
2. 프로젝트 생성 성공/실패 메시지
3. 수동 배포 결과 URL
4. `{year}` 오류 파일 경로 및 수정 결과
- 🔧 kitchen-hugo Cloudflare Pages 프로젝트 생성 및 배포 복구

## 컨텍스트
- 오류: `Project not found [code: 8000007]`
- 원인: Cloudflare Pages에 `kitchen-hugo` 프로젝트가 존재하지 않음
- 경로: `/Users/twinssn/Projects/CUAP/kitchen-hugo/`

---

## TASK 0. 현재 상태 파악

```bash
# 전체 Pages 프로젝트 목록
npx wrangler pages project list

# wrangler.toml 내용 확인
cat /Users/twinssn/Projects/CUAP/kitchen-hugo/wrangler.toml
- 핵심만 직접 타이핑
reasonix run "kitchen-hugo Cloudflare Pages 프로젝트가 없어서 배포 실패 중. wrangler pages project create kitchen-hugo --production-branch=main 으로 생성하고, wrangler.toml에 pages_build_output_dir = public 추가 후 배포까지 해줘. 경로는 /Users/twinssn/Projects/CUAP/kitchen-hugo/"
- 🔧 kitchen-hugo Cloudflare Pages 프로젝트 생성 및 배포 복구

## 컨텍스트
- 오류: `Project not found [code: 8000007]`
- 원인: Cloudflare Pages에 `kitchen-hugo` 프로젝트가 존재하지 않음
- 경로: `/Users/twinssn/Projects/CUAP/kitchen-hugo/`

---

## TASK 0. 현재 상태 파악

```bash
# 전체 Pages 프로젝트 목록
npx wrangler pages project list

# wrangler.toml 내용 확인
cat /Users/twinssn/Projects/CUAP/kitchen-hugo/wrangler.toml

# hugo 빌드 output 디렉토리 확인
ls /Users/twinssn/Projects/CUAP/kitchen-hugo/public/ | head -5
```

---

## TASK 1. Cloudflare Pages 프로젝트 생성

```bash
npx wrangler pages project create kitchen-hugo --production-branch=main
```

성공 메시지 확인:
```
✨ Successfully created the 'kitchen-hugo' project on Cloudflare Pages!
```

---

## TASK 2. wrangler.toml 수정

`pages_build_output_dir` 필드가 없어서 경고 발생 중. 아래 내용으로 수정:

```toml
name = "kitchen-hugo"
pages_build_output_dir = "public"
```

```bash
# 현재 toml 백업 후 수정
cp /Users/twinssn/Projects/CUAP/kitchen-hugo/wrangler.toml \
   /Users/twinssn/Projects/CUAP/kitchen-hugo/wrangler.toml.bak

# pages_build_output_dir 추가 (없는 경우)
grep -q "pages_build_output_dir" /Users/twinssn/Projects/CUAP/kitchen-hugo/wrangler.toml \
  || echo 'pages_build_output_dir = "public"' \
     >> /Users/twinssn/Projects/CUAP/kitchen-hugo/wrangler.toml

cat /Users/twinssn/Projects/CUAP/kitchen-hugo/wrangler.toml
```

---

## TASK 3. 수동 배포 테스트

```bash
cd /Users/twinssn/Projects/CUAP/kitchen-hugo

# Hugo 빌드
hugo --minify

# Wrangler 배포
npx wrangler pages deploy public \
  --project-name kitchen-hugo \
  --commit-dirty=true \
  --commit-message=init
```

성공 기준:
```
✨ Deployment complete!
https://kitchen-hugo.pages.dev
```

---

## TASK 4. 커스텀 도메인 연결 확인

```bash
npx wrangler pages project list | grep kitchen-hugo
```

Cloudflare 대시보드에서 `kitchen.informationhot.kr` 커스텀 도메인이
`kitchen-hugo` 프로젝트에 연결되어 있는지 확인.
없으면:
```bash
npx wrangler pages domain add kitchen-hugo kitchen.informationhot.kr
```

---

## TASK 5. © {year} 템플릿 오류 수정

`wrangler.toml` 또는 Hugo 테마 footer 파일에서 `{year}` → `{{ now.Year }}` 로 수정:

```bash
# footer 템플릿 파일 찾기
grep -r "{year}" /Users/twinssn/Projects/CUAP/kitchen-hugo/themes/ \
                 /Users/twinssn/Projects/CUAP/kitchen-hugo/layouts/ 2>/dev/null
```

찾은 파일에서 `{year}` → `{{ now.Year }}` 로 교체 후 Hugo 재빌드.

---

## 보고 형식
1. `wrangler pages project list` 전체 출력
2. 프로젝트 생성 성공/실패 메시지
3. 수동 배포 결과 URL
4. `{year}` 오류 파일 경로 및 수정 결과
- 🔧 kitchen-hugo Cloudflare Pages 프로젝트 생성 및 배포 복구

## 컨텍스트
- 오류: `Project not found [code: 8000007]`
- 원인: Cloudflare Pages에 `kitchen-hugo` 프로젝트가 존재하지 않음
- 경로: `/Users/twinssn/Projects/CUAP/kitchen-hugo/`

---

## TASK 0. 현재 상태 파악

```bash
# 전체 Pages 프로젝트 목록
npx wrangler pages project list

# wrangler.toml 내용 확인
cat /Users/twinssn/Projects/CUAP/kitchen-hugo/wrangler.toml

# hugo 빌드 output 디렉토리 확인
ls /Users/twinssn/Projects/CUAP/kitchen-hugo/public/ | head -5
```

---

## TASK 1. Cloudflare Pages 프로젝트 생성

```bash
npx wrangler pages project create kitchen-hugo --production-branch=main
```

성공 메시지 확인:
```
✨ Successfully created the 'kitchen-hugo' project on Cloudflare Pages!
```

---

## TASK 2. wrangler.toml 수정

`pages_build_output_dir` 필드가 없어서 경고 발생 중. 아래 내용으로 수정:

```toml
name = "kitchen-hugo"
pages_build_output_dir = "public"
```

```bash
# 현재 toml 백업 후 수정
cp /Users/twinssn/Projects/CUAP/kitchen-hugo/wrangler.toml \
   /Users/twinssn/Projects/CUAP/kitchen-hugo/wrangler.toml.bak

# pages_build_output_dir 추가 (없는 경우)
grep -q "pages_build_output_dir" /Users/twinssn/Projects/CUAP/kitchen-hugo/wrangler.toml \
  || echo 'pages_build_output_dir = "public"' \
     >> /Users/twinssn/Projects/CUAP/kitchen-hugo/wrangler.toml

cat /Users/twinssn/Projects/CUAP/kitchen-hugo/wrangler.toml
```

---

## TASK 3. 수동 배포 테스트

```bash
cd /Users/twinssn/Projects/CUAP/kitchen-hugo

# Hugo 빌드
hugo --minify

# Wrangler 배포
npx wrangler pages deploy public \
  --project-name kitchen-hugo \
  --commit-dirty=true \
  --commit-message=init
```

성공 기준:
```
✨ Deployment complete!
https://kitchen-hugo.pages.dev
```

---

## TASK 4. 커스텀 도메인 연결 확인

```bash
npx wrangler pages project list | grep kitchen-hugo
```

Cloudflare 대시보드에서 `kitchen.informationhot.kr` 커스텀 도메인이
`kitchen-hugo` 프로젝트에 연결되어 있는지 확인.
없으면:
```bash
npx wrangler pages domain add kitchen-hugo kitchen.informationhot.kr
```

---

## TASK 5. © {year} 템플릿 오류 수정

`wrangler.toml` 또는 Hugo 테마 footer 파일에서 `{year}` → `{{ now.Year }}` 로 수정:

```bash
# footer 템플릿 파일 찾기
grep -r "{year}" /Users/twinssn/Projects/CUAP/kitchen-hugo/themes/ \
                 /Users/twinssn/Projects/CUAP/kitchen-hugo/layouts/ 2>/dev/null
```

찾은 파일에서 `{year}` → `{{ now.Year }}` 로 교체 후 Hugo 재빌드.

---

## 보고 형식
1. `wrangler pages project list` 전체 출력
2. 프로젝트 생성 성공/실패 메시지
3. 수동 배포 결과 URL
4. `{year}` 오류 파일 경로 및 수정 결과
- 핵심만 직접 타이핑
reasonix run "kitchen-hugo Cloudflare Pages 프로젝트가 없어서 배포 실패 중. wrangler pages project create kitchen-hugo --production-branch=main 으로 생성하고, wrangler.toml에 pages_build_output_dir = public 추가 후 배포까지 해줘. 경로는 /Users/twinssn/Projects/CUAP/kitchen-hugo/"
- 핵심만 직접 타이핑
reasonix run "kitchen-hugo Cloudflare Pages 프로젝트가 없어서 배포 실패 중. wrangler pages project create kitchen-hugo --production-branch=main 으로 생성하고, wrangler.toml에 pages_build_output_dir = public 추가 후 배포까지 해줘. 경로는 /Users/twinssn/Projects/CUAP/kitchen-hugo/"
- 🔧 kitchen-hugo Cloudflare Pages 프로젝트 생성 및 배포 복구

## 컨텍스트
- 오류: `Project not found [code: 8000007]`
- 원인: Cloudflare Pages에 `kitchen-hugo` 프로젝트가 존재하지 않음
- 경로: `/Users/twinssn/Projects/CUAP/kitchen-hugo/`

---

## TASK 0. 현재 상태 파악

```bash
# 전체 Pages 프로젝트 목록
npx wrangler pages project list

# wrangler.toml 내용 확인
cat /Users/twinssn/Projects/CUAP/kitchen-hugo/wrangler.toml

# hugo 빌드 output 디렉토리 확인
ls /Users/twinssn/Projects/CUAP/kitchen-hugo/public/ | head -5
```

---

## TASK 1. Cloudflare Pages 프로젝트 생성

```bash
npx wrangler pages project create kitchen-hugo --production-branch=main
```

성공 메시지 확인:
```
✨ Successfully created the 'kitchen-hugo' project on Cloudflare Pages!
```

---

## TASK 2. wrangler.toml 수정

`pages_build_output_dir` 필드가 없어서 경고 발생 중. 아래 내용으로 수정:

```toml
name = "kitchen-hugo"
pages_build_output_dir = "public"
```

```bash
# 현재 toml 백업 후 수정
cp /Users/twinssn/Projects/CUAP/kitchen-hugo/wrangler.toml \
   /Users/twinssn/Projects/CUAP/kitchen-hugo/wrangler.toml.bak

# pages_build_output_dir 추가 (없는 경우)
grep -q "pages_build_output_dir" /Users/twinssn/Projects/CUAP/kitchen-hugo/wrangler.toml \
  || echo 'pages_build_output_dir = "public"' \
     >> /Users/twinssn/Projects/CUAP/kitchen-hugo/wrangler.toml

cat /Users/twinssn/Projects/CUAP/kitchen-hugo/wrangler.toml
```

---

## TASK 3. 수동 배포 테스트

```bash
cd /Users/twinssn/Projects/CUAP/kitchen-hugo

# Hugo 빌드
hugo --minify

# Wrangler 배포
npx wrangler pages deploy public \
  --project-name kitchen-hugo \
  --commit-dirty=true \
  --commit-message=init
```

성공 기준:
```
✨ Deployment complete!
https://kitchen-hugo.pages.dev
```

---

## TASK 4. 커스텀 도메인 연결 확인

```bash
npx wrangler pages project list | grep kitchen-hugo
```

Cloudflare 대시보드에서 `kitchen.informationhot.kr` 커스텀 도메인이
`kitchen-hugo` 프로젝트에 연결되어 있는지 확인.
없으면:
```bash
npx wrangler pages domain add kitchen-hugo kitchen.informationhot.kr
```

---

## TASK 5. © {year} 템플릿 오류 수정

`wrangler.toml` 또는 Hugo 테마 footer 파일에서 `{year}` → `{{ now.Year }}` 로 수정:

```bash
# footer 템플릿 파일 찾기
grep -r "{year}" /Users/twinssn/Projects/CUAP/kitchen-hugo/themes/ \
                 /Users/twinssn/Projects/CUAP/kitchen-hugo/layouts/ 2>/dev/null
```

찾은 파일에서 `{year}` → `{{ now.Year }}` 로 교체 후 Hugo 재빌드.

---

## 보고 형식
1. `wrangler pages project list` 전체 출력
2. 프로젝트 생성 성공/실패 메시지
3. 수동 배포 결과 URL
4. `{year}` 오류 파일 경로 및 수정 결과
- TASK: 5000 프로젝트 — shared/publisher.py에 한국어 humanize 단계 추가

## 작업 디렉토리
```
/Users/twinssn/Projects/5000/
```

## 목표
`shared/publisher.py`의 `publish()` 함수에서 한국어 블로그(TAP, RAP, STAP, CAP, CUAP, SEAP)에 한해
AI가 생성한 `body_md`를 자연스러운 한국어로 다듬는 **humanize 단계**를 추가한다.
영문 파이프라인(ETAP)은 건드리지 않는다.

---

## Step 1 — im-not-ai 레퍼런스 클론

```bash
cd /Users/twinssn/Projects
git clone https://github.com/epoko77-ai/im-not-ai.git
```

클론 후 아래 파일의 내용을 읽어 AI 말투 패턴 규칙을 파악한다:
```
/Users/twinssn/Projects/im-not-ai/.claude/skills/humanize-korean/references/ai-tell-taxonomy.md
/Users/twinssn/Projects/im-not-ai/.claude/skills/humanize-korean/references/rewriting-playbook.md
/Users/twinssn/Projects/im-not-ai/.claude/skills/humanize-korean/references/quick-rules.md
```

---

## Step 2 — shared/humanizer.py 신규 생성

`/Users/twinssn/Projects/5000/shared/humanizer.py`를 새로 만든다.

### 요구사항

**함수 시그니처**:
```python
def humanize_korean(body_md: str, blog_id: str, title: str = "") -> str:
    """
    한국어 AI 말투를 자연스러운 글로 변환한다.
    - 5,000자 미만: Fast 모드 (단일 호출)
    - 5,000자 이상: Fast 모드 유지 (Strict는 속도 문제로 제외)
    - 실패 시 원본 body_md 그대로 반환 (발행 중단 없음)
    - 영문 텍스트 비율 70% 이상이면 즉시 원본 반환
    """
```

**내부 구현 조건**:

1. `ai_writer.py`의 `generate()` 함수를 import해서 재사용한다 (새 API 클라이언트 만들지 말 것)

2. system_prompt는 im-not-ai의 `ai-tell-taxonomy.md`와 `rewriting-playbook.md`에서
   핵심 규칙만 압축해서 구성한다. 전체를 붙여넣지 말고 **Fast 모드 핵심 룰만** 추출한다.
   다음 카테고리를 반드시 포함한다:
   - A계열: 어미 패턴 (~ 드립니다, ~ 바랍니다, ~ 하겠습니다 남용)
   - C계열: AI 특징 (과도한 구조화, 불필요한 콜론 나열)
   - D계열: AI 어투 (~ 중요합니다, ~ 필요합니다 반복)
   - F계열: 번역투 (~ 을/를 통해, ~ 에 대한)
   - G계열: Hedging (~ 것 같습니다, ~ 수 있습니다 남용)

3. user_prompt 구성:
```
다음 한국어 블로그 글의 AI 말투를 자연스러운 한국어로 다듬어라.

제목: {title}
블로그: {blog_id}

[원본]
{body_md}

[출력 규칙]
- 내용(사실, 수치, 링크, 마크다운 구조)은 절대 변경하지 말 것
- 마크다운 헤더(##, ###), 표, 코드블록, HTML 태그는 그대로 유지
- 어투와 문장 흐름만 자연스럽게 교체
- 원본과 동일한 길이(±10%) 유지
- 수정된 글만 출력하고 설명, 요약, 메타 텍스트 일절 금지
```

4. 예외 처리: try/except로 감싸고, 실패 시 반드시 원본 반환 + 로그 출력

5. 처리 시간 로깅:
```python
logger.info(f"[HUMANIZE] {blog_id} | {len(body_md)}자 → {len(result)}자 | {elapsed:.1f}s")
```

---

## Step 3 — shared/publisher.py 수정

`publish()` 함수 (708번 라인)에서 `article` dict 생성 **직전**에 humanize 단계를 삽입한다.

### 삽입 위치 (719번 라인 slug = slugify(title) 직후):

```python
# ✅ humanize 단계 (2026-06-12 추가) — 한국어 파이프라인 전용
_KO_PIPELINES = {"rap", "rap2", "rap3", "rap4", "rap5",
                 "travel", "travel1", "travel2", "travel3", "travel4",
                 "stock", "stock1", "stock2", "stock3", "stock4", "stock5",
                 "car", "car1", "car2", "car3", "car4", "car5",
                 "laptop", "appliance", "interior", "baby", "fitness",
                 "senior", "senior2"}
_KO_BLOG_IDS = {b + "-hugo" for b in _KO_PIPELINES} | \
               {b + "-blogger" for b in _KO_PIPELINES}

if blog_id in _KO_BLOG_IDS and body_md:
    try:
        from shared.humanizer import humanize_korean
        body_md = humanize_korean(body_md, blog_id, title)
    except Exception as _he:
        logger.warning(f"[HUMANIZE] 건너뜀 ({blog_id}): {_he}")
```

### 주의사항
- `article` dict의 `body_md` 키는 이 단계 이후 값을 사용하므로 순서가 중요하다
- 기존 tuple 타입 가드 (726, 729번 라인) 로직은 건드리지 않는다
- blogger 플랫폼도 `body_md` 기반이므로 동일하게 적용된다

---

## Step 4 — 검증

### 4-1. 단위 테스트
```bash
cd /Users/twinssn/Projects/5000
source .venv/bin/activate
python3 -c "
from shared.humanizer import humanize_korean
test = '''## 부동산 시장 분석

현재 부동산 시장은 다양한 요인으로 인해 복잡한 양상을 보이고 있습니다.
이를 통해 투자자들은 신중한 접근이 필요하다고 할 수 있습니다.
다음과 같은 사항들을 고려하는 것이 중요합니다.
'''
result = humanize_korean(test, 'rap-hugo', '2026년 부동산 전망')
print('=== 결과 ===')
print(result)
print(f'원본 {len(test)}자 → 결과 {len(result)}자')
"
```

기대 결과:
- `것이 중요합니다` `필요하다고 할 수 있습니다` `이를 통해` 등이 자연스럽게 교체됨
- 마크다운 구조(`##`) 유지됨
- 길이 ±10% 유지

### 4-2. 실제 파이프라인 dry-run (발행 없이 humanize만 확인)
```bash
python3 -c "
import sys; sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv()
from shared.humanizer import humanize_korean

# rap.db에서 최근 발행된 글 하나 가져와서 테스트
import sqlite3
conn = sqlite3.connect('data/rap.db')
row = conn.execute('SELECT title, body_md FROM articles ORDER BY id DESC LIMIT 1').fetchone()
conn.close()

if row:
    title, body = row
    print(f'테스트 글: {title[:30]}...')
    result = humanize_korean(body, 'rap-hugo', title)
    print(f'원본 {len(body)}자 → 결과 {len(result)}자')
else:
    print('테스트 데이터 없음')
"
```

### 4-3. 처리 시간 확인
- Fast 모드 기준 **30초 이내** 완료 확인
- 30초 초과 시 `ai_writer.py`의 `tier="economy"` 로 fallback 하도록 humanizer.py 수정

---

## Step 5 — 설정 파일 추가 (선택적 ON/OFF)

`/Users/twinssn/Projects/5000/config/blogs.d/` 아래 각 블로그 yaml에
`humanize: true` 필드를 추가하는 방식 **대신**,
`publisher.py`의 `_KO_BLOG_IDS` 집합으로 중앙 관리한다.
(yaml 수정 없이 코드 한 곳만 관리하는 것이 유지보수에 유리)

특정 블로그를 임시 제외하려면 `_KO_BLOG_IDS`에서 제거한다.

---

## 완료 조건

- [ ] `shared/humanizer.py` 생성됨
- [ ] `shared/publisher.py` humanize 단계 삽입됨
- [ ] 단위 테스트 통과 (AI 말투 패턴 1개 이상 교체 확인)
- [ ] 실제 DB 데이터로 dry-run 완료
- [ ] 처리 시간 30초 이내
- [ ] 실패 시 원본 반환 동작 확인 (OPENAI_API_KEY 임시 무효화 테스트)

---

## 금지사항

- ETAP 파이프라인(`*-hugo` 중 영문 블로그) humanize 적용 금지
- `body_html` 필드 수정 금지 (Blogger용 HTML은 건드리지 않음)
- 기존 tuple 타입 가드 코드 삭제/수정 금지
- `daily_quota` 체크 로직 위치 변경 금지
- TASK: SAP 프로젝트 — shared/publisher.py에 한국어 humanize 단계 추가

## 작업 디렉토리
```
/Users/twinssn/Projects/SAP/
```

## 사전 조건 확인
im-not-ai 레퍼런스가 이미 클론되어 있다:
```
/Users/twinssn/Projects/im-not-ai/
```
아래 파일을 읽어 AI 말투 패턴 규칙을 파악한다:
```
/Users/twinssn/Projects/im-not-ai/.claude/skills/humanize-korean/references/ai-tell-taxonomy.md
/Users/twinssn/Projects/im-not-ai/.claude/skills/humanize-korean/references/rewriting-playbook.md
/Users/twinssn/Projects/im-not-ai/.claude/skills/humanize-korean/references/quick-rules.md
```

---

## Step 1 — SAP 전용 writers/humanizer.py 신규 생성

`/Users/twinssn/Projects/SAP/writers/humanizer.py`를 새로 만든다.

### 중요: 5000 프로젝트의 humanizer.py를 참고하되 SAP 구조에 맞게 재작성한다
```
/Users/twinssn/Projects/5000/shared/humanizer.py
```
로직과 system_prompt는 동일하게 유지하되, AI 호출 방식만 SAP 방식으로 교체한다.

### 함수 시그니처
```python
def humanize_korean(body_md: str, blog_id: str, title: str = "") -> str:
    """
    한국어 AI 말투를 자연스러운 글로 변환한다.
    - 실패 시 원본 body_md 그대로 반환 (발행 중단 없음)
    - 영문 텍스트 비율 70% 이상이면 즉시 원본 반환
    """
```

### SAP AI 호출 방식 (5000과 다름 — 반드시 이 방식 사용)
```python
# writers/ai_writer.py의 generate_article() 재사용
from writers.ai_writer import generate_article

result = generate_article(system_prompt, user_prompt)
```
`generate_article(system_prompt, user_prompt)` 시그니처 그대로 사용한다.
tier 파라미터 없음 — SAP는 단일 클라이언트 구조이므로 그대로 호출한다.

### system_prompt 구성 조건
im-not-ai `quick-rules.md`에서 Fast 모드 핵심 룰만 압축 추출:
- A계열: 어미 패턴 (`~드립니다`, `~바랍니다`, `~하겠습니다` 남용)
- C계열: AI 특징 (불필요한 콜론 나열, 과도한 구조화)
- D계열: AI 어투 (`~중요합니다`, `~필요합니다` 반복)
- F계열: 번역투 (`~을/를 통해`, `~에 대한` 남용)
- G계열: Hedging (`~것 같습니다`, `~수 있습니다` 남용)

**SAP 특화 추가 규칙** (스포츠 도메인 특성):
```
- 선수명, 팀명, 경기 수치(타율, 승률, 순위 등)는 절대 변경 금지
- 표(마크다운 테이블) 구조와 수치는 절대 변경 금지
- KBO/축구/프로토 전문 용어는 그대로 유지
```

### user_prompt 구성
```
다음 한국어 스포츠 블로그 글의 AI 말투를 자연스러운 한국어로 다듬어라.

제목: {title}
블로그: {blog_id}

[원본]
{body_md}

[출력 규칙]
- 선수명·팀명·경기 수치·순위는 절대 변경하지 말 것
- 마크다운 헤더(##, ###), 표, 코드블록은 그대로 유지
- 어투와 문장 흐름만 자연스럽게 교체
- 원본과 동일한 길이(±10%) 유지
- 수정된 글만 출력하고 설명, 요약, 메타 텍스트 일절 금지
```

### 예외 처리 및 로깅
```python
import logging, time
logger = logging.getLogger(__name__)

# 처리 시간 로깅
logger.info(f"[HUMANIZE] {blog_id} | {len(body_md)}자 → {len(result)}자 | {elapsed:.1f}s")

# 실패 시 원본 반환
except Exception as e:
    logger.warning(f"[HUMANIZE] 실패, 원본 반환 ({blog_id}): {e}")
    return body_md
```

### 길이 검증
```python
ratio = len(result) / len(body_md)
if not (0.85 <= ratio <= 1.15):
    logger.warning(f"[HUMANIZE] 길이 이상 ({ratio:.2f}), 원본 반환")
    return body_md
```

---

## Step 2 — shared/publisher.py 수정

`publish()` 함수 (155번 라인)에서
`slug = slugify(title)` **직후**에 humanize 단계를 삽입한다.

### 삽입 위치 (176번 라인 직후)
```python
slug = slugify(title)

# ✅ humanize 단계 (2026-06-12 추가) — 한국어 스포츠 블로그 전용
# SAP는 전 블로그가 한국어이므로 blog_id 필터 없이 전체 적용
if body_md:
    try:
        from writers.humanizer import humanize_korean
        body_md = humanize_korean(body_md, blog_id, title)
    except Exception as _he:
        logger.warning(f"[HUMANIZE] 건너뜀 ({blog_id}): {_he}")

filepath = _write_hugo_post(   # ← 기존 코드 (178번 라인)
```

### 주의사항
- SAP는 전 블로그가 한국어이므로 `_KO_BLOG_IDS` 필터 불필요
- `_write_hugo_post()` 호출 전에 `body_md`가 교체되므로 순서가 중요
- `sanitize_markdown()`, `_clean_body()` 등 기존 후처리는 건드리지 않음
- `SITE_MAP` dict 변경 금지

---

## Step 3 — 검증

### 3-1. 단위 테스트
```bash
cd /Users/twinssn/Projects/SAP
source venv/bin/activate
python3 -c "
import sys; sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv()
from writers.humanizer import humanize_korean

test = '''## KBO 타격 순위 분석

현재 시즌 타격 순위는 다양한 요인으로 인해 흥미로운 양상을 보이고 있습니다.
이를 통해 팬들은 선수들의 활약을 더욱 주목하게 될 것이라고 할 수 있습니다.
다음과 같은 사항들을 참고하는 것이 중요합니다.

| 순위 | 선수 | 팀 | 타율 |
|---|---|---|---|
| 1 | 홍길동 | KIA | .385 |
| 2 | 김철수 | LG | .371 |
'''
result = humanize_korean(test, 'kboplayer-hugo', '2026 KBO 타격 순위')
print('=== 결과 ===')
print(result)
print(f'원본 {len(test)}자 → 결과 {len(result)}자')
"
```

기대 결과:
- `것이 중요합니다` `이를 통해` `~할 수 있습니다` 등 AI 어투 교체됨
- 표 수치(`홍길동`, `.385` 등) 절대 변경되지 않음
- 마크다운 표 구조 유지됨

### 3-2. 실제 DB dry-run
```bash
python3 -c "
import sys; sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv()
from writers.humanizer import humanize_korean
import sqlite3

conn = sqlite3.connect('data/publish_log.db')
row = conn.execute(
    'SELECT blog_id, title, body_md FROM publish_log ORDER BY id DESC LIMIT 1'
).fetchone()
conn.close()

if row:
    blog_id, title, body = row
    if body:
        print(f'테스트: [{blog_id}] {title[:30]}...')
        result = humanize_korean(body, blog_id, title)
        print(f'원본 {len(body)}자 → 결과 {len(result)}자')
    else:
        print('body_md 없음 — sap.db 시도')
else:
    print('데이터 없음')
"
```

### 3-3. 처리 시간 확인
- **30초 이내** 완료 확인
- 30초 초과 시 `generate_article()` 호출에 `timeout` 파라미터 추가 검토

---

## 완료 조건

- [ ] `writers/humanizer.py` 생성됨
- [ ] `shared/publisher.py` humanize 단계 삽입됨 (176번 라인 직후)
- [ ] 단위 테스트 통과 (AI 말투 1개 이상 교체 + 표 수치 보존 확인)
- [ ] 실제 DB dry-run 완료
- [ ] 처리 시간 30초 이내
- [ ] 실패 시 원본 반환 동작 확인

---

## 금지사항

- `SITE_MAP` dict 수정 금지
- `sanitize_markdown()`, `_clean_body()` 수정 금지
- `_write_hugo_post()`, `deploy_site()` 수정 금지
- `writers/ai_writer.py` 수정 금지 — import해서 재사용만 할 것
- 5000 프로젝트 파일 수정 금지 (`/Users/twinssn/Projects/5000/`)
