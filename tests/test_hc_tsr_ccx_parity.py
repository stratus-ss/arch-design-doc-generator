"""Public-contract tests for TSR/CCX parity parsing, expansion, and CLI profiles."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Bug: Parser misses Status/Check leaf tables
# Mutant: Change _extract_leaf_check status regex
# Contract: public

# Bug: Name match wins over UUID match
# Mutant: Return first name match before id matches
# Contract: public

# Bug: Missing TSR HTML scores catalog FAIL
# Mutant: Default status "FAIL" when tsr_runtime_path is None
# Contract: public

# Bug: Missing CCX applies status_hint FAIL
# Mutant: Force use_ccx_baseline_status=True inside evaluate_checks
# Contract: public

# Bug: CLI advisory path never calls expand or omits source=tsr in audit
# Mutant: Skip _parse_tsr_html_runtime
# Contract: public

# Bug: Default/core leak catalog rows into core profile
# Mutant: Ignore check_profile=="core" early return
# Contract: public


def _ensure_health_check_path(project_root: Path) -> None:
    health_check_path = str(project_root / "scripts" / "health_check")
    if health_check_path not in sys.path:
        sys.path.insert(0, health_check_path)


def _pythonpath(project_root: Path) -> str:
    paths = [
        str(project_root / "scripts" / "health_check"),
        str(project_root / "scripts" / "shared" / "lib"),
    ]
    existing = os.environ.get("PYTHONPATH")
    if existing:
        paths.append(existing)
    return ":".join(paths)


def _write_tiny_catalog(catalog_path: Path, source: str) -> None:
    payload = {
        "schema_version": 1,
        "entries": [
            {
                "check_id": f"7.1.{source}.synthetic_no_runtime",
                "category_id": "7.1",
                "category_name": "Base Platform Checks",
                "source": source,
                "group": "section1",
                "title": "Synthetic No Runtime Check",
                "status_hint": "FAIL",
                "tsr_ref": "1.99",
                "tags": [],
            }
        ],
    }
    catalog_path.write_text(json.dumps(payload), encoding="utf-8")


def _prepare_report_workspace(tmp_path: Path, project_root: Path) -> Path:
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
    (fixture_dir / "03_base_platform" / "infrastructure.json").write_text(
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
    return fixture_dir


def _run_generate_report(
    project_root: Path,
    tmp_path: Path,
    fixture_dir: Path,
    report_dir: Path,
    extra_args: list[str],
) -> subprocess.CompletedProcess:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = _pythonpath(project_root)
    return subprocess.run(
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
            str(tmp_path / "templates" / "Health_Check" / "Template_HC_Report.md"),
            "--dry-run",
            *extra_args,
        ],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        env=environment,
    )


def test_parse_tsr_html_extracts_failing_leaf(project_root: Path) -> None:
    _ensure_health_check_path(project_root)
    from hc_report.tsr_parser import parse_tsr_html

    html = (project_root / "tests" / "fixtures" / "hc_tsr" / "minimal.html").read_text(
        encoding="utf-8"
    )
    records = parse_tsr_html(html)
    matching = [
        record
        for record in records
        if record.get("source") == "tsr"
        and record.get("status") == "FAIL"
        and "tsr" in str(record.get("check_id", ""))
        and "synthetic" in str(record.get("evidence", "")).lower()
    ]
    assert matching, records


def test_discover_tsr_html_prefers_cluster_id(tmp_path: Path, project_root: Path) -> None:
    _ensure_health_check_path(project_root)
    from hc_report.parity import discover_tsr_html

    cluster_id = "00000000-0000-0000-0000-000000000001"
    (tmp_path / "by-name.html").write_text("cluster fixture-cluster only", encoding="utf-8")
    (tmp_path / "by-id.html").write_text(cluster_id, encoding="utf-8")
    discovered = discover_tsr_html(
        tmp_path, cluster_id=cluster_id, cluster_name="fixture-cluster"
    )
    assert discovered == tmp_path / "by-id.html"


def test_expand_extended_without_runtime_is_skipped(
    tmp_path: Path, project_root: Path
) -> None:
    _ensure_health_check_path(project_root)
    from hc_report.parity import expand_with_parity_checks

    catalog_path = tmp_path / "catalog.json"
    _write_tiny_catalog(catalog_path, "tsr")
    expanded = expand_with_parity_checks(
        [],
        {},
        include_tsr=True,
        include_ccx=False,
        use_ccx_baseline_status=False,
        catalog_path=catalog_path,
        tsr_runtime_path=None,
    )
    assert expanded, "expected a catalog row"
    assert expanded[0].status == "SKIPPED"
    assert expanded[0].status != "FAIL"


def test_expand_advisory_without_ccx_payload_is_skipped(
    tmp_path: Path, project_root: Path
) -> None:
    _ensure_health_check_path(project_root)
    from hc_report.parity import expand_with_parity_checks

    catalog_path = tmp_path / "catalog.json"
    _write_tiny_catalog(catalog_path, "ccx")
    expanded = expand_with_parity_checks(
        [],
        {"12_ccx": {}},
        include_tsr=False,
        include_ccx=True,
        use_ccx_baseline_status=False,
        catalog_path=catalog_path,
        tsr_runtime_path=None,
    )
    assert expanded, "expected a catalog row"
    assert expanded[0].status == "SKIPPED"


def test_hc_report_advisory_cli_writes_tsr_source(
    tmp_path: Path, project_root: Path
) -> None:
    fixture_dir = _prepare_report_workspace(tmp_path, project_root)
    shutil.copy2(
        project_root / "tests" / "fixtures" / "hc_tsr" / "minimal.html",
        tmp_path / "tsr.html",
    )
    report_dir = tmp_path / "report"
    result = _run_generate_report(
        project_root,
        tmp_path,
        fixture_dir,
        report_dir,
        [
            "--check-profile",
            "advisory",
            "--tsr-html",
            str(tmp_path / "tsr.html"),
            "--catalog-path",
            str(
                project_root
                / "scripts"
                / "health_check"
                / "hc_report"
                / "catalogs"
                / "tsr_ccx_crosswalk.json"
            ),
        ],
    )
    assert result.returncode == 0, result.stderr or result.stdout
    audit_files = list(report_dir.glob("*_audit_*.json"))
    assert audit_files, "expected an audit JSON under the output dir"
    audit = json.loads(audit_files[0].read_text(encoding="utf-8"))
    assert audit.get("check_profile") == "advisory"
    assert any(row.get("source") == "tsr" for row in audit.get("checks", []))


def test_hc_report_core_still_has_no_tsr_source(
    tmp_path: Path, project_root: Path
) -> None:
    fixture_dir = _prepare_report_workspace(tmp_path, project_root)
    report_dir = tmp_path / "report"
    result = _run_generate_report(
        project_root,
        tmp_path,
        fixture_dir,
        report_dir,
        ["--check-profile", "core"],
    )
    assert result.returncode == 0, result.stderr or result.stdout
    audit_files = list(report_dir.glob("*_audit_*.json"))
    assert audit_files, "expected an audit JSON under the output dir"
    audit = json.loads(audit_files[0].read_text(encoding="utf-8"))
    sources = {row.get("source") for row in audit.get("checks", [])}
    assert "tsr" not in sources
    assert "ccx" not in sources
