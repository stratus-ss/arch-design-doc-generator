from __future__ import annotations

import os
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


def test_lld_to_workitems(tmp_path: Path, project_root: Path) -> None:
    cfg_template = (project_root / "project.example.yaml").read_text(encoding="utf-8")
    cfg_text = cfg_template.replace("{CLIENT}", "TestCo").replace("{CLIENT_PREFIX}", "TestCo")
    cfg = yaml.safe_load(cfg_text)
    cfg["phases"][0]["lld_file"] = "Template_OCP-V_LLD_Phase1_Foundation.md"

    cfg_path = tmp_path / "project.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    output_dir = tmp_path / "workitems"
    script_path = project_root / "scripts" / "hld_lld" / "lld_to_workitems.py"
    lld_dir = project_root / "templates" / "LLD"

    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--config",
            str(cfg_path),
            "--output-dir",
            str(output_dir),
            "--phases",
            "1",
            "--lld-dir",
            str(lld_dir),
        ],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        env=_script_env(project_root),
    )
    assert result.returncode == 0, result.stderr or result.stdout

    md_files = list(output_dir.rglob("*.md"))
    assert md_files, "No work-item markdown files generated"
    work_item_text = md_files[0].read_text(encoding="utf-8")
    assert "LLD-" in work_item_text


def test_workitems_selects_phase_by_yaml_id(tmp_path: Path, project_root: Path) -> None:
    cfg_template = (project_root / "project.example.yaml").read_text(encoding="utf-8")
    cfg_text = cfg_template.replace("{CLIENT}", "TestCo").replace("{CLIENT_PREFIX}", "TestCo")
    cfg = yaml.safe_load(cfg_text)
    for phase in cfg["phases"]:
        if phase["id"] == "phase4":
            phase["lld_file"] = "Template_OCP-V_LLD_Phase4_Migration.md"
            break

    cfg_path = tmp_path / "project.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    output_dir = tmp_path / "workitems"
    script_path = project_root / "scripts" / "hld_lld" / "lld_to_workitems.py"
    lld_dir = project_root / "templates" / "LLD"

    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--config",
            str(cfg_path),
            "--output-dir",
            str(output_dir),
            "--phases",
            "4",
            "--lld-dir",
            str(lld_dir),
        ],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        env=_script_env(project_root),
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert (output_dir / "Phase4_Migration").is_dir()
    assert not (output_dir / "Phase3_Fleet_Operations").exists()
    md_files = list((output_dir / "Phase4_Migration").glob("*.md"))
    assert md_files, "No Phase4_Migration work-item files"
    combined = "\n".join(p.read_text(encoding="utf-8") for p in md_files)
    assert "Migration Discovery" in combined
    assert "Fleet Registration" not in combined
