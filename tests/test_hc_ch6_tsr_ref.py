"""Public-contract tests for Chapter 6 §6.2 TSR ref correctness."""
from __future__ import annotations

import json
import re
from pathlib import Path

from hc_report.findings import _make_grouped_finding, derive_findings
from hc_report.models import CheckResult, Finding
from hc_report.renderer import _build_findings_sections

# Bug: Finding.tsr_ref empty when check has a dotted section number and the
# KB title has no leading number
# Mutant: Skip assigning tsr_ref in _make_finding
# Contract: public

# Bug: §6.2 would print CCX:internal as a TSR ref
# Mutant: Treat any non-empty tsr_ref as printable
# Contract: public

# Bug: Grouped finding keeps one ref or n/a when members have distinct
# dotted section numbers
# Mutant: Join with comma, or take primary only
# Contract: impl-detail (_make_grouped_finding)

# Bug: Renderer still title-splits; KB-style title yields n/a
# Mutant: Keep tsr = _split_finding_title(...)[1] for the TSR ref line
# Contract: public

# Bug: The seven one-6x489 KB-title-without-prefix IDs still render n/a or a
# number absent from the TSR HTML tree
# Mutant: Hardcode n/a or skip the HTML prefix check
# Contract: public

_AUDIT_JSON_PATH = Path("output/Health_Check_Report/GM_HC_audit_one-6x489.json")
_TSR_HTML_PATH = Path("output/tsr_html/homelab-one-2026-08-29T17_21_20.000Z.html")

_ONE6X489_TSR_ID_TO_SECTION = {
    "7.4.tsr.4_8_1_1_1_identification_and_state": "4.8.1.1.1",
    "7.4.tsr.4_8_4_5_host_kernel_bsod_indicators": "4.8.4.5",
    "7.4.tsr.4_8_4_6_nfs_client_mount_posture": "4.8.4.6",
    "7.4.tsr.4_8_4_7_nfs_client_sysctl_posture": "4.8.4.7",
    "7.4.tsr.4_8_5_2_1_active_alerts": "4.8.5.2.1",
    "7.4.tsr.4_12_1_1_1_mtv_installation_and_state": "4.12.1.1.1",
    "7.4.tsr.4_12_1_2_mtv_supported_configuration": "4.12.1.2",
}


def audit_check(check_id: str, source: str, tsr_ref: str) -> CheckResult:
    """Build a synthetic CheckResult matching audit-JSON check shape."""
    category_id = ".".join(check_id.split(".")[:2])
    return CheckResult(
        category_id=category_id,
        category_name="Layered Products",
        check_id=check_id,
        description="synthetic",
        status="FAIL",
        evidence="[FAIL] - reason: synthetic",
        source=source,
        tsr_ref=tsr_ref,
    )


def test_derive_copies_dotted_tsr_ref() -> None:
    check = audit_check(
        "7.4.tsr.4_8_1_1_1_identification_and_state", source="tsr", tsr_ref="4.8.1.1.1"
    )
    findings = derive_findings([check])
    assert findings[0].tsr_ref == "4.8.1.1.1"


def test_derive_drops_ccx_prefixed_ref() -> None:
    check = audit_check(
        "7.7.ccx_internal.etcd_low_backend_performance",
        source="ccx",
        tsr_ref="CCX:internal",
    )
    findings = derive_findings([check])
    assert findings[0].tsr_ref == ""


def test_grouped_joins_unique_dotted_refs() -> None:
    members = [
        audit_check("7.4.tsr.4_5_2_quay_pods", source="tsr", tsr_ref="4.5.2"),
        audit_check("7.4.tsr.4_5_4_1_quay_pods", source="tsr", tsr_ref="4.5.4.1"),
    ]
    finding = _make_grouped_finding(members, "P3", {"P3": 0})
    assert finding.tsr_ref == "4.5.2 4.5.4.1"

    empty_members = [
        audit_check("7.4.tsr.4_5_2_quay_pods", source="tsr", tsr_ref=""),
        audit_check("7.4.tsr.4_5_4_1_quay_pods", source="tsr", tsr_ref=""),
    ]
    empty_finding = _make_grouped_finding(empty_members, "P3", {"P3": 0})
    assert empty_finding.tsr_ref == ""


def test_render_tsr_ref_line_from_finding_field() -> None:
    tsr_finding = Finding(
        id="6.2.4.21",
        title="TSR CNV identification and state",
        priority="P3",
        description="e",
        recommendation="r",
        check_id="7.4.tsr.4_8_1_1_1_identification_and_state",
        tsr_ref="4.8.1.1.1",
    )
    det_finding = Finding(
        id="6.2.2.1",
        title="Internal registry storage",
        priority="P3",
        description="e",
        recommendation="r",
        check_id="7.3.registry.storage",
    )
    markdown = _build_findings_sections([tsr_finding, det_finding])
    tsr_block = markdown.split("6.2.4.21.")[1].split("6.2.2.1.")[0]
    det_block = markdown.split("6.2.2.1.")[1]
    assert "**TSR ref:** 4.8.1.1.1" in tsr_block
    assert "**TSR ref:** n/a" not in tsr_block
    assert "**TSR ref:** n/a" in det_block


def test_one6x489_kb_title_tsr_ids_match_html() -> None:
    audit_payload = json.loads(_AUDIT_JSON_PATH.read_text(encoding="utf-8"))
    audit_checks_by_id = {check["id"]: check for check in audit_payload["checks"]}
    html_text = _TSR_HTML_PATH.read_text(encoding="utf-8")
    tree_node_texts = re.findall(
        r'class="pf-v6-c-tree-view__node-text">(.*?)</span>', html_text
    )

    for check_id, expected_section in _ONE6X489_TSR_ID_TO_SECTION.items():
        audit_row = audit_checks_by_id.get(check_id)
        assert audit_row is not None, f"missing from audit JSON: {check_id}"
        assert audit_row["tsr_ref"] == expected_section, (
            f"{check_id}: audit tsr_ref {audit_row['tsr_ref']!r} != expected {expected_section!r}"
        )

        check = audit_check(check_id, source=audit_row["source"], tsr_ref=audit_row["tsr_ref"])
        findings = derive_findings([check])
        markdown = _build_findings_sections(findings)
        assert f"**TSR ref:** {expected_section}" in markdown

        assert any(
            node_text.startswith(expected_section + ".")
            or node_text.startswith(expected_section + " ")
            for node_text in tree_node_texts
        ), f"{expected_section} not found as a TSR HTML tree node"
