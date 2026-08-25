"""Public-contract tests for paused MCP scoring and staged KB gap fill."""
from __future__ import annotations

import shutil
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

from hc_report.findings import derive_findings
from hc_report.evaluators.topology import evaluate_topology
from hc_report.kb_loader import NEEDS_REVIEW_MARKER, load_kb
from hc_report.models import CheckResult

_REPO_ROOT = Path(__file__).resolve().parents[1]
_LIVE_KB_DIR = _REPO_ROOT / "scripts" / "health_check" / "hc_report" / "kb"
_STAGING_DIR = _REPO_ROOT / "tmp" / "kb_needs_review_outstanding"
_FIVE_SEVEN_IMPACT_DETAIL = (
    'impact_detail = "Resolving MCP degradation may require the MCO to drain '
    'and reboot stuck nodes to complete configuration rollout."\n'
)

OUTSTANDING_KB_IDS = (
    "7.7.ccx_external.cluster_does_not_support_olm_operators_network_policies",
    "7.7.ccx_external.mcp_set_to_pause",
    "7.7.ccx_external.ocp_version_end_of_life",
    "7.7.ccx_internal.machine_pool_check",
    "7.2.mcp.worker",
    "7.5.pods.failed",
    "7.4.tsr.4_1_1_logging_supported_configuration",
    "7.4.tsr.4_8_4_9_smbios_baseboard_serial_posture",
    "7.4.tsr.4_8_1_4_1_cpu_physical_resource_overhead_requirements",
    "7.7.ccx_internal.pods_crash_loop_check",
)


def _machine_config_pool_item(
    name,
    *,
    paused,
    total,
    ready,
    updated,
    degraded_count,
    updated_condition,
    updating_condition,
    degraded_condition,
):
    return {
        "metadata": {"name": name},
        "spec": {"paused": paused},
        "status": {
            "machineCount": total,
            "readyMachineCount": ready,
            "updatedMachineCount": updated,
            "degradedMachineCount": degraded_count,
            "conditions": [
                {"type": "Updated", "status": updated_condition},
                {"type": "Updating", "status": updating_condition},
                {"type": "Degraded", "status": degraded_condition},
            ],
        },
    }


def _topology_category_data(pool_item: dict) -> dict:
    return {
        "machineconfigpool": {"items": [pool_item]},
        "nodes": {"_hc_not_found": True},
        "etcd": {"_hc_not_found": True},
        "etcd_pods": {"_hc_not_found": True},
    }


def _worker_mcp_check(pool_item: dict) -> CheckResult:
    checks = evaluate_topology(_topology_category_data(pool_item), {}, "7.2", "Topology")
    for check in checks:
        if check.check_id == "7.2.mcp.worker":
            return check
    raise AssertionError("missing 7.2.mcp.worker check")


def _apply_cluster_health_overlay(copied_toml: Path) -> None:
    overlay_path = _STAGING_DIR / "7_5_cluster_health.overlay.toml"
    overlay = tomllib.loads(overlay_path.read_text())["overlays"][0]
    text = copied_toml.read_text()
    anchor = 'check_id = "7.5.tsr.5_7_machine_config_pool"'
    start = text.index(anchor)
    next_check = text.find("\n[[checks]]", start)
    section_end = next_check if next_check != -1 else len(text)
    section = text[start:section_end]
    if _FIVE_SEVEN_IMPACT_DETAIL not in section:
        raise AssertionError("5.7 impact_detail overlay anchor missing")
    insert = (
        _FIVE_SEVEN_IMPACT_DETAIL
        + f'finding_group = "{overlay["finding_group"]}"\n'
        + f'finding_group_title = "{overlay["finding_group_title"]}"\n'
    )
    new_section = section.replace(_FIVE_SEVEN_IMPACT_DETAIL, insert, 1)
    copied_toml.write_text(text[:start] + new_section + text[section_end:])


def _staged_knowledge_base(destination: Path):
    shutil.copytree(_LIVE_KB_DIR, destination, dirs_exist_ok=True)
    for add_path in sorted(_STAGING_DIR.glob("*.add.toml")):
        live_name = add_path.name.removesuffix(".add.toml") + ".toml"
        target = destination / live_name
        if not _STAGING_DIR.exists():
            break
        existing_text = target.read_text()
        add_text = add_path.read_text()
        first_id_line = next(
            (line for line in add_text.splitlines() if line.startswith("check_id")), ""
        )
        if first_id_line and first_id_line in existing_text:
            continue
        target.write_text(existing_text + "\n" + add_text)
    overlay_path = _STAGING_DIR / "7_5_cluster_health.overlay.toml"
    if overlay_path.exists():
        dest_five = destination / "7_5_cluster_health.toml"
        section_text = dest_five.read_text()
        if 'finding_group = "mcp-pool-health"' not in section_text:
            _apply_cluster_health_overlay(dest_five)
    return load_kb(destination)


def _check_result(
    check_id: str,
    evidence: str,
    *,
    status: str = "WARNING",
    description: str = "",
    source: str = "deterministic",
) -> CheckResult:
    return CheckResult(
        category_id="7.2",
        category_name="synthetic",
        check_id=check_id,
        description=description or check_id,
        status=status,
        evidence=evidence,
        source=source,
    )


def test_paused_mcp_matching_counts_warns_paused_not_not_fully_updated() -> None:
    pool_item = _machine_config_pool_item(
        "worker",
        paused=True,
        total=53,
        ready=53,
        updated=53,
        degraded_count=0,
        updated_condition="False",
        updating_condition="False",
        degraded_condition="False",
    )
    check = _worker_mcp_check(pool_item)
    assert check.status == "WARNING"
    assert "paused" in check.evidence.lower()
    assert "not fully updated" not in check.evidence.lower()


def test_unpaused_mcp_updated_false_count_mismatch_still_not_fully_updated() -> None:
    pool_item = _machine_config_pool_item(
        "worker",
        paused=False,
        total=53,
        ready=52,
        updated=52,
        degraded_count=0,
        updated_condition="False",
        updating_condition="False",
        degraded_condition="False",
    )
    check = _worker_mcp_check(pool_item)
    assert check.status == "WARNING"
    assert "not fully updated" in check.evidence
    assert "52/53" in check.evidence


def test_outstanding_needs_review_kb_inventory(tmp_path: Path) -> None:
    knowledge_base = _staged_knowledge_base(tmp_path)
    for check_id in OUTSTANDING_KB_IDS:
        entry = knowledge_base.get_entry(check_id)
        assert entry is not None, check_id
        assert entry.recommendation.strip()
        assert entry.recommendation.strip() != NEEDS_REVIEW_MARKER
        assert entry.impact.strip()


def test_mcp_pause_group_collapses_worker_and_ccx(tmp_path: Path, monkeypatch) -> None:
    knowledge_base = _staged_knowledge_base(tmp_path)
    monkeypatch.setattr("hc_report.findings.load_kb", lambda kb_dir=None: knowledge_base)
    checks = [
        _check_result("7.2.mcp.worker", "paused worker", status="WARNING"),
        _check_result(
            "7.7.ccx_external.mcp_set_to_pause",
            "paused ccx",
            status="WARNING",
            source="ccx",
        ),
    ]
    findings = derive_findings(checks)
    assert len(findings) == 1
    member_ids = findings[0].member_check_ids
    assert "7.2.mcp.worker" in member_ids
    assert "7.7.ccx_external.mcp_set_to_pause" in member_ids
