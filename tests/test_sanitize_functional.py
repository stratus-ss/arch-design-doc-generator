from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _script_env(project_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    python_paths = [
        str(project_root / "scripts" / "shared" / "lib"),
        str(project_root / "scripts" / "shared" / "tools"),
    ]
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = ":".join(python_paths + ([existing] if existing else []))
    return env


def test_sanitize_from_output_requires_yes(tmp_path: Path, project_root: Path) -> None:
    examples = tmp_path / "templates" / "Diagrams" / "examples"
    examples.mkdir(parents=True)
    dest = examples / "HLD_Foo.drawio"
    original = "<mxfile>generic-example</mxfile>\n"
    dest.write_text(original, encoding="utf-8")

    source_dir = tmp_path / "output" / "Diagrams" / "phase1"
    source_dir.mkdir(parents=True)
    source = source_dir / "HLD_Foo.drawio"
    source.write_text("<mxfile>client-payload</mxfile>\n", encoding="utf-8")

    script = project_root / "scripts" / "shared" / "tools" / "sanitize_diagrams.py"
    result = subprocess.run(
        [sys.executable, str(script), "--from-output", "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        env=_script_env(project_root),
        cwd=str(tmp_path),
    )
    assert result.returncode == 2, result.stderr or result.stdout
    assert dest.read_text(encoding="utf-8") == original
    assert "HLD_Foo.drawio" in result.stderr
