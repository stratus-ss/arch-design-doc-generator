"""Public-contract tests for Chapter 6 omit-by-check-id."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HEALTH_CHECK_ROOT = PROJECT_ROOT / "scripts" / "health_check"
if str(HEALTH_CHECK_ROOT) not in sys.path:
    sys.path.insert(0, str(HEALTH_CHECK_ROOT))

from hc_report.models import Finding
from hc_report.omit_findings import (
    apply_finding_omit,
    compact_finding_ids,
    load_omit_check_ids,
    pruned_report_path,
)


def _finding(
    finding_id: str,
    check_id: str,
    priority: str = "P3",
    member_check_ids: tuple[str, ...] = (),
) -> Finding:
    return Finding(
        id=finding_id,
        title="synthetic",
        priority=priority,
        description="desc",
        recommendation="rec",
        check_id=check_id,
        member_check_ids=member_check_ids,
    )


def test_load_omit_check_ids_skips_comments_and_blanks(tmp_path: Path) -> None:
    omit_file = tmp_path / "omit.txt"
    omit_file.write_text(
        "# Chapter 6 suppressions\n"
        "\n"
        "7.4.tsr.mtv\n"
        "  # indented comment\n"
        "7.4.tsr.mtv\n"
        "7.3.etcd\n",
        encoding="utf-8",
    )
    loaded = load_omit_check_ids(omit_file)
    assert loaded == ("7.4.tsr.mtv", "7.3.etcd")


def test_apply_finding_omit_drops_group_when_member_listed() -> None:
    grouped = _finding(
        "6.2.4.1",
        "7.4.a",
        member_check_ids=("7.4.a", "7.4.b"),
    )
    other = _finding("6.2.4.2", "7.3.keep")
    result = apply_finding_omit([grouped, other], ("7.4.b",))
    assert result.kept == [other]
    assert result.omitted_count == 1


def test_apply_finding_omit_reports_unmatched() -> None:
    finding = _finding("6.2.4.1", "7.3.keep")
    result = apply_finding_omit([finding], ("7.4.missing", "7.3.keep"))
    assert result.unmatched == ("7.4.missing",)
    assert result.kept == []


def test_compact_finding_ids_resequences_per_priority() -> None:
    first = _finding("6.2.4.2", "7.3.a")
    second = _finding("6.2.4.5", "7.3.b")
    compacted = compact_finding_ids([first, second])
    assert [finding.id for finding in compacted] == ["6.2.4.1", "6.2.4.2"]
    assert first.id == "6.2.4.2"
    assert second.id == "6.2.4.5"


def test_pruned_report_path_appends_suffix() -> None:
    original = Path("/tmp/Example_OpenShift_Health_Check_cluster.md")
    assert pruned_report_path(original) == Path(
        "/tmp/Example_OpenShift_Health_Check_cluster_pruned.md"
    )
