"""Allowlisted tests for native volume mount p99 (CQ11)."""
from __future__ import annotations

from hc_report.evaluators.health import _evaluate_volume_mount_p99
from hc_report.kb_loader import load_kb


def _prometheus_vector(*seconds: str) -> dict:
    results = [{"metric": {}, "value": [0, sample]} for sample in seconds]
    return {"status": "success", "data": {"result": results}}


def _mount_status(prometheus_data: dict) -> str:
    checks = _evaluate_volume_mount_p99(prometheus_data, "7.5", "Cluster Health")
    assert checks[0].check_id == "7.5.volume.mount_p99"
    return checks[0].status


def test_volume_mount_fail_over_10s() -> None:
    assert _mount_status(_prometheus_vector("11")) == "FAIL"


def test_volume_mount_warning_over_2s() -> None:
    assert _mount_status(_prometheus_vector("3")) == "WARNING"


def test_volume_mount_pass_under_2s() -> None:
    assert _mount_status(_prometheus_vector("1")) == "PASS"


def test_volume_mount_info_when_empty() -> None:
    empty_vector = {"status": "success", "data": {"result": []}}
    assert _mount_status(empty_vector) == "INFO"


def test_volume_mount_tsr_aliases() -> None:
    knowledge_base = load_kb()
    alias = knowledge_base.get_entry("7.5.tsr.5_10_volume_mount_durations")
    assert alias.content_from == "7.5.volume.mount_p99"
    assert alias.include_in_findings is False
