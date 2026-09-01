"""Public-contract tests for 7.1/7.2 aliases and CoreDNS alerts."""
from __future__ import annotations

from hc_report.evaluators.platform import _evaluate_coredns_alerts
from hc_report.kb_loader import load_kb


def _coredns_status(alerts_data: dict) -> str:
    checks = _evaluate_coredns_alerts(alerts_data, "7.1", "Base Platform Checks")
    assert checks, "7.1.dns.coredns_alerts not emitted"
    return checks[0].status


def test_coredns_alerts_fail_when_coredns_errors_high_firing() -> None:
    alerts_data = {
        "data": {
            "alerts": [
                {"state": "firing", "labels": {"alertname": "CoreDNSErrorsHigh"}},
            ],
        },
    }
    assert _coredns_status(alerts_data) == "FAIL"


def test_coredns_alerts_pass_when_no_coredns_alerts() -> None:
    alerts_data = {"data": {"alerts": []}}
    assert _coredns_status(alerts_data) == "PASS"


def test_master_memory_alias_targets_native() -> None:
    knowledge_base = load_kb()
    alias = knowledge_base.get_entry("7.1.tsr.1_4_1_3_master_memory")
    assert alias.content_from == "7.1.nodes.master_mem"
    assert alias.include_in_findings is False


def test_auth_az_haproxy_aliases_target_natives() -> None:
    knowledge_base = load_kb()
    auth_alias = knowledge_base.get_entry("7.1.tsr.1_5_17_authentication")
    assert auth_alias.content_from == "7.1.sys.auth"
    assert auth_alias.include_in_findings is False
    az_alias = knowledge_base.get_entry("7.2.tsr.2_2_2_master_av_zone_labels")
    assert az_alias.content_from == "7.2.topo.master_az"
    assert az_alias.include_in_findings is False
    haproxy_alias = knowledge_base.get_entry("7.2.tsr.2_2_3_haproxy_ha")
    assert haproxy_alias.content_from == "7.2.topo.haproxy_ha"
    assert haproxy_alias.include_in_findings is False


def test_dns_tsr_and_coredns_ccx_alias_to_native() -> None:
    knowledge_base = load_kb()
    dns_alias = knowledge_base.get_entry("7.1.tsr.1_5_2_3_dns_alerts")
    assert dns_alias.content_from == "7.1.dns.coredns_alerts"
    assert dns_alias.include_in_findings is False
    ccx_alias = knowledge_base.get_entry("7.7.ccx_internal.high_core_dns_errors_high_alerts")
    assert ccx_alias.content_from == "7.1.dns.coredns_alerts"
    assert ccx_alias.include_in_findings is False


def test_unrelated_alert_aliases_not_coredns() -> None:
    knowledge_base = load_kb()
    etcd_alias = knowledge_base.get_entry("7.3.tsr.3_5_9_etcd_alerts")
    assert etcd_alias.content_from == "7.5.alerts.critical"
    assert etcd_alias.content_from != "7.1.dns.coredns_alerts"


def test_firewalls_tsr_aliases_overlay_not_sys_firewall() -> None:
    knowledge_base = load_kb()
    firewalls = knowledge_base.get_entry("7.1.tsr.1_5_5_firewalls")
    assert firewalls.content_from == "7.1.net.overlay_ports"
    assert firewalls.content_from != "7.1.sys.firewall"
    assert firewalls.include_in_findings is False
