"""Shared title normalization and stable-slug helpers."""
from __future__ import annotations
import re
from typing import Callable, Iterable

_KO_SPACING = {
    "\uc811\uc774\uc2dd\uc790\uc804\uac70": "\uc811\uc774\uc2dd \uc790\uc804\uac70",
    "\ub85c\ub4dc\uc790\uc804\uac70": "\ub85c\ub4dc \uc790\uc804\uac70",
    "\ubbf8\ub2c8\ubca8\ub85c\uc790\uc804\uac70": "\ubbf8\ub2c8\ubca8\ub85c \uc790\uc804\uac70",
    "\uc804\uae30\uc790\uc804\uac70\ucd94\ucc9c": "\uc804\uae30\uc790\uc804\uac70 \ucd94\ucc9c",
    "\uc5b4\uae68\ub9c8\uc0ac\uc9c0\uae30": "\uc5b4\uae68 \ub9c8\uc0ac\uc9c0\uae30",
    "\ubcbd\uac78\uc774\uc5d0\uc5b4\ucee8": "\ubcbd\uac78\uc774 \uc5d0\uc5b4\ucee8",
    "\ud2b8\ub801\ud06c\uc815\ub9ac\ud568": "\ud2b8\ub801\ud06c \uc815\ub9ac\ud568",
    "\ud578\ub4e4\ucee4\ubc84": "\ud578\ub4e4 \ucee4\ubc84",
    "\uc6cc\uc2dc\ud0c0\uc6cc\ube44\uad50": "\uc6cc\uc2dc\ud0c0\uc6cc \ube44\uad50",
    "\uace0\ud568\ub7c9\uc624\uba54\uac00": "\uace0\ud568\ub7c9 \uc624\uba54\uac00",
}
_BRAND_CANONICAL = {
    "bacicle": "Bacicle",
    "Bacicle": "Bacicle",
    "G4\uc53d\ud06c\ud328\ub4dc": "G4 ThinkPad",
    "\uc53d\ud06c\ud328\ub4dc": "ThinkPad",
    "\ub9ac\uc3d8\ucf54\uc9c0\ub9c8": "\ub9ac\uc3d8\u00b7\ucf54\uc9c0\ub9c8",
    "\ud55c\uc77c\uc758\ub8cc\uae30\ud734\ud50c\ub7ec\uc2a4": "\ud55c\uc77c\uc758\ub8cc\uae30\u00b7\ud734\ud50c\ub7ec\uc2a4",
}
_AD_STYLE = re.compile(r"(\uc5c4\uc120|\ud569\uaca9\uc810|\ud6c4\ud68c \uc5c6\ub294 \uc120\ud0dd|\ubb34\uc870\uac74|\ucd5c\uace0\uc758|\ub180\ub77c\uc6b4|\ud544\uc218\ud15c)")


def normalize_korean_title(title: str) -> str:
    value = re.sub(r"\s+", " ", (title or "").strip())
    for old, new in _KO_SPACING.items():
        value = value.replace(old, new)
    for old, new in _BRAND_CANONICAL.items():
        value = value.replace(old, new)
    value = re.sub(r"\s*[-\u2013\u2014]\s*", " - ", value)
    value = re.sub(r"\s*([:\u00b7])\s*", r"\1 ", value)
    value = re.sub(r"([\uac00-\ud7a3])(?=(?:Bacicle|ThinkPad)\b)", r"\1 ", value)
    return re.sub(r"\s+", " ", value).strip(" -")


def normalize_title(title: str, *, language: str = "ko") -> str:
    value = normalize_korean_title(title) if language == "ko" else re.sub(r"\s+", " ", (title or "").strip())
    return re.sub(r"\s+[|\uff5c]\s+.*$", "", value).strip()


def preserve_slug(existing_slug: str | None, title: str, make_slug: Callable[[str], str]) -> str:
    if existing_slug and str(existing_slug).strip():
        return str(existing_slug).strip()
    return make_slug(title)


def title_skeleton(title: str) -> str:
    value = re.sub(r"\b20\d{2}\b", "YEAR", title.lower())
    value = re.sub(r"\d+(?:\.\d+)?\s*(?:\ub9cc\uc6d0|\uc6d0|\ub2ec\ub7ec|eur|usd)?", "NUMBER", value)
    value = re.sub(r"[\uac00-\ud7a3]{2,}|[a-z]{3,}", "WORD", value)
    return re.sub(r"\s+", " ", value).strip()


def title_issues(title: str, *, language: str = "ko", required_terms: Iterable[str] = (), recent_titles: Iterable[str] = ()) -> list[str]:
    value = normalize_title(title, language=language)
    issues = []
    if not value: issues.append("empty_title")
    if len(value) < 10: issues.append("too_short")
    if len(value) > 72: issues.append("too_long")
    if _AD_STYLE.search(value): issues.append("overly_promotional")
    if language == "en":
        if re.search(r"\bA\s+[AEIOUaeiou]", value): issues.append("article_a_before_vowel_sound")
        if re.search(r"\bAn\s+[^AEIOUaeiou\W]", value): issues.append("article_an_before_consonant_sound")
        if re.search(r"\b(?:Guide|Tips|Tours)\s+Guide\b", value, re.I): issues.append("repeated_noun")
    if any(title_skeleton(t) == title_skeleton(value) for t in recent_titles if t): issues.append("repeated_template")
    missing = [term for term in required_terms if term and term.lower() not in value.lower()]
    if missing: issues.append("missing:" + ",".join(missing))
    return issues

CUAP_TITLE_TEMPLATES = (
    "{use} {category} \uc120\ud0dd \uae30\uc900\uacfc \ucd94\ucc9c",
    "{category} \ube44\uad50: {use}\uc5d0 \ub9de\ub294 \uc120\ud0dd \uae30\uc900",
    "{category} \ucd94\ucc9c\uacfc \uad6c\ub9e4 \uc804 \ud655\uc778\ud560 \uc810",
    "{use} {category}, \ud575\uc2ec \ucc28\uc774\uc640 \uc120\ud0dd \ubc29\ubc95",
)
ETAP_TITLE_TEMPLATES = (
    "{city} {intent}: What to Know Before You Go",
    "Practical {intent} in {city}: Booking and Timing Tips",
    "{city} {intent}: Routes, Timing, and Local Tips",
    "Planning {city}: {intent}, Costs, and What to Expect",
)


def title_templates(site_family: str, language: str = "ko") -> tuple[str, ...]:
    return ETAP_TITLE_TEMPLATES if site_family.lower() == "etap" or language == "en" else CUAP_TITLE_TEMPLATES
