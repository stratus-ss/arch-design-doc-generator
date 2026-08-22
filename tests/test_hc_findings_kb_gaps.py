"""Public-contract tests for Chunk C KB gaps and impact rendering."""
from __future__ import annotations

from hc_report.findings import derive_findings
from hc_report.kb_loader import NEEDS_REVIEW_MARKER, load_kb
from hc_report.models import CheckResult, Finding
from hc_report.renderer import _build_findings_sections

# Bug: Missing KB rec still shows generic oc get csv -A 7.4 paragraph
# Mutant: Restore _CATEGORY_FALLBACK branch
# Contract: public

# Bug: impact = "none" still omits Level of Impact
# Mutant: Keep if finding.impact == "none": return ""
# Contract: public

# Bug: Blank impact still omits the section
# Mutant: Treat empty like none omit
# Contract: public

# Bug: An inventory check_id still has empty description/rec/impact
# Mutant: Skip filling one TOML row
# Contract: public

CHUNK_C_INVENTORY = (
    "7.4.tsr.4_1_2_logging_storage_type",
    "7.4.tsr.4_1_4_logging_pod_status",
    "7.4.tsr.4_1_5_2_loki_health",
    "7.4.tsr.4_1_6_cluster_log_forwarders",
    "7.4.tsr.4_1_8_logging_security_context_constraints",
    "7.4.tsr.4_8_4_2_windows_bsod_risk_posture",
    "7.4.tsr.4_8_4_3_windows_hyper_v_enlightenments",
    "7.4.tsr.4_8_5_2_1_active_alerts",
    "7.4.tsr.4_12_1_2_mtv_supported_configuration",
    "7.4.tsr.4_12_1_1_1_mtv_installation_and_state",
    "7.4.tsr.4_12_1_1_2_operator_subscription_posture",
    "7.4.tsr.4_8_1_1_1_identification_and_state",
    "7.4.tsr.4_8_1_5_3_2_storage_checkup",
    "7.4.tsr.4_8_5_2_3_cnv_vmi_readiness_prometheus",
    "7.7.ccx_internal.tls_handshake_errors",
)


def test_missing_recommendation_is_needs_review_not_fallback() -> None:
    check = CheckResult(
        "7.4",
        "Layered Products",
        "7.9.synthetic.missing",
        "synthetic widget",
        "FAIL",
        "[FAIL] - reason: widgets",
    )
    findings = derive_findings([check])
    assert findings
    assert NEEDS_REVIEW_MARKER in findings[0].recommendation
    assert "oc get csv -A" not in findings[0].recommendation


def test_impact_none_renders_visible_none() -> None:
    finding = Finding(
        "6.2.2.1",
        "Synthetic none impact",
        "P1",
        "evidence",
        "recommendation",
        impact="none",
    )
    markdown = _build_findings_sections([finding])
    assert "**Level of Impact:** None" in markdown


def test_missing_impact_renders_needs_review() -> None:
    finding = Finding(
        "6.2.2.2",
        "Synthetic missing impact",
        "P1",
        "evidence",
        "recommendation",
        impact="",
    )
    markdown = _build_findings_sections([finding])
    assert f"**Level of Impact:** {NEEDS_REVIEW_MARKER}" in markdown


def test_chunk_c_inventory_kb_fields_present() -> None:
    knowledge_base = load_kb()
    for check_id in CHUNK_C_INVENTORY:
        entry = knowledge_base.get_entry(check_id)
        assert entry is not None, check_id
        assert entry.description.strip(), check_id
        assert entry.recommendation.strip(), check_id
        assert entry.recommendation.strip() != NEEDS_REVIEW_MARKER, check_id
        assert entry.impact.strip(), check_id

    logging_storage = knowledge_base.get_entry("7.4.tsr.4_1_2_logging_storage_type")
    bsod_posture = knowledge_base.get_entry("7.4.tsr.4_8_4_2_windows_bsod_risk_posture")
    assert logging_storage is not None
    assert bsod_posture is not None
    assert "lokistack" in logging_storage.recommendation.lower()
    assert "watchdog" in bsod_posture.recommendation.lower()
    for entry in (logging_storage, bsod_posture):
        assert entry.recommendation == entry.recommendation.strip()
        assert entry.recommendation.isascii()
