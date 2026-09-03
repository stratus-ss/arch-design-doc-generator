"""Public-contract tests for Chunk G evidence, titles, registry INFO, VMI, and collect gap."""
from __future__ import annotations

import json
from pathlib import Path

from hc_report.evaluators.health import (
    annotate_pod_restart_collection_gap,
    _evaluate_health_registry,
)
from hc_report.build_crosswalk_catalog import _collect_tsr_sections
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
            <tr><td>Status</td><td><b>PASS</b></td></tr>
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


def test_catalog_fallback_evidence_omitted_from_chapter_seven_result() -> None:
    # Bug: operator debug ("was not found in the supplied TSR HTML export") shown in client Result
    # Mutant: skip fallback blanking in _clean_evidence_for_cell
    # Contract: public
    check = CheckResult(
        category_id="7.1",
        category_name="Base Platform Checks",
        check_id="7.1.tsr.openshift_must_gather_collection",
        description="OpenShift Must Gather Collection",
        status="SKIPPED",
        evidence=(
            "'OpenShift Must Gather Collection' was not found in the supplied "
            "TSR HTML export (output/Health_Check_Report/tsr_parsed_runtime.json). "
            "This check is mapped in the TSR/CCX catalog but has no native "
            "deterministic evaluator yet, and the TSR export did not contain a "
            "matching entry — verify the TSR HTML corresponds to this "
            "cluster/session, or check for a title mismatch."
        ),
        source="tsr",
    )
    table = _build_check_results_table([check], "7.1")
    assert "was not found in the supplied TSR HTML export" not in table
    assert "no native deterministic evaluator" not in table
    assert "tsr_parsed_runtime.json" not in table
    assert "**Result**" in table


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


def tsr_leaf_html(result_text: str, status: str = "PASS") -> str:
    """Minimal TSR leaf HTML wrapping a Result cell (public parse_tsr_html tests)."""
    return f"""<!DOCTYPE html>
<html lang="en">
<body>
  <div id="1. Basic Checks-panel">
    <div class="leaf-extra">
      <div>
        <table>
          <tbody>
            <tr><td>Check</td><td>1.5.7.2. Chrony</td></tr>
            <tr><td>Status</td><td><b>{status}</b></td></tr>
            <tr><td>Result</td><td>{result_text}</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</body>
</html>
"""


_PASS_BODY = (
    "status check:   [PASS]   - reason: chrony leap status is Normal<br>"
    "current config check:   [PASS]   - reason: same as reference"
)
_WORKER_ONE = "examplehost061.cl1.cluster.example.com"
_WORKER_TWO = "examplehost062.cl1.cluster.example.com"
_WORKER_THREE = "examplehost063.cl1.cluster.example.com"
_WORKER_FOUR = "examplehost064.cl1.cluster.example.com"
_MASTER_LIMITED = "examplehost058.cl1.cluster.example.com"


def _first_evidence(html: str) -> str:
    records = parse_tsr_html(html)
    assert records
    return str(records[0].get("evidence", ""))


def test_identical_pass_hosts_collapse_to_all_nodes() -> None:
    # Bug: Identical worker PASS blocks stay expanded
    # Mutant: Skip condense call
    # Contract: public
    result_text = (
        f"RHCOS NODES:::<br>"
        f"{_WORKER_ONE}:<br>{_PASS_BODY}<br>"
        f"{_WORKER_TWO}:<br>{_PASS_BODY}"
    )
    evidence = _first_evidence(tsr_leaf_html(result_text))
    assert "RHCOS NODES::>ALL NODES:" in evidence
    assert evidence.count("chrony leap status is Normal") == 1
    assert _WORKER_ONE not in evidence
    assert _WORKER_TWO not in evidence


def test_non_pass_hosts_remain_named_when_siblings_collapse() -> None:
    # Bug: SUPPORT LIMITATION host dropped; or RHCOS PASS workers still dumped / PASS NODES emitted on WARNING
    # Mutant: Skip filter or keep PASS NODES
    # Contract: public
    result_text = (
        f"MASTER NODES:::<br>"
        f"{_MASTER_LIMITED}:<br>"
        "number of time-servers:   [SUPPORT LIMITATION]   - reason: two entries<br>"
        f"RHCOS NODES:::<br>"
        f"{_WORKER_ONE}:<br>{_PASS_BODY}<br>"
        f"{_WORKER_TWO}:<br>{_PASS_BODY}"
    )
    evidence = _first_evidence(tsr_leaf_html(result_text, status="WARNING"))
    assert _MASTER_LIMITED in evidence
    assert "[SUPPORT LIMITATION]" in evidence
    assert _WORKER_ONE not in evidence
    assert _WORKER_TWO not in evidence
    assert "ALL NODES" not in evidence
    assert "PASS NODES" not in evidence


def test_mixed_group_does_not_emit_all_nodes() -> None:
    # Bug: PASS NODES or PASS hostnames remain on WARNING
    # Mutant: Keep _emit_collapsed_group on filtered path
    # Contract: public
    result_text = (
        f"RHCOS NODES:::<br>"
        f"{_WORKER_ONE}:<br>"
        "high availability:   [WARNING]   - reason: single NIC<br>"
        f"{_WORKER_TWO}:<br>{_PASS_BODY}<br>"
        f"{_WORKER_THREE}:<br>{_PASS_BODY}"
    )
    evidence = _first_evidence(tsr_leaf_html(result_text, status="WARNING"))
    assert "ALL NODES" not in evidence
    assert "PASS NODES" not in evidence
    assert _WORKER_ONE in evidence
    assert _WORKER_TWO not in evidence
    assert _WORKER_THREE not in evidence
    assert "[WARNING]" in evidence


def test_unique_pass_bodies_are_not_collapsed() -> None:
    # Bug: Different PASS reasons merged
    # Mutant: Collapse without body equality
    # Contract: public
    # When every host is ok, hostnames are purged even if reasons differ.
    result_text = (
        f"RHCOS NODES:::<br>"
        f"{_WORKER_ONE}:<br>"
        "status check:   [PASS]   - reason: offset under 100ms<br>"
        f"{_WORKER_TWO}:<br>"
        "status check:   [PASS]   - reason: leap status is Normal"
    )
    evidence = _first_evidence(tsr_leaf_html(result_text))
    assert "RHCOS NODES::>ALL NODES:" in evidence
    assert _WORKER_ONE not in evidence
    assert _WORKER_TWO not in evidence


def test_heterogeneous_ok_bodies_keep_all_hosts_named() -> None:
    # Bug: Two distinct ok bodies produce two ALL NODES blocks
    # Mutant: Collapse per-body instead of per-group
    # Contract: public
    body_a = "status check:   [PASS]   - reason: body-alpha"
    body_b = "status check:   [PASS]   - reason: body-beta"
    result_text = (
        f"RHCOS NODES:::<br>"
        f"{_WORKER_ONE}:<br>{body_a}<br>"
        f"{_WORKER_TWO}:<br>{body_a}<br>"
        f"{_WORKER_THREE}:<br>{body_b}<br>"
        f"{_WORKER_FOUR}:<br>{body_b}"
    )
    evidence = _first_evidence(tsr_leaf_html(result_text))
    assert "RHCOS NODES::>ALL NODES:" in evidence
    assert _WORKER_ONE not in evidence
    assert _WORKER_FOUR not in evidence


def test_existing_all_nodes_group_is_left_unchanged() -> None:
    # Bug: Double-collapse of TSR-native ALL NODES
    # Mutant: Always rewrite ALL NODES groups
    # Contract: public
    native_line = "RHCOS NODES::>ALL NODES:   [PASS]   - reason: fixture"
    evidence = _first_evidence(tsr_leaf_html(native_line))
    assert native_line in evidence
    assert "examplehost" not in evidence


def test_inline_pass_hosts_collapse_to_all_nodes() -> None:
    # Bug: hostname: [PASS] on one line stays expanded
    # Mutant: Require a hostname-only line (no remainder after colon)
    # Contract: public
    result_text = (
        f"RHCOS NODES:::<br>"
        f'{_WORKER_ONE}:   [PASS]   - reason: "up" matches reference<br>'
        f'{_WORKER_TWO}:   [PASS]   - reason: "up" matches reference'
    )
    evidence = _first_evidence(tsr_leaf_html(result_text))
    assert 'RHCOS NODES::>ALL NODES:   [PASS]   - reason: "up" matches reference' in evidence
    assert _WORKER_ONE not in evidence
    assert _WORKER_TWO not in evidence


def test_repeated_field_groups_collapse_without_swallowing_labels() -> None:
    # Bug: mtu / ipv4.enabled after hosts is eaten into the last host body
    # Mutant: End a node group only on ::/::: headers
    # Contract: public
    result_text = (
        "state<br>"
        f"MASTER NODES:::<br>"
        f'{_MASTER_LIMITED}:   [PASS]   - reason: "up" matches reference<br>'
        f'{_WORKER_ONE}:   [PASS]   - reason: "up" matches reference<br>'
        f"RHCOS NODES:::<br>"
        f'{_WORKER_TWO}:   [PASS]   - reason: "up" matches reference<br>'
        f'{_WORKER_THREE}:   [PASS]   - reason: "up" matches reference<br>'
        "mtu<br>"
        f"MASTER NODES:::<br>"
        f'{_MASTER_LIMITED}:   [PASS]   - reason: "9000" matches reference<br>'
        f'{_WORKER_ONE}:   [PASS]   - reason: "9000" matches reference<br>'
        f"RHCOS NODES:::<br>"
        f'{_WORKER_TWO}:   [PASS]   - reason: "9000" matches reference<br>'
        f'{_WORKER_THREE}:   [PASS]   - reason: "9000" matches reference'
    )
    evidence = _first_evidence(tsr_leaf_html(result_text))
    assert evidence.count("mtu") == 1
    assert evidence.count("state") == 1
    assert '"up" matches reference' in evidence
    assert '"9000" matches reference' in evidence
    assert _WORKER_TWO not in evidence
    assert _WORKER_THREE not in evidence
    assert "RHCOS NODES::>ALL NODES:" in evidence


def test_interface_names_are_not_treated_as_hosts() -> None:
    # Bug: bond0: / bond0.1709: counted as hosts so real nodes never collapse
    # Mutant: Treat any name with a digit or a dot as a host
    # Contract: public
    result_text = (
        f"MASTER NODES::<br>"
        f"{_MASTER_LIMITED}:<br>"
        "bond0:   [PASS]   - reason: multiple ports<br>"
        f"{_WORKER_ONE}:<br>"
        "bond0:   [PASS]   - reason: multiple ports"
    )
    evidence = _first_evidence(tsr_leaf_html(result_text))
    assert "MASTER NODES::>ALL NODES:" in evidence
    assert _MASTER_LIMITED not in evidence
    assert "bond0:" in evidence


def test_bare_fqdn_hosts_collapse_without_nodes_header() -> None:
    # Bug: FQDN lines without a trailing colon are left expanded
    # Mutant: Require hostname:
    # Contract: public
    result_text = (
        f"{_WORKER_ONE}<br>"
        "KubeletReady:   [PASS]   - kubelet is posting ready status<br>"
        f"{_WORKER_TWO}<br>"
        "KubeletReady:   [PASS]   - kubelet is posting ready status"
    )
    evidence = _first_evidence(tsr_leaf_html(result_text))
    assert "ALL NODES::>ALL NODES:" in evidence
    assert _WORKER_ONE not in evidence
    assert _WORKER_TWO not in evidence


def test_dot_table_collapses_identical_remainders() -> None:
    # Bug: Identical VMI table rows stay expanded
    # Mutant: Skip table helper
    # Contract: public
    result_text = (
        "NAMESPACE · VMI · LIVEMIGRATABLE<br>"
        "examplens · examplevm-a · true<br>"
        "examplens · examplevm-b · true<br>"
        "examplens · examplevm-c · true"
    )
    evidence = _first_evidence(tsr_leaf_html(result_text))
    assert "NAMESPACE · VMI · LIVEMIGRATABLE" in evidence
    assert "(2 more)" in evidence
    assert "examplevm-a" in evidence
    assert "examplevm-b" not in evidence
    assert "examplevm-c" not in evidence


def test_dot_table_keeps_distinct_remainders() -> None:
    # Bug: Two remainder signatures merged
    # Mutant: Collapse without grouping by remainder
    # Contract: public
    result_text = (
        "NAMESPACE · NAME · TYPE<br>"
        "examplens · vlan10 · bridge<br>"
        "examplens · vlan11 · bridge<br>"
        "examplens · bond0 · bond"
    )
    evidence = _first_evidence(tsr_leaf_html(result_text))
    assert "(1 more)" in evidence
    assert "vlan10 · bridge" in evidence
    assert "vlan11" not in evidence
    assert "bond0 · bond" in evidence


def test_headerless_dot_rows_collapse_by_remainder() -> None:
    # Bug: Inventory dump without ALL-CAPS header stays expanded
    # Mutant: Require a header before grouping data rows
    # Contract: public
    result_text = (
        "examplens · examplepvc-a · ReadWriteMany · Bound · yes<br>"
        "examplens · examplepvc-b · ReadWriteMany · Bound · yes<br>"
        "examplens · examplepvc-c · ReadWriteMany · Bound · yes"
    )
    evidence = _first_evidence(tsr_leaf_html(result_text))
    assert "(2 more)" in evidence
    assert "examplepvc-a" in evidence
    assert "examplepvc-b" not in evidence
    assert "examplepvc-c" not in evidence


def test_dot_table_resumes_after_broken_row() -> None:
    # Bug: A non-dot line stops the rest of the table from collapsing
    # Mutant: End the table on any non-data line and never regroup
    # Contract: public
    result_text = (
        "NAMESPACE · PVC · PHASE · STORAGECLASS<br>"
        "examplens · examplepvc-a · Bound · px-rwx-vm<br>"
        "examplens · examplepvc-b · Bound · px-rwx-vm<br>"
        "broken-row-without-dots<br>"
        "examplens · examplepvc-c · Bound · px-rwx-vm<br>"
        "examplens · examplepvc-d · Bound · px-rwx-vm"
    )
    evidence = _first_evidence(tsr_leaf_html(result_text))
    assert evidence.count("(1 more)") == 2
    assert "broken-row-without-dots" in evidence
    assert "examplepvc-a" in evidence
    assert "examplepvc-c" in evidence
    assert "examplepvc-b" not in evidence
    assert "examplepvc-d" not in evidence


def test_nfs_nconnect_lines_collapse_by_token() -> None:
    # Bug: Identical nconnect mounts stay expanded
    # Mutant: Skip nconnect helper
    # Contract: public
    result_text = (
        f"{_WORKER_ONE}: server:/share /mnt nfs4 (nconnect=default/1)<br>"
        f"{_WORKER_TWO}: server:/share /mnt nfs4 (nconnect=default/1)"
    )
    evidence = _first_evidence(tsr_leaf_html(result_text))
    assert _WORKER_ONE in evidence
    assert _WORKER_TWO not in evidence
    assert "(1 more NFS mounts with (nconnect=default/1))" in evidence


def test_repeated_node_warnings_collapse_without_all_nodes() -> None:
    # Bug: Identical node WARNING lines stay; or labelled ALL NODES
    # Mutant: Skip node helper or emit ALL NODES
    # Contract: public
    reason = "[WARNING]   - reason: max_session_slots=64"
    result_text = (
        f"node {_WORKER_ONE}:   {reason}<br>"
        f"node {_WORKER_TWO}:   {reason}"
    )
    evidence = _first_evidence(tsr_leaf_html(result_text))
    assert "(2 nodes):   [WARNING]   - reason: max_session_slots=64" in evidence
    assert "ALL NODES" not in evidence
    assert _WORKER_ONE not in evidence


def test_qualified_node_status_lines_collapse() -> None:
    # Bug: "node host qualifier: [STATUS]" lines left expanded
    # Mutant: Regex only matches "node host:" without qualifier
    # Contract: public
    reason = "[INFO]   - reason: no nfs.max_session_slots in cmdline"
    result_text = (
        f"node {_WORKER_ONE} cmdline:   {reason}<br>"
        f"node {_WORKER_TWO} cmdline:   {reason}<br>"
        f"node {_WORKER_THREE} cmdline:   {reason}"
    )
    evidence = _first_evidence(tsr_leaf_html(result_text))
    assert "(3 nodes) cmdline:   [INFO]   - reason: no nfs.max_session_slots in cmdline" in evidence
    assert _WORKER_ONE not in evidence
    assert _WORKER_TWO not in evidence


def test_mixed_host_group_emits_pass_nodes_not_all_nodes() -> None:
    # Bug: Mixed FQDN group keeps PASS hostnames or PASS NODES on WARNING
    # Mutant: Keep PASS NODES
    # Contract: public
    result_text = (
        f"{_WORKER_ONE}<br>"
        "KubeletReady:   [WARNING]   - kubelet is not ready<br>"
        f"{_WORKER_TWO}<br>"
        "KubeletReady:   [PASS]   - kubelet is posting ready status<br>"
        f"{_WORKER_THREE}<br>"
        "KubeletReady:   [PASS]   - kubelet is posting ready status"
    )
    evidence = _first_evidence(tsr_leaf_html(result_text, status="WARNING"))
    assert "PASS NODES" not in evidence
    assert "ALL NODES::>ALL NODES:" not in evidence
    assert _WORKER_ONE in evidence
    assert _WORKER_TWO not in evidence
    assert _WORKER_THREE not in evidence


def test_unhealthy_pods_collapse_by_workload() -> None:
    # Bug: Replica WARNING pods stay expanded
    # Mutant: Skip pod helper
    # Contract: public
    result_text = (
        "examplens:app-85f858f84f-26gvp   [WARNING]   - looks unhealthy, as it has 22 restarts<br>"
        "examplens:app-cfcfd6486-5n9mb   [WARNING]   - looks unhealthy, as it has 23 restarts"
    )
    evidence = _first_evidence(tsr_leaf_html(result_text))
    assert evidence.count("[WARNING]") == 1
    assert "(1 more pods)" in evidence
    assert "app-cfcfd6486-5n9mb" not in evidence


def test_warning_result_keeps_only_important_lines() -> None:
    # Bug: PASS/INFO/SKIP/NA and inventory survive on WARNING; LIMITATION/WARNING lost
    # Mutant: No-op filter
    # Contract: public
    result_text = (
        f"{_MASTER_LIMITED}:<br>"
        "number of time-servers:   [SUPPORT LIMITATION]   - reason: two entries<br>"
        f"{_WORKER_ONE}:<br>"
        "high availability:   [WARNING]   - reason: single NIC<br>"
        "status check:   [PASS]   - reason: leap is Normal<br>"
        "catalog:   [INFO]   - source listed<br>"
        "job:   [SKIPPED]   - not collected<br>"
        "quota:   [NOT APPLICABLE]   - none<br>"
        "NAMESPACE · VMI · LIVEMIGRATABLE<br>"
        "examplens · examplevm-a · true<br>"
        "examplens · examplevm-b · true<br>"
        "examplens · examplevm-c · true<br>"
        f"RHCOS NODES:::<br>"
        f"{_WORKER_TWO}:<br>{_PASS_BODY}<br>"
        f"{_WORKER_THREE}:<br>{_PASS_BODY}"
    )
    evidence = _first_evidence(tsr_leaf_html(result_text, status="WARNING"))
    assert "[SUPPORT LIMITATION]" in evidence
    assert "[WARNING]" in evidence
    assert "[PASS]" not in evidence
    assert "[INFO]" not in evidence
    assert "[SKIPPED]" not in evidence
    assert "[NOT APPLICABLE]" not in evidence
    assert "examplevm-a" not in evidence
    assert "PASS NODES" not in evidence
    assert "ALL NODES" not in evidence


def test_unfiltered_status_keeps_pass_and_info_lines() -> None:
    # Bug: Filter wrongly applied to PASS or NOT_APPLICABLE
    # Mutant: Gate always-on
    # Contract: public
    result_text = (
        "status check:   [PASS]   - reason: leap is Normal<br>"
        "catalog:   [INFO]   - source listed"
    )
    pass_evidence = _first_evidence(tsr_leaf_html(result_text, status="PASS"))
    not_applicable_evidence = _first_evidence(
        tsr_leaf_html(result_text, status="NOT_APPLICABLE")
    )
    assert "[PASS]" in pass_evidence
    assert "[INFO]" in pass_evidence
    assert "[PASS]" in not_applicable_evidence
    assert "[INFO]" in not_applicable_evidence


def test_not_applicable_space_variant_recognised_as_status() -> None:
    # Bug: [NOT APPLICABLE] (with space) missing from _NOT_OK_BODY_TOKENS
    #      → _is_field_label misclassifies it → group boundary breaks early
    # Mutant: Remove [NOT APPLICABLE] from _NOT_OK_BODY_TOKENS
    # Contract: public
    result_text = (
        f"RHCOS NODES:::<br>"
        f"{_MASTER_LIMITED}:<br>"
        "quota:   [NOT APPLICABLE]   - none<br>"
        f"{_WORKER_ONE}:<br>"
        "status check:   [PASS]   - reason: ok<br>"
        f"{_WORKER_TWO}:<br>"
        "status check:   [PASS]   - reason: ok"
    )
    evidence = _first_evidence(tsr_leaf_html(result_text))
    assert _MASTER_LIMITED in evidence
    assert "[NOT APPLICABLE]" in evidence
    assert "PASS NODES" in evidence
    assert _WORKER_ONE not in evidence
    assert _WORKER_TWO not in evidence


def test_warning_result_splits_same_line_status_tokens() -> None:
    # Bug: HTML-stripped Result keeps [PASS]/[INFO]/[NOT APPLICABLE] on the same line as WARNING/FAIL
    # Mutant: Skip _split_line_on_result_tokens
    # Contract: public
    result_text = (
        "identity providers configured:   [PASS]   - reason: types configured.   "
        "HTPasswd: my_htpasswd_provider:   [WARNING]   - reason: do not use htpasswd in production"
        "<br>"
        "FileSystem Type:   [FAIL]   reason: emptyDir   "
        "Registry storage checks:   [NOT APPLICABLE]   - reason: no registry PV"
        "<br>"
        "deploymentconfig:   [NOT APPLICABLE]   - none   "
        "[INFO]   DEPLOYMENTS   "
        "[WARNING]   | istio-system   | istio-egressgateway"
    )
    evidence = _first_evidence(tsr_leaf_html(result_text, status="WARNING"))
    assert "[WARNING]" in evidence
    assert "[FAIL]" in evidence
    assert "htpasswd" in evidence.lower()
    assert "emptyDir" in evidence
    assert "istio-egressgateway" in evidence
    assert "[PASS]" not in evidence
    assert "[INFO]" not in evidence
    assert "[NOT APPLICABLE]" not in evidence


def test_catalog_builder_excludes_group_headers() -> None:
    # Bug: tree-view dropdown group headers ("Other Basic Checks") become catalog entries
    # Mutant: remove _node_text_is_group_header lookahead skip
    # Contract: public
    tsr_html = """<!DOCTYPE html>
<html lang="en">
<body>
  <div id="1. Basic Checks-panel">
    <li>
      <div class="pf-v6-c-tree-view__content">
        <button>
          <span class="pf-v6-c-tree-view__node-toggle"></span>
          <span class="pf-v6-c-tree-view__node-text">1.5. Other Basic Checks</span>
          <span><div class="chip chip-pass">Pass 1</div></span>
        </button>
        <ul class="pf-v6-c-tree-view__list" role="group">
          <li>
            <div class="pf-v6-c-tree-view__content">
              <button>
                <span class="pf-v6-c-tree-view__node-text">1.5.7.2. Chrony</span>
                <span><div class="chip chip-pass">Pass 1</div></span>
              </button>
            </div>
          </li>
        </ul>
      </div>
    </li>
  </div>
  <div id="2. Topology Checks-btn"></div>
</body>
</html>
"""
    entries = _collect_tsr_sections(tsr_html)
    titles = [entry["title"] for entry in entries]
    assert "1.5. Other Basic Checks" not in titles
    assert "1.5.7.2. Chrony" in titles
