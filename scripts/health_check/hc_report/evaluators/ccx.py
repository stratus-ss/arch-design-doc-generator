"""Core-profile CCX CVE/external rows from a static map plus optional Insights payload."""
from __future__ import annotations

import re

from hc_report.models import CheckResult
from hc_report.parity import _collect_runtime_ccx, _status

CCX_STATIC_CHECK_IDS: tuple[str, ...] = (
    "7.7.ccx_external.cve_2026_31431_copy_fail_in_algif_aead",
    "7.7.ccx_external.cve_2026_43284_dirty_frag",
    "7.7.ccx_external.cve_2023_3089_fips_incompliant",
    "7.7.ccx_external.cve_2025_10725_rhoai",
)

_CVE_IN_CHECK_ID = re.compile(r"cve_(\d{4})_(\d+)", re.IGNORECASE)


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


def evaluate_ccx(results: dict) -> list[CheckResult]:
    """Emit mapped CVE/external CCX IDs. SKIPPED when Insights payload does not match."""
    runtime_ccx = _collect_runtime_ccx(results)
    checks: list[CheckResult] = []
    for check_id in CCX_STATIC_CHECK_IDS:
        cve_label = _cve_label(check_id)
        runtime_row = _runtime_row_for_cve(cve_label, runtime_ccx)
        if runtime_row is None:
            checks.append(CheckResult(
                category_id="7.7",
                category_name="Security and Compliance",
                check_id=check_id,
                description=cve_label or check_id,
                status="SKIPPED",
                evidence="Insights/CCX payload absent or unmatched for this CVE",
                source="ccx",
            ))
            continue
        status_value = runtime_row.get("status", "SKIPPED")
        message = str(runtime_row.get("message", "")).strip()
        checks.append(CheckResult(
            category_id="7.7",
            category_name="Security and Compliance",
            check_id=check_id,
            description=cve_label or check_id,
            status=_status(str(status_value)),
            evidence=message or f"CCX runtime status for {cve_label}",
            source="ccx",
        ))
    return checks
