# Current CATEGORY_FILTERS — Documented

> Extracted from `pipeline.py` lines 174–284.

## Filter Mechanism

`_filter_irrelevant_products()` (line 305) applies two checks:
1. **Blocked check**: Does `category_name` contain any blocked word?
2. **Allowed check**: Does `product_name + " " + category_name` contain any allowed word?

If blocked → skip. If not allowed → skip. If fewer than 3 survive → revert to original products[:5].

---

## Per-Blog Filter Configuration

### laptop-hugo
| Aspect | Content |
|--------|---------|
| **Allowed** | 노트북, laptop, 랩탑, 맥북, macbook, 그램, gram, 갤럭시북, thinkpad, 씽크패드, victus, 오멘, vivobook, 비보북, zenbook, 젠북, ideapad, 아이디어패드, 크롬북, chromebook, 울트라북, 서피스 |
| **Blocked** | 도서, 교재, 필기, 실기, 기능사, 자격증, 스티커, 마우스패드, 장패드, 키보드, 마우스, 가방, 파우치, 거치대, 받침대, 쿨링패드, 모니터, 데스크탑, 태블릿, 아이패드, 갤럭시탭, 헤드셋, 이어폰, 이어버드, 스피커, 웹캠, 캡쳐보드, 캡처보드, 책상, 의자, 케이블, HDMI, USB허브, dock, 어댑터, 충전기, 보호필름, 스킨, 서류가방, 노트북가방, CrowPi, 크롤파이, 중고, 트레이딩 |
| **Missing blocks?** | "여성의류", "남성의류", "생활용품", "식품", "주방용품", "화장품" — not blocked |

### appliance-hugo
| Aspect | Content |
|--------|---------|
| **Allowed** | 청소기, 에어프라이어, 공기청정기, 제습기, 가습기, 냉장고, 세탁기, 건조기, 식기세척기, 전자레인지, 오븐, 밥솥, 정수기, 선풍기, 히터, 난방기, 로봇청소기, 스팀청소기, 물걸레, 다리미 |
| **Blocked** | 도서, 교재, 스티커, 인형, 장난감, 의류, 패션, 화장품 |
| **Missing blocks?** | "생활용품" (위생용품), "식품", "가방" — not blocked |

### interior-hugo
| Aspect | Content |
|--------|---------|
| **Allowed** | 의자, 책상, 소파, 매트리스, 침대, 선반, 수납, 커튼, 블라인드, 조명, 램프, 러그, 카페트, 테이블, 화장대, 옷장, 행거, 거울 |
| **Blocked** | 도서, 교재, 식품, 화장품, 의류, 패션, 장난감, 완구 |
| **Missing blocks?** | "생활용품", "주방용품", "전자기기", "사무용품" — not blocked |

### baby-hugo
| Aspect | Content |
|--------|---------|
| **Allowed** | 카시트, 유모차, 아기띠, 바운서, 젖병, 분유, 기저귀, 보행기, 범퍼침대, 아기침대, 수유, 이유식, 체온계, 멸균기, 신생아, 유아, 아기, 베이비, 유아용, 영아 |
| **Blocked** | 강아지, 반려견, 반려동물, 개모차, pet, 고양이, 강아지용, 도그, dog, 도서, 교재, 성인용, 장난감, 완구, 블록, 보드게임, 퍼즐, 유모차 가방, 유모차 후크, 유모차 고리, 유모차 걸이, 유모차 정리함, 유모차 양산, 유모차 액세서리, 핸들장난감, 드라이빙, 모빌 |
| **Notable gap** | **"여성의류" / "남성의류" not blocked** — adult clothing can slip through |
| **Missing blocks?** | "생활용품" (물티슈 → 생활용품/위생용품 category), "식품" |

### fitness-hugo
| Aspect | Content |
|--------|---------|
| **Allowed** | 덤벨, 아령, 바벨, 케틀벨, 런닝머신, 러닝머신, 트레드밀, 워킹머신, 실내자전거, 스핀바이크, 풀업바, 철봉, 푸쉬업바, 요가매트, 폼롤러, 헬스, 운동, 피트니스, 스텝퍼, 로잉머신, 근력, 스트레칭, 밴드, 트램폴린, 훌라후프, 줄넘기, 레깅스, 타이즈, 운동복, 스포츠브라, 요가복, 트레이닝, 런닝화, 운동화, 워킹화, 트레일러닝, 스마트워치, 스마트밴드, 가민, 핏빗, 단백질, 프로틴, 크레아틴, BCAA, 보충제, 쉐이커, 보호대, 헬스장갑, 헬스벨트, 마사지건, 짐볼, 필라테스, ab롤러, 복근, 홈짐, 홈트, 파워랙, 스쿼트랙, 스미스머신, 딥스바 |
| **Blocked** | 도서, 교재, 인형, 장난감, 화장품 |
| **Missing blocks?** | "의류" not in blocked (but "레깅스"/"운동복" are in allowed — could pass general clothing), "전자기기", "생활용품" |

### health-hugo
| Aspect | Content |
|--------|---------|
| **Allowed** | 건강, 영양, 비타민, 유산균, 루테인, 오메가, 콜라겐, 홍삼, 프로폴리스, 마그네슘, 아연, 철분, 칼슘, 단백질, 보충제, 크레아틴, 글루타치온, 비오틴, 코엔자임, 밀크씨슬, 프로바이오틱스, 엽산, 면역, 혈행, 혈압, 혈당, 장건강, 간건강, 관절, 뼈, 갱년기, 전립선, 피로 |
| **Blocked** | 생활용품, 주방, 반려동물, 패션, 전자기기, 장난감, 완구 |
| **Missing blocks?** | "식품" not in blocked (but "깐마늘" category may differ), "화장품", "의류" |

### pet-hugo
| Aspect | Content |
|--------|---------|
| **Allowed** | 강아지, 고양이, 반려동물, 개, dog, cat, pet, 사료, 간식, 캣타워, 스크래쳐, 하네스, 리드줄, 배변, 화장실, 모래, 이동장, 켄넬, 방석, 급식기, 정수기, 드라이룸, 샴푸, 치약, 유모차, 장난감, 노즈워크, 그루밍, 영양제 |
| **Blocked** | 식품, 의류, 전자기기, 가전, 주방, 완구, 장난감 |
| **Missing blocks?** | "생활용품", "화장품" — not blocked |

### kitchen-hugo
| Aspect | Content |
|--------|---------|
| **Allowed** | 냄비, 프라이팬, 주방, 식기, 칼, 도마, 용기, 텀블러, 도시락, 밀폐, 보관, 조리도구, 가위, 저울, 타이머, 주걱, 냄비받침, 에어프라이어, 전기냄비, 밥솥, 믹서기, 전기포트, 커피머신, 식기세척기, 찜기, 와플, 토스터, 블렌더, 착즙기, 그릴, 인덕션, 세제 |
| **Blocked** | 패션, 의류, 반려동물, 완구, 장난감, 건강식품, 영양제 |
| **Missing blocks?** | "생활용품", "전자기기", "화장품" — not blocked |

### beauty-hugo
| Aspect | Content |
|--------|---------|
| **Allowed** | 크림, 에센스, 토너, 세럼, 앰플, 클렌저, 클렌징, 마스크팩, 선크림, 자외선차단, 쿠션, 파운데이션, 립스틱, 립밤, 아이크림, 마스카라, 아이라이너, 블러셔, 하이라이터, 파우더, 컨실러, 향수, 헤어, 샴푸, 린스, 트리트먼트, 바디로션, 바디워시, 핸드크림, 미스트, 여드름, 각질, 고데기, 드라이어 |
| **Blocked** | 식품, 전자기기, 가전, 완구, 반려동물, 주방, 캠핑 |
| **Missing blocks?** | "생활용품/위생용품" (물티슈 category), "의류", "패션" — not blocked |

### camping-hugo
| Aspect | Content |
|--------|---------|
| **Allowed** | 텐트, 타프, 침낭, 캠핑, 랜턴, 버너, 코펠, 매트, 쿨러, 아이스박스, 화로대, 그릴, 식기, 헤드랜턴, 해먹, 모기장, 선풍기, 난로, 조명, 카트, 가스통, 방수포, 멀티툴, 배낭, 등산화, 트레킹폴, 폴대, 페그, 우비, 모자, 백패킹, 스노우피크, 정리함 |
| **Blocked** | 식품, 건강식품, 완구, 장난감, 주방가전, 뷰티, 화장품 |
| **Missing blocks?** | "생활용품", "전자기기", "의류" — not blocked |

---

## Summary of Blocklist Completeness

| Blog | Blocked Count | Notable Gaps |
|------|--------------|--------------|
| laptop-hugo | 38 | 여성의류, 남성의류, 생활용품, 식품, 화장품 |
| appliance-hugo | 8 | 생활용품, 식품, 가방 |
| interior-hugo | 8 | 생활용품, 전자기기 |
| baby-hugo | 26 | **여성의류/남성의류 (critical)**, 생활용품, 식품 |
| fitness-hugo | 5 | 의류(일반), 전자기기, 생활용품 |
| health-hugo | 8 | 식품(깐마늘 등), 화장품, 의류 |
| pet-hugo | 7 | 생활용품, 화장품 |
| kitchen-hugo | 7 | 생활용품, 전자기기, 화장품 |
| beauty-hugo | 7 | **생활용품/위생용품 (critical)**, 의류, 패션 |
| camping-hugo | 7 | 생활용품, 전자기기, 의류 |
