"""Public-contract tests for native virt P3 leaves and parked TSR rows."""
from __future__ import annotations

from hc_report.evaluators.layered_cnv import evaluate_cnv_p3
from hc_report.kb_loader import load_kb

_CATEGORY_ID = "7.4"
_CATEGORY_NAME = "Layered Products"
_HCO_PRESENT = {"items": [{"metadata": {"name": "kubevirt-hyperconverged"}}]}


def _status_for(checks: list, check_id: str) -> str:
    return next(check.status for check in checks if check.check_id == check_id)


def _evaluate_p3(
    *,
    hyperconverged=None,
    csv_data=None,
    subscriptions=None,
    nodes=None,
    nad=None,
    vm_data=None,
    vmi_data=None,
    pods=None,
    cdi_data=None,
    daemonset=None,
):
    category_data = {
        "cnv_hyperconverged": hyperconverged if hyperconverged is not None else _HCO_PRESENT,
        "cnv_vm": vm_data if vm_data is not None else {},
        "cnv_vmi": vmi_data if vmi_data is not None else {},
        "cnv_pods": pods if pods is not None else {},
        "cnv_cdi": cdi_data if cdi_data is not None else {},
        "cnv_virt_handler_ds": daemonset if daemonset is not None else {},
    }
    results = {
        "03_base_platform": {
            "csv": csv_data if csv_data is not None else {},
            "subscriptions": subscriptions if subscriptions is not None else {},
            "nodes": nodes if nodes is not None else {},
        },
        "05_components": {
            "net_attach_def": nad if nad is not None else {},
        },
    }
    return evaluate_cnv_p3(category_data, results, _CATEGORY_ID, _CATEGORY_NAME)


def test_cnv_subscription_fails_when_not_at_latest() -> None:
    subscriptions = {
        "items": [
            {
                "metadata": {"name": "kubevirt-hyperconverged", "namespace": "openshift-cnv"},
                "spec": {"name": "kubevirt-hyperconverged"},
                "status": {
                    "state": "UpgradePending",
                    "installedCSV": "kubevirt-hyperconverged-operator.v4.18.0",
                    "currentCSV": "kubevirt-hyperconverged-operator.v4.18.1",
                },
            },
        ],
    }
    checks = _evaluate_p3(subscriptions=subscriptions)
    assert _status_for(checks, "7.4.cnv.subscription") == "FAIL"


def test_cnv_subscription_na_when_hco_missing() -> None:
    checks = _evaluate_p3(hyperconverged={"_hc_not_found": True})
    assert _status_for(checks, "7.4.cnv.subscription") == "NOT_APPLICABLE"


def test_cnv_nmstate_csv_na_when_namespace_empty() -> None:
    csv_data = {
        "items": [
            {
                "metadata": {"name": "other", "namespace": "openshift-operators"},
                "status": {"phase": "Succeeded"},
            },
        ],
    }
    checks = _evaluate_p3(csv_data=csv_data)
    assert _status_for(checks, "7.4.cnv.nmstate_csv") == "NOT_APPLICABLE"


def test_cnv_sriov_csv_fails_when_phase_not_succeeded() -> None:
    csv_data = {
        "items": [
            {
                "metadata": {
                    "name": "sriov-network-operator",
                    "namespace": "openshift-sriov-network-operator",
                },
                "status": {"phase": "Failed"},
            },
        ],
    }
    checks = _evaluate_p3(csv_data=csv_data)
    assert _status_for(checks, "7.4.cnv.sriov_csv") == "FAIL"


def test_cnv_run_strategy_info_when_not_always() -> None:
    vm_data = {
        "items": [
            {
                "metadata": {"name": "guest-1"},
                "spec": {"runStrategy": "Manual"},
            },
        ],
    }
    checks = _evaluate_p3(vm_data=vm_data)
    assert _status_for(checks, "7.4.cnv.run_strategy") == "INFO"


def test_cnv_vmi_phase_warning_when_failed() -> None:
    vmi_data = {
        "items": [
            {
                "metadata": {"name": "guest-1"},
                "status": {"phase": "Failed"},
            },
        ],
    }
    checks = _evaluate_p3(vmi_data=vmi_data)
    assert _status_for(checks, "7.4.cnv.vmi_phase") == "WARNING"


def test_cnv_migration_network_fails_when_named_nad_missing() -> None:
    hyperconverged = {
        "items": [
            {
                "metadata": {"name": "kubevirt-hyperconverged"},
                "spec": {"liveMigrationConfig": {"network": "migration"}},
            },
        ],
    }
    checks = _evaluate_p3(hyperconverged=hyperconverged, nad={"items": []})
    assert _status_for(checks, "7.4.cnv.migration_network") == "FAIL"


def test_cnv_linux_bridge_info_when_no_bridge_type() -> None:
    nad = {
        "items": [
            {
                "metadata": {"name": "macvlan0", "namespace": "default"},
                "spec": {"config": '{"type": "macvlan"}'},
            },
        ],
    }
    checks = _evaluate_p3(nad=nad)
    assert _status_for(checks, "7.4.cnv.linux_bridge") == "INFO"


def test_cnv_node_placement_fails_when_handler_not_ready() -> None:
    daemonset = {
        "items": [
            {
                "metadata": {"name": "virt-handler"},
                "status": {"numberReady": 1, "desiredNumberScheduled": 2},
            },
        ],
    }
    checks = _evaluate_p3(daemonset=daemonset)
    assert _status_for(checks, "7.4.cnv.node_placement") == "FAIL"


def test_cnv_node_placement_warning_when_worker_not_schedulable() -> None:
    daemonset = {
        "items": [
            {
                "metadata": {"name": "virt-handler"},
                "status": {"numberReady": 1, "desiredNumberScheduled": 1},
            },
        ],
    }
    nodes = {
        "items": [
            {
                "metadata": {
                    "name": "master-0",
                    "labels": {"node-role.kubernetes.io/control-plane": ""},
                },
            },
            {
                "metadata": {
                    "name": "worker-0",
                    "labels": {"node-role.kubernetes.io/worker": ""},
                },
            },
        ],
    }
    checks = _evaluate_p3(daemonset=daemonset, nodes=nodes)
    assert _status_for(checks, "7.4.cnv.node_placement") == "WARNING"


def test_cnv_cdi_na_when_cr_missing() -> None:
    checks = _evaluate_p3(cdi_data={"_hc_not_found": True})
    assert _status_for(checks, "7.4.cnv.cdi") == "NOT_APPLICABLE"


def test_cnv_cdi_fails_when_degraded() -> None:
    cdi_data = {
        "items": [
            {
                "metadata": {"name": "cdi"},
                "status": {
                    "conditions": [
                        {"type": "Available", "status": "True"},
                        {"type": "Progressing", "status": "False"},
                        {"type": "Degraded", "status": "True"},
                    ],
                },
            },
        ],
    }
    checks = _evaluate_p3(cdi_data=cdi_data)
    assert _status_for(checks, "7.4.cnv.cdi") == "FAIL"


def test_virt_p3_aliases_and_parks() -> None:
    knowledge_base = load_kb()
    alias_map = {
        "7.4.tsr.4_8_1_1_2_related_subscriptions": "7.4.cnv.subscription",
        "7.4.tsr.4_8_1_5_1_1_cnv_operators_node_placement": "7.4.cnv.node_placement",
        "7.4.tsr.4_8_1_5_1_5_vm_run_strategy_and_availability": "7.4.cnv.run_strategy",
        "7.4.tsr.4_8_2_1_1_3_live_migration_network_readiness": "7.4.cnv.migration_network",
        "7.4.tsr.4_8_3_2_1_nmstate_operator": "7.4.cnv.nmstate_csv",
        "7.4.tsr.4_8_3_2_2_sr_iov_operator": "7.4.cnv.sriov_csv",
        "7.4.tsr.4_8_3_2_3_linux_bridge_network": "7.4.cnv.linux_bridge",
        "7.4.tsr.4_8_5_2_3_cnv_vmi_readiness_prometheus": "7.4.cnv.vmi_phase",
        "7.4.tsr.4_8_5_3_5_cdi_image_upload_posture": "7.4.cnv.cdi",
    }
    for orig_check_id, native_id in alias_map.items():
        entry = knowledge_base.get_entry(orig_check_id)
        assert entry.content_from == native_id
        assert entry.include_in_findings is False
