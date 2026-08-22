"""Public-contract tests for Chunk D mode-neutral wrong-story KB prose."""
from __future__ import annotations

from hc_report.kb_loader import load_kb

# Bug: Description still asserts emptyDir as the only failure
# Mutant: Leave old emptyDir-only description
# Contract: public

# Bug: Rec still assumes OLM CSV in openshift-adp only
# Mutant: Restore CSV-only rec
# Contract: public

# Bug: D rewrote rows reserved for G
# Mutant: Edit 4_8_1_3_4 or 3_9_5
# Contract: public

# Bug: A D-inventory check_id missing or empty description
# Mutant: Skip one rewrite
# Contract: public

CHUNK_D_INVENTORY = (
    "7.3.tsr.3_7_2_monitoring_storage_type",
    "7.3.tsr.3_9_3_dynamic_storage_provisioner_plugins",
    "7.3.tsr.3_9_4_storage_pv_status",
    "7.3.tsr.3_17_6_network_bond_configuration",
    "7.4.tsr.4_8_1_1_1_identification_and_state",
    "7.4.tsr.4_8_1_1_2_related_subscriptions",
    "7.4.tsr.4_8_1_5_3_2_storage_checkup",
    "7.4.tsr.4_8_2_1_1_3_live_migration_network_readiness",
    "7.4.tsr.4_8_3_1_1_storage_profiles",
    "7.4.tsr.4_8_3_2_1_nmstate_operator",
    "7.4.tsr.4_8_3_2_2_sr_iov_operator",
    "7.4.tsr.4_8_4_6_nfs_client_mount_posture",
    "7.4.tsr.4_8_5_2_3_cnv_vmi_readiness_prometheus",
    "7.4.tsr.4_8_5_3_1_oadp_operator",
    "7.6.tsr.6_1_1_1_quota_resources_project_assignment",
    "7.6.tsr.6_3_1_active_alerts",
    "7.1.tsr.1_1_identification_and_state",
)


def test_monitoring_storage_description_is_mode_neutral() -> None:
    knowledge_base = load_kb()
    entry = knowledge_base.get_entry("7.3.tsr.3_7_2_monitoring_storage_type")
    assert entry is not None
    description = entry.description
    recommendation = entry.recommendation
    assert "emptyDir" in description
    assert "RWX" in description or "file" in description.lower()
    assert "The monitoring stack storage is configured as" not in description
    assert "emptyDir" in recommendation
    assert "RWX" in recommendation or "block" in recommendation.lower()


def test_oadp_recommendation_covers_non_olm() -> None:
    knowledge_base = load_kb()
    entry = knowledge_base.get_entry("7.4.tsr.4_8_5_3_1_oadp_operator")
    assert entry is not None
    recommendation = entry.recommendation.casefold()
    assert "csv" in recommendation
    assert any(
        token in recommendation
        for token in ("helm", "manual", "non-olm", "outside olm", "olm")
    )
    assert any(
        token in recommendation
        for token in (
            "grep",
            "-a",
            "elsewhere",
            "namespace that actually",
            "non-olm",
            "helm",
        )
    )


def test_node_disk_and_csi_39_5_untouched() -> None:
    knowledge_base = load_kb()
    node_disk = knowledge_base.get_entry("7.4.tsr.4_8_1_3_4_node_disk")
    assert node_disk is not None
    # Chunk G already replaced the pre-G disk-space wrong-story. D must leave
    # that row as G wrote it (virt default StorageClass), not rewrite it.
    assert (
        "is-default-virt-class" in node_disk.description
        or "default StorageClass for virtualization" in node_disk.description
    )
    csi = knowledge_base.get_entry("7.3.tsr.3_9_5_csi_drivers")
    assert csi is not None
    assert "Validates installed CSI drivers" in csi.description


def test_chunk_d_inventory_descriptions_present() -> None:
    knowledge_base = load_kb()
    for check_id in CHUNK_D_INVENTORY:
        entry = knowledge_base.get_entry(check_id)
        assert entry is not None, check_id
        assert entry.description.strip(), check_id
        assert entry.recommendation.strip(), check_id
