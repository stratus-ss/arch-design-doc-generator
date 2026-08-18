"""Public-contract tests for expensive slot-map extract vs skip decisions."""

from __future__ import annotations

import sys
from pathlib import Path

_DET_DIR = Path(__file__).resolve().parent.parent / "scripts" / "hld_lld" / "ai" / "deterministic"
if str(_DET_DIR) not in sys.path:
    sys.path.insert(0, str(_DET_DIR))

from slot_cache import build_fingerprint, decide_extraction  # noqa: E402


def test_decide_extracts_when_slot_map_missing() -> None:
    current = build_fingerprint({"ADR/a.md": "aaa"})
    decision = decide_extraction(slot_exists=False, force=False, stored=None, current=current)
    assert decision.action == "extract"
    assert decision.status == "missing"


def test_decide_skips_when_fingerprint_matches() -> None:
    current = build_fingerprint({"ADR/a.md": "aaa"})
    decision = decide_extraction(slot_exists=True, force=False, stored=current, current=current)
    assert decision.action == "skip"
    assert decision.status == "fresh"


def test_decide_extracts_when_input_hash_changes() -> None:
    stored = build_fingerprint({"ADR/a.md": "old"})
    current = build_fingerprint({"ADR/a.md": "new"})
    decision = decide_extraction(slot_exists=True, force=False, stored=stored, current=current)
    assert decision.action == "extract"
    assert decision.status == "stale"
    assert "ADR/a.md" in decision.changed


def test_decide_skips_untracked_existing_map() -> None:
    current = build_fingerprint({"ADR/a.md": "aaa"})
    decision = decide_extraction(slot_exists=True, force=False, stored=None, current=current)
    assert decision.action == "skip"
    assert decision.status == "untracked"


def test_decide_force_extracts_when_fresh() -> None:
    current = build_fingerprint({"ADR/a.md": "aaa"})
    decision = decide_extraction(slot_exists=True, force=True, stored=current, current=current)
    assert decision.action == "extract"
    assert decision.status == "forced"
