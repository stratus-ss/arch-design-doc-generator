"""Allowlisted tests for native ClusterVersion failed hops (CQ11)."""
from __future__ import annotations

from hc_report.evaluators.day2 import _evaluate_upgrade_failed_hops
from hc_report.kb_loader import load_kb


def _cluster_version_history(*states: str) -> dict:
    hops = []
    for index, state in enumerate(states):
        hops.append({"state": state, "version": f"4.18.{index}"})
    return {"kind": "ClusterVersion", "status": {"history": hops}}


def _failed_hops_status(cluster_version_raw: dict) -> str:
    checks = _evaluate_upgrade_failed_hops(cluster_version_raw, "7.6", "Day-2")
    assert checks[0].check_id == "7.6.upgrade.failed_hops"
    return checks[0].status


def test_failed_hops_fail_when_partial() -> None:
    assert _failed_hops_status(_cluster_version_history("Completed", "Partial")) == "FAIL"


def test_failed_hops_pass_when_all_completed() -> None:
    assert _failed_hops_status(_cluster_version_history("Completed", "Completed")) == "PASS"


def test_failed_hops_skipped_when_error() -> None:
    assert _failed_hops_status({"_hc_error": True}) == "SKIPPED"


def test_update_history_tsr_stays_on_upgrade_history() -> None:
    knowledge_base = load_kb()
    entry = knowledge_base.get_entry("7.6.tsr.6_2_1_update_history")
    assert entry.content_from == "7.6.upgrade.history"
    assert entry.content_from != "7.6.upgrade.failed_hops"
