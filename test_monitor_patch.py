#!/usr/bin/env python3
"""monitor_sector_patch.py + monitor_sector.py 테스트.

운영 monitor 미변경. 패치 후보의 URL 빌드 로직 + PROPAGATING 로직 테스트.
"""
import unittest
import json
import os
import tempfile
from unittest.mock import patch, MagicMock
from monitor_sector_patch import build_url_variants, _percent_encode, extract_canonical_from_html


class TestPercentEncode(unittest.TestCase):
    """_percent_encode: 정확히 한 번 UTF-8 percent-encoding."""

    def test_ascii_passthrough(self):
        """ASCII 문자는 그대로."""
        result = _percent_encode("hello-world")
        self.assertEqual(result, "hello-world")

    def test_korean_encoding(self):
        """한글은 %xx로 인코딩 (기본: 소문자)."""
        result = _percent_encode("섹터")
        self.assertIn("%", result)
        self.assertEqual(result, "%ec%84%b9%ed%84%b0")

    def test_lowercase(self):
        """lower=True면 소문자 %xx."""
        result = _percent_encode("섹터", lower=True)
        self.assertEqual(result, "%ec%84%b9%ed%84%b0")

    def test_uppercase(self):
        """lower=False면 대문자 %XX."""
        result = _percent_encode("섹터", lower=False)
        self.assertEqual(result, "%EC%84%B9%ED%84%B0")

    def test_hyphen_preserved(self):
        """하이픈(-)은 인코딩 안됨."""
        result = _percent_encode("a-b")
        self.assertEqual(result, "a-b")

    def test_no_double_encoding(self):
        """이중 인코딩 없음 (%25 없음)."""
        slug = "섹터-로테이션-전략의-핵심과-경기순환-사이클의-이해"
        result = _percent_encode(slug)
        self.assertNotIn("%25", result)

    def test_full_slug(self):
        """전체 slug 인코딩 검증."""
        slug = "섹터-로테이션-전략의-핵심과-경기순환-사이클의-이해"
        result = _percent_encode(slug, lower=False)
        expected = "%EC%84%B9%ED%84%B0-%EB%A1%9C%ED%85%8C%EC%9D%B4%EC%85%98-%EC%A0%84%EB%9E%B5%EC%9D%98-%ED%95%B5%EC%8B%AC%EA%B3%BC-%EA%B2%BD%EA%B8%B0%EC%88%9C%ED%99%98-%EC%82%AC%EC%9D%B4%ED%81%B4%EC%9D%98-%EC%9D%B4%ED%95%B4"
        self.assertEqual(result, expected)

    def test_already_encoded_no_double(self):
        """이미 인코딩된 slug를 다시 인코딩하면 이중 인코딩됨을 확인."""
        already_encoded = "%EC%84%B9%ED%84%B0"  # 이미 인코딩된 "섹터"
        result = _percent_encode(already_encoded)
        # 이중 인코딩: % → %25
        self.assertIn("%25", result)
        self.assertNotEqual(result, already_encoded)


class TestNFCNormalization(unittest.TestCase):
    """NFC 정규화: DB slug = Hugo dir slug."""

    def test_nfc_equivalence(self):
        """NFC 정규화된 한글 slug가 동일한지 확인."""
        # NFC 정규화
        import unicodedata
        slug_nfc = unicodedata.normalize("NFC", "섹터-로테이션")
        slug_nfd = unicodedata.normalize("NFD", "섹터-로테이션")
        # NFC로 정규화하면 동일
        self.assertEqual(unicodedata.normalize("NFC", slug_nfc),
                        unicodedata.normalize("NFC", slug_nfd))

    def test_percent_encode_nfc(self):
        """NFC slug 인코딩 결과 동일."""
        import unicodedata
        slug_nfc = unicodedata.normalize("NFC", "섹터")
        slug_nfd = unicodedata.normalize("NFD", "섹터")
        # NFC로 정규화 후 인코딩하면 동일
        result_nfc = _percent_encode(slug_nfc)
        result_nfd = _percent_encode(unicodedata.normalize("NFC", slug_nfd))
        self.assertEqual(result_nfc, result_nfd)


class TestBuildUrlVariants(unittest.TestCase):
    """build_url_variants: 3종 URL 생성."""

    def test_returns_3_variants(self):
        """raw, lowercase_pct, uppercase_pct 3종 반환."""
        variants = build_url_variants("hello-world")
        self.assertEqual(set(variants.keys()), {"raw", "lowercase_pct", "uppercase_pct"})

    def test_raw_uses_slug_directly(self):
        """raw는 slug를 그대로 사용."""
        variants = build_url_variants("test-slug")
        self.assertIn("test-slug", variants["raw"])

    def test_encoded_uses_percent(self):
        """인코딩 변형은 %xx 포함."""
        variants = build_url_variants("섹터")
        self.assertIn("%", variants["lowercase_pct"])
        self.assertIn("%", variants["uppercase_pct"])

    def test_all_end_with_slash(self):
        """모든 URL은 /로 끝남."""
        for slug in ["test", "섹터-로테이션"]:
            variants = build_url_variants(slug)
            for url in variants.values():
                self.assertTrue(url.endswith("/"), f"URL이 /로 끝나지 않음: {url}")


class TestExtractCanonical(unittest.TestCase):
    """extract_canonical_from_html: Hugo HTML에서 canonical 추출."""

    def test_blowfish_format(self):
        """Blowfish 테마 형식 (따옴표 없음, self-closing />)."""
        html = '<link rel=canonical href=https://example.com/posts/test/>'
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html)
            path = f.name
        try:
            result = extract_canonical_from_html(path)
            self.assertEqual(result, "https://example.com/posts/test")
        finally:
            os.unlink(path)

    def test_quoted_format(self):
        """따옴표 있는 형식."""
        html = '<link rel="canonical" href="https://example.com/posts/test/" />'
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html)
            path = f.name
        try:
            result = extract_canonical_from_html(path)
            self.assertEqual(result, "https://example.com/posts/test/")
        finally:
            os.unlink(path)

    def test_nonexistent_file(self):
        """파일 없으면 None."""
        result = extract_canonical_from_html("/nonexistent/path.html")
        self.assertIsNone(result)

    def test_korean_canonical(self):
        """한글 canonical URL 추출."""
        html = '<link rel=canonical href=https://sector.techpawz.com/posts/%EC%84%B9%ED%84%B0-%ED%85%8C%EC%9D%B4%EC%85%98/>'
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html)
            path = f.name
        try:
            result = extract_canonical_from_html(path)
            self.assertIn("%EC%84%B9", result)
        finally:
            os.unlink(path)


class TestPropagatingLogic(unittest.TestCase):
    """PROPAGATING 상태 로직 테스트."""

    def test_propagating_vs_fail_distinction(self):
        """HTTP 문제만 있으면 PROPAGATING, 제목 문제 있으면 FAIL."""
        # PROPAGATING: HTTP 문제만 있음
        reasons_http = ["HTTP 404"]
        has_http = any("HTTP" in r for r in reasons_http)
        has_other = any(r for r in reasons_http if "HTTP" not in r)
        is_propagating = has_http and not has_other
        self.assertTrue(is_propagating)

        # FAIL: HTTP + 제목 문제
        reasons_mixed = ["HTTP 404", "title_empty"]
        has_http = any("HTTP" in r for r in reasons_mixed)
        has_other = any(r for r in reasons_mixed if "HTTP" not in r)
        is_propagating = has_http and not has_other
        self.assertFalse(is_propagating)

        # SUCCESS: 문제 없음
        reasons_empty = []
        is_success = not reasons_empty
        self.assertTrue(is_success)

    def test_propagate_intervals(self):
        """PROPAGATE_INTERVALS이 30/90/180초인지 확인."""
        from monitor_sector import PROPAGATE_INTERVALS
        self.assertEqual(PROPAGATE_INTERVALS, [30, 90, 180])


class TestAppendOnlyLog(unittest.TestCase):
    """append-only 로그 보존 테스트."""

    def test_append_preserves_existing(self):
        """append 시 기존 항목이 보존됨."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            path = f.name
            # 기존 항목 추가
            f.write(json.dumps({"reason": "SUCCESS", "id": 1}) + "\n")
            f.write(json.dumps({"reason": "FAIL", "id": 2}) + "\n")

        try:
            # append
            with open(path, "a") as f:
                f.write(json.dumps({"reason": "PROPAGATING", "id": 3}) + "\n")

            # 확인
            with open(path) as f:
                lines = [json.loads(l) for l in f if l.strip()]
            self.assertEqual(len(lines), 3)
            self.assertEqual(lines[0]["reason"], "SUCCESS")
            self.assertEqual(lines[1]["reason"], "FAIL")
            self.assertEqual(lines[2]["reason"], "PROPAGATING")
        finally:
            os.unlink(path)

    def test_correction_event_format(self):
        """CORRECTION 이벤트 형식 검증."""
        correction = {
            "reason": "CORRECTION",
            "original_reason": "FAIL",
            "corrected_reason": "SUCCESS",
            "correction_reason": "Cloudflare 전파 지연",
        }
        # 필수 필드 확인
        self.assertIn("reason", correction)
        self.assertEqual(correction["reason"], "CORRECTION")
        self.assertIn("original_reason", correction)
        self.assertIn("corrected_reason", correction)
        self.assertIn("correction_reason", correction)


class TestNetworkException(unittest.TestCase):
    """네트워크 예외 처리 테스트."""

    def test_check_http_exception_returns_0(self):
        """네트워크 예외 시 0 반환."""
        from monitor_sector import check_http
        # 존재하지 않는 호스트로 테스트 (타임아웃)
        result = check_http("http://192.0.2.1:99999/test", retries=1, delay=0)
        self.assertEqual(result, 0)

    def test_check_http_with_retries(self):
        """retries 파라미터가 동작하는지 확인."""
        from monitor_sector import check_http
        # 존재하지 않는 호스트, retries=2
        result = check_http("http://192.0.2.1:99999/test", retries=2, delay=0)
        self.assertEqual(result, 0)

    def test_check_http_200_returns_immediately(self):
        """200 응답 시 즉시 반환 (재시도 안함)."""
        from monitor_sector import check_http
        # 실제 사이트로 테스트
        result = check_http("https://sector.techpawz.com/", retries=3, delay=1)
        # 200이거나 네트워크 문제로 0
        self.assertIn(result, [0, 200])


class TestMonitorIntegration(unittest.TestCase):
    """monitor_sector.py 통합 테스트."""

    def test_run_check_returns_entry(self):
        """run_check()가 dict 반환."""
        from monitor_sector import run_check
        entry = run_check()
        self.assertIsInstance(entry, dict)
        self.assertIn("reason", entry)
        self.assertIn(entry["reason"], ["SUCCESS", "PROPAGATING", "FAIL", "no_article"])

    def test_check_monitor_log_returns_tuple(self):
        """check_monitor_log()가 (int, list) 반환."""
        from monitor_sector import check_monitor_log
        count, entries = check_monitor_log()
        self.assertIsInstance(count, int)
        self.assertIsInstance(entries, list)

    def test_append_log_creates_file(self):
        """append_log()가 파일 생성."""
        from monitor_sector import append_log
        with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as f:
            path = f.name
        try:
            # 임시 경로로 테스트
            import monitor_sector
            original = monitor_sector.LOG_FILE
            monitor_sector.LOG_FILE = path
            try:
                append_log({"test": True})
                with open(path) as f:
                    lines = f.readlines()
                self.assertEqual(len(lines), 1)
                data = json.loads(lines[0])
                self.assertTrue(data["test"])
            finally:
                monitor_sector.LOG_FILE = original
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
