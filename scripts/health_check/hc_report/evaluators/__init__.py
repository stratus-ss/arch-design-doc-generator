"""evaluate_checks() dispatcher — registry-driven category execution."""
from __future__ import annotations

from pathlib import Path

from hc_report.evaluators.ccx import evaluate_ccx
from hc_report.evaluators.health import annotate_pod_restart_collection_gap
from hc_report.models import CheckResult
from hc_report.parity import expand_with_parity_checks
from hc_report.registry import evaluate_from_registry


def evaluate_checks(
    results: dict,
    *,
    check_profile: str = "core",
    use_ccx_baseline_status: bool = False,
    catalog_path: Path | None = None,
    tsr_runtime_path: Path | None = None,
) -> list[CheckResult]:
    """Apply deterministic checks, then optional TSR/CCX parity expansion."""
    checks = evaluate_from_registry(results)
    existing_ids = {check.check_id for check in checks}
    for ccx_check in evaluate_ccx(results):
        if ccx_check.check_id in existing_ids:
            continue
        checks.append(ccx_check)
        existing_ids.add(ccx_check.check_id)
    profile = check_profile.lower().strip()
    if profile == "core":
        return checks

    include_tsr = profile in {"extended", "advisory"}
    include_ccx = profile == "advisory"
    checks = expand_with_parity_checks(
        checks,
        results,
        include_tsr=include_tsr,
        include_ccx=include_ccx,
        use_ccx_baseline_status=use_ccx_baseline_status,
        catalog_path=catalog_path,
        tsr_runtime_path=tsr_runtime_path,
    )
    annotate_pod_restart_collection_gap(checks, results)
    return checks
