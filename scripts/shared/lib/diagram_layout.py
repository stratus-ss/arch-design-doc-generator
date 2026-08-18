"""Shared diagram filename prefixes and slug helpers."""

from __future__ import annotations

import re

PHASE_DIAGRAM_PREFIXES = {
    "phase1": ["HLD_Phase1_", "LLD_Phase1_", "HLD_phase1_", "LLD_phase1_"],
    "phase2": ["HLD_Phase2_", "LLD_Phase2_", "HLD_phase2_", "LLD_phase2_"],
    "phase3": ["HLD_Phase3_", "LLD_Phase3_", "HLD_phase3_", "LLD_phase3_"],
    "phase4": ["HLD_Phase4_", "LLD_Phase4_", "HLD_phase4_", "LLD_phase4_"],
}

TOP_LEVEL_PREFIXES = [
    "HLD_Network_",
    "HLD_Storage_",
    "HLD_Physical_",
    "HLD_Observability_",
    "HLD_Provisioning_",
    "HLD_GitOps_",
    "HLD_ACM_",
    "HLD_RBAC_",
    "HLD_Platform_",
    "HLD_External_",
    "HLD_Backup_",
    "HLD_Fleet_",
    "HLD_Migration_",
    "HLD_Decision_",
    "HLD_Master_",
]


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:60]


def phase_tag_from_basename(base: str) -> str:
    lower = base.lower()
    if "phase1" in lower:
        return "phase1"
    if "phase2" in lower:
        return "phase2"
    if "phase3" in lower:
        return "phase3"
    if "phase4" in lower:
        return "phase4"
    if "combined" in lower:
        return "combined"
    return "misc"
