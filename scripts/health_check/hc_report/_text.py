"""Shared text-normalization helpers for TSR/CCX modules."""
from __future__ import annotations

import re

_CHECK_ID_PREFIX = "**Check ID:**"
_BACKTICK_VALUE = re.compile(r"`([^`]+)`")


def slugify(text: str) -> str:
    """Lowercase, strip non-alphanumeric, collapse underscores, cap at 120 chars."""
    text = re.sub(r"\s+", " ", text).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:120] or "unnamed"


def parse_check_ids_from_line(line: str) -> list[str]:
    """Extract backtick-delimited check_ids from a **Check ID:** markdown line.

    Returns an empty list when the line is not a Check ID line or contains
    no parseable identifiers.
    """
    if not line.startswith(_CHECK_ID_PREFIX):
        return []
    remainder = line[len(_CHECK_ID_PREFIX):]
    values = _BACKTICK_VALUE.findall(remainder)
    if values:
        return [value.strip() for value in values if value.strip()]
    leftover = remainder.strip()
    return [leftover] if leftover else []
