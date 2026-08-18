"""Public-contract tests for deterministic template rendering."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_DET_DIR = Path(__file__).resolve().parent.parent / "scripts" / "hld_lld" / "ai" / "deterministic"
if str(_DET_DIR) not in sys.path:
    sys.path.insert(0, str(_DET_DIR))

import render  # noqa: E402


def _write_slot_map(path: Path, slots: dict) -> None:
    path.write_text(json.dumps({"slots": slots}) + "\n", encoding="utf-8")


def test_render_preserves_shell_dollar_braces(tmp_path: Path) -> None:
    template = tmp_path / "tmpl.md"
    template.write_text("client={CLIENT}\nshell=${CLUSTER} ${API_VIP}\n", encoding="utf-8")
    slots_path = tmp_path / "slots.json"
    _write_slot_map(slots_path, {"CLIENT": "Acme"})
    out_path = tmp_path / "out.md"
    render.render_phase(template, slots_path, out_path)
    text = out_path.read_text(encoding="utf-8")
    assert "client=Acme" in text
    assert "${CLUSTER}" in text
    assert "${API_VIP}" in text


def test_render_fills_unprefixed_slots(tmp_path: Path) -> None:
    template = tmp_path / "tmpl.md"
    template.write_text("client={CLIENT}\n", encoding="utf-8")
    slots_path = tmp_path / "slots.json"
    _write_slot_map(slots_path, {"CLIENT": "Acme"})
    out_path = tmp_path / "out.md"
    render.render_phase(template, slots_path, out_path)
    text = out_path.read_text(encoding="utf-8")
    assert "client=Acme" in text
    assert "{CLIENT}" not in text


def test_render_empty_slot_is_tbd(tmp_path: Path) -> None:
    template = tmp_path / "tmpl.md"
    template.write_text("client={CLIENT}\n", encoding="utf-8")
    slots_path = tmp_path / "slots.json"
    _write_slot_map(slots_path, {"CLIENT": ""})
    out_path = tmp_path / "out.md"
    render.render_phase(template, slots_path, out_path)
    text = out_path.read_text(encoding="utf-8")
    assert "client={TBD}" in text
    assert "{CLIENT}" not in text
