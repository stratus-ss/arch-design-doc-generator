"""Public-contract tests for Chunk G evidence, titles, registry INFO, VMI, and collect gap."""
from __future__ import annotations

import json
from pathlib import Path

from hc_report.evaluators.health import (
    annotate_pod_restart_collection_gap,
    _evaluate_health_registry,
)
from hc_report.evaluators.layered import evaluate_layered
from hc_report.findings import derive_findings
from hc_report.models import CheckResult
from hc_report.parity import expand_with_parity_checks
from hc_report.renderer import _build_check_results_table
from hc_report.tsr_parser import (
    _EVIDENCE_MAX_CHARS,
    _EVIDENCE_TRUNCATION_MARK,
    _clip_evidence,
    parse_tsr_html,
)


def test_tsr_html_result_keeps_text_past_2000_characters() -> None:
    # Bug: Result still sliced at 2000
    # Mutant: Restore [:2000]
    # Contract: public
    result_text = ("A" * 2500) + "UNIQUE_TAIL_TOKEN"
    html = f"""<!DOCTYPE html>
<html lang="en">
<body>
  <div id="1. Basic Checks-panel">
    <div class="leaf-extra">
      <div>
        <table>
          <tbody>
            <tr><td>Check</td><td>1.99 Long Result Fixture</td></tr>
            <tr><td>Status</td><td><b>WARNING</b></td></tr>
            <tr><td>Result</td><td>{result_text}</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</body>
</html>
"""
    records = parse_tsr_html(html)
    matching = [record for record in records if "UNIQUE_TAIL_TOKEN" in str(record.get("evidence", ""))]
    assert matching


def test_tsr_html_result_clips_at_evidence_max_chars() -> None:
    # Bug: 1_000_000-char Result cells hang WeasyPrint
    # Mutant: Keep slicing at 1_000_000 or restore [:2000]
    # Contract: public
    clipped = _clip_evidence(("B" * (_EVIDENCE_MAX_CHARS + 5000)) + "SHOULD_NOT_SURVIVE")
    assert len(clipped) <= _EVIDENCE_MAX_CHARS
    assert clipped.endswith(_EVIDENCE_TRUNCATION_MARK)
    assert "SHOULD_NOT_SURVIVE" not in clipped
    assert "UNIQUE_TAIL_TOKEN" in _clip_evidence(("A" * 2500) + "UNIQUE_TAIL_TOKEN")


def test_absent_logging_does_not_emit_pascalcase_stubs() -> None:
    # Bug: PascalCase 7.4.tsr.4_1_2_Logging_Storage_Type still emitted
    # Mutant: Restore product-group call
    # Contract: public
    category_data = {"logging_clusterlogging": {"_hc_not_found": True}}
    checks = evaluate_layered(category_data, {}, "7.4", "Layered Products")
    check_ids = [check.check_id for check in checks]
    assert "7.4.tsr.4_1_2_Logging_Storage_Type" not in check_ids
    assert any(
        check.status == "NOT_APPLICABLE"
        and ("4.1.1" in check.description or "Logging Supported" in check.description)
        for check in checks
    )


def test_tsr_warning_kept_when_native_title_matches(tmp_path: Path) -> None:
    # Bug: TSR WARNING dropped when native shares normalized title
    # Mutant: Keep FAIL-only bypass
    # Contract: public
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "entries": [
                    {
                        "check_id": "7.9.tsr.shared",
                        "category_id": "7.9",
                        "category_name": "Synthetic",
                        "source": "tsr",
                        "title": "Shared Title For Dedup",
                        "tsr_ref": "9.9",
                        "tags": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    runtime_path = tmp_path / "tsr_runtime.json"
    runtime_path.write_text(
        json.dumps(
            [
                {
                    "title": "Shared Title For Dedup",
                    "status": "WARNING",
                    "evidence": "tsr warning evidence",
                }
            ]
        ),
        encoding="utf-8",
    )
    native = CheckResult(
        category_id="7.9",
        category_name="Synthetic",
        check_id="7.9.native.shared",
        description="Shared Title For Dedup",
        status="WARNING",
        evidence="native warning",
    )
    expanded = expand_with_parity_checks(
        [native],
        {},
        include_tsr=True,
        include_ccx=False,
        use_ccx_baseline_status=False,
        catalog_path=catalog_path,
        tsr_runtime_path=runtime_path,
    )
    check_ids = {check.check_id for check in expanded}
    assert "7.9.native.shared" in check_ids
    assert "7.9.tsr.shared" in check_ids


def test_kb_title_used_for_chapter_seven_and_finding() -> None:
    # Bug: Node Disk still shows TSR HTML title when KB title is set
    # Mutant: check.description only in both surfaces
    # Contract: public
    check = CheckResult(
        category_id="7.4",
        category_name="Layered Products",
        check_id="7.4.tsr.4_8_1_3_4_node_disk",
        description="Node Disk",
        status="WARNING",
        evidence="virt default StorageClass missing",
    )
    findings = derive_findings([check])
    assert findings
    assert "Default virtualization StorageClass" in findings[0].title
    table = _build_check_results_table([check], "7.4")
    assert "Default virtualization StorageClass" in table


def test_unmanaged_registry_is_info_and_p3_finding() -> None:
    # Bug: Unmanaged still WARNING or INFO with no Chapter 6 finding
    # Mutant: Skip finding_on_info
    # Contract: public
    results = {
        "05_components": {
            "imageregistry": {"spec": {"managementState": "Unmanaged"}},
        }
    }
    checks = _evaluate_health_registry(results, "7.5", "Cluster Health")
    assert checks
    assert checks[0].status == "INFO"
    findings = derive_findings(checks)
    assert len(findings) == 1
    assert findings[0].priority == "P3"
    assert findings[0].check_id == "7.5.registry_health"


def test_not_live_migratable_vmi_includes_reason() -> None:
    # Bug: Engine check omits KubeVirt reason/message
    # Mutant: Drop condition message from evidence
    # Contract: public
    category_data = {
        "cnv_hyperconverged": {
            "items": [
                {
                    "status": {
                        "conditions": [{"type": "Available", "status": "True"}],
                    }
                }
            ]
        },
        "cnv_vmi": {
            "items": [
                {
                    "metadata": {"name": "vm-fixture", "namespace": "ns-fixture"},
                    "status": {
                        "conditions": [
                            {
                                "type": "LiveMigratable",
                                "status": "False",
                                "reason": "DisksNotLiveMigratable",
                                "message": "volume is RWO",
                            }
                        ]
                    },
                }
            ]
        },
    }
    checks = evaluate_layered(category_data, {}, "7.4", "Layered Products")
    live_checks = [
        check for check in checks if check.check_id == "7.4.cnv.live_migratable"
    ]
    assert live_checks
    evidence = live_checks[0].evidence
    assert "DisksNotLiveMigratable" in evidence
    assert "volume is RWO" in evidence


def test_pod_restart_gap_when_tsr_pod_missing_from_collection() -> None:
    # Bug: No gap sentence when TSR names a pod absent from pods_all
    # Mutant: Skip annotate hook
    # Contract: public
    engine_check = CheckResult(
        category_id="7.5",
        category_name="Cluster Health",
        check_id="7.5.pod_restarts",
        description="5.5 Pod Frequent Restarts",
        status="WARNING",
        evidence="1 pod(s) with >10 restarts: other-ns/other-pod (12)",
    )
    tsr_check = CheckResult(
        category_id="7.5",
        category_name="Cluster Health",
        check_id="7.5.tsr.5_5_pod_frequent_restarts",
        description="5.5 Pod Frequent Restarts",
        status="WARNING",
        evidence="gap-ns/gap-pod restarted frequently",
        source="tsr",
    )
    results = {
        "07_cluster_health": {
            "pods_all": {
                "items": [
                    {"metadata": {"namespace": "other-ns", "name": "other-pod"}},
                ]
            }
        }
    }
    annotate_pod_restart_collection_gap([engine_check, tsr_check], results)
    assert "collect gap" in engine_check.evidence
    assert "1" in engine_check.evidence
