"""Public-contract functional tests for Health Check foundation (CQ11 allowlist)."""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import yaml

# Bug: hc_collect.sh finishes without writing manifest.json or category JSON
# Mutant: delete the manifest-write block in hc_collect.sh
# Contract: public

# Bug: cluster_name taken from ClusterVersion metadata.name ("version")
# Mutant: in derive_metadata, set cluster_name from ClusterVersion name
# Contract: public

# Bug: merge drops real JSON when a sibling dir has _hc_error
# Mutant: change is_stub to treat all dicts as stubs
# Contract: public

# Bug: PROJECT=HC falls through to OCP-V example
# Mutant: omit "hc" from PROJECT_TYPES
# Contract: public


def _stub_oc_env(tmp_path: Path, project_root: Path) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    dest = bin_dir / "oc"
    shutil.copy2(project_root / "tests" / "helpers" / "hc_stub_oc.py", dest)
    dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    kubeconfig = tmp_path / "kubeconfig"
    kubeconfig.write_text("", encoding="utf-8")
    environment = os.environ.copy()
    environment["PATH"] = str(bin_dir) + ":" + environment.get("PATH", "")
    environment["KUBECONFIG"] = str(kubeconfig)
    return environment


def _run_collect_category_03(tmp_path: Path, project_root: Path) -> subprocess.CompletedProcess[str]:
    output_dir = tmp_path / "hc_collect"
    environment = _stub_oc_env(tmp_path, project_root)
    return subprocess.run(
        [
            "bash",
            str(project_root / "scripts" / "health_check" / "collect" / "hc_collect.sh"),
            "--categories",
            "03",
            "--output-dir",
            str(output_dir),
        ],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        env=environment,
    )


def test_hc_collect_category_03_writes_manifest(tmp_path: Path, project_root: Path) -> None:
    result = _run_collect_category_03(tmp_path, project_root)
    assert result.returncode == 0, result.stderr or result.stdout
    collect_dir = tmp_path / "hc_collect"
    assert (collect_dir / "manifest.json").exists()
    assert (collect_dir / "03_base_platform" / "infrastructure.json").exists()
    assert (collect_dir / "03_base_platform" / "clusterversion.json").exists()
    manifest = json.loads((collect_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "03_base_platform" in manifest["categories"]
    assert manifest["total_files"] >= 1


def test_hc_collect_then_derive_metadata_writes_json(tmp_path: Path, project_root: Path) -> None:
    result = _run_collect_category_03(tmp_path, project_root)
    assert result.returncode == 0, result.stderr or result.stdout
    health_check_path = str(project_root / "scripts" / "health_check")
    if health_check_path not in sys.path:
        sys.path.insert(0, health_check_path)
    from hc_report.loader import load_results
    from hc_report.metadata import derive_metadata

    results = load_results(tmp_path / "hc_collect")
    metadata = derive_metadata(results, {"client_name": "Example Client", "health_check": {}})
    output_file = tmp_path / "hc_foundation_metadata.json"
    output_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    assert output_file.exists()
    assert metadata["cluster_name"] == "test-cluster-abc123"
    assert metadata["cluster_name"] != "version"
    assert metadata["client_prefix"] == "EC"


def test_hc_merge_writes_unified_results_dir(tmp_path: Path, project_root: Path) -> None:
    dir_a = tmp_path / "a" / "03_base_platform"
    dir_b = tmp_path / "b" / "03_base_platform"
    dir_a.mkdir(parents=True)
    dir_b.mkdir(parents=True)
    real_cv = {
        "kind": "ClusterVersion",
        "apiVersion": "config.openshift.io/v1",
        "metadata": {"name": "version"},
        "status": {"desired": {"version": "4.18.1"}},
    }
    (dir_a / "clusterversion.json").write_text(json.dumps(real_cv), encoding="utf-8")
    (dir_b / "clusterversion.json").write_text(json.dumps({"_hc_error": True}), encoding="utf-8")
    merged = tmp_path / "merged"
    result = subprocess.run(
        [
            sys.executable,
            str(project_root / "scripts" / "health_check" / "supportshell" / "hc_merge.py"),
            str(tmp_path / "a"),
            str(tmp_path / "b"),
            "-o",
            str(merged),
        ],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    merged_cv = json.loads((merged / "03_base_platform" / "clusterversion.json").read_text(encoding="utf-8"))
    assert merged_cv.get("_hc_error") is not True
    assert merged_cv["kind"] == "ClusterVersion"


def test_setup_hc_writes_project_yaml(tmp_path: Path, project_root: Path) -> None:
    shutil.copy2(project_root / "project.example.hc.yaml", tmp_path / "project.example.hc.yaml")
    environment = os.environ.copy()
    python_paths = [str(project_root / "scripts" / "shared" / "lib")]
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = ":".join(python_paths + ([existing] if existing else []))
    result = subprocess.run(
        [sys.executable, str(project_root / "scripts" / "setup_project.py"), str(tmp_path), "Example Client", "HC"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        env=environment,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    project_yaml = tmp_path / "project.yaml"
    assert project_yaml.exists()
    config = yaml.safe_load(project_yaml.read_text(encoding="utf-8"))
    assert config["engagement_type"] == "health-check"
    assert (tmp_path / "output" / "hc_collect").is_dir()
    assert (tmp_path / "output" / "Health_Check_Report").is_dir()
    hld_md = tmp_path / "output" / "HLD"
    assert not hld_md.exists() or not any(hld_md.rglob("*.md"))
