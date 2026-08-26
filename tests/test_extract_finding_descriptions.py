"""Public-contract tests for extract_finding_descriptions CLI."""
from __future__ import annotations

from pathlib import Path

import pytest

from extract_finding_descriptions import (
    extract_finding_descriptions,
    format_finding_descriptions,
    main,
)

# Bug: Observation leaked or check_id omitted
# Mutant: Stop at next ####; skip Check ID parse
# Contract: public

# Bug: Missing path exits 0 or traceback
# Mutant: No exists check
# Contract: public

# Bug: Wrong band / matching P1 in body
# Mutant: Regex on whole file for P1
# Contract: public

_FIXTURE = """## Chapter 1. Introduction

Findings are classified P0–P3.

## Chapter 6. Observations and Recommendations

### 6.1 Critical Findings Summary

| Priority | Finding | Summary |
|----------|---------|---------|
| P1 | 6.2.2.1 — Monitoring configuration | Cluster-monitoring-config has no volumeClaimTemplate. |

### P1: High

#### 6.2.2.1. Monitoring configuration

**Check ID:** `7.3.monitoring.config`
**TSR ref:** n/a

**Description:**

The cluster monitoring stack uses temporary storage.

**Observation:**

Cluster-monitoring-config has no volumeClaimTemplate; Prometheus storage is ephemeral.

**Recommendation:**

Add a volumeClaimTemplate.

### P2: Medium

#### 6.2.3.1. Identity available updates

**Check ID:** `7.1.identity.updates`

**Description:**

Identity provider updates are available.

**Observation:**

An update is listed.

## Chapter 7. Raw Check Report
"""


def test_extracts_description_and_check_id_not_observation() -> None:
    findings = extract_finding_descriptions(_FIXTURE)
    assert len(findings) == 2
    first = findings[0]
    assert first.check_ids == ["7.3.monitoring.config"]
    assert "temporary storage" in first.description
    assert "volumeClaimTemplate" not in first.description
    assert "Add a volumeClaimTemplate" not in first.description
    rendered = format_finding_descriptions(findings, Path("report.md"))
    assert "Check ID: 7.3.monitoring.config" in rendered
    assert "Check ID: 7.1.identity.updates" in rendered


def test_missing_report_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "missing.md"
    monkeypatch.setattr(
        "sys.argv",
        ["extract_finding_descriptions.py", str(missing)],
    )
    with pytest.raises(SystemExit) as caught:
        main()
    assert caught.value.code == 2


def test_priority_bands_from_fixture() -> None:
    findings = extract_finding_descriptions(_FIXTURE)
    assert [finding.priority for finding in findings] == ["P1", "P2"]
    assert findings[0].finding_id == "6.2.2.1"
    assert findings[1].finding_id == "6.2.3.1"
    rendered = format_finding_descriptions(findings, Path("report.md"))
    assert "P0=0 P1=1 P2=1 P3=0 (total 2)" in rendered
    assert rendered.count("## P1") == 1
    assert rendered.count("## P2") == 1
    assert "6.1 Critical" not in rendered
