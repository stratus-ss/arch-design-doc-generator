"""Public-contract tests for 7.3 aliases and platform-operator rollup."""
from __future__ import annotations

from hc_report.evaluators.components import _evaluate_cluster_operators
from hc_report.kb_loader import load_kb

_PLATFORM_OPERATOR_ALIAS_IDS = (
    "7.3.tsr.3_2_1_platform_operators",
    "7.3.tsr.3_2_operators",
    "7.3.tsr.3_2_2_additional_operators",
    "7.7.ccx_internal.uninstalled_operators_with_leftover_resources",
)


def _operator_item(
    name: str, *, available: str, degraded: str, progressing: str,
) -> dict:
    return {
        "metadata": {"name": name},
        "status": {
            "conditions": [
                {"type": "Available", "status": available},
                {"type": "Degraded", "status": degraded, "message": "degraded"},
                {"type": "Progressing", "status": progressing},
            ]
        },
    }


def _platform_rollup(checks):
    match = next(
        (check for check in checks if check.check_id == "7.3.co.platform"),
        None,
    )
    assert match is not None, "7.3.co.platform not found in check list"
    return match


def test_platform_operators_rollup_fails_when_any_co_degraded() -> None:
    cluster_operators = {
        "items": [
            _operator_item(
                "authentication",
                available="True",
                degraded="True",
                progressing="False",
            ),
            _operator_item(
                "console",
                available="True",
                degraded="False",
                progressing="False",
            ),
        ]
    }
    checks = _evaluate_cluster_operators(
        cluster_operators, "7.3", "Component Checks",
    )
    assert _platform_rollup(checks).status == "FAIL"


def test_platform_operators_rollup_pass_when_all_co_healthy() -> None:
    cluster_operators = {
        "items": [
            _operator_item(
                "authentication",
                available="True",
                degraded="False",
                progressing="False",
            ),
        ]
    }
    checks = _evaluate_cluster_operators(
        cluster_operators, "7.3", "Component Checks",
    )
    assert _platform_rollup(checks).status == "PASS"


def test_platform_operators_rollup_na_when_co_missing() -> None:
    checks = _evaluate_cluster_operators({}, "7.3", "Component Checks")
    rollup = _platform_rollup(checks)
    assert rollup.status == "NOT_APPLICABLE"


def test_platform_operator_aliases_target_native() -> None:
    knowledge_base = load_kb()
    for check_id in _PLATFORM_OPERATOR_ALIAS_IDS:
        entry = knowledge_base.get_entry(check_id)
        assert entry.content_from == "7.3.co.platform"
        assert entry.include_in_findings is False


def test_crd_tsr_aliases_to_crds_not_operators() -> None:
    knowledge_base = load_kb()
    entry = knowledge_base.get_entry("7.3.tsr.3_3_custom_resource_definitions")
    assert entry.content_from == "7.3.crds"
    assert entry.include_in_findings is False


def test_ingress_sharding_alias_targets_native() -> None:
    knowledge_base = load_kb()
    entry = knowledge_base.get_entry("7.3.tsr.3_8_3_ingress_sharding")
    assert entry.content_from == "7.3.ingress.sharding"
    assert entry.include_in_findings is False


def test_mcp_and_5_2_alias_to_misc_mcp() -> None:
    knowledge_base = load_kb()
    mcp_alias = knowledge_base.get_entry("7.3.tsr.3_15_machine_config_pool")
    hop = knowledge_base.get_entry("7.5.tsr.5_2_machine_config")
    assert mcp_alias.content_from == "7.3.misc.mcp"
    assert hop.content_from == "7.3.misc.mcp"
    assert mcp_alias.include_in_findings is False
    assert hop.include_in_findings is False


def test_csi_tsr_aliases_csi_cso() -> None:
    knowledge_base = load_kb()
    entry = knowledge_base.get_entry("7.3.tsr.3_9_5_csi_drivers")
    assert entry.content_from == "7.3.storage.csi_cso"
    assert entry.include_in_findings is False
