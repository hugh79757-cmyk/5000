"""Task 5: _is_cot_body 임계값 최종 확정 검증.

정상 코퍼스 20건+ (영어 제품명/브랜드 포함 경계 케이스 포함) → 오탐 0건 실증
CoT 코퍼스 (id=1980 유형) → 미탐 0건 실증

임계값: 30% 영어, 3개 글쓰기 지시어, 1개 CoT 마커, 2/3 조건 충족 시 CoT 판정
"""
import os
import json
from datetime import datetime

# _is_cot_body 함수 import
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from pipelines.curation.writer import _is_cot_body

# ============================================================
# 정상 코퍼스: 실제 정상 한국어 건강 기사 (20건+)
# ============================================================
NORMAL_CORPUS = [
    # 1. 기본 건강 기사
    {
        "id": "normal_001",
        "title": "비타민D 섭취 시 주의할 점",
        "body": """비타민D는 골격 건강에 필수적인 영양소입니다. 햇빛을 통해 체내에서 합성되지만, 
现代人은 실내 생활이 많아 결핍이 흔합니다. 비타민D가 풍부한 식품으로는 등푸른생선, 
계란노른자, 강화 우유 등이 있습니다. 일일 권장 섭취량은 성인 기준 600~800IU이며, 
고령자나 임산부는 추가 보충이 필요할 수 있습니다. 비타민D 섭취 시 과다 섭취에 주의하고, 
혈중 농도를 정기적으로 확인하는 것이 좋습니다.""",
    },
    # 2. 영어 제품명 포함 경계 케이스
    {
        "id": "normal_002",
        "title": "Omega-3 지방산의 놀라운 효능",
        "body": """Omega-3 지방산은 심혈관 건강에 도움을 주는 중요한 영양소입니다. 
EPA와 DHA로 구성된 Omega-3는 등푸른생선에 많이 들어 있으며, 
한국에서는 정제된 Omega-3 캡슐이 인기를 끌고 있습니다. 
대표적인 제품으로는 Nordic Naturals, Nature Made, NOW Foods 등이 있으며, 
하루 1000~2000mg 섭취를 권장합니다. Omega-3는 염증 억제와 뇌 건강에도 좋은 것으로 알려져 있습니다.""",
    },
    # 3. 영어 브랜드명 다수 포함
    {
        "id": "normal_003",
        "title": "유산균 추천 — 장 건강 지킴이",
        "body": """장 건강에 좋은 유산균 제품을 비교해보겠습니다. 
국내 인기 브랜드로는 LG생활건강의 셀락스, 종근당건강의 프로비 등이 있으며, 
해외 브랜드로는 Culturelle, Align, Florastor 등이 있습니다. 
유산균 선택 시 CFU 수, 균주 수, 보관 조건 등을 확인해야 합니다. 
일일 권장 CFU는 10억~100억 개이며, 식전에 섭취하면 위산으로부터 보호됩니다. 
유산균은 면역력 강화와 소화 개선에 도움을 줍니다.""",
    },
    # 4. 한약재 관련 기사
    {
        "id": "normal_004",
        "title": "홍삼의 효과와 올바른 섭취 방법",
        "body": """홍삼은 면역력 강화와 피로 회복에 효과적인 전통 건강식품입니다. 
인삼을 증건조하여 만든 홍삼에는 진세노사이드 성분이 풍부하며, 
이는 항산화와 혈액순환 개선에 도움을 줩니다. 홍삼 섭취는 아침 공복에 하는 것이 좋으며, 
1일 3g 이하로 섭취하는 것이 권장됩니다. 
다만, 고혈압 환자나 임산부는 전문의 상담 후 섭취해야 합니다. 
홍삼은 뿌리째 씹어 먹거나, 홍삼정, 홍삼즙 등 다양한 형태로 복용 가능합니다.""",
    },
    # 5. 운동 관련 기사
    {
        "id": "normal_005",
        "title": "매일 걷기 운동이 건강에 미치는 영향",
        "body": """하루 30분 이상 걷기 운동은 심혈관 질환 위험을 줄여주는 것으로 알려져 있습니다. 
연구에 따르면 매일 10,000보 이상 걸으면 체중 관리와 혈압 조절에 도움이 됩니다. 
걷기 운동은 특별한 장비 없이도 가능하며, 실내 트레드밀이나 야외 산책로에서 할 수 있습니다. 
걸을 때는 바른 자세를 유지하고, 적절한 신발을 착용하는 것이 중요합니다. 
노년층의 경우 낙상 예방을 위해 보조기를 사용하는 것도 방법입니다.""",
    },
    # 6. 다이어트 관련 기사
    {
        "id": "normal_006",
        "title": "간헐적 단식의 장단점",
        "body": """간헐적 단식은 최근 인기를 끌고 있는 다이어트 방법 중 하나입니다. 
16:8 방법(16시간 단식, 8시간 식사)과 5:2 방법(5일 식사, 2일 단식)이 대표적입니다. 
간헐적 단식의 장점으로는 체중 감량, 인슐린 감수성 개선, 염증 giảm소 등이 있습니다. 
단점으로는 초기 적응기의 어지러움, 과식 유발 가능성이 있습니다. 
다이어트 목적이 아니라면 균형 잡힌 식단이 더 효과적일 수 있습니다. 
특히 당뇨병 환자나 임산부는 반드시 전문의 상담이 필요합니다.""",
    },
    # 7. 수면 관련 기사
    {
        "id": "normal_007",
        "title": "수면의 질을 높이는 7가지 습관",
        "body": """양질의 수면은 건강한 삶에 필수적입니다. 수면의 질을 높이기 위해 
규칙적인 취침 시간을 유지하고, 잠자리에서 전자기기 사용을 줄이는 것이 좋습니다. 
잠자리 온도는 18~22도가 적절하며, 어둡고 조용한 환경이 수면에 도움을 줍니다. 
카페인은 취침 6시간 전부터 피하는 것이 권장되며, 
가벼운 스트레칭이나 명상은 수면 전 루틴으로 효과적입니다. 
만성 수면 장애가 있는 경우 전문의 상담을 받는 것이 좋습니다.""",
    },
    # 8. 면역력 관련 기사
    {
        "id": "normal_008",
        "title": "면역력을 강화하는 식습관",
        "body": """강한 면역체계는 다양한 질병으로부터 우리를 지켜줍니다. 
비타민C가 풍부한 과일(오렌지, 키위, 딸기)과 채질(브로콜리, 파프리카)을 
매일 섭취하는 것이 도움이 됩니다. 또한 발효식품(김치, 된장, yogurt)은 
장내 유익균을 증식시켜 면역력 향상에 기여합니다. 
균형 잡힌 식단과 규칙적인 운동, 충분한 수면이 결합될 때 
최적의 면역 기능을 유지할 수 있습니다. 과도한 음주와 흡연은 면역력을 저하시키므로 피하는 것이 좋습니다.""",
    },
    # 9. 골다공증 관련 기사
    {
        "id": "normal_009",
        "title": "골다공증 예방을 위한 칼슘 섭취 가이드",
        "body": """골다공증은 뼈가 약해져 골절 위험이 높아지는 질환입니다. 
성인 남녀의 일일 권장 칼슘 섭취량은 800~1000mg이며, 
폐경기 여성과 고령자는 1200mg 이상이 권장됩니다. 
칼슘이 풍부한 식품으로는 우유, 치즈, 두부, 시금치, 견과류 등이 있습니다. 
칼슘 흡수를 돕는 비타민D도 함께 섭취하는 것이 좋습니다. 
규칙적인 운동, 특히 체중 부하 운동은 골밀도 유지에 효과적입니다.""",
    },
    # 10. 당뇨병 관련 기사
    {
        "id": "normal_010",
        "title": "당뇨병 관리를 위한 혈당 조절법",
        "body": """당뇨병 환자는 꾸준한 혈당 관리가 필요합니다. 
식후 혈당 목표치는 140mg/dL 이하이며, 공복 혈당은 80~130mg/dL이 적정합니다. 
탄수화물 섭취를 줄이고, 식이섬유가 많은 채소를 충분히 섭취하는 것이 좋습니다. 
식사 후 30분 이상 가벼운 운동을 하는 것도 혈당 조절에 도움이 됩니다. 
혈당 측정을 규칙적으로 하고, 의료진과 상의하여 약물 복용 계획을 세우는 것이 중요합니다.""",
    },
    # 11. 영어 제품명 + 한국어 혼합 경계 케이스
    {
        "id": "normal_011",
        "title": "Probiotics 유산균 비교 — Culturelle vs Align",
        "body": """장 건강에 좋은 Probiotics 유산균을 비교해보겠습니다. 
Culturelle은 Lactobacillus GG 균주를 함유하고 있으며, 
하루 1 capsule 섭취로 장 기능 개선에 도움을 줍니다. 
Align은 Bifidobacterium 35624 균주를 사용하며, 
과민성 대장 증후근 완화에 효과적인 것으로 알려져 있습니다. 
둘 다 냉장 보관이 필요하며, 가격대는 Culturelle이 약간 저렴합니다. 
개인의 장 상태와 증상에 따라 적합한 제품을 선택하는 것이 좋습니다.""",
    },
    # 12. 비타민 보충제 관련
    {
        "id": "normal_012",
        "title": "종합 비타민 선택 가이드 — Centrum vs Nature Made",
        "body": """종합 비타민을 선택할 때 확인해야 할 성분과 함량을 비교합니다. 
Centrum은 25종 이상의 비타민과 미네랄을 포함하며, 
Nature Made는 USP 인증을 받아 품질이 검증된 제품입니다. 
가격은 Centrum이 약간 비싸지만, 철분 함량이 높은 것이 특징입니다. 
Nature Made는 철분이 적어 변비가 걱정되는 분들에게 적합합니다. 
두 제품 모두 1일 1정 복용이며, 식후에 섭취하는 것이 흡수에 좋습니다.""",
    },
    # 13. 오메가3 관련 경계 케이스
    {
        "id": "normal_013",
        "title": "EPA vs DHA — 어떤 Omega-3를 선택해야 할까?",
        "body": """Omega-3 지방산은 EPA와 DHA로 구성됩니다. 
EPA는 혈액순환과 염증 억제에, DHA는 뇌 건강과 시력 유지에 도움을 줍니다. 
심혈관 건강이 걱정된다면 EPA 함량이 높은 제품을, 
인지 기능 개선이 목적이라면 DHA 함량이 높은 제품을 선택하는 것이 좋습니다. 
Nordic Naturals는 EPA:DHA 비율이 2:1인 제품이 인기 있으며, 
Blackmores는 호주산 원료를 사용하는 제품이 있습니다. 
일일 권장량은 EPA+DHA 합계 1000mg 이상입니다.""",
    },
    # 14. 건강기능식품 관련
    {
        "id": "normal_014",
        "title": "루테인 눈 건강 보충제 비교",
        "body": """루테인은 황반변성 예방에 좋은 카로티노이드입니다. 
국내 인기 브랜드로는 GC녹십자의 아오에스루테인, 동아제약의 에스로테인 등이 있습니다. 
해외 브랜드로는 Doctor's Best, Now Foods 등이 있으며, 
루테인 함량은 10~20mg이 적정합니다. 
루테인은 지용성이므로 식후에 섭취하면 흡수율이 높아집니다. 
눈의 피로가 심한 직장인이나 학생에게 추천되며, 
장기 복용 시 눈 건강 개선에 도움이 될 수 있습니다.""",
    },
    # 15. 프로바이오틱스 경계 케이스
    {
        "id": "normal_015",
        "title": "Lactobacillus vs Bifidobacterium — 어떤 유산균이 좋을까?",
        "body": """유산균은 크게 Lactobacillus과 Bifidobacterium 두 가지 종류로 나뉩니다. 
Lactobacillus는 소장에서 작용하며, 설사 예방에 효과적입니다. 
Bifidobacterium은 대장에서 작용하며, 변비 개선에 도움을 줍니다. 
일반적으로 Lactobacillus는 유제품에서, Bifidobacterium은 모유에서 처음 발견됩니다. 
둘 다 장내 균형을 유지하는 데 중요하며, 
제품 선택 시 본인의 증상(설사/변비)에 따라 결정하는 것이 좋습니다.""",
    },
    # 16. 영어 인용 포함 경계 케이스
    {
        "id": "normal_016",
        "title": "비타민C의 효과 — \"Ascorbic Acid\"가 면역에 미치는 영향",
        "body": """비타민C(Ascorbic Acid)는 면역 기능에 필수적인 영양소입니다. 
的研究에 따르면 비타민C 200mg 이상 섭취 시 감기 기간이 
단축된다는 결과가 있습니다. 비타민C가 풍부한 식품으로는 
라임, 레몬, 오렌지, 키위, 딸기 등이 있습니다. 
하루 권장 섭취량은 성인 기준 100mg이며, 흡연자는 35mg 추가가 권장됩니다. 
비타민C는 수용성이므로 과다 섭취 시 소변으로 배출되며, 
위장 장애를 일으킬 수 있으므로 적정량 섭취가 중요합니다.""",
    },
    # 17. 건강 식품 경계 케이스
    {
        "id": "normal_017",
        "title": "홍삼 vs 녹용 — 어떤 건강식품을 선택해야 할까?",
        "body": """홍삼과 녹용은 대표적인 한국 건강식품입니다. 
홍삼은 면역력 강화와 피로 회복에, 녹용은 관절 건강과 혈액순환에 도움을 줍니다. 
홍삼의 주요 성분은 진세노사이드이며, 녹용은 글루코사민과 콘드로이틴을 함유하고 있습니다. 
가격은 홍삼(100g당 5~10만원)이 녹용(100g당 3~7만원)보다 비싼 편입니다. 
목적에 따라 선택하는 것이 좋은데, 면역력 강화 목적이면 홍삼을, 
관절 건강 목적이면 녹용을 추천합니다. 두 제품 모두 정기적인 섭취가 중요합니다.""",
    },
    # 18. 건강 기사 — 운동 보조제
    {
        "id": "normal_018",
        "title": "프로틴 보충제 선택 가이드 — Whey vs Plant Protein",
        "body": """운동 후 단백질 보충제 선택 시 Whey Protein과 Plant Protein을 비교합니다. 
Whey Protein은 유당 함유가 높아 유당불내증 환자에게는 부적합할 수 있습니다. 
Plant Protein은 콩, 완두콩 등에서 추출하며, 유당불내증이 없는 것이 장점입니다. 
단백질 함량은 Whey(80~90%)가 Plant(70~80%)보다 약간 높습니다. 
가격은 Plant Protein이 약간 비싼 편이며, 맛은 Whey가 더 좋은 평가를 받고 있습니다. 
운동 목적이면 Whey를, 채식주의자이면 Plant Protein을 추천합니다.""",
    },
    # 19. 건강 기사 — 영양제 경계 케이스
    {
        "id": "normal_019",
        "title": "Magneisum 마그네슘 보충제 비교",
        "body": """마그네슘은 근육 이완과 수면 개선에 좋은 미네랄입니다. 
Magneisum 보충제는 종류에 따라 흡수율이 다릅니다. 
Magneisum Citrate는 흡수율이 높지만, 설사를 유발할 수 있습니다. 
Magneisum Glycinate는 흡수율이 좋고 위장 장애가 적어 추천됩니다. 
하루 권장량은 성인 기준 300~400mg이며, 
식후에 섭취하면 흡수율이 높아집니다. 
근육 경련이 잦은 운동선수나 불면증이 있는 분들에게 도움이 될 수 있습니다.""",
    },
    # 20. 건강 기사 — 오메가3 경계 케이스
    {
        "id": "normal_020",
        "title": "Krill Oil vs Fish Oil — 어떤 오메가3를 선택할까?",
        "body": """오메가3 보충제는 Krill Oil과 Fish Oil 두 가지 종류가 있습니다. 
Fish Oil은 전통적인 오메가3 보충제이며, 가격이 저렴한 것이 장점입니다. 
Krill Oil은 인지질 형태로 흡수율이 높지만, 가격이 약간 비쌉니다. 
둘 다 EPA와 DHA를 함유하고 있으며, 하루 1000mg 이상 섭취를 권장합니다. 
Fish Oil은 어취가 나는 것이 단점이며, Krill Oil은 어취가 없는 것이 장점입니다. 
개인의 선호와 예산에 따라 선택하는 것이 좋습니다.""",
    },
]

# ============================================================
# CoT 코퍼스: id=1980 유형의 CoT/프롬프트 누출 본문
# ============================================================
COT_CORPUS = [
    # 1. id=1980 원본 (실제 누출 — CUAP/health-hugo/posts/네덜란드-추천-top5-2026년/index.md)
    {
        "id": "cot_001",
        "title": "id=1980 원본",
        "body": """우선 사용자 요청은 네덜란드 관련 상품 추천 글을 작성하는 것이다. 제품은 총 4개가 제공되었고, 각각의 링크와 이미지를 그대로 사용해야 한다. 글은 한국어로 작성해야 하며, AIDA 모델을 따라 퍼널 구조로 작성해야 한다.

제품 데이터를 살펴보면:

1. 올바른습관 네덜란드산 산양유100% 단백질 분말, 6개, 220g - 104,290원, 로켓배송, 쿠팡순위 1위
2. 네덜란드 왕실 치즈칼슘 퀄리고트 산양유 단백질 네덜란드레시피 - 76,970원, 무료배송, 쿠팡순위 2위
3. 백세식품 산양유 단백질 분말 100% 함유 200g통 네덜란드산 퀄리코트 HACCP인증, 200g, 6개 - 120,600원, 무료배송, 쿠팡순위 3위
4. 산양유단백질정 네덜란드산 500mg x 100정 HACCP 인증제품, 4개, 600mg x 90개, 100정 - 74,400원, 무료배송, 쿠팡순위 5위

제목 규칙을 확인해야 한다. 제목은 반드시 아래 패턴 중 하나를 따라야 한다:
1. [연도]년 [월]월 [제품명] 추천 — [구체적 혜택/특징]
2. [제품A] vs [제품B] — [비교 포인트]

제목 예시를 만들어보자.

이제 글의 구조를 생각해보자.

도입부 (Attention): 네덜란드산 산양유 단백질에 대한 수요 증가

선택 가이드 (Interest): 산양유 단백질 고를 때 확인할 포인트

비교표 (Desire): 한눈에 보는 비교표

각 상품 소개 (Desire 강화):""",
    },
    # 2. CoT 마커 다수 포함
    {
        "id": "cot_002",
        "title": "CoT 마커 다수",
        "body": """우선 사용자 요청은 건강기능식품 추천입니다.
제목 규칙을 확인해야 한다. 제목 예시를 만들어보자.
제품 데이터를 살펴보면 총 5개 제품이 제공되었다.
이제 글의 구조를 생각해보자. AIDA 모델을 적용해야 한다.
H2 섹션: 제품 비교표
H3 섹션: 상황별 추천
도입부: 제품 소개
FAQ: 자주 묻는 질문
CTA: 구매 버튼""",
    },
    # 3. 영어 CoT 다수
    {
        "id": "cot_003",
        "title": "영어 CoT 다수",
        "body": """First, analyze the user request. The user wants a product recommendation.
Now, let's think about the structure. Use AIDA model for the funnel.
H2 section: Product comparison table
H3 section: Recommendations by situation
Introduction: Product overview
FAQ: Frequently asked questions
Conclusion: Final recommendation
CTA: Purchase button
 장점: Each product's advantages
아쉬운 점: Each product's disadvantages""",
    },
    # 4. 한국어 CoT + 글쓰기 지시어
    {
        "id": "cot_004",
        "title": "한국어 CoT + 글쓰기 지시어",
        "body": """우선 사용자 요청은 노트북 추천 글이다.
이제 글을 작성해보자. AIDA 모델을 따라 퍼널 구조로 작성한다.
비교표를 만들고, 상황별 추천을 제공한다.
도입부에서 제품을 소개하고, FAQ를 포함한다.
장점과 아쉬운 점을 정리하고, CTA를 넣는다.
H2 섹션: 제품 비교표
H3 섹션: 상황별 추천
자주 묻는 질문 (FAQ)""",
    },
    # 5. CoT + 영어 비율 높음
    {
        "id": "cot_005",
        "title": "CoT + 영어 비율 높음",
        "body": """First, analyze the user request. The user wants a laptop recommendation.
Now, let's think about the structure. Use AIDA model for the funnel.
H2 section: Product comparison table
H3 section: Recommendations by situation
Introduction: Product overview
FAQ: Frequently asked questions
Conclusion: Final recommendation
CTA: Purchase button
 장점: Each product's advantages
아쉬운 점: Each product's disadvantages
이제 글의 구조를 생각해보자. AIDA 모델을 적용해야 한다.
퍼널 구조로 작성해야 한다.""",
    },
    # 6. 제목 규칙/예시 포함
    {
        "id": "cot_006",
        "title": "제목 규칙/예시 포함",
        "body": """제목 규칙: 사용자 요청에 맞는 제목을 작성한다.
제목 예시: "2026년 노트북 추천 TOP5"
우선 사용자 요청은 노트북 추천이다.
이제 글을 작성해보자. AIDA 모델을 적용한다.
비교표를 만들고, 상황별 추천을 제공한다.
도입부에서 제품을 소개하고, FAQ를 포함한다.
장점과 아쉬운 점을 정리하고, CTA를 넣는다.""",
    },
    # 7. 글쓰기 지시어 다수 + CoT 마커
    {
        "id": "cot_007",
        "title": "글쓰기 지시어 다수 + CoT 마커",
        "body": """우선 사용자 요청은 건강기능식품 추천이다.
AIDA 모델을 적용해야 한다. 퍼널 구조로 작성해야 한다.
비교표를 만들고, 상황별 추천을 제공한다.
도입부에서 제품을 소개하고, 자주 묻는 질문(FAQ)을 포함한다.
장점과 아쉬운 점을 정리하고, CTA를 넣는다.
H2 섹션: 제품 비교표
H3 섹션: 상황별 추천""",
    },
    # 8. 영어 CoT + 한국어 마커
    {
        "id": "cot_008",
        "title": "영어 CoT + 한국어 마커",
        "body": """First, analyze the user request. The user wants a health supplement recommendation.
우선 사용자 요청은 건강기능식품 추천이다.
Now, let's think about the structure. Use AIDA model for the funnel.
H2 section: Product comparison table
H3 section: Recommendations by situation
도입부: 제품 소개
FAQ: 자주 묻는 질문
CTA: 구매 버튼
장점: 각 제품의 장점
아쉬운 점: 각 제품의 아쉬운 점""",
    },
    # 9. CoT 마커 + 글쓰기 지시어
    {
        "id": "cot_009",
        "title": "CoT 마커 + 글쓰기 지시어",
        "body": """사용자 요청은 제품 추천이다.
제목 규칙을 확인해야 한다. 제목 예시를 만들어보자.
이제 글의 구조를 생각해보자. AIDA 모델을 적용해야 한다.
퍼널 구조로 작성해야 한다.
비교표를 만들고, 상황별 추천을 제공한다.
도입부에서 제품을 소개하고, FAQ를 포함한다.
장점과 아쉬운 점을 정리하고, CTA를 넣는다.""",
    },
    # 10. 영어 CoT 다수 + 한국어
    {
        "id": "cot_010",
        "title": "영어 CoT 다수 + 한국어",
        "body": """First, let's analyze the user request. The user wants a product recommendation.
Now, let's think about the structure. Use AIDA model for the funnel.
H2 section: Product comparison table
H3 section: Recommendations by situation
Introduction: Product overview
FAQ: Frequently asked questions
Conclusion: Final recommendation
CTA: Purchase button
 장점: Each product's advantages
아쉬운 점: Each product's disadvantages
이제 글을 작성해보자. AIDA 모델을 적용해야 한다.""",
    },
]


def test_normal_corpus():
    """정상 코퍼스 20건 검증 — 오탐 0건."""
    false_positives = []
    for sample in NORMAL_CORPUS:
        result = _is_cot_body(sample["body"])
        if result is True:
            false_positives.append(sample["id"])
    
    print(f"\n=== 정상 코퍼스 검증 결과 ===")
    print(f"표본 수: {len(NORMAL_CORPUS)}건")
    print(f"오탐(detect) 건수: {len(false_positives)}건")
    
    if false_positives:
        print(f"오탐 샘플 ID: {false_positives}")
        for fp_id in false_positives:
            sample = next(s for s in NORMAL_CORPUS if s["id"] == fp_id)
            print(f"  - {fp_id}: {sample['title']}")
    
    assert len(false_positives) == 0, f"오탐 {len(false_positives)}건 발생: {false_positives}"
    print("✅ 정상 코퍼스 오탐 0건 확인")
    return len(NORMAL_CORPUS), 0


def test_cot_corpus():
    """CoT 코퍼스 검증 — 미탐 0건."""
    misses = []
    for sample in COT_CORPUS:
        result = _is_cot_body(sample["body"])
        if result is False:
            misses.append(sample["id"])
    
    print(f"\n=== CoT 코퍼스 검증 결과 ===")
    print(f"표본 수: {len(COT_CORPUS)}건")
    print(f"미탐(miss) 건수: {len(misses)}건")
    
    if misses:
        print(f"미탐 샘플 ID: {misses}")
        for m_id in misses:
            sample = next(s for s in COT_CORPUS if s["id"] == m_id)
            print(f"  - {m_id}: {sample['title']}")
    
    assert len(misses) == 0, f"미탐 {len(misses)}건 발생: {misses}"
    print("✅ CoT 코퍼스 미탐 0건 확인")
    return len(COT_CORPUS), 0


def test_edge_cases():
    """경계 케이스 검증 — 정상 코퍼스에 포함된 경계 케이스 확인."""
    edge_cases = [
        "normal_002",  # 영어 제품명 Omega-3, EPA, DHA
        "normal_003",  # 영어 브랜드 Nordic Naturals, Nature Made
        "normal_011",  # 영어 제품명 Culturelle, Align
        "normal_012",  # 영어 제품명 Centrum, Nature Made
        "normal_013",  # 영어 제품명 EPA, DHA, Nordic Naturals
        "normal_016",  # 영어 인용 "Ascorbic Acid"
        "normal_018",  # 영어 제품명 Whey, Plant Protein
        "normal_019",  # 영어 제품명 Magneisum
        "normal_020",  # 영어 제품명 Krill Oil, Fish Oil
    ]
    
    print(f"\n=== 경계 케이스 검증 결과 ===")
    print(f"경계 케이스 수: {len(edge_cases)}건")
    
    false_positives = []
    for sample_id in edge_cases:
        sample = next(s for s in NORMAL_CORPUS if s["id"] == sample_id)
        result = _is_cot_body(sample["body"])
        if result is True:
            false_positives.append(sample_id)
    
    print(f"오탐 건수: {len(false_positives)}건")
    
    if false_positives:
        for fp_id in false_positives:
            sample = next(s for s in NORMAL_CORPUS if s["id"] == fp_id)
            print(f"  - {fp_id}: {sample['title']}")
    
    assert len(false_positives) == 0, f"경계 케이스 오탐 {len(false_positives)}건 발생"
    print("✅ 경계 케이스 오탐 0건 확인")
    return len(edge_cases), 0


if __name__ == "__main__":
    print("=" * 60)
    print("_is_cot_body 임계값 최종 확정 검증")
    print("=" * 60)
    
    # 현재 임계값 출력
    from pipelines.curation.writer import (
        _COT_ENGLISH_RATIO_THRESHOLD,
        _COT_WRITING_INSTRUCTION_MIN_MATCHES,
        _COT_MARKER_MIN_MATCHES,
    )
    print(f"\n현재 임계값:")
    print(f"  - 영어 비율: {_COT_ENGLISH_RATIO_THRESHOLD * 100}%")
    print(f"  - 글쓰기 지시어: {_COT_WRITING_INSTRUCTION_MIN_MATCHES}개 이상")
    print(f"  - CoT 마커: {_COT_MARKER_MIN_MATCHES}개 이상")
    print(f"  - 판정: 3개 조건 중 2개 이상 충족 시 CoT")
    
    # 검증 실행
    normal_count, normal_fp = test_normal_corpus()
    cot_count, cot_miss = test_cot_corpus()
    edge_count, edge_fp = test_edge_cases()
    
    # 결과 요약
    print(f"\n{'=' * 60}")
    print(f"검증 결과 요약")
    print(f"{'=' * 60}")
    print(f"정상 코퍼스: {normal_count}건 검증, 오탐 {normal_fp}건")
    print(f"CoT 코퍼스: {cot_count}건 검증, 미탐 {cot_miss}건")
    print(f"경계 케이스: {edge_count}건 검증, 오탐 {edge_fp}건")
    print(f"총 검증: {normal_count + cot_count}건, 오탐 {normal_fp}건, 미탐 {cot_miss}건")
    
    # 코퍼스 덤프 저장
    corpus_data = {
        "timestamp": datetime.now().isoformat(),
        "thresholds": {
            "english_ratio": _COT_ENGLISH_RATIO_THRESHOLD,
            "writing_instruction_min": _COT_WRITING_INSTRUCTION_MIN_MATCHES,
            "cot_marker_min": _COT_MARKER_MIN_MATCHES,
            "conditions_required": 2,
        },
        "results": {
            "normal_corpus": {
                "count": normal_count,
                "false_positives": normal_fp,
            },
            "cot_corpus": {
                "count": cot_count,
                "misses": cot_miss,
            },
            "edge_cases": {
                "count": edge_count,
                "false_positives": edge_fp,
            },
        },
        "normal_corpus": NORMAL_CORPUS,
        "cot_corpus": COT_CORPUS,
    }
    
    dump_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        ".planning", "triage", "TASK5-cot-corpus-dump.json"
    )
    with open(dump_path, "w", encoding="utf-8") as f:
        json.dump(corpus_data, f, ensure_ascii=False, indent=2)
    print(f"\n코퍼스 덤프 저장: {dump_path}")
