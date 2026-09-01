"""Allowlisted tests for the frozen native KB voice list (CQ11)."""
from __future__ import annotations

from pathlib import Path

import pytest

from hc_report.kb_loader import INHERITED_CONTENT_FIELDS, load_kb

REPO_ROOT = Path(__file__).resolve().parents[1]
STUBS_PATH = REPO_ROOT / "tmp" / "hc_kb_live_parity_narratives" / "STUBS.txt"
KB_DIRECTORY = REPO_ROOT / "scripts" / "health_check" / "hc_report" / "kb"


def _frozen_check_ids() -> list[str]:
    lines = STUBS_PATH.read_text(encoding="utf-8").splitlines()
    check_ids: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        check_ids.append(stripped)
    return check_ids


def test_frozen_stubs_have_description() -> None:
    frozen_check_ids = _frozen_check_ids()
    if not frozen_check_ids:
        pytest.skip("empty freeze list — no stubs to verify")
    knowledge_base = load_kb()
    for check_id in frozen_check_ids:
        entry = knowledge_base.get_entry(check_id)
        assert entry is not None
        assert entry.content_from == ""
        assert len(entry.description.strip()) >= 40


def test_aliases_untouched() -> None:
    frozen_check_ids = set(_frozen_check_ids())
    if not frozen_check_ids:
        pytest.skip("empty freeze list — no alias overlap to check")
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib
    for toml_path in sorted(KB_DIRECTORY.glob("7_*.toml")):
        with toml_path.open("rb") as toml_file:
            payload = tomllib.load(toml_file)
        for row in payload.get("checks", []):
            if not isinstance(row, dict):
                continue
            content_from = str(row.get("content_from", "")).strip()
            if not content_from:
                continue
            check_id = str(row.get("check_id", "")).strip()
            if check_id not in frozen_check_ids and content_from not in frozen_check_ids:
                continue
            for field_name in INHERITED_CONTENT_FIELDS:
                assert field_name not in row, f"{toml_path.name} {check_id} overlays {field_name}"
