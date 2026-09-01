"""Core-profile CCX CVE/external rows from a static map plus optional Insights payload."""
from __future__ import annotations

import re

from hc_report.evaluators.platform import _insights_reporting_disabled
from hc_report.models import CheckResult
from hc_report.parity import _collect_runtime_ccx, _status

CCX_STATIC_CHECK_IDS: tuple[str, ...] = (
    "7.7.ccx_external.cve_2026_31431_copy_fail_in_algif_aead",
    "7.7.ccx_external.cve_2026_43284_dirty_frag",
    "7.7.ccx_external.cve_2023_3089_fips_incompliant",
    "7.7.ccx_external.cve_2025_10725_rhoai",
)

_CVE_IN_CHECK_ID = re.compile(r"cve_(\d{4})_(\d+)", re.IGNORECASE)
_DISABLED_INSIGHTS_EVIDENCE = "InsightsOperator reporting is disabled"
_MISSING_RULES_FILE_EVIDENCE = (
    "HC_CCX_RULES_FILE unset; 12_ccx/ccx_rules.json is _hc_not_found. "
    "Insights Available; CVE rows are not scraped from Advisor APIs."
)
_UNMATCHED_CVE_EVIDENCE = "Insights/CCX payload absent or unmatched for this CVE"


def _cve_label(check_id: str) -> str:
    match = _CVE_IN_CHECK_ID.search(check_id)
    if not match:
        return ""
    return f"CVE-{match.group(1)}-{match.group(2)}"


def _runtime_row_for_cve(cve_label: str, runtime_ccx: dict[str, dict]) -> dict | None:
    if not cve_label:
        return None
    compact_needle = cve_label.lower().replace("-", "").replace("_", "")
    for title, row in runtime_ccx.items():
        blob = " ".join(
            [
                title,
                str(row.get("check", "")),
                str(row.get("title", "")),
                str(row.get("id", "")),
            ]
        )
        compact_blob = blob.lower().replace("-", "").replace("_", "")
        if compact_needle in compact_blob:
            return row
    return None


def _ccx_rules_file_missing(payload: object) -> bool:
    if not isinstance(payload, dict) or not payload:
        return True
    return bool(payload.get("_hc_not_found") or payload.get("_hc_error"))


def _static_cve_result(check_id: str, status: str, evidence: str) -> CheckResult:
    cve_label = _cve_label(check_id)
    return CheckResult(
        category_id="7.7",
        category_name="Security and Compliance",
        check_id=check_id,
        description=cve_label or check_id,
        status=status,
        evidence=evidence,
        source="ccx",
    )


def evaluate_ccx(results: dict) -> list[CheckResult]:
    """Emit mapped CVE/external CCX IDs. N/A when Insights disabled; SKIPPED without rules file."""
    platform = results.get("03_base_platform")
    insights_operator = platform.get("insightsoperator") if isinstance(platform, dict) else {}
    if not isinstance(insights_operator, dict):
        insights_operator = {}
    if _insights_reporting_disabled(insights_operator):
        return [
            _static_cve_result(check_id, "NOT_APPLICABLE", _DISABLED_INSIGHTS_EVIDENCE)
            for check_id in CCX_STATIC_CHECK_IDS
        ]

    payload = results.get("12_ccx", {}).get("ccx_rules") if isinstance(results.get("12_ccx"), dict) else None
    file_missing = _ccx_rules_file_missing(payload)
    runtime_ccx = _collect_runtime_ccx(results)
    checks: list[CheckResult] = []
    for check_id in CCX_STATIC_CHECK_IDS:
        cve = _cve_label(check_id)
        runtime_row = _runtime_row_for_cve(cve, runtime_ccx)
        if runtime_row is None:
            skipped_evidence = (
                _MISSING_RULES_FILE_EVIDENCE if file_missing else _UNMATCHED_CVE_EVIDENCE
            )
            checks.append(_static_cve_result(check_id, "SKIPPED", skipped_evidence))
            continue
        status_value = runtime_row.get("status", "SKIPPED")
        message = str(runtime_row.get("message", "")).strip()
        checks.append(_static_cve_result(
            check_id,
            _status(str(status_value)),
            message or f"CCX runtime status for {cve}",
        ))
    return checks
