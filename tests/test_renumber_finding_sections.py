"""Public-contract tests for renumber_finding_sections CLI."""
from __future__ import annotations

from pathlib import Path

import pytest

from renumber_finding_sections import main, renumber_finding_sections

# Bug: Moved block keeps old 6.2.2.n id and stays in §6.1
# Mutant: Ignore ### P band; only increment a global counter
# Contract: public

# Bug: Swap leaves both headings as 6.2.2.1 (chained replace)
# Mutant: Sequential str.replace without placeholders
# Contract: public

# Bug: Missing path exits 0 or traceback
# Mutant: No is_file() check
# Contract: public

# Bug: Chapter 7 still points at the old finding-* id
# Mutant: Rewrite #### headings only
# Contract: public

_FIXTURE = """## Chapter 6. Observations and Recommendations

### 6.1 Critical Findings Summary

| Priority | Finding | Summary |
|----------|---------|---------|
| P1 | 6.2.2.1 — Monitoring configuration | Cluster-monitoring-config has no volumeClaimTemplate. |
| P1 | 6.2.2.2 — CrashLoopBackOff pods | 2 pods in CrashLoopBackOff. |

### 6.2 Observations and Recommendations by Priority

### P1: High

#### 6.2.2.2. CrashLoopBackOff pods

**Check ID:** `7.5.pods.crashloop`

**Observation:**

2 pods in CrashLoopBackOff.

<span id="finding-6-2-2-2" data-check-id="7.5.pods.crashloop"></span>

**Recommendation:**

Investigate.

### P2: Medium

#### 6.2.3.1. Identity available updates

**Check ID:** `7.1.identity.updates`

**Observation:**

An update is listed.

<span id="finding-6-2-3-1" data-check-id="7.1.identity.updates"></span>

### P3: Low

#### 6.2.2.1. Monitoring configuration

**Check ID:** `7.3.monitoring.config`

**Observation:**

Cluster-monitoring-config has no volumeClaimTemplate.

<span id="finding-6-2-2-1" data-check-id="7.3.monitoring.config"></span>

## Chapter 7. Raw Check Report

<span id="evidence-7-5-pods-crashloop" data-finding-ids="finding-6-2-2-2"></span>
<span id="evidence-7-3-monitoring-config" data-finding-ids="finding-6-2-2-1"></span>
"""


def test_moved_finding_takes_new_band_and_leaves_critical_table() -> None:
    rewritten, placements = renumber_finding_sections(_FIXTURE)
    ids = [(item.old_id, item.new_id, item.priority) for item in placements]
    assert ids == [
        ("6.2.2.2", "6.2.2.1", "P1"),
        ("6.2.3.1", "6.2.3.1", "P2"),
        ("6.2.2.1", "6.2.4.1", "P3"),
    ]
    assert "#### 6.2.2.1. CrashLoopBackOff pods" in rewritten
    assert "#### 6.2.4.1. Monitoring configuration" in rewritten
    assert "| P1 | 6.2.2.1 — CrashLoopBackOff pods |" in rewritten
    assert "Monitoring configuration" not in rewritten.split("### 6.2")[0]


def test_swap_does_not_collapse_both_ids() -> None:
    rewritten, _placements = renumber_finding_sections(_FIXTURE)
    assert rewritten.count("#### 6.2.2.1. CrashLoopBackOff pods") == 1
    assert rewritten.count("#### 6.2.4.1. Monitoring configuration") == 1
    assert "#### 6.2.2.2." not in rewritten


def test_missing_report_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "missing.md"
    monkeypatch.setattr(
        "sys.argv",
        ["renumber_finding_sections.py", str(missing)],
    )
    with pytest.raises(SystemExit) as caught:
        main()
    assert caught.value.code == 2


def test_updates_finding_anchor_and_chapter_7_link() -> None:
    rewritten, _placements = renumber_finding_sections(_FIXTURE)
    assert 'id="finding-6-2-2-1"' in rewritten
    assert 'id="finding-6-2-4-1"' in rewritten
    assert 'data-finding-ids="finding-6-2-2-1"' in rewritten
    assert 'data-finding-ids="finding-6-2-4-1"' in rewritten
    assert 'id="finding-6-2-2-2"' not in rewritten
    assert 'data-finding-ids="finding-6-2-2-2"' not in rewritten
