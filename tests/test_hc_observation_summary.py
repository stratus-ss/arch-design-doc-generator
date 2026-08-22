"""Public-contract tests for §6.2 Observation assembly."""
from __future__ import annotations

from hc_report.models import Finding
from hc_report.renderer import _build_findings_sections

# Bug: Observation stays count-only, or drops pattern, or drops the TSR remainder
# Mutant: Skip pattern, skip extract, or keep _summarize_evidence(text) count-only
# Contract: public

# Bug: Same sentence printed twice when pattern text equals the FAIL reason
# Mutant: Skip casefold equality check
# Contract: public

# Bug: n/a FAIL reason still printed in Observation
# Mutant: Skip usable-text check on the extracted layer
# Contract: public

# Bug: Untagged dump chopped mid-word at 200; or no pattern; or a false count sentence
# Mutant: Keep _truncate_at_word_boundary(flat, 200) and skip pattern
# Contract: public

# Bug: No pattern → Observation is count-only
# Mutant: Call extract only when a pattern matched
# Contract: public


def _observation_block(markdown: str) -> str:
    start = markdown.index("**Observation:**")
    end = markdown.index("**Recommendation:**")
    return markdown[start:end]


def _priority_finding(check_id: str, evidence: str, title: str) -> Finding:
    return Finding(
        id="6.2.2.1",
        title=title,
        priority="P1",
        description=evidence,
        recommendation="review",
        check_id=check_id,
    )


def test_observation_includes_count_pattern_and_extracted_reason() -> None:
    evidence = (
        "FileSystem Type: [FAIL] - reason: the access modes include RWX what indicates "
        "that file storage is used, while Red Hat strongly recommends block storage\n"
        "other: [WARNING] - reason: extra\n"
        "[PASS] a\n"
        "[PASS] b\n"
        "[PASS] c\n"
        "[PASS] d\n"
        "[PASS] e"
    )
    finding = _priority_finding(
        "7.3.tsr.3_7_2_monitoring_storage_type",
        evidence,
        "3.7.2. Monitoring Storage Type",
    )
    block = _observation_block(_build_findings_sections([finding]))
    assert "sub-checks evaluated" in block
    assert "block storage" in block or "RWX/file storage" in block
    assert "RWX" in block
    assert "emptyDir" not in block
    assert "Prometheus metrics, Alertmanager state" not in block


def test_observation_dedups_identical_pattern_and_reason() -> None:
    evidence = (
        "storage: [FAIL] - reason: Monitoring uses RWX/file storage; block storage is recommended\n"
        "[PASS] other"
    )
    finding = _priority_finding(
        "7.3.tsr.3_7_2_monitoring_storage_type",
        evidence,
        "3.7.2. Monitoring Storage Type",
    )
    block = _observation_block(_build_findings_sections([finding]))
    assert block.count("block storage is recommended") == 1
    assert "sub-checks evaluated" in block


def test_observation_omits_unusable_extracted_reason() -> None:
    finding = _priority_finding(
        "7.9.synthetic.missing",
        "widget: [FAIL] - reason: n/a\n[PASS] other",
        "Synthetic widget check",
    )
    block = _observation_block(_build_findings_sections([finding]))
    assert "sub-checks evaluated" in block
    assert "n/a" not in block
    assert "N/a" not in block


def test_observation_untagged_uses_pattern_and_sentence_cap() -> None:
    first_sentence = (
        "Admission controllers declare a Failure Policy other than Ignore "
        "for cluster-scoped API resources."
    )
    second_sentence = (
        "This filler sentence describes additional webhook configuration notes "
        "that must be long enough to exceed the two-hundred-character prose cap "
        "so truncation can drop the distinctive tail marker "
        "without chopping the first sentence mid-word ZZZWEBHOOKTAIL"
    )
    finding = _priority_finding(
        "7.3.tsr.3_13_webhooks",
        f"{first_sentence} {second_sentence}",
        "3.13. Webhooks",
    )
    block = _observation_block(_build_findings_sections([finding]))
    assert (
        "failurePolicy" in block
        or "Failure Policy" in block
        or "Webhooks watch" in block
    )
    assert first_sentence in block
    assert "ZZZWEBHOOKTAIL" not in block
    assert "sub-checks evaluated" not in block


def test_observation_extracts_fail_reason_without_pattern() -> None:
    evidence = (
        "noise [INFO] skip\n"
        "widget check: [FAIL] - reason: widgets are on fire\n"
        "[PASS] other"
    )
    finding = _priority_finding(
        "7.9.synthetic.missing",
        evidence,
        "Synthetic widget check",
    )
    block = _observation_block(_build_findings_sections([finding]))
    assert "sub-checks evaluated" in block
    assert "Widgets are on fire" in block
    assert "noise" not in block
    assert "skip" not in block
