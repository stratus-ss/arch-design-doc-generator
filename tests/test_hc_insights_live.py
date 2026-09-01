"""Allowlisted tests for Insights CCX CVE ingest bars (CQ11)."""
from __future__ import annotations

from hc_report.evaluators.ccx import CCX_STATIC_CHECK_IDS, evaluate_ccx
from hc_report.models import CheckResult

PRIMARY_CVE_ID = "7.7.ccx_external.cve_2026_31431_copy_fail_in_algif_aead"


def _primary_cve(results: dict) -> CheckResult:
    checks = evaluate_ccx(results)
    return next(check for check in checks if check.check_id == PRIMARY_CVE_ID)


def test_ccx_na_when_insights_disabled() -> None:
    results = {
        "03_base_platform": {
            "insightsoperator": {
                "items": [{"spec": {"disabled": True}}],
            }
        }
    }
    all_checks = evaluate_ccx(results)
    check = next(row for row in all_checks if row.check_id == PRIMARY_CVE_ID)
    assert check.status == "NOT_APPLICABLE"
    assert all(row.status == "NOT_APPLICABLE" for row in all_checks)
    assert len(all_checks) == len(CCX_STATIC_CHECK_IDS)


def test_ccx_skipped_when_no_rules_file() -> None:
    results = {
        "03_base_platform": {
            "insightsoperator": {
                "items": [{"spec": {"disabled": False}}],
            }
        },
        "12_ccx": {
            "ccx_rules": {
                "_hc_not_found": True,
                "note": "HC_CCX_RULES_FILE not provided",
            }
        },
    }
    check = _primary_cve(results)
    assert check.status == "SKIPPED"
    assert "HC_CCX_RULES_FILE" in check.evidence
    assert "Insights Available" in check.evidence
    assert check.status != "FAIL"


def test_ccx_pass_when_payload_matches() -> None:
    results = {
        "12_ccx": {
            "ccx_rules": {
                "rules": [
                    {
                        "title": "CVE-2026-31431 copy fail in algif aead",
                        "status": "PASS",
                        "message": "kernel rule matched pass",
                    }
                ]
            }
        }
    }
    check = _primary_cve(results)
    assert check.status == "PASS"
    assert check.status != "SKIPPED"


def test_ccx_does_not_fail_unmatched_cve() -> None:
    results = {
        "12_ccx": {
            "ccx_rules": {
                "rules": [
                    {
                        "title": "unrelated advisor rule",
                        "status": "FAIL",
                        "message": "should not map onto static CVEs",
                    }
                ]
            }
        }
    }
    check = _primary_cve(results)
    assert check.status == "SKIPPED"
    assert check.status != "FAIL"
