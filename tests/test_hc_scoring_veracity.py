"""Public-contract tests for scoring_veracity evaluator and report provenance."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from hc_report.cli import _write_outputs
from hc_report.evaluators._common import _evaluate_approval_strategy
from hc_report.evaluators.components_infra import _evaluate_etcd_aggregate
from hc_report.evaluators.components_network import _evaluate_net_config
from hc_report.evaluators.metrics import _evaluate_etcd_backend_commit, _evaluate_etcd_wal_fsync
from hc_report.evaluators.platform import (
    _evaluate_master_cpu,
    _evaluate_master_schedulable,
    _evaluate_system_security,
    _evaluate_worker_disk,
)
from hc_report.evaluators.topology import _NodeContext, _check_node_disk
from hc_report.models import CheckResult
from hc_report.renderer import _build_check_results_table


def _node(name: str, *, cpu: str = "8", memory: str = "32Gi", disk: str = "200Gi", roles: tuple[str, ...]) -> dict:
    labels = {f"node-role.kubernetes.io/{role}": "" for role in roles}
    return {
        "metadata": {"name": name, "labels": labels},
        "status": {
            "capacity": {"cpu": cpu, "memory": memory, "ephemeral-storage": disk},
            "nodeInfo": {},
        },
    }


def _dedicated_items() -> tuple[list[dict], list[dict]]:
    masters = [
        _node("master-0", roles=("master",)),
        _node("master-1", roles=("master",)),
        _node("master-2", roles=("master",)),
    ]
    worker = _node("worker-0", roles=("worker",))
    return masters + [worker], masters


def _compact_items() -> tuple[list[dict], list[dict]]:
    nodes = [
        _node("compact-0", roles=("master", "worker")),
        _node("compact-1", roles=("master", "worker")),
        _node("compact-2", roles=("master", "worker")),
    ]
    return nodes, nodes


def _prometheus_pod(pod_name: str, seconds: str) -> dict:
    return {
        "status": "success",
        "data": {"result": [{"metric": {"pod": pod_name}, "value": [0, seconds]}]},
    }


def test_master_schedulable_dedicated_true_is_warning() -> None:
    items, masters = _dedicated_items()
    scheduler = {"spec": {"mastersSchedulable": True}}
    checks = _evaluate_master_schedulable(scheduler, items, masters, "7.1", "Base")
    assert checks[0].status == "WARNING"
    assert checks[0].scoring_basis == "doc_backed"


def test_master_schedulable_compact_true_is_info() -> None:
    items, masters = _compact_items()
    scheduler = {"spec": {"mastersSchedulable": True}}
    checks = _evaluate_master_schedulable(scheduler, items, masters, "7.1", "Base")
    assert checks[0].status == "INFO"


def test_master_schedulable_compact_false_is_warning() -> None:
    items, masters = _compact_items()
    scheduler = {"spec": {"mastersSchedulable": False}}
    checks = _evaluate_master_schedulable(scheduler, items, masters, "7.1", "Base")
    assert checks[0].status == "WARNING"
    assert checks[0].scoring_basis == "doc_backed"


def test_fips_disabled_is_info() -> None:
    checks = _evaluate_system_security({}, "fips: false\n", "7.1", "Base")
    fips = next(check for check in checks if check.check_id == "7.1.sys.fips")
    assert fips.status == "INFO"


def test_featuregates_skipped_when_operators_present() -> None:
    category_data = {"cluster_operators": {"items": [{"metadata": {"name": "network"}}]}}
    checks = _evaluate_net_config(category_data, "7.3", "Components")
    featuregate = next(check for check in checks if check.check_id == "7.3.net.featuregates")
    assert featuregate.status == "SKIPPED"


def test_cnv_automatic_not_counted_in_approval_warning() -> None:
    subscriptions = [
        {
            "metadata": {"name": "kubevirt-hyperconverged"},
            "spec": {"installPlanApproval": "Automatic", "name": "kubevirt-hyperconverged"},
        }
    ]
    result = _evaluate_approval_strategy(subscriptions, "7.1", "Base", "7.1.subs.approval", "Approval")
    assert result.status == "PASS"


def test_non_cnv_automatic_is_warning() -> None:
    subscriptions = [
        {
            "metadata": {"name": "cluster-logging"},
            "spec": {"installPlanApproval": "Automatic", "name": "cluster-logging"},
        }
    ]
    result = _evaluate_approval_strategy(subscriptions, "7.1", "Base", "7.1.subs.approval", "Approval")
    assert result.status == "WARNING"
    assert result.scoring_basis == "engine_policy"


def test_seven_one_master_cpu_below_min_is_fail() -> None:
    masters = [_node("master-0", cpu="2", roles=("master",))]
    checks = _evaluate_master_cpu(masters, "7.1", "Base")
    assert checks[0].status == "FAIL"
    assert checks[0].scoring_basis == "doc_backed"


def test_seven_one_worker_disk_below_min_is_fail() -> None:
    workers = [_node("worker-0", disk="20Gi", roles=("worker",))]
    checks = _evaluate_worker_disk(workers, "7.1", "Base")
    assert checks[0].status == "FAIL"
    assert checks[0].scoring_basis == "doc_backed"


def test_seven_two_node_disk_below_min_is_fail() -> None:
    node_context = _NodeContext("7.2", "Topology", "worker-0", "worker-0", "7.2")
    capacity = {"ephemeral-storage": "20Gi"}
    result = _check_node_disk(capacity, node_context)
    assert result.status == "FAIL"
    assert result.scoring_basis == "doc_backed"


def test_wal_p99_above_ten_ms_is_fail() -> None:
    checks = _evaluate_etcd_wal_fsync(_prometheus_pod("etcd-0", "0.015"), "7.8", "Metrics")
    assert checks[0].status == "FAIL"
    assert checks[0].scoring_basis == "doc_backed"


def test_backend_p99_high_is_info() -> None:
    checks = _evaluate_etcd_backend_commit(_prometheus_pod("etcd-0", "0.060"), "7.8", "Metrics")
    assert checks[0].status == "INFO"


def test_etcd_native_has_no_skipped_placeholder_ids() -> None:
    checks = _evaluate_etcd_aggregate({}, {}, "7.3", "Components")
    placeholder_ids = [
        check.check_id for check in checks
        if "3_5_4" in check.check_id or "3_5_8" in check.check_id or "3_5_9" in check.check_id
    ]
    assert placeholder_ids == []


def test_fail_warning_render_scoring_row() -> None:
    fail_check = CheckResult(
        "7.1", "Base", "7.1.nodes.master_cpu", "CPU", "FAIL", "below min",
        scoring_basis="doc_backed",
    )
    rendered = _build_check_results_table([fail_check], "7.1")
    assert "| **Scoring** | Doc-backed |" in rendered
    info_check = CheckResult("7.1", "Base", "7.1.sys.fips", "FIPS", "INFO", "off")
    info_rendered = _build_check_results_table([info_check], "7.1")
    assert "**Scoring**" not in info_rendered


def test_audit_json_includes_scoring_basis(tmp_path: Path) -> None:
    check = CheckResult(
        "7.1", "Base", "7.1.nodes.master_cpu", "CPU", "FAIL", "below min",
        scoring_basis="doc_backed",
    )
    meta = {"cluster_name": "test-cluster", "client_prefix": "XX"}
    _write_outputs(tmp_path, "# report\n", meta, [check], [], Counter(), "core")
    audit_path = tmp_path / "XX_HC_audit_test-cluster.json"
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    assert payload["checks"][0]["scoring_basis"] == "doc_backed"
