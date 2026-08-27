"""Public-contract tests for supportshell well-known vs salvage results layout."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _run_layout_script(
    project_root: Path,
    body: str,
    extra_environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    lib_path = project_root / "scripts" / "health_check" / "supportshell" / "lib" / "output_layout.sh"
    script = f"source '{lib_path}'\n{body}\n"
    environment = os.environ.copy()
    if extra_environment:
        environment.update(extra_environment)
    return subprocess.run(
        ["bash", "-c", script],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )


def test_clear_well_known_keeps_cluster_salvage_tarball(
    tmp_path: Path, project_root: Path
) -> None:
    output_dir = tmp_path / "hc_results"
    cluster_dir = output_dir / "cluster_a"
    cluster_dir.mkdir(parents=True)
    (cluster_dir / "manifest.json").write_text("{}", encoding="utf-8")
    aggregate_tarball = tmp_path / "hc_results.tar.gz"
    aggregate_tarball.write_bytes(b"stale-aggregate")
    salvage_tarball = tmp_path / "hc_results.cluster_a.tar.gz"
    salvage_tarball.write_bytes(b"keep-me")

    result = _run_layout_script(
        project_root,
        f"clear_well_known_results '{output_dir}'",
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert not output_dir.exists()
    assert not aggregate_tarball.exists()
    assert salvage_tarball.exists()
    assert salvage_tarball.read_bytes() == b"keep-me"


def test_publish_cluster_salvage_tarball_copies_inner_tar(
    tmp_path: Path, project_root: Path
) -> None:
    output_dir = tmp_path / "hc_results"
    cluster_dir = output_dir / "cluster_b"
    cluster_dir.mkdir(parents=True)
    inner_tarball = output_dir / "cluster_b.tar.gz"
    inner_tarball.write_bytes(b"inner-payload")
    salvage_tarball = tmp_path / "hc_results.cluster_b.tar.gz"

    result = _run_layout_script(
        project_root,
        f"publish_cluster_salvage_tarball '{output_dir}' cluster_b",
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert salvage_tarball.exists()
    assert salvage_tarball.read_bytes() == b"inner-payload"


def test_clear_well_known_refuses_home_directory(
    tmp_path: Path, project_root: Path
) -> None:
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    canary = fake_home / "canary.txt"
    canary.write_text("do-not-delete", encoding="utf-8")

    result = _run_layout_script(
        project_root,
        f"clear_well_known_results '{fake_home}'",
        extra_environment={"HOME": str(fake_home)},
    )
    assert result.returncode != 0
    assert canary.exists()
    assert canary.read_text(encoding="utf-8") == "do-not-delete"
