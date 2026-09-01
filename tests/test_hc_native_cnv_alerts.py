"""Allowlisted tests for native CNV firing alerts (CQ11)."""
from __future__ import annotations

from hc_report.evaluators.layered_cnv import _evaluate_cnv_alerts
from hc_report.kb_loader import load_kb


def _alerts_payload(alerts: list[dict]) -> dict:
    return {"data": {"alerts": alerts}}


def _cnv_alerts_status(alerts_data: dict) -> str:
    checks = _evaluate_cnv_alerts(alerts_data, "7.4", "Layered Products")
    assert checks[0].check_id == "7.4.cnv.alerts"
    return checks[0].status


def test_cnv_alerts_fail_when_kubevirt_firing() -> None:
    assert _cnv_alerts_status(_alerts_payload([
        {
            "state": "firing",
            "labels": {"alertname": "KubeVirtVMINotRunning", "namespace": "default"},
        },
    ])) == "FAIL"


def test_cnv_alerts_pass_when_only_platform_alerts() -> None:
    assert _cnv_alerts_status(_alerts_payload([
        {
            "state": "firing",
            "labels": {"alertname": "CPUThrottlingHigh", "namespace": "openshift-monitoring"},
        },
    ])) == "PASS"


def test_cnv_alerts_pass_when_none() -> None:
    assert _cnv_alerts_status(_alerts_payload([])) == "PASS"


def test_cnv_alerts_skipped_when_missing() -> None:
    assert _cnv_alerts_status({}) == "SKIPPED"


def test_cnv_alerts_tsr_aliases() -> None:
    knowledge_base = load_kb()
    entry = knowledge_base.get_entry("7.4.tsr.4_8_5_2_1_active_alerts")
    assert entry.content_from == "7.4.cnv.alerts"
