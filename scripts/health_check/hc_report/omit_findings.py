"""Omit Chapter 6 findings by check ID and name the pruned report path."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from hc_report.findings import _PRIORITY_PREFIX
from hc_report.models import Finding


@dataclass
class OmitApplyResult:
    kept: list[Finding]
    unmatched: tuple[str, ...]
    omitted_count: int


def load_omit_check_ids(path: Path) -> tuple[str, ...]:
    loaded: list[str] = []
    seen: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        check_id = raw_line.strip()
        if not check_id or check_id.startswith("#"):
            continue
        if check_id in seen:
            continue
        seen.add(check_id)
        loaded.append(check_id)
    return tuple(loaded)


def apply_finding_omit(
    findings: list[Finding], omit_ids: tuple[str, ...]
) -> OmitApplyResult:
    omit_set = set(omit_ids)
    covered: set[str] = set()
    kept: list[Finding] = []
    for finding in findings:
        member_ids = set(finding.member_check_ids)
        if finding.check_id:
            member_ids.add(finding.check_id)
        hits = member_ids & omit_set
        if hits:
            covered.update(hits)
            continue
        kept.append(finding)
    unmatched = tuple(omit_id for omit_id in omit_ids if omit_id not in covered)
    return OmitApplyResult(
        kept=kept,
        unmatched=unmatched,
        omitted_count=len(findings) - len(kept),
    )


def compact_finding_ids(findings: list[Finding]) -> list[Finding]:
    counters: dict[str, int] = {priority: 0 for priority in _PRIORITY_PREFIX}
    compacted: list[Finding] = []
    for finding in findings:
        counters[finding.priority] += 1
        new_id = f"{_PRIORITY_PREFIX[finding.priority]}.{counters[finding.priority]}"
        compacted.append(replace(finding, id=new_id))
    return compacted


def pruned_report_path(original_report: Path) -> Path:
    return original_report.with_name(original_report.stem + "_pruned.md")
