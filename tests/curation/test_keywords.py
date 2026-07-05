import sys
sys.path.insert(0, "/Users/twinssn/Projects/5000")

from pipelines.curation.keywords import KEYWORD_MAP, get_keywords


class TestKeywords:
    def test_all_10_blogs_present(self):
        assert len(KEYWORD_MAP) == 10

    def test_each_blog_has_80_to_200_keywords(self):
        for blog, kws in KEYWORD_MAP.items():
            assert 80 <= len(kws) <= 200, f"{blog}: {len(kws)} keywords (expected 80-200)"

    def test_no_generic_keywords_remain(self):
        generics = {"가방", "가벼운", "가성비", "가정용", "가죽", "가죽소파",
                     "각도조절", "갤럭시북", "공기청정기", "냉장고", "노트북",
                     "덤벨", "데스크"}
        for blog, kws in KEYWORD_MAP.items():
            found = generics & set(kws)
            assert not found, f"{blog} still has generic keywords: {found}"

    def test_get_keywords_returns_list(self):
        kws = get_keywords("fitness-hugo")
        assert isinstance(kws, list)
        assert len(kws) > 0

    def test_get_keywords_unknown_blog(self):
        kws = get_keywords("nonexistent-blog")
        assert kws == []

    def test_get_keywords_all_blogs_have_unique_keywords(self):
        for blog in KEYWORD_MAP:
            kws = get_keywords(blog)
            assert len(kws) == len(set(kws)), f"{blog} has duplicate keywords"

    def test_keywords_are_strings(self):
        for blog, kws in KEYWORD_MAP.items():
            for kw in kws:
                assert isinstance(kw, str), f"{blog}: non-string keyword: {kw}"
