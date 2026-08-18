"""Public-contract tests for generic tier slot defaults."""

from __future__ import annotations

import sys
from pathlib import Path

_DET_DIR = Path(__file__).resolve().parent.parent / "scripts" / "hld_lld" / "ai" / "deterministic"
if str(_DET_DIR) not in sys.path:
    sys.path.insert(0, str(_DET_DIR))

from markdown_utils import apply_derived_slots  # noqa: E402


def test_empty_tier_slots_default_to_dc1_dc2_dc3() -> None:
    slots = apply_derived_slots({})
    assert slots["TIER_COUNT"] == "3"
    assert slots["TIER_PRIMARY"] == "DC1"
    assert slots["TIER_MIDDLE"] == "DC2"
    assert slots["TIER_EDGE"] == "DC3"
    assert slots["TIER_PRIMARY_LOWER"] == "dc1"
    assert slots["TIER_MIDDLE_LOWER"] == "dc2"
    assert slots["TIER_EDGE_LOWER"] == "dc3"


def test_extracted_tier_names_are_not_overwritten() -> None:
    slots = apply_derived_slots(
        {
            "TIER_PRIMARY": "DC",
            "TIER_MIDDLE": "Campus",
            "TIER_EDGE": "Branch",
        }
    )
    assert slots["TIER_COUNT"] == "3"
    assert slots["TIER_PRIMARY"] == "DC"
    assert slots["TIER_MIDDLE"] == "Campus"
    assert slots["TIER_EDGE"] == "Branch"
    assert slots["TIER_MIDDLE_LOWER"] == "campus"
    assert slots["TIER_EDGE_LOWER"] == "branch"


def test_tier_count_1_unused_match_primary() -> None:
    slots = apply_derived_slots(
        {
            "TIER_COUNT": "1",
            "TIER_PRIMARY": "DC",
            "TIER_MIDDLE": "Campus",
            "TIER_EDGE": "Branch",
        }
    )
    assert slots["TIER_PRIMARY"] == "DC"
    assert slots["TIER_MIDDLE"] == "same as DC"
    assert slots["TIER_EDGE"] == "same as DC"
    assert slots["TIER_MIDDLE_LOWER"] == "dc"
    assert slots["TIER_EDGE_LOWER"] == "dc"


def test_tier_count_2_edge_is_emdash() -> None:
    slots = apply_derived_slots(
        {
            "TIER_COUNT": "2",
            "TIER_PRIMARY": "DC",
            "TIER_MIDDLE": "Campus",
            "TIER_EDGE": "Branch",
        }
    )
    assert slots["TIER_PRIMARY"] == "DC"
    assert slots["TIER_MIDDLE"] == "Campus"
    assert slots["TIER_EDGE"] == "—"
    assert slots["TIER_MIDDLE_LOWER"] == "campus"
    assert slots["TIER_EDGE_LOWER"] == "na"
