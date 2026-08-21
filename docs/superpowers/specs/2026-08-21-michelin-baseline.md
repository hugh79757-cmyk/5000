# michelin-hugo 기준선 (라이브 확정, 2026-08-21)

## M1 소스 기반 수치 폐기 선언
M1에서 측정한 소스/프런트매터 기반 수치 — wordCount 1218, aff 0, og:image 부재 — 는
**오류였다**. 라이브 렌더 바이트(/posts/{slug}/) 재측정(N1) 결과로 폐기한다.
소스 파일로 렌더 레이어 산출물(광고·어필리에이트·메타·이미지)을 판정한 것이 근본 오류.

## 라이브 기준선 (N1 15행, /posts/ prefix, curl -sL)
| slug | aff | tc | og | ads | img | r2 | author | wc(JSON-LD) |
|---|---|---|---|---|---|---|---|---|
| ensenada | 16 | NONE | Y | Y | 6 | 8 | NONE | 2066 |
| bath | 16 | NONE | Y | Y | 6 | 8 | NONE | 961 |
| charleston | 0 | NONE | Y | Y | 6 | 8 | NONE | 837 |
| phang-nga | 0 | NONE | Y | Y | 6 | 8 | NONE | 942 |
| brighton | 0 | NONE | Y | Y | 6 | 8 | NONE | 852 |
| florence | 0 | NONE | Y | Y | 7 | 9 | NONE | 1635 |
| chon-buri | 0 | NONE | Y | Y | 5 | 7 | NONE | 910 |
| kraków | 0 | NONE | Y | Y | 6 | 8 | NONE | 706 |
| paris | 0 | NONE | Y | Y | 7 | 9 | NONE | 1550 |
| biarritz | 0 | NONE | Y | Y | 1 | 3 | NONE | 908 |
| kuala-lumpur | 0 | NONE | Y | Y | 4 | 6 | NONE | 1039 |
| riga | 0 | NONE | Y | Y | 6 | 8 | NONE | 893 |
| vienna | 0 | NONE | Y | Y | 6 | 8 | NONE | 879 |
| zermatt | 0 | NONE | Y | Y | 6 | 8 | NONE | 1224 |
| jaipur | 0 | NONE | Y | Y | 4 | 6 | NONE | 947 |

## 기준선 정의 — median 아님, 하한(lower bound)
- **wordCount ≥ 706** (최솟값 kraków 706)
- **H2 ≥ 5**
- **본문 이미지 ≥ 4**
- **cover는 R2 webp** (현재 .jpg만 있음 → THUMBNAIL-01 위반, webp 변환 필요)
- **og:image 필수** (라이브 존재 확인 — 소스 프런트매터 부재와 무관)
- **twitter:card = summary_large_image 필수** (현재 NONE → 템플릿 누락, P3 수정)
- **rel=sponsored 어필리에이트 ≥ 8** (bath/ensenada만 16, 나머지 0 → P2 사망 시점 조사)
- **adsbygoogle 로더 존재** (확인됨)

## 400 문턱과의 관계
400단어 기준은 변함없이 유지된다. 위 하한(706)은 michelin이 400을 **여유 있게** 상회함을
보증하는 최소 보증선일 뿐, 400 통과 여부 자체는 개별 포스트 wordCount≥400로 판정한다.
즉 하한 706 ≫ 400 이므로 michelin은 400 기준으로 통과하되, 하한 미달 포스트는
품질 게이트(R14/R15) 대상이 된다.
