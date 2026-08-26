"""Data classes shared across the hc_report package."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CheckResult:
    category_id: str      # e.g. "7.1"
    category_name: str
    check_id: str
    description: str
    status: str           # PASS, FAIL, WARNING, INFO, NOT_APPLICABLE, SKIPPED
    evidence: str         # Brief evidence string from collected data
    resource_name: str = ""
    source: str = "deterministic"  # deterministic, tsr, ccx
    tsr_ref: str = ""              # e.g. 3.10.2, CCX:internal
    tags: list[str] = field(default_factory=list)
    doc_ref: str = ""              # URL citing official docs proving/contradicting status
    scoring_basis: str = ""        # doc_backed, engine_policy, or empty


@dataclass
class Finding:
    id: str               # e.g. "6.2.1.1"
    title: str
    priority: str         # P0, P1, P2, P3
    description: str
    recommendation: str
    impact: str = ""
    impact_scope: str = ""
    impact_detail: str = ""
    kcs_refs: list[str] = field(default_factory=list)
    check_id: str = ""    # CheckResult.check_id this finding was derived from
    member_check_ids: tuple[str, ...] = field(default_factory=tuple)
