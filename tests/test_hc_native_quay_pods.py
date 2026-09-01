"""Allowlisted tests for native Quay application pods (CQ11)."""
from __future__ import annotations

from hc_report.evaluators.layered import _evaluate_quay_pods
from hc_report.kb_loader import load_kb


def _registry_item(namespace: str, target_namespace: str = "") -> dict:
    spec = {}
    if target_namespace:
        spec["targetNamespace"] = target_namespace
    return {"metadata": {"namespace": namespace, "name": "registry"}, "spec": spec}


def _pod_item(
    name: str,
    namespace: str,
    phase: str = "Running",
    ready: bool = True,
) -> dict:
    return {
        "metadata": {"namespace": namespace, "name": name},
        "status": {
            "phase": phase,
            "containerStatuses": [{"name": "quay-app", "ready": ready}],
        },
    }


def _quay_pods_status(registry_data: dict, pods_data: dict) -> str:
    checks = _evaluate_quay_pods(
        registry_data, pods_data, "7.4", "Layered Products",
    )
    assert checks[0].check_id == "7.4.quay.pods"
    return checks[0].status


def test_quay_pods_na_when_no_registry() -> None:
    registry_data = {"_hc_not_found": True}
    pods_data = {"items": []}
    assert _quay_pods_status(registry_data, pods_data) == "NOT_APPLICABLE"


def test_quay_pods_fail_when_no_app_pod() -> None:
    registry_data = {"items": [_registry_item("quay-enterprise")]}
    pods_data = {
        "items": [
            _pod_item("quay-operator-abc", "quay-enterprise"),
        ],
    }
    assert _quay_pods_status(registry_data, pods_data) == "FAIL"


def test_quay_pods_pass_when_app_running() -> None:
    registry_data = {"items": [_registry_item("quay-enterprise")]}
    pods_data = {
        "items": [
            _pod_item("example-quay-app-abc", "quay-enterprise"),
        ],
    }
    assert _quay_pods_status(registry_data, pods_data) == "PASS"


def test_quay_pods_skipped_when_missing() -> None:
    registry_data = {"items": [_registry_item("quay-enterprise")]}
    assert _quay_pods_status(registry_data, {}) == "SKIPPED"


def test_quay_pod_tsr_aliases_native() -> None:
    knowledge_base = load_kb()
    first_alias = knowledge_base.get_entry("7.4.tsr.4_5_2_quay_pods")
    second_alias = knowledge_base.get_entry("7.4.tsr.4_5_4_1_quay_pods")
    native = knowledge_base.get_entry("7.4.quay.pods")
    assert first_alias.content_from == "7.4.quay.pods"
    assert second_alias.content_from == "7.4.quay.pods"
    assert first_alias.include_in_findings is False
    assert second_alias.include_in_findings is False
    assert native is not None
