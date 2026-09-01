"""Allowlisted tests for native CSI CSO allow-list (CQ11)."""
from __future__ import annotations

from hc_report.evaluators.components_infra import _evaluate_csi_cso
from hc_report.kb_loader import load_kb


def _csi_driver_item(name: str) -> dict:
    return {"metadata": {"name": name}}


def _cso_crd(enum_names: list[str]) -> dict:
    return {
        "metadata": {"name": "clustercsidrivers.operator.openshift.io"},
        "spec": {"versions": [{"storage": True, "schema": {"enum": enum_names}}]},
    }


def _csi_cso_status(csidriver_data: dict, crds_data: dict) -> str:
    checks = _evaluate_csi_cso(csidriver_data, crds_data, "7.3", "Components")
    assert checks[0].check_id == "7.3.storage.csi_cso"
    return checks[0].status


def test_csi_cso_warning_when_nfs_outside_enum() -> None:
    csidriver_data = {"items": [_csi_driver_item("nfs.csi.k8s.io")]}
    crds_data = {"items": [_cso_crd(["ebs.csi.aws.com"])]}
    assert _csi_cso_status(csidriver_data, crds_data) == "WARNING"


def test_csi_cso_pass_when_all_in_enum() -> None:
    csidriver_data = {"items": [_csi_driver_item("ebs.csi.aws.com")]}
    crds_data = {"items": [_cso_crd(["ebs.csi.aws.com"])]}
    assert _csi_cso_status(csidriver_data, crds_data) == "PASS"


def test_csi_cso_skipped_when_enum_missing() -> None:
    csidriver_data = {"items": [_csi_driver_item("ebs.csi.aws.com")]}
    crds_data = {
        "items": [
            {
                "metadata": {"name": "clustercsidrivers.operator.openshift.io"},
                "spec": {},
            }
        ]
    }
    assert _csi_cso_status(csidriver_data, crds_data) == "SKIPPED"


def test_csi_alias_not_storage_csi() -> None:
    knowledge_base = load_kb()
    entry = knowledge_base.get_entry("7.3.tsr.3_9_5_csi_drivers")
    assert entry.content_from == "7.3.storage.csi_cso"
    assert entry.include_in_findings is False
