"""Allowlisted tests for native registry and monitoring storage (CQ11)."""
from __future__ import annotations

from hc_report.evaluators.components import (
    _evaluate_monitoring_storage,
    _evaluate_registry_storage,
)
from hc_report.kb_loader import load_kb


def test_registry_storage_fails_on_emptydir_when_managed() -> None:
    registry_data = {
        "spec": {
            "managementState": "Managed",
            "storage": {"emptyDir": {}},
        },
    }
    checks = _evaluate_registry_storage(registry_data, "7.3", "Components")
    assert checks[0].status == "FAIL"
    assert checks[0].check_id == "7.3.registry.storage"
    assert checks[0].scoring_basis == "doc_backed"
    unknown_backend = {
        "spec": {
            "managementState": "Managed",
            "storage": {"hostPath": {}},
        },
    }
    unknown_checks = _evaluate_registry_storage(unknown_backend, "7.3", "Components")
    assert unknown_checks[0].status != "FAIL"


def test_registry_storage_removed_is_info() -> None:
    registry_data = {
        "spec": {
            "managementState": "Removed",
            "storage": {"emptyDir": {}},
        },
    }
    checks = _evaluate_registry_storage(registry_data, "7.3", "Components")
    assert checks[0].status == "INFO"
    assert checks[0].check_id == "7.3.registry.storage"


def test_monitoring_storage_fails_without_volume_claim() -> None:
    prometheus_data = {
        "items": [
            {
                "metadata": {"name": "k8s"},
                "spec": {"storage": {}},
            },
        ],
    }
    alertmanager_data = {
        "items": [
            {
                "metadata": {"name": "main"},
                "spec": {
                    "storage": {
                        "volumeClaimTemplate": {
                            "spec": {
                                "accessModes": ["ReadWriteOnce"],
                                "storageClassName": "gp3-csi",
                            },
                        },
                    },
                },
            },
        ],
    }
    storageclass_data = {
        "items": [
            {"metadata": {"name": "gp3-csi"}, "provisioner": "ebs.csi.aws.com"},
        ],
    }
    checks = _evaluate_monitoring_storage(
        prometheus_data, alertmanager_data, storageclass_data, "7.3", "Components",
    )
    assert checks[0].status == "FAIL"
    assert checks[0].check_id == "7.3.monitoring.storage"
    assert checks[0].scoring_basis == "doc_backed"


def test_monitoring_storage_warns_on_rwx() -> None:
    prometheus_data = {
        "items": [
            {
                "metadata": {"name": "k8s"},
                "spec": {
                    "storage": {
                        "volumeClaimTemplate": {
                            "spec": {
                                "accessModes": ["ReadWriteMany"],
                                "storageClassName": "gp3-csi",
                            },
                        },
                    },
                },
            },
        ],
    }
    alertmanager_data = {"items": []}
    storageclass_data = {
        "items": [
            {"metadata": {"name": "gp3-csi"}, "provisioner": "ebs.csi.aws.com"},
        ],
    }
    checks = _evaluate_monitoring_storage(
        prometheus_data, alertmanager_data, storageclass_data, "7.3", "Components",
    )
    assert checks[0].status == "WARNING"
    assert checks[0].check_id == "7.3.monitoring.storage"


def test_tsr_storage_aliases_resolve_to_natives() -> None:
    knowledge_base = load_kb()
    registry_alias = knowledge_base.get_entry("7.3.tsr.3_6_2_registry_storage_type")
    monitoring_alias = knowledge_base.get_entry("7.3.tsr.3_7_2_monitoring_storage_type")
    assert registry_alias.content_from == "7.3.registry.storage"
    assert registry_alias.include_in_findings is False
    assert monitoring_alias.content_from == "7.3.monitoring.storage"
    assert monitoring_alias.include_in_findings is False
