"""Allowlisted tests for native node expected limits (CQ11)."""
from __future__ import annotations

from hc_report.evaluators.day2 import _evaluate_node_expected_limits
from hc_report.kb_loader import load_kb


def _prometheus_limits_vector(node_name: str, percent: str) -> dict:
    return {
        "status": "success",
        "data": {
            "result": [
                {"metric": {"node": node_name}, "value": [0, percent]},
            ],
        },
    }


def _expected_limits_status(cpu_data: dict, memory_data: dict) -> str:
    checks = _evaluate_node_expected_limits(
        cpu_data, memory_data, "7.6", "Day-2 Operations",
    )
    assert checks[0].check_id == "7.6.node.expected_limits"
    return checks[0].status


def test_expected_limits_fail_at_90() -> None:
    assert _expected_limits_status(
        {},
        _prometheus_limits_vector("worker-1", "90"),
    ) == "FAIL"


def test_expected_limits_warning_at_80() -> None:
    assert _expected_limits_status(
        _prometheus_limits_vector("worker-1", "80"),
        {},
    ) == "WARNING"


def test_expected_limits_pass_below_80() -> None:
    assert _expected_limits_status(
        _prometheus_limits_vector("worker-1", "50"),
        {},
    ) == "PASS"


def test_expected_limits_skipped_when_missing() -> None:
    assert _expected_limits_status({}, {}) == "SKIPPED"


def test_expected_limits_tsr_aliases() -> None:
    knowledge_base = load_kb()
    entry = knowledge_base.get_entry(
        "7.6.tsr.6_1_3_2_node_expected_resource_consumption",
    )
    assert entry.content_from == "7.6.node.expected_limits"
