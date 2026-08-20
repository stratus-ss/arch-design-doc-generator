"""Shared text-normalization helpers for TSR/CCX modules."""
from __future__ import annotations

import re


def slugify(text: str) -> str:
    """Lowercase, strip non-alphanumeric, collapse underscores, cap at 120 chars."""
    text = re.sub(r"\s+", " ", text).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:120] or "unnamed"
