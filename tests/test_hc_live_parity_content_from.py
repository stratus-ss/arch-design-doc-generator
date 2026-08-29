"""Public-contract tests for Plan 2c CONTENT_FROM aliases."""
from __future__ import annotations

import json
from pathlib import Path

from hc_report.kb_loader import load_kb

FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "hc_content_from_alias_map_sample.json"
)
IDENTIFICATION_CANONICAL = "7.4.tsr.4_8_1_1_1_identification_and_state"


def _sample_payload() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_production_kb_load_succeeds() -> None:
    knowledge_base = load_kb()
    assert knowledge_base.entries


def test_content_from_aliases_match_map_file() -> None:
    knowledge_base = load_kb()
    payload = _sample_payload()
    assert len(payload["apply_sample"]) >= 5
    for row in payload["apply_sample"]:
        alias_entry = knowledge_base.get_entry(row["alias_check_id"])
        assert alias_entry is not None
        assert alias_entry.content_from == row["canonical_check_id"]
        assert alias_entry.include_in_findings is False


def test_new_aliases_exclude_from_findings() -> None:
    knowledge_base = load_kb()
    payload = _sample_payload()
    alias_check_id = payload["apply_sample"][0]["alias_check_id"]
    alias_entry = knowledge_base.get_entry(alias_check_id)
    assert alias_entry is not None
    assert alias_entry.include_in_findings is False


def test_virt_leaves_not_all_identification_canonical() -> None:
    knowledge_base = load_kb()
    payload = _sample_payload()
    virt_rows = payload["virt_sample"]
    assert virt_rows
    targets = []
    for row in virt_rows:
        alias_entry = knowledge_base.get_entry(row["alias_check_id"])
        assert alias_entry is not None
        assert alias_entry.content_from == row["canonical_check_id"]
        targets.append(alias_entry.content_from)
    assert any(target.startswith("7.4.cnv.") for target in targets)
    assert not all(target == IDENTIFICATION_CANONICAL for target in targets)
