"""Public-contract tests for overlay-port posture and firewalls TSR alias."""
from __future__ import annotations

from hc_report.evaluators.platform import _evaluate_overlay_ports
from hc_report.kb_loader import load_kb


def _overlay_status(network_data: dict) -> str:
    checks = _evaluate_overlay_ports(network_data, "7.1", "Base Platform Checks")
    assert checks, "7.1.net.overlay_ports not emitted"
    return checks[0].status


def test_overlay_ports_pass_when_ovn() -> None:
    network_data = {"spec": {"networkType": "OVNKubernetes"}}
    assert _overlay_status(network_data) == "PASS"


def test_overlay_ports_warning_when_sdn() -> None:
    network_data = {"spec": {"networkType": "OpenShiftSDN"}}
    assert _overlay_status(network_data) == "WARNING"


def test_overlay_ports_skipped_when_error() -> None:
    network_data = {"_hc_error": True}
    assert _overlay_status(network_data) == "SKIPPED"


def test_overlay_ports_not_applicable_when_missing() -> None:
    assert _overlay_status({}) == "NOT_APPLICABLE"


def test_overlay_ports_info_when_other_cni() -> None:
    network_data = {"spec": {"networkType": "Cilium"}}
    assert _overlay_status(network_data) == "INFO"


def test_firewall_alias_not_sys_firewall() -> None:
    knowledge_base = load_kb()
    firewalls = knowledge_base.get_entry("7.1.tsr.1_5_5_firewalls")
    assert firewalls.content_from == "7.1.net.overlay_ports"
    assert firewalls.content_from != "7.1.sys.firewall"
    assert firewalls.include_in_findings is False
