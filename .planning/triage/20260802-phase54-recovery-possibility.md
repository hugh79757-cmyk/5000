# 콘텐츠 복구 가능성 확인

> 확인일: 2026-08-02
> 대상: fitness-hugo, laptop-hugo 2건 (+ camping, health, kitchen, pet 4건)

## 1. 백업 파일 검증

| 파일 | 크기 | 라인 수 | MD5 해시 | draft 상태 |
|------|------|--------|----------|-----------|
| camping-hugo__잘만-cpu쿨러...index.md | 21,333B | 296 | d6089b4769940b20bd2c6c427e655012 | false (원본) |
| fitness-hugo__케틀벨-하나로...index.md | 19,053B | 276 | b9995ef675865e2d929d9a178f7f8a78 | false (원본) |
| health-hugo__뉴질랜드-초록입홍합...index.md | 20,943B | 315 | 05ba77ac909a2c48c9e7683082bab8e2 | false (원본) |
| kitchen-hugo__주방이-즐거워지는...index.md | 20,939B | 218 | 8b97e448ffb4db542ef96afbcb1affc6 | false (원본) |
| laptop-hugo__맥북-에어-m5...index.md | 20,435B | 241 | 917015a9bd3bf3b339fd5d906df45c79 | false (원본) |
| pet-hugo__파스텔펫민소매...index.md | 19,355B | 271 | 966c6c1188be33c78b9c40db16985035 | false (원본) |

**위치**: `/Users/twinssn/Projects/5000/.planning/triage/phase54-hotfix-backup/`

## 2. 현재 소스 파일 검증

| 블로그 | 현재 draft 상태 | 소스 해시 |
|--------|---------------|----------|
| camping-hugo | true | b782515a4c1a65a17d72f56e1e98b703 |
| fitness-hugo | true | 00a2b86fa0d6b4963cf66e13ad106471 |
| health-hugo | true | f1e20a529a7efd355bddd8822f86ebb4 |
| kitchen-hugo | true | 4592894e9d01e3ec07bf5c978e15d5cb |
| laptop-hugo | true | a0f27cd5a5a662d52dcc48edc985cfcf |
| pet-hugo | true | f09088663e5255a77d46f3570284a76f |

## 3. 복구 가능성 판정

| 항목 | 상태 |
|------|------|
| 백업 파일 온전성 | ✅ 6건 모두 MD5 해시 확인, 크기/라인 정상 |
| 원본 콘텐츠 보존 | ✅ 백업에 `draft: false` 원본 본문 전체 포함 |
| 소스 파일 변경 이력 | ✅ `draft: true`로 전환됨 (정상) |
| Git 커밋 | ✅ CUAP `769f3aa`에 변경사항 커밋됨 |
| 재빌드 가능성 | ✅ 백업 파일 → 소스 디렉토리 복사 → Hugo 빌드 → 배포 순서로 복구 가능 |

**결론**: 배포 삭제와 무관하게 콘텐츠 복구는 **완전 가능**. 백업 파일이 영구 경로에 온전히 보존되어 있어 언제든 정상 재빌드가 가능함.

복구 절차 (수동):
```
# 1. 백업 파일을 소스 디렉토리로 복사
cp .planning/triage/phase54-hotfix-backup/fitness-hugo__*__index.md \
   /Users/twinssn/Projects/CUAP/fitness-hugo/content/posts/케틀벨-하나로-전신을-태우는-20분-홈트-루틴/index.md

# 2. draft: true로 변경 (또는 복구 시 원본 draft: false 사용)
# 3. Hugo 빌드 + 배포
```
