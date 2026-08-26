"""Public-contract tests for draft_summary_conclusion CLI (sidecar + in-place)."""
from __future__ import annotations

from pathlib import Path

import pytest

from draft_summary_conclusion import (
    apply_summary_conclusion,
    default_summary_conclusion_path,
    default_prompt_output_path,
    fill_prompt,
    load_prompt_template,
    main,
    split_draft_chapters,
    EXECUTIVE_SUMMARY_HEADING,
    TECHNICAL_SUMMARY_HEADING,
)
from extract_finding_descriptions import (
    extract_finding_descriptions,
    format_finding_descriptions,
)

# Bug: Cluster path or Observation text sent to the model
# Mutant: Always pass include_source_path=True; concatenate raw report markdown
# Contract: public

# Bug: Output written under cwd or a globbed directory
# Mutant: Path("out.md") ignore report parent
# Contract: public

# Bug: Dry-run still calls invoke_ai
# Mutant: Unconditional invoke_ai(...)
# Contract: public

# Bug: Missing report exits 0 or traceback
# Mutant: No is_file() check
# Contract: public

# Bug: Prompt template not filled or findings missing from output file
# Mutant: Skip {{FINDING_DUMP}} replacement; write empty file
# Contract: public

# Bug: In-place splice misses headings or clobbers Summary Statistics
# Mutant: Replace from Chapter 3 through Chapter 8
# Contract: public

# Bug: Missing headings still rewrite the file
# Mutant: apply_summary_conclusion returns original on miss
# Contract: public

# Bug: Container still creates repo .cursor-sdk-venv
# Mutant: Always call ensure_cursor_sdk
# Contract: public

# Bug: claude/codex --in-place invokes anyway
# Mutant: Skip CONTAINER_DRAFT_TOOLS check
# Contract: public

# Bug: --in-place writes sidecar instead of the report
# Mutant: Ignore --in-place flag
# Contract: public

_FIXTURE = """## Chapter 1. Introduction

Findings are classified P0–P3.

## Chapter 6. Observations and Recommendations

### P1: High

#### 6.2.2.1. Monitoring configuration

**Check ID:** `7.3.monitoring.config`

**Description:**

The cluster monitoring stack uses temporary storage.

**Observation:**

Cluster-monitoring-config has no volumeClaimTemplate; Prometheus storage is ephemeral.

### P2: Medium

#### 6.2.3.1. Identity available updates

**Check ID:** `7.1.identity.updates`

**Description:**

Identity provider updates are available.

**Observation:**

An update is listed.

## Chapter 7. Raw Check Report
"""


def test_prompt_omits_source_path_and_observation(tmp_path: Path) -> None:
    findings = extract_finding_descriptions(_FIXTURE)
    dump = format_finding_descriptions(
        findings,
        tmp_path / "Example_OpenShift_Health_Check_one-6x489.md",
        include_source_path=False,
    )
    assert "one-6x489" not in dump
    assert "Finding descriptions from:" not in dump
    assert "volumeClaimTemplate" not in dump
    assert "temporary storage" in dump
    template = load_prompt_template(
        Path("scripts/health_check/prompts/draft_summary_conclusion.md")
    )
    filled = fill_prompt(template, dump)
    assert "one-6x489" not in filled
    assert "volumeClaimTemplate" not in filled
    assert "{{FINDING_DUMP}}" not in filled
    assert "temporary storage" in filled


def test_summary_conclusion_output_path_beside_report(tmp_path: Path) -> None:
    report = tmp_path / "clusters" / "Example_OpenShift_Health_Check_foo.md"
    expected = tmp_path / "clusters" / "Example_OpenShift_Health_Check_foo_summary_conclusion.md"
    assert default_summary_conclusion_path(report) == expected


def test_dry_run_writes_prompt_without_invoke(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = tmp_path / "report.md"
    report.write_text(_FIXTURE, encoding="utf-8")
    calls: list[str] = []

    def fake_invoke(*_args, **_kwargs) -> str:
        calls.append("invoked")
        return "should not run"

    monkeypatch.setattr("draft_summary_conclusion.invoke_ai", fake_invoke)
    monkeypatch.setattr(
        "sys.argv",
        ["draft_summary_conclusion.py", "--dry-run", str(report)],
    )
    main()
    assert calls == []
    prompt_path = tmp_path / "report_summary_conclusion.prompt.md"
    assert prompt_path.is_file()


def test_missing_report_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "missing.md"
    monkeypatch.setattr(
        "sys.argv",
        ["draft_summary_conclusion.py", str(missing)],
    )
    with pytest.raises(SystemExit) as caught:
        main()
    assert caught.value.code == 2


def test_dry_run_end_to_end_from_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = tmp_path / "fixture.md"
    report.write_text(_FIXTURE, encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        ["draft_summary_conclusion.py", "--dry-run", str(report)],
    )
    main()
    prompt_path = default_prompt_output_path(report)
    filled = prompt_path.read_text(encoding="utf-8")
    assert "## Chapter 3. Executive Summary" in filled
    assert "## Chapter 8. Conclusions" in filled
    assert "temporary storage" in filled
    assert "7.3.monitoring.config" in filled
    assert "volumeClaimTemplate" not in filled
    assert "{{FINDING_DUMP}}" not in filled


_APPLY_REPORT = """## Chapter 3. Executive Summary

### 3.1 Executive Summary

PLACEHOLDER EXECUTIVE SUMMARY

### 3.2 Technical Summary

PLACEHOLDER TECHNICAL SUMMARY

### Summary Statistics

| Metric | Count |
|--------|------:|
| Total  |     1 |

## Chapter 4. Scope

In scope.

## Chapter 8. Conclusions

PLACEHOLDER CONCLUSIONS

---

*This document is prepared for Client and is intended for internal use only.
"""

_MODEL_CHAPTERS = """## Chapter 3. Executive Summary

### 3.1 Executive Summary

The cluster is at elevated risk with 1 critical and 12 high findings.

### 3.2 Technical Summary

Control-plane etcd storage does not meet latency requirements (`7.3.etcd.fsync`).

- **P0** — CrashLoopBackOff pods (`7.5.pods.crashloop`)
- **P1** — Etcd fsync latency (`7.3.etcd.fsync`)

## Chapter 8. Conclusions

Drafted conclusions paragraph.
"""


def test_apply_replaces_chapter_three_and_eight() -> None:
    updated = apply_summary_conclusion(
        _APPLY_REPORT,
        "The cluster is at elevated risk with 1 critical and 12 high findings.",
        "Control-plane etcd storage does not meet latency requirements (`7.3.etcd.fsync`).\n\n- **P0** — CrashLoopBackOff pods (`7.5.pods.crashloop`)",
        "Drafted conclusions paragraph.",
    )
    assert "elevated risk" in updated
    assert "7.3.etcd.fsync" in updated
    assert "Drafted conclusions paragraph." in updated
    assert "PLACEHOLDER EXECUTIVE SUMMARY" not in updated
    assert "PLACEHOLDER TECHNICAL SUMMARY" not in updated
    assert "PLACEHOLDER CONCLUSIONS" not in updated
    assert "### Summary Statistics" in updated
    assert "## Chapter 4. Scope" in updated
    assert "*This document is prepared" in updated
    assert EXECUTIVE_SUMMARY_HEADING in updated
    assert TECHNICAL_SUMMARY_HEADING in updated


def test_apply_stops_if_headings_missing() -> None:
    with pytest.raises(ValueError, match="Chapter 3"):
        apply_summary_conclusion("no headings", "a", "b", "c")


def test_in_place_uses_cursor_python_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = tmp_path / "report.md"
    report.write_text(_APPLY_REPORT, encoding="utf-8")
    captured: dict[str, str] = {}

    def fake_invoke(
        _prompt: str,
        _tool: str,
        _model: str,
        _timeout: int,
        _retries: int,
        cursor_python: str,
    ) -> str:
        captured["cursor_python"] = cursor_python
        return _MODEL_CHAPTERS

    def fail_sdk(_root: Path) -> str:
        raise AssertionError("ensure_cursor_sdk must not run")

    monkeypatch.setenv("HC_CURSOR_PYTHON", "/opt/container-python")
    monkeypatch.setattr("draft_summary_conclusion.invoke_ai", fake_invoke)
    monkeypatch.setattr("draft_summary_conclusion.ensure_cursor_sdk", fail_sdk)
    monkeypatch.setattr("draft_summary_conclusion.ensure_cursor_key", lambda: "key")
    monkeypatch.setattr(
        "sys.argv",
        ["draft_summary_conclusion.py", "--in-place", str(report)],
    )
    main()
    assert captured["cursor_python"] == "/opt/container-python"


def test_non_cursor_tool_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = tmp_path / "report.md"
    report.write_text(_APPLY_REPORT, encoding="utf-8")
    original = report.read_text(encoding="utf-8")
    calls: list[str] = []

    def fake_invoke(*_args, **_kwargs) -> str:
        calls.append("invoked")
        return _MODEL_CHAPTERS

    monkeypatch.setattr("draft_summary_conclusion.invoke_ai", fake_invoke)
    monkeypatch.setattr(
        "sys.argv",
        ["draft_summary_conclusion.py", "--in-place", "--tool", "claude", str(report)],
    )
    with pytest.raises(SystemExit) as caught:
        main()
    assert caught.value.code == 2
    assert calls == []
    assert report.read_text(encoding="utf-8") == original


def test_in_place_mocked_invoke_rewrites_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = tmp_path / "report.md"
    report.write_text(_APPLY_REPORT, encoding="utf-8")
    monkeypatch.setenv("HC_CURSOR_PYTHON", "/opt/container-python")
    monkeypatch.setattr(
        "draft_summary_conclusion.invoke_ai",
        lambda *_args, **_kwargs: _MODEL_CHAPTERS,
    )
    monkeypatch.setattr("draft_summary_conclusion.ensure_cursor_key", lambda: "key")
    monkeypatch.setattr(
        "sys.argv",
        ["draft_summary_conclusion.py", "--in-place", str(report)],
    )
    main()
    rewritten = report.read_text(encoding="utf-8")
    assert "elevated risk" in rewritten
    assert "Drafted conclusions paragraph." in rewritten
    assert "PLACEHOLDER EXECUTIVE SUMMARY" not in rewritten
    assert "PLACEHOLDER TECHNICAL SUMMARY" not in rewritten
    assert not report.with_name(report.name + ".tmp").exists()


def test_split_draft_chapters_missing_heading_raises() -> None:
    missing_tech = (
        "## Chapter 3. Executive Summary\n\n"
        "### 3.1 Executive Summary\n\nSome text.\n\n"
        "## Chapter 8. Conclusions\n\nDone.\n"
    )
    with pytest.raises(ValueError, match="missing.*3.2 Technical Summary"):
        split_draft_chapters(missing_tech)

    missing_exec = (
        "## Chapter 3. Executive Summary\n\n"
        "### 3.2 Technical Summary\n\nDetail.\n\n"
        "## Chapter 8. Conclusions\n\nDone.\n"
    )
    with pytest.raises(ValueError, match="missing.*3.1 Executive Summary"):
        split_draft_chapters(missing_exec)

    with pytest.raises(ValueError, match="missing Chapter 3 or Chapter 8"):
        split_draft_chapters("random model garbage")


def test_split_draft_chapters_valid_output() -> None:
    executive, technical, conclusions = split_draft_chapters(_MODEL_CHAPTERS)
    assert "elevated risk" in executive
    assert "7.3.etcd.fsync" in technical
    assert "P0" in technical
    assert "Drafted conclusions paragraph." in conclusions
