"""Public-contract functional tests for the Health Check report engine."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# Bug: generate_report.py exits non-zero or writes neither markdown nor audit JSON
# Mutant: skip _write_outputs or sys.exit(1) after render
# Contract: public

# Bug: AI imports reintroduced into cli.py
# Mutant: add `from ai_invoke import invoke_ai`
# Contract: public

# Bug: evaluate_checks returns empty or non-CheckResult values
# Mutant: return [] from evaluate_from_registry
# Contract: public


def _pythonpath(project_root: Path) -> str:
    paths = [
        str(project_root / "scripts" / "health_check"),
        str(project_root / "scripts" / "shared" / "lib"),
    ]
    existing = os.environ.get("PYTHONPATH")
    if existing:
        paths.append(existing)
    return ":".join(paths)


def test_hc_report_core_produces_markdown_and_audit(tmp_path: Path, project_root: Path) -> None:
    fixture_dir = tmp_path / "hc_collect"
    platform_dir = fixture_dir / "03_base_platform"
    platform_dir.mkdir(parents=True)
    clusterversion = {
        "kind": "ClusterVersion",
        "metadata": {"name": "version"},
        "spec": {"channel": "stable-4.18", "clusterID": "test-uuid"},
        "status": {"desired": {"version": "4.18.1"}, "history": []},
    }
    infrastructure = {
        "kind": "Infrastructure",
        "metadata": {"name": "cluster"},
        "spec": {},
        "status": {"infrastructureName": "test-cluster"},
    }
    (platform_dir / "clusterversion.json").write_text(
        json.dumps(clusterversion), encoding="utf-8"
    )
    (platform_dir / "infrastructure.json").write_text(
        json.dumps(infrastructure), encoding="utf-8"
    )
    manifest = {
        "categories": ["03_base_platform"],
        "total_files": 2,
        "timestamp": "2026-08-19T12:00:00Z",
        "files": [
            "03_base_platform/clusterversion.json",
            "03_base_platform/infrastructure.json",
        ],
    }
    (fixture_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    shutil.copy2(project_root / "project.example.hc.yaml", tmp_path / "project.yaml")
    template_dest = tmp_path / "templates" / "Health_Check" / "Template_HC_Report.md"
    template_dest.parent.mkdir(parents=True)
    shutil.copy2(
        project_root / "templates" / "Health_Check" / "Template_HC_Report.md",
        template_dest,
    )

    report_dir = tmp_path / "report"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = _pythonpath(project_root)
    result = subprocess.run(
        [
            sys.executable,
            str(project_root / "scripts" / "health_check" / "generate_report.py"),
            "--results-dir",
            str(fixture_dir),
            "--output-dir",
            str(report_dir),
            "--config",
            str(tmp_path / "project.yaml"),
            "--template",
            str(template_dest),
            "--check-profile",
            "core",
            "--dry-run",
        ],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        env=environment,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    markdown_files = list(report_dir.glob("*.md"))
    assert markdown_files, "expected a markdown report under the output dir"
    audit_files = list(report_dir.glob("*_audit_*.json"))
    assert audit_files, "expected an audit JSON under the output dir"
    audit = json.loads(audit_files[0].read_text(encoding="utf-8"))
    assert "metadata" in audit
    assert "checks" in audit
    assert "findings" in audit


def test_hc_report_cli_has_no_ai_imports(project_root: Path) -> None:
    cli_text = (project_root / "scripts" / "health_check" / "hc_report" / "cli.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "ai_invoke",
        "prompt_loader",
        "invoke_ai",
        "load_prompt_template",
        "CURSOR_API_KEY",
    )
    for token in forbidden:
        assert token not in cli_text, f"AI token {token!r} must not appear in cli.py"


def test_hc_evaluator_registry_returns_checks(project_root: Path) -> None:
    health_check_path = str(project_root / "scripts" / "health_check")
    if health_check_path not in sys.path:
        sys.path.insert(0, health_check_path)
    from hc_report.evaluators import evaluate_checks
    from hc_report.models import CheckResult

    results = {
        "03_base_platform": {
            "clusterversion": {
                "kind": "ClusterVersion",
                "metadata": {"name": "version"},
                "spec": {"channel": "stable-4.18", "clusterID": "test"},
                "status": {"desired": {"version": "4.18.1"}, "history": []},
            },
            "infrastructure": {
                "kind": "Infrastructure",
                "metadata": {"name": "cluster"},
                "status": {"infrastructureName": "test-cluster"},
                "spec": {},
            },
        },
        "04_topology": {},
        "05_components": {},
        "06_layered": {},
        "07_cluster_health": {},
        "08_day2": {},
        "09_security": {},
        "10_metrics": {},
        "11_hardware": {},
    }
    checks = evaluate_checks(results, check_profile="core")
    assert isinstance(checks, list)
    assert len(checks) > 0
    assert all(isinstance(check, CheckResult) for check in checks)


def test_parse_args_accepts_omit_check_ids_and_omit_strict(
    monkeypatch: pytest.MonkeyPatch, project_root: Path
) -> None:
    health_check_path = str(project_root / "scripts" / "health_check")
    if health_check_path not in sys.path:
        sys.path.insert(0, health_check_path)
    from hc_report.cli import parse_args

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate_report.py",
            "--omit-check-ids",
            "/tmp/x",
            "--omit-strict",
            "--dry-run",
        ],
    )
    args = parse_args()
    assert args.omit_check_ids == Path("/tmp/x")
    assert args.omit_strict is True
    assert args.dry_run is True
