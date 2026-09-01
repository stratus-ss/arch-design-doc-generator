"""Allowlisted tests for native etcd worksheets (CQ11)."""
from __future__ import annotations

from hc_report.evaluators.metrics import (
    _evaluate_etcd_compaction,
    _evaluate_etcd_disk_aggregate,
    _evaluate_etcd_heartbeat,
    _evaluate_etcd_log_errors,
)
from hc_report.kb_loader import load_kb


def _prometheus_vector(*samples: tuple[str, str]) -> dict:
    results = [
        {"metric": {"pod": pod_name}, "value": [0, seconds]}
        for pod_name, seconds in samples
    ]
    return {"status": "success", "data": {"result": results}}


def test_etcd_disk_aggregate_fails_when_any_wal_over_10ms() -> None:
    wal_fsync = _prometheus_vector(("etcd-0", "0.015"), ("etcd-1", "0.005"))
    checks = _evaluate_etcd_disk_aggregate(wal_fsync, "7.8", "Metrics")
    assert checks[0].status == "FAIL"
    assert checks[0].check_id == "7.8.etcd.disk"
    assert checks[0].scoring_basis == "doc_backed"


def test_etcd_log_errors_fail_when_phrase_count_positive() -> None:
    log_data = {
        "since": "6h",
        "members": [
            {"pod": "etcd-0", "heartbeat": 0, "timed_out": 0, "rafthttp": 1},
        ],
    }
    checks = _evaluate_etcd_log_errors(log_data, "7.8", "Metrics")
    assert checks[0].status == "FAIL"
    assert checks[0].check_id == "7.8.etcd.log_errors"


def test_etcd_compaction_missing_metric_is_info() -> None:
    checks = _evaluate_etcd_compaction({"_hc_error": True}, {}, "7.8", "Metrics")
    assert checks[0].status == "INFO"
    assert checks[0].check_id == "7.8.etcd.compaction"


def test_tsr_etcd_aliases_resolve_to_natives() -> None:
    knowledge_base = load_kb()
    disk_alias = knowledge_base.get_entry("7.3.tsr.3_5_8_1_etcd_disk_performance")
    compaction_alias = knowledge_base.get_entry("7.3.tsr.3_5_5_etcd_compaction")
    log_alias = knowledge_base.get_entry("7.3.tsr.3_5_7_etcd_log_errors")
    assert disk_alias.content_from == "7.8.etcd.disk"
    assert disk_alias.include_in_findings is False
    assert compaction_alias.content_from == "7.8.etcd.compaction"
    assert compaction_alias.include_in_findings is False
    assert log_alias.content_from == "7.8.etcd.log_errors"
    assert log_alias.include_in_findings is False


def test_etcd_disk_aggregate_passes_when_all_below_bar() -> None:
    wal_fsync = _prometheus_vector(("etcd-0", "0.005"), ("etcd-1", "0.008"))
    checks = _evaluate_etcd_disk_aggregate(wal_fsync, "7.8", "Metrics")
    assert checks[0].status == "PASS"
    assert checks[0].check_id == "7.8.etcd.disk"


def test_etcd_compaction_passes_when_below_200ms() -> None:
    compaction = _prometheus_vector(("etcd-0", "0.10"), ("etcd-1", "0.15"))
    checks = _evaluate_etcd_compaction(compaction, {}, "7.8", "Metrics")
    assert checks[0].status == "PASS"
    assert checks[0].check_id == "7.8.etcd.compaction"


def test_etcd_heartbeat_warning_when_increase_positive() -> None:
    heartbeat = _prometheus_vector(("etcd-0", "5"), ("etcd-1", "0"))
    checks = _evaluate_etcd_heartbeat(heartbeat, "7.8", "Metrics")
    assert checks[0].status == "WARNING"
    assert checks[0].check_id == "7.8.etcd.heartbeat"


def test_etcd_heartbeat_pass_when_increase_zero() -> None:
    heartbeat = _prometheus_vector(("etcd-0", "0"), ("etcd-1", "0"))
    checks = _evaluate_etcd_heartbeat(heartbeat, "7.8", "Metrics")
    assert checks[0].status == "PASS"
    assert checks[0].check_id == "7.8.etcd.heartbeat"


def test_etcd_heartbeat_info_when_metric_missing() -> None:
    checks = _evaluate_etcd_heartbeat({}, "7.8", "Metrics")
    assert checks[0].status == "INFO"
    assert checks[0].check_id == "7.8.etcd.heartbeat"
