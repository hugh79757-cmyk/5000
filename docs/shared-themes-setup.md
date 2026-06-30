# Hugo Blowfish 테마 공유 설정

> **작성일:** 2026-06-07
> **목적:** Hugo 블로그들의 blowfish 테마를 git submodule 개별 관리에서
> 공유 폴더 단일 참조로 전환하여 디스크 용량 최적화

---

## 목차

1. [개요](#1-개요)
2. [변경 전 문제점](#2-변경-전-문제점)
3. [변경 후 아키텍처](#3-변경-후-아키텍처)
4. [적용 방법](#4-적용-방법)
5. [적용 대상 블로그](#5-적용-대상-블로그)
6. [작동 확인](#6-작동-확인)
7. [주의사항](#7-주의사항)
8. [복구 방법](#8-복구-방법)
9. [관련 파일](#9-관련-파일)

---

## 1. 개요

5000 프로젝트는 SAP, ETAP, CAP, STAP, CUAP, RAP, SEAP, TAP 등
여러 분기에 걸쳐 약 75개의 Hugo 블로그를 운영 중이다.
모든 블로그는 [Blowfish](https://github.com/nunocoracao/blowfish) 테마를 사용하며,
기존에는 각 블로그가 `git submodule`로 테마를 개별 보유했다.

**문제:** 각 submodule이 `.git/modules`에 별도 객체 저장소를 생성하여
블로그당 약 537MB의 용량을 차지, 전체 약 5.5GB가 낭비되고 있었다.

**해결:** 하나의 공유 테마 폴더를 만들어 모든 블로그가 동일 경로를 참조하도록
변경하였다. 공유 테마 1개만 유지하므로 디스크 사용량이 132MB로 줄었다.

| 항목 | 변경 전 | 변경 후 |
|------|---------|---------|
| 테마 저장 방식 | 블로그별 git submodule | 단일 공유 폴더 참조 |
| 테마 위치 | 각 블로그의 `themes/blowfish/` | `~/projects/shared-themes/blowfish/` |
| 테마 디스크 사용량 | ~537MB × 75개 ≈ 40GB | 132MB (1개) |
| `.git/modules` 사용량 | ~5.5GB | 0 |
| **총 절감** | — | **~45.4GB** |

---

## 2. 변경 전 문제점

### 2.1. 디스크 사용량 상세

각 블로그의 blowfish submodule은 다음 두 곳에 중복 저장된다:

| 저장 위치 | 설명 | 용량 |
|-----------|------|------|
| `themes/blowfish/` | 작업 트리 (워킹 디렉토리) | ~132MB |
| `.git/modules/themes/blowfish/` | git 객체 저장소 | ~405MB |
| **소계** | 블로그 1개당 | **~537MB** |

75개 블로그 기준 약 40GB의 중복 저장이 발생하며,
`.git/modules`의 git 메타데이터만 약 30GB에 달한다.

### 2.2. git submodule 관리 부담

새 블로그를 생성할 때마다 submodule 초기화 필요:

```bash
git submodule add https://github.com/nunocoracao/blowfish.git themes/blowfish
git submodule update --init --recursive
```

테마 업데이트 시 모든 블로그에서 개별적으로 pull 필요:

```bash
# 블로그마다 반복
cd ~/projects/cap/compare-hugo
git submodule update --remote themes/blowfish
cd ~/projects/cap/deal-hugo
git submodule update --remote themes/blowfish
# ... 75번 반복
```

---

## 3. 변경 후 아키텍처

### 3.1. 디렉토리 구조

```
~/projects/
├── shared-themes/               # ← 공유 테마 루트
│   └── blowfish/                #   Blowfish 테마 (유일한 복사본, 132MB)
├── cap/
│   ├── compare-hugo/
│   │   ├── hugo.yaml            #   themesDir = shared-themes 참조
│   │   └── themes/              #   (더 이상 blowfish 없음)
│   ├── deal-hugo/
│   │   └── hugo.yaml
│   └── ...
├── etap/
│   └── *-hugo/ (34개) …
├── stap/
│   └── *-hugo/ …
├── cuap/
│   └── *-hugo/ …
├── seap/
│   └── *-hugo/ …
├── tap/
│   └── *-hugo/ …
├── sap/
│   └── *-hugo/ …
└── ...
```

### 3.2. Hugo 테마 탐색 순서

Hugo는 빌드 시 다음 순서로 테마 디렉토리를 탐색한다:

1. `themesDir` 설정값 확인 (기본값: `themes`)
2. 설정된 디렉토리 내에서 `theme` 필드명과 일치하는 디렉토리 검색
3. 테마 로드

`themesDir`을 `~/projects/shared-themes`로 설정하면
Hugo가 `~/projects/shared-themes/blowfish/`를 테마로 인식한다.

---

## 4. 적용 방법

### 4.1. 공유 테마 준비

```bash
# 공유 테마 폴더 생성 및 클론
mkdir -p ~/projects/shared-themes
git clone --depth 1 https://github.com/nunocoracao/blowfish.git \
    ~/projects/shared-themes/blowfish
```

### 4.2. 블로그별 설정 파일 수정

각 블로그의 Hugo 설정 파일에 `themesDir` 한 줄을 추가한다.
설정 파일 위치는 블로그마다 다를 수 있다.

#### Case A: `config/_default/hugo.toml` (TOML)

```toml
# 기존 설정 …
baseURL = "https://example.com/"
theme = "blowfish"

# 공유 테마 참조 (한 줄 추가)
themesDir = "/Users/twinssn/projects/shared-themes"
```

#### Case B: `hugo.toml` (프로젝트 루트)

```toml
# 기존 설정 …
baseURL = "https://example.com/"
theme = "blowfish"

themesDir = "/Users/twinssn/projects/shared-themes"
```

#### Case C: `hugo.yaml` (프로젝트 루트)

```yaml
# 기존 설정 …
baseURL: "https://example.com/"
theme: "blowfish"

# 공유 테마 참조 (한 줄 추가)
themesDir: "/Users/twinssn/projects/shared-themes"
```

### 4.3. 일괄 적용 명령어 예시

모든 블로그에 themesDir을 추가하는 스크립트 예시:

```bash
# 모든 블로그의 config 파일을 찾아 themesDir 추가
# (TOML 형식)
grep -rl "^theme.*blowfish" ~/projects/{cap,etap,stap,cuap,seap,tap,rap,sap}/*/hugo.toml \
  | xargs -I{} sh -c \
    'grep -q "themesDir" "{}" || echo '\''themesDir = "/Users/twinssn/projects/shared-themes"'\'' >> "{}"'

# (YAML 형식)
grep -rl "^theme.*blowfish" ~/projects/{cap,etap,stap,cuap,seap,tap,rap,sap}/*/hugo.yaml \
  | xargs -I{} sh -c \
    'grep -q "themesDir" "{}" || echo '\''themesDir: "/Users/twinssn/projects/shared-themes"'\'' >> "{}"'
```

> **주의:** 위 명령어는 예시이며, `config/_default/` 하위 설정 파일은 별도 처리 필요.
> 적용 전 반드시 블로그 중 하나로 테스트 후 전체 적용할 것.

---

## 5. 적용 대상 블로그

다음 분기 전체 Hugo 블로그가 적용 대상이다
(블로그 수는 `~/projects/5000/config/blogs.d/*.yaml` 기준):

| 분기 | 경로 베이스 | 블로그 수 (대략) |
|------|-------------|-------------------|
| CAP | `~/projects/cap/*-hugo/` | 8 |
| ETAP | `~/projects/etap/*-hugo/` | 34 |
| STAP | `~/projects/stap/*-hugo/` | 5 |
| CUAP | `~/projects/cuap/*-hugo/` | 4 |
| SEAP | `~/projects/seap/*-hugo/` | 5 |
| TAP | `~/projects/tap/*-hugo/` | 8 |
| RAP | `~/projects/rap/*-hugo/` | 5 |
| SAP | `~/projects/sap/*-hugo/` | 5 |
| **합계** | | **약 75** |

---

## 6. 작동 확인

블로그 하나로 정상 빌드되는지 확인한다.

### 6.1. 로컬 빌드 테스트

```bash
cd ~/projects/cap/compare-hugo
hugo --gc --minify

# themesDir 미설정 시 에러:
# ERROR ... failed to resolve output format "robots" ...
# ERROR ... render: failed to render pages: ...
#
# themesDir 정상 설정 시:
#                   | KO
# -------------------+-----
#   Pages            | XX
#   Paginator pages  |  X
#   Non-page files   |  X
#   Static files     | XX
#   Processed images |  X
#   Aliases          |  X
#   Sitemaps         |  1
#   Cleaned          |  X
```

### 6.2. dispatcher.py (중앙 빌드/배포) 테스트

`dispatcher.py`의 `_build_and_deploy_central()` 함수가
블로그의 `site_path` 디렉토리에서 `hugo --gc --minify`를 실행한다.
`site_path`는 `config/blogs.d/*.yaml`에 정의되어 있다.

```bash
# dispatcher.py를 통한 단일 블로그 빌드/배포
cd ~/projects/5000
python dispatcher.py compare-hugo
```

### 6.3. wrangler 배포 테스트

```bash
cd ~/projects/cap/compare-hugo
hugo --gc --minify
npx wrangler pages deploy public \
  --project-name compare-hugo \
  --commit-dirty=true \
  --commit-message="test shared themes"
```

---

## 7. 주의사항

### 7.1. 절대경로 사용

`themesDir`에 절대경로(`/Users/twinssn/projects/shared-themes`)를 사용하므로
**이 설정은 현재 로컬 환경 전용이다.**

- 다른 개발자 환경, CI/CD, 새 맥북에서는 경로 수정 필요
- GitHub Actions 등에서는 `themesDir` 설정을 제거하거나 조건부 적용해야 함

### 7.2. 공유 테마 보호

공유 테마 폴더는 단일 장애점(Single Point of Failure)이다:

- `~/projects/shared-themes/blowfish/`가 없거나 손상되면 **모든 블로그** 빌드 실패
- 실수로 삭제/변경 시 전체 블로그에 영향
- 테마 업데이트 전 반드시 혹시 모를 상황에 대비해 git stash나 백업 권장

### 7.3. CI/CD 환경 미적용

다음 환경에서는 `themesDir` 설정이 적용되지 않아야 한다:

- GitHub Actions 워크플로우
- 기타 CI/CD 파이프라인
- 다른 개발자의 로컬 환경

CI/CD 환경에서는 git submodule이나 `hugo mod`로 테마를 설치하는 별도 설정 필요.

### 7.4. 공유 테마 업데이트

테마 업데이트는 한 번만 하면 모든 블로그에 적용된다:

```bash
cd ~/projects/shared-themes/blowfish
git pull
```

업데이트 후 1~2개 블로그로 빌드 테스트 필수.

### 7.5. 기존 submodule 정리 (선택사항)

공유 테마로 전환 후 각 블로그의 git submodule은 제거할 수 있다:

```bash
cd ~/projects/cap/compare-hugo

# .gitmodules에서 blowfish 항목 제거
git submodule deinit -f themes/blowfish
rm -rf .git/modules/themes/blowfish
rm -rf themes/blowfish
```

> submodule 해제 전 `themesDir`이 정상 적용되었는지
> `hugo --gc --minify`로 먼저 확인할 것.

---

## 8. 복구 방법

### 8.1. 공유 테마 복구

`~/projects/shared-themes/blowfish`가 없거나 손상된 경우:

```bash
git clone --depth 1 https://github.com/nunocoracao/blowfish.git \
    ~/projects/shared-themes/blowfish
```

### 8.2. 개별 블로그 submodule 복구

공유 테마 방식을 중단하고 블로그별 submodule로 되돌리려면:

```bash
cd ~/projects/cap/compare-hugo

# 1) hugo.yaml / hugo.toml에서 themesDir 줄 제거
# 2) git submodule 재설치
git submodule add https://github.com/nunocoracao/blowfish.git themes/blowfish
git submodule update --init --recursive

# 3) 빌드 테스트
hugo --gc --minify
```

---

## 9. 관련 파일

| 파일 | 설명 |
|------|------|
| `~/projects/5000/config/blogs.d/*.yaml` | 각 블로그의 `site_path`, `theme` 등 정의 |
| `~/projects/5000/dispatcher.py` | `_build_and_deploy_central()` — 중앙 빌드/배포 |
| `~/projects/5000/docs/shared-themes-setup.md` | **본 문서** |
| `~/projects/shared-themes/blowfish/` | 공유 blowfish 테마 (실제 테마 파일) |
| 각 블로그의 `hugo.toml` / `hugo.yaml` | `themesDir` 설정이 추가된 Hugo 설정 파일 |

---

### dispatcher.py 빌드 시퀀스 참고

`dispatcher.py`의 `_build_and_deploy_central(blog_id)` 함수 실행 흐름:

1. `config/blogs.d/*.yaml`에서 `blog_id`에 해당하는 엔트리 로드
2. `site_path` 추출 (예: `/Users/twinssn/projects/cap/compare-hugo`)
3. 해당 디렉토리에서 `hugo --gc --minify` 실행
4. Hugo가 `themesDir` + `theme` 설정을 읽어 공유 테마 참조
5. 빌드 성공 시 `wrangler pages deploy public` 수행
6. Cloudflare Pages에 업로드 완료
