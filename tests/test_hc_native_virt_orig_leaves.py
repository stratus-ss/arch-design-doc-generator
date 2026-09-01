"""Public-contract tests for native virt NNCP, virt-default StorageClass, and OADP."""
from __future__ import annotations

from hc_report.evaluators.layered import (
    _evaluate_cnv_nncp,
    _evaluate_cnv_virt_storageclass,
    _evaluate_oadp_state,
)
from hc_report.kb_loader import load_kb


def test_cnv_nncp_info_when_zero_policies() -> None:
    empty_list = {"items": []}
    checks = _evaluate_cnv_nncp(empty_list, empty_list, "7.4", "Layered Products")
    assert checks[0].status == "INFO"


def test_cnv_nncp_fails_when_enactment_not_available() -> None:
    nnce_data = {
        "items": [
            {
                "metadata": {"name": "br-ex-worker-0"},
                "status": {"conditions": [{"type": "Available", "status": "False"}]},
            },
        ],
    }
    checks = _evaluate_cnv_nncp({"items": []}, nnce_data, "7.4", "Layered Products")
    assert checks[0].status == "FAIL"


def test_virt_storageclass_na_when_cnv_missing() -> None:
    checks = _evaluate_cnv_virt_storageclass(
        {"_hc_not_found": True},
        {"items": []},
        {"items": []},
        "7.4",
        "Layered Products",
    )
    assert checks[0].status == "NOT_APPLICABLE"


def test_virt_storageclass_fails_when_cnv_and_zero_virt_default() -> None:
    hyperconverged_data = {"items": [{"metadata": {"name": "kubevirt-hyperconverged"}}]}
    storage_class_data = {
        "items": [
            {
                "metadata": {
                    "name": "gp3-csi",
                    "annotations": {"storageclass.kubernetes.io/is-default-class": "true"},
                },
            },
        ],
    }
    checks = _evaluate_cnv_virt_storageclass(
        hyperconverged_data,
        storage_class_data,
        {"items": []},
        "7.4",
        "Layered Products",
    )
    assert checks[0].status == "FAIL"


def test_oadp_na_when_no_resources() -> None:
    empty_list = {"items": []}
    checks = _evaluate_oadp_state(empty_list, empty_list, empty_list, "7.4", "Layered Products")
    assert checks[0].status == "NOT_APPLICABLE"


def test_oadp_fails_when_csv_not_succeeded() -> None:
    csv_data = {
        "items": [
            {
                "metadata": {"name": "oadp-operator", "namespace": "openshift-adp"},
                "status": {"phase": "Failed"},
            },
        ],
    }
    checks = _evaluate_oadp_state({"items": []}, csv_data, {"items": []}, "7.4", "Layered Products")
    assert checks[0].status == "FAIL"


def test_tsr_virt_orig_leaves_aliases_resolve() -> None:
    knowledge_base = load_kb()
    nncp_alias = knowledge_base.get_entry("7.4.tsr.4_8_2_2_1_2_network_configuration")
    virt_alias = knowledge_base.get_entry("7.4.tsr.4_8_1_3_4_node_disk")
    oadp_alias = knowledge_base.get_entry("7.4.tsr.4_8_5_3_1_oadp_operator")
    parent_alias = knowledge_base.get_entry("7.4.tsr.4_8_1_4_node_disk")
    assert nncp_alias.content_from == "7.4.cnv.nncp"
    assert nncp_alias.include_in_findings is False
    assert virt_alias.content_from == "7.4.cnv.virt_storageclass"
    assert virt_alias.include_in_findings is False
    assert oadp_alias.content_from == "7.4.oadp.state"
    assert oadp_alias.include_in_findings is False
    assert parent_alias.content_from == "7.4.cnv.state"
