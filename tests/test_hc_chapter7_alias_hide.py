"""Public-contract tests: Chapter 7 omits content_from aliases."""
from __future__ import annotations

from hc_report.findings import derive_findings
from hc_report.models import CheckResult
from hc_report.renderer import _build_check_results_table

_NATIVE_CHECK_ID = "7.2.tsr.2_2_1_number_of_master_nodes"
_NATIVE_TITLE = "2.2.1. Number of Master Nodes"
_ALIAS_CHECK_ID = "7.2.tsr.2_2_high_availability"
_ALIAS_TITLE = "2.2. High Availability"


def _check(check_id: str, description: str) -> CheckResult:
    return CheckResult(
        category_id="7.2",
        category_name="Topology",
        check_id=check_id,
        description=description,
        status="FAIL",
        evidence="fixture evidence",
    )


def test_chapter7_omits_content_from_alias() -> None:
    table = _build_check_results_table(
        [_check(_ALIAS_CHECK_ID, _ALIAS_TITLE), _check(_NATIVE_CHECK_ID, _NATIVE_TITLE)],
        "7.2",
    )
    assert _ALIAS_TITLE not in table


def test_chapter7_keeps_native() -> None:
    table = _build_check_results_table(
        [_check(_NATIVE_CHECK_ID, _NATIVE_TITLE)],
        "7.2",
    )
    assert _NATIVE_TITLE in table


def test_chapter6_findings_unchanged_by_filter() -> None:
    native = _check(_NATIVE_CHECK_ID, _NATIVE_TITLE)
    alias = _check(_ALIAS_CHECK_ID, _ALIAS_TITLE)
    findings = derive_findings([native, alias])
    finding_check_ids = {finding.check_id for finding in findings}
    assert _NATIVE_CHECK_ID in finding_check_ids
