"""Public-contract tests for StorageProfile and VM-namespace quota natives."""
from __future__ import annotations

from hc_report.evaluators.layered_cnv import (
    _evaluate_cnv_storageprofile,
    _evaluate_cnv_vm_quota,
)
from hc_report.kb_loader import load_kb

_CATEGORY_ID = "7.4"
_CATEGORY_NAME = "Layered Products"
_HCO_PRESENT = {"items": [{"metadata": {"name": "kubevirt-hyperconverged"}}]}


def test_storageprofile_warning_when_clone_copy() -> None:
    storageprofile_data = {
        "items": [
            {
                "metadata": {"name": "ocs-storagecluster-ceph-rbd"},
                "status": {"cloneStrategy": "copy"},
            },
        ],
    }
    checks = _evaluate_cnv_storageprofile(
        storageprofile_data, _CATEGORY_ID, _CATEGORY_NAME,
    )
    assert checks[0].status == "WARNING"


def test_storageprofile_info_when_zero_items() -> None:
    checks = _evaluate_cnv_storageprofile(
        {"items": []}, _CATEGORY_ID, _CATEGORY_NAME,
    )
    assert checks[0].status == "INFO"


def test_vm_quota_info_when_vm_namespace_has_no_quota() -> None:
    vm_data = {
        "items": [
            {"metadata": {"name": "guest-1", "namespace": "vm-workloads"}},
        ],
    }
    checks = _evaluate_cnv_vm_quota(
        _HCO_PRESENT, vm_data, {"items": []}, _CATEGORY_ID, _CATEGORY_NAME,
    )
    assert checks[0].status == "INFO"


def test_vm_quota_warning_when_used_equals_hard() -> None:
    vm_data = {
        "items": [
            {"metadata": {"name": "guest-1", "namespace": "vm-workloads"}},
        ],
    }
    resourcequota_data = {
        "items": [
            {
                "metadata": {"name": "compute", "namespace": "vm-workloads"},
                "spec": {"hard": {"cpu": "4"}},
                "status": {"used": {"cpu": "4"}},
            },
        ],
    }
    checks = _evaluate_cnv_vm_quota(
        _HCO_PRESENT, vm_data, resourcequota_data, _CATEGORY_ID, _CATEGORY_NAME,
    )
    assert checks[0].status == "WARNING"


def test_remainder_aliases_and_not_rq() -> None:
    knowledge_base = load_kb()
    storage_profiles = knowledge_base.get_entry("7.4.tsr.4_8_3_1_1_storage_profiles")
    vm_quota = knowledge_base.get_entry("7.4.tsr.4_8_5_1_1_quota_and_resources")
    assert storage_profiles.content_from == "7.4.cnv.storageprofile"
    assert storage_profiles.include_in_findings is False
    assert vm_quota.content_from == "7.4.cnv.vm_quota"
    assert vm_quota.content_from != "7.6.rq"
    assert vm_quota.include_in_findings is False
