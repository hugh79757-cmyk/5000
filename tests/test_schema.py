import os

import pytest

SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "layouts", "partials", "schema.html",
)


@pytest.fixture
def schema_content():
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return f.read()


def test_schema_has_date_modified(schema_content):
    assert "dateModified" in schema_content


def test_schema_has_article_modified_time(schema_content):
    assert "article:modified_time" in schema_content
