from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml


def _script_env(project_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    python_paths = [
        str(project_root / "scripts" / "shared" / "lib"),
    ]
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = ":".join(python_paths + ([existing] if existing else []))
    return env


def _prepare_ocpv_workspace(tmp_path: Path, project_root: Path) -> None:
    shutil.copy2(project_root / "project.example.yaml", tmp_path / "project.example.yaml")
    # Immutable templates
    shutil.copytree(project_root / "templates" / "ADR", tmp_path / "templates" / "ADR")
    shutil.copytree(
        project_root / "templates" / "HLD" / "markdown_files",
        tmp_path / "templates" / "HLD" / "markdown_files",
    )
    shutil.copytree(project_root / "templates" / "LLD", tmp_path / "templates" / "LLD")
    shutil.copytree(
        project_root / "templates" / "Diagrams" / "examples",
        tmp_path / "templates" / "Diagrams" / "examples",
    )
    # Engagement ADR dir (filled ADR lives at repo root)
    (tmp_path / "ADR").mkdir(parents=True, exist_ok=True)


def test_setup_ocpv(tmp_path: Path, project_root: Path) -> None:
    _prepare_ocpv_workspace(tmp_path, project_root)
    script_path = project_root / "scripts" / "setup_project.py"
    result = subprocess.run(
        [sys.executable, str(script_path), str(tmp_path), "Test Client", "OCP-V"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        env=_script_env(project_root),
    )
    assert result.returncode == 0, result.stderr or result.stdout

    project_yaml = tmp_path / "project.yaml"
    assert project_yaml.exists()
    cfg = yaml.safe_load(project_yaml.read_text(encoding="utf-8"))
    assert cfg["client_name"] == "Test Client"

    # Client working copies land under output/
    assert (tmp_path / "output" / "HLD" / "markdown_files" / "Test_OCP-V_HLD_DecisionJourney_phase1.md").exists()
    assert (tmp_path / "output" / "LLD" / "Test_OCP-V_LLD_Phase1_Foundation.md").exists()
    assert (tmp_path / "ADR" / "ADR_test.md").exists()


def _run_setup(
    tmp_path: Path, project_root: Path, extra_args: list[str] | None = None
) -> subprocess.CompletedProcess[str]:
    script_path = project_root / "scripts" / "setup_project.py"
    cmd = [sys.executable, str(script_path), str(tmp_path), "Test Client", "OCP-V"]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(
        cmd,
        cwd=str(project_root),
        capture_output=True,
        text=True,
        env=_script_env(project_root),
    )


def test_setup_refuses_overwrite_without_force(tmp_path: Path, project_root: Path) -> None:
    _prepare_ocpv_workspace(tmp_path, project_root)
    first = _run_setup(tmp_path, project_root)
    assert first.returncode == 0, first.stderr or first.stdout
    lld_path = tmp_path / "output" / "LLD" / "Test_OCP-V_LLD_Phase1_Foundation.md"
    marker = "FORCE_MARKER_UNIQUE"
    lld_path.write_text(lld_path.read_text(encoding="utf-8") + marker, encoding="utf-8")
    second = _run_setup(tmp_path, project_root)
    assert second.returncode != 0
    combined = (second.stderr or "") + (second.stdout or "")
    assert "--force" in combined
    assert marker in lld_path.read_text(encoding="utf-8")


def test_setup_force_overwrites(tmp_path: Path, project_root: Path) -> None:
    _prepare_ocpv_workspace(tmp_path, project_root)
    first = _run_setup(tmp_path, project_root)
    assert first.returncode == 0, first.stderr or first.stdout
    lld_path = tmp_path / "output" / "LLD" / "Test_OCP-V_LLD_Phase1_Foundation.md"
    marker = "FORCE_MARKER_UNIQUE"
    lld_path.write_text(lld_path.read_text(encoding="utf-8") + marker, encoding="utf-8")
    forced = _run_setup(tmp_path, project_root, extra_args=["--force"])
    assert forced.returncode == 0, forced.stderr or forced.stdout
    assert marker not in lld_path.read_text(encoding="utf-8")
