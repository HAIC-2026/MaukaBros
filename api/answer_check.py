"""Checks the numbers in an assistant answer against the data its tools returned.

The model writes its own answer text, so a manipulative question could get it to state a figure
that is not in the data, next to a real citation. This finds every number in the answer and
reports the ones that do not match anything the tools returned (or the question itself). The page
shows those as "not found in the data", so a reader never mistakes them for sourced figures.

Matching is at the precision the answer uses: "13.4%" matches a tool value of 0.13357 (a share)
or 13.36; "$94,684" matches 94684.0. Shares are also compared as percentages, and negative
differences by their size ("6.2 points lower" matches -0.062).

Not checked, because they are labels rather than figures: district numbers (HD-47, District 47),
table ids (B19013), citation markers ([S3]), years (1900-2099) and plain whole numbers up to 100
without a unit (counts of districts or programs, ranks, page numbers).
"""

import json
import re

# A number with optional $ before it and an optional unit after it.
_NUMBER = re.compile(
    r"(?<![\w.\-/])(\$)?(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?"
    r"(?:\s*(%|percent\b|percentage points?\b|points?\b))?"
)


def _numbers_in_text(text: str):
    """(value, decimals, has_unit) for each number in free text."""
    for m in _NUMBER.finditer(text or ""):
        dollar, whole, frac, unit = m.groups()
        value = float(whole.replace(",", "") + (frac or ""))
        decimals = len(frac) - 1 if frac else 0
        yield value, decimals, bool(dollar or unit or "," in whole or frac), m.group(0).strip()


def _numbers_in_json(obj, out: set[float]) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        out.add(float(obj))
    elif isinstance(obj, str):
        out.update(v for v, *_ in _numbers_in_text(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _numbers_in_json(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _numbers_in_json(v, out)


def known_numbers(tool_texts: list[str], extra_texts: list[str] = ()) -> set[float]:
    """Every number the tools returned, also as a percentage when it looks like a share."""
    raw: set[float] = set()
    for t in tool_texts:
        try:
            _numbers_in_json(json.loads(t), raw)
        except (ValueError, TypeError):
            raw.update(v for v, *_ in _numbers_in_text(t))
    for t in extra_texts:
        raw.update(v for v, *_ in _numbers_in_text(t))
    out: set[float] = set()
    for v in raw:
        out.update({v, abs(v)})
        if abs(v) <= 1.5:  # shares, rates and relative differences, written as percentages
            out.update({v * 100, abs(v) * 100})
    return out


def _matches(value: float, decimals: int, known: set[float]) -> bool:
    tolerance = 0.5 * 10 ** -decimals + 1e-9
    return any(abs(k - value) <= tolerance for k in known)


def unverified_numbers(answer: str, tool_texts: list[str], extra_texts: list[str] = ()) -> list[str]:
    """Numbers in the answer that match nothing the tools returned (as written in the answer)."""
    # Remove labels that contain digits but are not figures.
    text = re.sub(r"\b(?:HD|SD)-\d+\b|\bDistrict \d+\b|\[[^\]]*\bS\d+[^\]]*\]|\b[A-Z]\d{4,6}[A-Z]?\b", " ", answer or "")
    known = known_numbers(tool_texts, extra_texts)
    found: list[str] = []
    for value, decimals, has_unit, shown in _numbers_in_text(text):
        if not has_unit and value == int(value) and (value <= 100 or 1900 <= value <= 2099):
            continue
        if not _matches(value, decimals, known) and shown not in found:
            found.append(shown)
    return found
