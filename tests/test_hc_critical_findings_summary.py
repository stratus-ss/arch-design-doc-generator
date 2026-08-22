"""Public-contract tests for Chapter 4 and §6.1 finding summaries."""
from __future__ import annotations

from hc_report.models import Finding
from hc_report.renderer import _build_critical_findings, _build_critical_findings_summary

# Bug: Chapter 4/§6.1 use generic KB description when evidence is RWX
# Mutant: Prefer get_description over summary_patterns
# Contract: public

# Bug: No pattern dumps full evidence or KB text
# Mutant: Fall back to get_description or raw evidence dump
# Contract: public

# Bug: Empty/n/a reason still printed
# Mutant: Skip usable-text check
# Contract: public

# Bug: Mid-word 120-char cut
# Mutant: text[:120]
# Contract: public


def _high_priority_finding(check_id: str, evidence: str, title: str = "3.7.2. Monitoring Storage Type") -> Finding:
    return Finding(
        id="6.2.2.1",
        title=title,
        priority="P1",
        description=evidence,
        recommendation="review",
        check_id=check_id,
    )


def test_critical_summary_uses_pattern_not_kb_description() -> None:
    evidence = (
        "Prometheus is on RWX file storage for metrics; persistent block is missing."
    )
    finding = _high_priority_finding("7.3.tsr.3_7_2_monitoring_storage_type", evidence)
    chapter_four = _build_critical_findings_summary([finding])
    section_six = _build_critical_findings([finding])
    for output in (chapter_four, section_six):
        assert "block storage" in output or "RWX/file storage" in output
        assert "emptyDir" not in output
        assert "Prometheus metrics, Alertmanager state" not in output


def test_critical_summary_extracts_fail_reason_without_pattern() -> None:
    evidence = (
        "noise [INFO] skip\n"
        "widget check: [FAIL] - reason: widgets are on fire\n"
        "[PASS] other"
    )
    finding = _high_priority_finding("7.9.synthetic.missing", evidence, title="Synthetic widget check")
    chapter_four = _build_critical_findings_summary([finding])
    section_six = _build_critical_findings([finding])
    for output in (chapter_four, section_six):
        assert "Widgets are on fire" in output
        assert "noise" not in output
        assert "skip" not in output


def test_critical_summary_omits_unusable_text() -> None:
    finding = _high_priority_finding(
        "7.9.synthetic.missing",
        "[FAIL] - reason: n/a",
        title="Synthetic widget check",
    )
    chapter_four = _build_critical_findings_summary([finding])
    assert "- **6.2.2.1 — Synthetic widget check**" in chapter_four
    assert ": n/a" not in chapter_four
    section_six = _build_critical_findings([finding])
    data_rows = [
        line for line in section_six.splitlines() if line.startswith("| P1")
    ]
    assert len(data_rows) == 1
    cells = [cell.strip() for cell in data_rows[0].split("|")[1:-1]]
    assert cells[2] == ""
    assert "n/a" not in cells[2]


def test_critical_summary_truncates_at_sentence_boundary() -> None:
    first_sentence = (
        "The widget subsystem failed because replica pods cannot schedule on ready workers."
    )
    second_sentence = (
        "Additional diagnostic text continues with unused capacity details "
        "and a unique ending fragment called zebra-tail-token-999"
        + (" padding" * 40)
    )
    evidence = f"[FAIL] - reason: {first_sentence} {second_sentence}"
    finding = _high_priority_finding("7.9.synthetic.missing", evidence, title="Synthetic widget check")
    chapter_four = _build_critical_findings_summary([finding])
    section_six = _build_critical_findings([finding])
    for output in (chapter_four, section_six):
        assert first_sentence in output
        assert second_sentence[-20:] not in output
        assert not output.rstrip().endswith("padding")
