"""Allowlisted tests for native OLM failed CSV (CQ11)."""
from __future__ import annotations

from hc_report.evaluators.components import _evaluate_olm_failed_csv
from hc_report.kb_loader import load_kb


def _csv_item(name: str, phase: str) -> dict:
    return {"metadata": {"name": name}, "status": {"phase": phase}}


def _olm_failed_csv_status(csv_data: dict) -> str:
    checks = _evaluate_olm_failed_csv(csv_data, "7.3", "Components")
    assert checks[0].check_id == "7.3.olm.failed_csv"
    return checks[0].status


def test_olm_failed_csv_fail() -> None:
    csv_data = {"items": [_csv_item("broken.v1", "Failed")]}
    assert _olm_failed_csv_status(csv_data) == "FAIL"


def test_olm_succeeded_csv_pass() -> None:
    csv_data = {"items": [_csv_item("copied.v1", "Succeeded")]}
    assert _olm_failed_csv_status(csv_data) == "PASS"


def test_olm_replacing_csv_warning() -> None:
    csv_data = {"items": [_csv_item("rolling.v1", "Replacing")]}
    assert _olm_failed_csv_status(csv_data) == "WARNING"


def test_additional_operators_tsr_stays_on_co_platform() -> None:
    knowledge_base = load_kb()
    entry = knowledge_base.get_entry("7.3.tsr.3_2_2_additional_operators")
    assert entry.content_from == "7.3.co.platform"
