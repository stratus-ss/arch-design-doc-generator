"""Public-contract tests for §6.2 Recommendation HTML line breaks."""
from __future__ import annotations

import shutil
import subprocess

from hc_report.models import Finding
from hc_report.renderer import _build_findings_sections

# Bug: Numbered Verification steps with \n (not \n\n) emit as one HTML paragraph (run-on)
# Mutant: _build_findings_sections interpolates finding.recommendation with no hard breaks
# Contract: public

# Bug: Helper injects <br> into a one-line rec
# Mutant: Unconditional "<br>" prefix/suffix on every recommendation
# Contract: public


def _recommendation_block(markdown: str) -> str:
    start = markdown.index("**Recommendation:**")
    end = markdown.index("**Level of Impact:**")
    return markdown[start:end]


def _priority_finding(recommendation: str) -> Finding:
    return Finding(
        id="6.2.2.1",
        title="Synthetic etcd storage",
        priority="P1",
        description="etcd disk latency is elevated.",
        recommendation=recommendation,
        check_id="7.9.synthetic.etcd-disk",
    )


def _pandoc_html(markdown: str) -> str:
    pandoc = shutil.which("pandoc")
    if pandoc is None:
        raise AssertionError("pandoc is required to verify <strong>Verification:</strong>")
    return subprocess.check_output(
        [pandoc, "-f", "markdown", "-t", "html"],
        input=markdown,
        text=True,
    )


def test_recommendation_single_newlines_become_html_breaks() -> None:
    finding = _priority_finding(
        "Move etcd onto dedicated NVMe.\n\n**Verification:**\n1. first step\n2. second step"
    )
    block = _recommendation_block(_build_findings_sections([finding]))
    assert "1. first step<br>" in block
    assert "1. first step 2. second step" not in block
    assert "**Verification:**<br>" in block
    html = _pandoc_html(block)
    assert "<strong>Verification:</strong>" in html


def test_recommendation_without_newlines_unchanged() -> None:
    finding = _priority_finding("Move etcd onto dedicated NVMe.")
    block = _recommendation_block(_build_findings_sections([finding]))
    assert "<br>" not in block
