"""register_sample_cuap_entities.py — 테스트용 샘플 엔티티 10개 등록.

실제 발행 글이 없을 때 크로스 링크 시스템을 검증하기 위한 샘플 데이터.
실행: python3 scripts/register_sample_cuap_entities.py
"""
from shared.cuap_entity_linker import register_cuap_entity

SAMPLE_ENTITIES = [
    ("category", "노트북 추천", "laptop-hugo", "20260720-notebook-rec", "노트북 추천", 50),
    ("category", "에어컨 추천", "appliance-hugo", "20260720-ac-rec", "에어컨 추천", 50),
    ("category", "요가매트 추천", "fitness-hugo", "20260720-yoga-rec", "요가매트 추천", 50),
    ("category", "인테리어 추천", "interior-hugo", "20260720-interior-rec", "인테리어 추천", 50),
    ("category", "유아용품 추천", "baby-hugo", "20260720-baby-rec", "유아용품 추천", 50),
    ("category", "건강식품 추천", "health-hugo", "20260720-health-rec", "건강식품 추천", 50),
    ("category", "반려동물 추천", "pet-hugo", "20260720-pet-rec", "반려동물 추천", 50),
    ("category", "주방용품 추천", "kitchen-hugo", "20260720-kitchen-rec", "주방용품 추천", 50),
    ("category", "뷰티용품 추천", "beauty-hugo", "20260720-beauty-rec", "뷰티용품 추천", 50),
    ("category", "캠핑용품 추천", "camping-hugo", "20260720-camping-rec", "캠핑용품 추천", 50),
]


def main():
    for entity_type, entity_name, blog_id, post_slug, link_label, priority in SAMPLE_ENTITIES:
        register_cuap_entity(
            entity_type, entity_name, blog_id, post_slug, link_label, priority, published=1
        )
    print(f"Registered {len(SAMPLE_ENTITIES)} sample entities")


if __name__ == "__main__":
    main()
