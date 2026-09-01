"""Allowlisted tests for native etcd fragment-ratio rollup (CQ11)."""
from __future__ import annotations

from hc_report.evaluators.metrics import _evaluate_etcd_defrag
from hc_report.kb_loader import load_kb


def _prometheus_vector(*samples: tuple[str, str]) -> dict:
    results = [
        {"metric": {"pod": pod_name}, "value": [0, byte_count]}
        for pod_name, byte_count in samples
    ]
    return {"status": "success", "data": {"result": results}}


def _defrag_status(db_size: dict, db_used: dict) -> str:
    checks = _evaluate_etcd_defrag(db_size, db_used, "7.8", "Metrics")
    assert checks[0].check_id == "7.8.etcd.defrag"
    return checks[0].status


def test_etcd_defrag_fail_at_70() -> None:
    db_size = _prometheus_vector(("etcd-0", "100"), ("etcd-1", "100"))
    db_used = _prometheus_vector(("etcd-0", "30"), ("etcd-1", "90"))
    assert _defrag_status(db_size, db_used) == "FAIL"


def test_etcd_defrag_warning_at_50() -> None:
    db_size = _prometheus_vector(("etcd-0", "100"), ("etcd-1", "100"))
    db_used = _prometheus_vector(("etcd-0", "50"), ("etcd-1", "90"))
    assert _defrag_status(db_size, db_used) == "WARNING"


def test_etcd_defrag_pass_low_ratio() -> None:
    db_size = _prometheus_vector(("etcd-0", "100"), ("etcd-1", "100"))
    db_used = _prometheus_vector(("etcd-0", "90"), ("etcd-1", "95"))
    assert _defrag_status(db_size, db_used) == "PASS"


def test_etcd_defrag_info_when_empty() -> None:
    empty = {"status": "success", "data": {"result": []}}
    assert _defrag_status(empty, empty) == "INFO"


def test_etcd_defrag_tsr_aliases() -> None:
    knowledge_base = load_kb()
    alias = knowledge_base.get_entry("7.3.tsr.3_5_6_etcd_defragmentation")
    native = knowledge_base.get_entry("7.8.etcd.defrag")
    assert alias.content_from == "7.8.etcd.defrag"
    assert alias.include_in_findings is False
    assert native is not None
