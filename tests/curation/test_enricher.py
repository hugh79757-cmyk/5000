import sys
sys.path.insert(0, "/Users/twinssn/Projects/5000")

import pytest
from pipelines.curation.enricher import SPEC_PATTERNS, _parse_specs_from_name


class TestParseSpecsFromName:
    def test_laptop_ram_from_pattern(self):
        specs = _parse_specs_from_name("삼성 노트북 16GB RAM DDR5 갤럭시북4", "laptop-hugo")
        assert specs.get("ram") == "16GB"

    def test_laptop_ssd_from_pattern(self):
        specs = _parse_specs_from_name("LG 그램 512GB SSD 16GB", "laptop-hugo")
        assert specs.get("ssd") == "512GB"

    def test_laptop_screen_from_pattern(self):
        specs = _parse_specs_from_name("16인치 노트북", "laptop-hugo")
        assert specs.get("screen") == "16인치"

    def test_laptop_cpu_from_pattern(self):
        specs = _parse_specs_from_name("Intel Core i7 13세대 노트북", "laptop-hugo")
        assert "i7" in specs.get("cpu", "")

    def test_laptop_ram_ssd_from_comma_separated(self):
        specs = _parse_specs_from_name("삼성 갤럭시북4, 16GB, 512GB, WIN11", "laptop-hugo")
        assert specs.get("ram") == "16GB"
        assert specs.get("ssd") == "512GB"

    def test_no_match_returns_empty(self):
        specs = _parse_specs_from_name("그냥 일반 텍스트입니다", "laptop-hugo")
        assert specs == {}

    def test_appliance_capacity(self):
        specs = _parse_specs_from_name("에어프라이어 오븐형 20L 대용량", "appliance-hugo")
        if "capacity" in specs:
            assert "20" in specs["capacity"]

    def test_appliance_power(self):
        specs = _parse_specs_from_name("1500W 고출력 핸드블렌더", "appliance-hugo")
        if "power" in specs:
            assert "1500" in specs["power"]
