"""Public-contract tests for extract value pack (CQ11 allowlist only)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_LIB_DIR = _ROOT / "scripts" / "shared" / "lib"
_DET_DIR = _ROOT / "scripts" / "hld_lld" / "ai" / "deterministic"
_AI_DIR = _ROOT / "scripts" / "hld_lld" / "ai"
for _path in (_LIB_DIR, _DET_DIR, _AI_DIR):
    _path_text = str(_path)
    if _path_text not in sys.path:
        sys.path.insert(0, _path_text)

import slots  # noqa: E402
from ai_draft_deterministic import parse_args  # noqa: E402
from markdown_utils import apply_yaml_overlay, render_drawio_tree  # noqa: E402
from slots import SINGLE_PASS_MAX_CHARS, SINGLE_PASS_MAX_CHUNKS, build_chunks  # noqa: E402


def _envelope(value: str) -> dict:
    return {
        "value": value,
        "confidence": "high",
        "evidence_excerpt": "",
        "evidence_source": "adr",
    }


def test_single_pass_one_chunk_includes_adr_tail(tmp_path: Path) -> None:
    adr = tmp_path / "ADR_test.md"
    adr.write_text(
        "# Head\n" + ("A" * 13000) + "\n# Migration 65\nTAIL_MARKER_MIGRATION_65\n",
        encoding="utf-8",
    )
    chunks = build_chunks([adr], SINGLE_PASS_MAX_CHARS, SINGLE_PASS_MAX_CHUNKS)
    assert len(chunks) == 1
    assert "TAIL_MARKER_MIGRATION_65" in chunks[0]["text"]


def test_overlay_nonempty_overrides_extract() -> None:
    slots_map = {"CLIENT_DOMAIN": _envelope("extracted.example")}
    apply_yaml_overlay(slots_map, {"slots": {"CLIENT_DOMAIN": "overlay.example"}})
    assert slots_map["CLIENT_DOMAIN"]["value"] == "overlay.example"


def test_overlay_empty_does_not_wipe_extract() -> None:
    slots_map = {"GITOPS_HOST": _envelope("git.example")}
    apply_yaml_overlay(slots_map, {"slots": {"GITOPS_HOST": ""}})
    assert slots_map["GITOPS_HOST"]["value"] == "git.example"


def test_mirror_policy_copies_image_registry() -> None:
    slots_map = {
        "IMAGE_REGISTRY": _envelope("reg.example"),
        "REGISTRY_MIRROR": _envelope(""),
    }
    apply_yaml_overlay(slots_map, {"registry_mirror_policy": "same_as_image_registry"})
    assert slots_map["REGISTRY_MIRROR"]["value"] == "reg.example"


def test_empty_repair_skipped_when_required_filled(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def _boom(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("invoke_ai must not be called")

    monkeypatch.setattr(slots, "_invoke_ai_shared", _boom)
    schema = {"required_slots_for_phase": {"phase1": ["CLIENT"]}}
    filled = {"CLIENT": _envelope("Acme")}
    args = argparse.Namespace(tool="cursor", model="x", timeout=1, retries=1, cursor_python="python3")
    out = slots.run_empty_slot_repair(filled, [{"text": "adr"}], "prompt", args, tmp_path, schema)
    assert out["CLIENT"]["value"] == "Acme"


def test_drawio_render_fills_unprefixed_slot(tmp_path: Path) -> None:
    examples = tmp_path / "examples"
    examples.mkdir()
    dest = tmp_path / "out"
    (examples / "HLD_phase2_cis-compliance-workflow.drawio").write_text(
        "<mxGraphModel>{ITSM_PLATFORM}</mxGraphModel>",
        encoding="utf-8",
    )
    written = render_drawio_tree(examples, dest, {"ITSM_PLATFORM": "ServiceNow"})
    assert written == 1
    text = (dest / "phase2" / "HLD_phase2_cis-compliance-workflow.drawio").read_text(encoding="utf-8")
    assert "ServiceNow" in text
    assert "{ITSM_PLATFORM}" not in text


def test_drawio_render_preserves_dollar_braces(tmp_path: Path) -> None:
    examples = tmp_path / "examples"
    examples.mkdir()
    dest = tmp_path / "out"
    (examples / "HLD_External_Integration_Map.drawio").write_text(
        "<mx>{ITSM_PLATFORM} and ${FOO}</mx>",
        encoding="utf-8",
    )
    render_drawio_tree(examples, dest, {"ITSM_PLATFORM": "SNOW", "FOO": "nope"})
    text = (dest / "HLD_External_Integration_Map.drawio").read_text(encoding="utf-8")
    assert "SNOW" in text
    assert "${FOO}" in text


def test_skip_phase_refine_is_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["ai_draft_deterministic.py", "hld"])
    args = parse_args()
    assert args.refine_phases is False


def test_chunk_no_include_text_omits_body(tmp_path: Path, project_root: Path) -> None:
    marker = "UNIQUE_ADR_BODY_MARKER_Z9Q"
    adr_dir = tmp_path / "adr"
    adr_dir.mkdir()
    (adr_dir / "ADR_chunk_test.md").write_text(f"# ADR\n{marker}\n", encoding="utf-8")
    out = tmp_path / "chunks.json"
    script = project_root / "scripts" / "hld_lld" / "ai" / "deterministic" / "cli.py"
    env = os.environ.copy()
    python_paths = [
        str(project_root / "scripts" / "shared" / "lib"),
        str(project_root / "scripts" / "hld_lld" / "ai" / "deterministic"),
    ]
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = ":".join(python_paths + ([existing] if existing else []))
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "chunk",
            "--adr-dir",
            str(adr_dir),
            "--out",
            str(out),
            "--no-include-text",
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(project_root),
    )
    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(out.read_text(encoding="utf-8"))
    blob = json.dumps(payload)
    assert marker not in blob
