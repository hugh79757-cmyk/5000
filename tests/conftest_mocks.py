"""conftest_mocks.py — Shared mock fixtures for external API testing.

Usage:
    from tests.conftest_mocks import mock_tourapi, mock_openai, mock_blogger
"""

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_tourapi():
    """Mock TourAPI areaBasedList2 response.
    Returns a realistic set of travel items as the API would return.
    """
    mock_items = [
        {
            "contentid": "123456",
            "contenttypeid": "39",
            "title": "속초 이선장",
            "addr1": "강원특별자치도 속초시",
            "addr2": "",
            "firstimage": "https://tong.visitkorea.or.kr/test.jpg",
            "firstimage2": "https://tong.visitkorea.or.kr/test_s.jpg",
            "tel": "033-123-4567",
            "mapx": "128.592",
            "mapy": "38.207",
            "areacode": "32",
            "sigungucode": "3",
            "cat1": "A05",
            "cat2": "A0502",
            "cat3": "A050201",
        },
        {
            "contentid": "789012",
            "contenttypeid": "39",
            "title": "강릉 초당순두부",
            "addr1": "강원특별자치도 강릉시",
            "addr2": "",
            "firstimage": "",
            "firstimage2": "",
            "tel": "",
            "mapx": "128.876",
            "mapy": "37.749",
            "areacode": "32",
            "sigungucode": "1",
            "cat1": "A05",
            "cat2": "A0502",
            "cat3": "A050201",
        },
    ]
    with patch("pipelines.travel.fetcher.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": {
                "body": {
                    "items": {
                        "item": mock_items
                    },
                    "numOfRows": 10,
                    "pageNo": 1,
                    "totalCount": 2,
                }
            }
        }
        mock_get.return_value = mock_response
        yield mock_get


@pytest.fixture
def mock_openai():
    """Mock OpenAI API chat completion response.
    Matches the ai_writer.py calling pattern.
    """
    mock_content = (
        "## 속초의 숨은 맛집, 이선장\n\n"
        "속초시 중심부에 위치한 이선장은 신선한 해산물 요리로 유명한 곳입니다. "
        "대표 메뉴는 물회와 회덮밥으로, 현지인들에게도 사랑받는 맛집입니다.\n\n"
        "### 위치 및 연락처\n"
        "- 주소: 강원특별자치도 속초시\n"
        "- 전화: 033-123-4567\n\n"
        "> 이 포스팅은 쿠팡 파트너스의 일환으로 수수료를 제공받습니다.\n"
    )
    with patch("shared.ai_writer.client.chat.completions.create") as mock_create:
        mock_choice = MagicMock()
        mock_choice.message.content = mock_content
        mock_choice.message.refusal = None
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_create.return_value = mock_response
        yield mock_create


@pytest.fixture
def mock_blogger():
    """Mock Blogger API posts.insert response.
    Matches the blogger_publisher.py calling pattern.
    """
    with patch("shared.blogger_publisher.service.posts") as mock_posts:
        mock_insert = MagicMock()
        mock_insert.execute.return_value = {
            "id": "987654321",
            "url": "https://travel.rotcha.kr/2026/07/test-post.html",
            "published": "2026-07-01T12:00:00+09:00",
        }
        mock_posts.return_value.insert.return_value = mock_insert
        yield mock_posts


@pytest.fixture
def mock_all_apis(mock_tourapi, mock_openai, mock_blogger):
    """Convenience fixture that mocks all 3 external APIs at once."""
    yield {
        "tourapi": mock_tourapi,
        "openai": mock_openai,
        "blogger": mock_blogger,
    }
