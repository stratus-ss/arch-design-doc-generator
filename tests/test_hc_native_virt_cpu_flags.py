"""Public-contract tests for native virt CPU flags."""
from __future__ import annotations

from hc_report.evaluators.layered_cnv import _evaluate_cnv_cpu_virt_flag
from hc_report.kb_loader import load_kb

_CATEGORY_ID = "7.4"
_CATEGORY_NAME = "Layered Products"
_HCO_PRESENT = {"items": [{"metadata": {"name": "kubevirt-hyperconverged"}}]}
_HCO_MISSING = {"_hc_not_found": True}


def test_cpu_virt_flag_pass_when_svm() -> None:
    nodes_data = {
        "items": [
            {
                "metadata": {
                    "name": "worker-0",
                    "labels": {"cpu-feature.node.kubevirt.io/svm": "true"},
                },
            },
        ],
    }
    checks = _evaluate_cnv_cpu_virt_flag(
        nodes_data, _HCO_PRESENT, _CATEGORY_ID, _CATEGORY_NAME,
    )
    assert checks[0].status == "PASS"


def test_cpu_virt_flag_warning_when_no_labels() -> None:
    nodes_data = {
        "items": [
            {"metadata": {"name": "worker-0", "labels": {}}},
        ],
    }
    checks = _evaluate_cnv_cpu_virt_flag(
        nodes_data, _HCO_PRESENT, _CATEGORY_ID, _CATEGORY_NAME,
    )
    assert checks[0].status == "WARNING"


def test_cpu_virt_flag_na_when_hco_missing() -> None:
    nodes_data = {
        "items": [
            {
                "metadata": {
                    "name": "worker-0",
                    "labels": {"cpu-feature.node.kubevirt.io/svm": "true"},
                },
            },
        ],
    }
    checks = _evaluate_cnv_cpu_virt_flag(
        nodes_data, _HCO_MISSING, _CATEGORY_ID, _CATEGORY_NAME,
    )
    assert checks[0].status == "NOT_APPLICABLE"


def test_node_cpu_tsr_stays_on_cnv_state() -> None:
    knowledge_base = load_kb()
    node_cpu = knowledge_base.get_entry("7.4.tsr.4_8_1_3_2_node_cpu")
    native = knowledge_base.get_entry("7.4.cnv.cpu_virt_flag")
    assert node_cpu.content_from == "7.4.cnv.state"
    assert native is not None
