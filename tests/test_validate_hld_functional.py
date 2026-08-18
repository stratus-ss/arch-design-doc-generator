"""Public-contract tests for validate-hld determinism hashing."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DET_DIR = Path(__file__).resolve().parent.parent / "scripts" / "hld_lld" / "ai" / "deterministic"
if str(_DET_DIR) not in sys.path:
    sys.path.insert(0, str(_DET_DIR))

import render  # noqa: E402


def _write_slot_map(path: Path, slots: dict) -> None:
    path.write_text(json.dumps({"slots": slots}) + "\n", encoding="utf-8")


def _run_validate(tmp_path: Path, *, text: str, slots: dict, state: dict | None, name: str = "phase1.md") -> int:
    target = tmp_path / name
    target.write_text(text, encoding="utf-8")
    contract = tmp_path / "contract.json"
    contract.write_text(json.dumps({"contracts": {}}) + "\n", encoding="utf-8")
    slots_path = tmp_path / "slots.json"
    _write_slot_map(slots_path, slots)
    state_path = tmp_path / "state.json"
    if state is not None:
        state_path.write_text(json.dumps(state) + "\n", encoding="utf-8")
    return render.run_validate_hld(
        [
            "--file",
            str(target),
            "--contract",
            str(contract),
            "--document-key",
            name,
            "--state-file",
            str(state_path),
            "--slots",
            str(slots_path),
        ]
    )


def test_validate_hld_allows_render_change_when_slot_map_changes(tmp_path: Path) -> None:
    assert _run_validate(tmp_path, text="hello\n", slots={"CLIENT": "A"}, state=None) == 0
    assert _run_validate(tmp_path, text="world\n", slots={"CLIENT": "B"}, state=None) == 0


def test_validate_hld_accepts_legacy_flat_state_after_reextract(tmp_path: Path) -> None:
    name = "Acme_OCP-V_HLD_DecisionJourney_phase1.md"
    legacy = {name: "0" * 64}
    assert _run_validate(tmp_path, text="new render\n", slots={"CLIENT": "Acme"}, state=legacy, name=name) == 0


def test_validate_hld_fails_when_same_slot_map_drifts(tmp_path: Path) -> None:
    assert _run_validate(tmp_path, text="hello\n", slots={"CLIENT": "A"}, state=None) == 0
    with pytest.raises(SystemExit) as exc:
        _run_validate(tmp_path, text="world\n", slots={"CLIENT": "A"}, state=None)
    assert exc.value.code == 1
