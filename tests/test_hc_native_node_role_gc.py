"""Public-contract tests for native node-role labels and image GC."""
from __future__ import annotations

from hc_report.evaluators.day2 import _evaluate_node_image_gc
from hc_report.evaluators.health import _evaluate_health_node_roles
from hc_report.kb_loader import load_kb


def test_node_roles_fails_when_label_missing() -> None:
    nodes_data = {
        "items": [
            {
                "metadata": {
                    "name": "worker-unlabeled",
                    "labels": {"kubernetes.io/hostname": "worker-unlabeled"},
                },
            },
        ],
    }
    checks = _evaluate_health_node_roles(nodes_data, "7.5", "Cluster Health")
    assert checks[0].status == "FAIL"


def test_image_gc_fails_when_used_at_or_above_high() -> None:
    image_gc_data = {
        "high_default_percent": 85,
        "early_warning_percent": 50,
        "members": [
            {
                "node": "worker-0",
                "high_percent": 85,
                "used_percent": 85,
            },
        ],
    }
    checks = _evaluate_node_image_gc(image_gc_data, "7.6", "Day-2")
    assert checks[0].status == "FAIL"
    assert checks[0].scoring_basis == "doc_backed"


def test_image_gc_warns_when_used_at_least_50_below_high() -> None:
    image_gc_data = {
        "members": [
            {
                "node": "worker-0",
                "high_percent": 85,
                "used_percent": 50,
            },
        ],
    }
    checks = _evaluate_node_image_gc(image_gc_data, "7.6", "Day-2")
    assert checks[0].status == "WARNING"


def test_image_gc_passes_when_all_below_50() -> None:
    image_gc_data = {
        "members": [
            {"node": "worker-0", "high_percent": 85, "used_percent": 30},
            {"node": "worker-1", "high_percent": 85, "used_percent": 49},
        ],
    }
    checks = _evaluate_node_image_gc(image_gc_data, "7.6", "Day-2")
    assert checks[0].status == "PASS"


def test_image_gc_root_error_is_info() -> None:
    image_gc_data = {"_hc_error": True, "members": []}
    checks = _evaluate_node_image_gc(image_gc_data, "7.6", "Day-2")
    assert checks[0].status == "INFO"


def test_image_gc_all_stats_missing_is_info() -> None:
    image_gc_data = {
        "members": [
            {"node": "worker-0", "_hc_error": True},
            {"node": "worker-1", "_hc_error": True},
        ],
    }
    checks = _evaluate_node_image_gc(image_gc_data, "7.6", "Day-2")
    assert checks[0].status == "INFO"


def test_tsr_node_role_gc_aliases_resolve_to_natives() -> None:
    knowledge_base = load_kb()
    node_role_alias = knowledge_base.get_entry("7.5.tsr.5_6_node_role_values")
    assert node_role_alias.content_from == "7.5.node_roles"
    assert node_role_alias.include_in_findings is False
    garbage_alias = knowledge_base.get_entry("7.6.tsr.6_1_5_5_node_garbage_collection")
    assert garbage_alias.content_from == "7.6.node.image_gc"
    assert garbage_alias.include_in_findings is False
