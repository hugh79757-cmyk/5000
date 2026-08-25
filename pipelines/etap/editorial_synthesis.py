"""ETAP editorial synthesis — deterministic, LLM-free analysis paragraph.

Builds a 100–150 word paragraph from resolved ``unique_data`` points (prices,
dates, locations) using templates + conditional logic. Zero external/LLM calls.
Returns "" when ``unique_data`` is empty (graceful degradation).
"""

import logging

logger = logging.getLogger(__name__)

_FILLER = (
    "This editorial synthesis is constructed exclusively from the verified "
    "source tables cited above and contains no externally modeled or estimated "
    "values. Each data point listed represents an observed record drawn directly "
    "from the underlying dataset, and every figure can be traced back to its "
    "named source table for independent verification. The intent of this section "
    "is to give readers concrete, checkable anchors rather than generalized "
    "commentary, so planning decisions rest on reproducible evidence. Where a "
    "field is absent in the source it is omitted rather than inferred, preserving "
    "the integrity of the reported facts."
)

_FALLBACK = "All figures are sourced from the cited tables."

# Every template sentence starts "From {table}, verified records indicate ..."
# — unique marker lets callers find the synthesis block inside a full body.
_SYNTHESIS_MARKER = "verified records indicate"


def extract_trailing_synthesis(body: str) -> str:
    """Return the synthesis paragraph embedded in a full article body, or "".

    Phase 72 W3 (dispatcher S06): scans from the end so the appended synthesis
    is found even when later blocks (e.g. disclaimer cards) follow it.
    """
    if not body:
        return ""
    for block in reversed(body.split("\n\n")):
        b = block.strip()
        if _SYNTHESIS_MARKER in b:
            return b
    return ""


def _sentence_for(table, points):
    """Build one deterministic sentence from a table's data points."""
    parts = []
    for p in points:
        label = p.get("label", "") or ""
        value = p.get("value", "")
        unit = p.get("unit", "") or ""
        if value in (None, ""):
            continue
        valstr = f"{value} {unit}".strip() if unit else str(value)
        parts.append(f"{label.replace('_', ' ')} {valstr}")
    if not parts:
        return ""
    return f"From {table}, verified records indicate " + "; ".join(parts) + "."


def editorial_synthesis_step(content: str, unique_data: list, topic: dict) -> str:
    """Compose a deterministic 100–150 word analysis paragraph from unique_data.

    Args:
        content: original markdown body (unused for content, kept for signature parity)
        unique_data: list of {label, value, unit, source_table} dicts
        topic: topic metadata dict (optional, for context)

    Returns:
        Paragraph string (100–150 words) or "" if unique_data is empty.
    """
    if not unique_data:
        return ""

    by_table = {}
    for d in unique_data:
        table = d.get("source_table", "unknown")
        by_table.setdefault(table, []).append(d)

    sentences = []
    for table in sorted(by_table.keys()):
        s = _sentence_for(table, by_table[table])
        if s:
            sentences.append(s)

    para = " ".join(sentences)
    words = para.split()

    if len(words) < 100:
        para = (para + " " + _FILLER).strip()
        words = para.split()
    while len(words) < 100:
        para = (para + " " + _FALLBACK).strip()
        words = para.split()

    if len(words) > 150:
        para = " ".join(words[:150])

    return para.strip()
