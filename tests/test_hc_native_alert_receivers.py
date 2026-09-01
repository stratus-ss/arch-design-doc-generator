"""Allowlisted tests for native Alertmanager receivers (CQ11)."""
from __future__ import annotations

from hc_report.evaluators.day2 import _evaluate_alert_receivers
from hc_report.kb_loader import load_kb


def _alert_receivers_status(receivers_data: dict) -> str:
    checks = _evaluate_alert_receivers(receivers_data, "7.6", "Day-2 Operations")
    assert checks[0].check_id == "7.6.alert_receivers"
    return checks[0].status


def test_alert_receivers_fail_when_empty() -> None:
    assert _alert_receivers_status({"receiver_names": []}) == "FAIL"


def test_alert_receivers_fail_when_only_ignored() -> None:
    assert _alert_receivers_status({
        "receiver_names": ["null", "Default", "default", "Watchdog", "watchdog"],
    }) == "FAIL"


def test_alert_receivers_pass_when_named() -> None:
    assert _alert_receivers_status({
        "receiver_names": ["pagerduty-prod"],
    }) == "PASS"


def test_alert_receivers_skipped_when_missing() -> None:
    assert _alert_receivers_status({}) == "SKIPPED"


def test_alert_receivers_tsr_aliases_native() -> None:
    knowledge_base = load_kb()
    entry = knowledge_base.get_entry("7.6.tsr.6_3_2_alert_receivers")
    assert entry.content_from == "7.6.alert_receivers"
