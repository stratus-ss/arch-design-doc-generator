#!/usr/bin/env python3
"""Deterministic template-fill HLD drafting lane."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml


class TeeStream:
    def __init__(self, original, log_fp) -> None:
        self.original = original
        self.log_fp = log_fp

    def write(self, data: str) -> int:
        self.original.write(data)
        self.log_fp.write(data)
        self.log_fp.flush()
        return len(data)

    def flush(self) -> None:
        self.original.flush()
        self.log_fp.flush()


def run(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    subprocess.run(cmd, check=True, cwd=str(cwd), env=env)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Deterministic HLD drafting pipeline.",
    )
    parser.add_argument("doc_type", choices=["hld"])
    parser.add_argument("--phase", default="")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--stitch-only", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--canonical-dir", default="")
    parser.add_argument("--extractor", default="ai")
    parser.add_argument("--ai-tool", default="cursor", choices=["claude", "codex", "cursor"])
    parser.add_argument("--ai-model", default=os.environ.get("CURSOR_MODEL", "claude-sonnet-4-6"))
    parser.add_argument("--ai-max-chars", type=int, default=12000)
    parser.add_argument("--ai-max-chunks", type=int, default=8)
    parser.add_argument("--ai-phase-max-chars", type=int, default=24000)
    parser.add_argument("--ai-retries", type=int, default=3)
    parser.add_argument("--ai-timeout", type=int, default=180)
    parser.add_argument("--skip-phase-refine", action="store_true")
    return parser.parse_args()


def ensure_cursor_sdk(project_root: Path) -> str:
    cursor_venv = project_root / ".cursor-sdk-venv"
    cursor_python = cursor_venv / "bin" / "python"
    cursor_pip = cursor_venv / "bin" / "pip"
    if not cursor_python.exists():
        print("Setting up Cursor SDK environment...")
        run(["python3", "-m", "venv", str(cursor_venv)], cwd=project_root)
        run([str(cursor_pip), "install", "--quiet", "--upgrade", "pip"], cwd=project_root)
        run([str(cursor_pip), "install", "--quiet", "cursor-sdk", "pyyaml"], cwd=project_root)
        print("Cursor SDK installed.")
    else:
        try:
            run([str(cursor_python), "-c", "import cursor_sdk"], cwd=project_root)
        except subprocess.CalledProcessError:
            print("Installing cursor-sdk into existing venv...")
            run([str(cursor_pip), "install", "--quiet", "cursor-sdk"], cwd=project_root)
        try:
            run([str(cursor_python), "-c", "import yaml"], cwd=project_root)
        except subprocess.CalledProcessError:
            run([str(cursor_pip), "install", "--quiet", "pyyaml"], cwd=project_root)
    return str(cursor_python)


def ensure_cursor_key() -> None:
    key_file = Path.home() / ".config" / "arch-doc-gen" / "cursor_api_key"
    api_key = os.environ.get("CURSOR_API_KEY", "")
    if not api_key and key_file.exists():
        api_key = key_file.read_text(encoding="utf-8")
        print(f"Cursor API key loaded from {key_file}")

    if not api_key:
        print("\nCursor SDK requires an API key.")
        print("Get yours from: https://cursor.com/dashboard/integrations\n")
        api_key = getpass.getpass("Paste your CURSOR_API_KEY (input hidden): ").strip()
        if not api_key:
            raise SystemExit("Error: No API key provided. Aborting.")
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_text(api_key, encoding="utf-8")
        key_file.chmod(0o600)
        print(f"API key saved to {key_file}")
        print("  (Delete that file to be prompted again)\n")
    os.environ["CURSOR_API_KEY"] = api_key


def fmt_elapsed(start: float) -> str:
    secs = int(time.time() - start)
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def load_project(project_yaml: Path) -> tuple[str, str]:
    cfg = yaml.safe_load(project_yaml.read_text(encoding="utf-8")) or {}
    client_name = str(cfg.get("client_name", "")).strip()
    project_code = str(cfg.get("project_code", "OCP-V")).strip() or "OCP-V"
    if not client_name:
        raise SystemExit("Error: project.yaml missing client_name")
    return client_name, project_code


def main() -> int:
    args = parse_args()
    if args.extractor != "ai":
        raise SystemExit(f"Error: only --extractor ai is supported after cleanup (got: {args.extractor})")

    project_root = Path(__file__).resolve().parents[2]
    project_yaml = project_root / "project.yaml"
    if not project_yaml.exists():
        raise SystemExit(f"Error: project.yaml not found at {project_yaml}")

    cfg = yaml.safe_load(project_yaml.read_text(encoding="utf-8")) or {}
    client_name, project_code = load_project(project_yaml)
    base_python = os.environ.get("PYTHON", "python3")

    hld_phase_files: list[str] = cfg.get("hld", {}).get("phase_files", [])
    if len(hld_phase_files) != 4:
        raise SystemExit("Error: expected 4 hld.phase_files entries in project.yaml")
    phase_file_map = {
        "phase1": hld_phase_files[0],
        "phase2": hld_phase_files[1],
        "phase3": hld_phase_files[2],
        "phase4": hld_phase_files[3],
    }
    base_prefix = phase_file_map["phase1"].removesuffix("_phase1.md")
    support_file_map = {
        "preamble": f"{base_prefix}_preamble.md",
        "appendix": f"{base_prefix}_appendix.md",
    }
    combined_deterministic_name = f"{base_prefix}_combined_deterministic.md"

    deter_dir = project_root / "scripts" / "ai" / "deterministic"
    cli_py = deter_dir / "cli.py"
    template_dir = project_root / "HLD" / "markdown_files"
    output_root = Path(os.environ.get("OUTPUT_ROOT", str(project_root / "output")))
    draft_dir = output_root / "drafts_deterministic"
    state_dir = output_root / ".deterministic"
    contract_file = state_dir / "contracts" / "template_contracts.json"
    citation_lock_file = state_dir / "locks" / "citation_lock.json"
    slot_file = state_dir / "slots" / "slot_map.json"
    state_hash_file = state_dir / "state_hashes.json"

    run_timestamp = time.strftime("%Y%m%dT%H%M%S")
    ai_run_dir = state_dir / "runs" / f"{run_timestamp}_{args.extractor}"
    chunk_manifest = state_dir / "slots" / "chunk_manifest.json"

    cursor_python = "python3"
    if args.ai_tool == "cursor":
        cursor_python = ensure_cursor_sdk(project_root)
        ensure_cursor_key()

    draft_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "contracts").mkdir(parents=True, exist_ok=True)
    (state_dir / "locks").mkdir(parents=True, exist_ok=True)
    (state_dir / "slots").mkdir(parents=True, exist_ok=True)
    (output_root / "HLD" / "markdown_files").mkdir(parents=True, exist_ok=True)

    log_file = state_dir / "last_run.log"
    run_start = time.time()
    with open(log_file, "a", encoding="utf-8") as log_fp:
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        sys.stdout = TeeStream(original_stdout, log_fp)
        sys.stderr = TeeStream(original_stderr, log_fp)
        try:
            print(f"=== Run started: {time.ctime()} (log: {log_file}) ===")

            phases = ["phase1", "phase2", "phase3", "phase4"]
            if args.phase:
                if args.phase not in phases:
                    raise SystemExit(f"Unsupported phase: {args.phase} (expected phase1..phase4)")
                phases = [args.phase]
            support_sections = ["preamble", "appendix"]

            templates = [
                template_dir / "Template_OCP-V_HLD_DecisionJourney_phase1.md",
                template_dir / "Template_OCP-V_HLD_DecisionJourney_phase2.md",
                template_dir / "Template_OCP-V_HLD_DecisionJourney_phase3.md",
                template_dir / "Template_OCP-V_HLD_DecisionJourney_phase4.md",
            ]

            run(
                [base_python, str(cli_py), "build-contract", "--templates", *map(str, templates), "--out", str(contract_file)],
                cwd=project_root,
            )

            canonical_files: list[Path] = []
            canonical_dir = Path(args.canonical_dir) if args.canonical_dir else None
            if canonical_dir:
                for phase in ["phase1", "phase2", "phase3", "phase4"]:
                    f = canonical_dir / f"{client_name}_{project_code}_HLD_DecisionJourney_{phase}.md"
                    if f.exists():
                        canonical_files.append(f)
                combined = canonical_dir / f"{client_name}_{project_code}_HLD_DecisionJourney_combined.md"
                if combined.exists():
                    canonical_files.append(combined)

            if canonical_files:
                run(
                    [
                        base_python,
                        str(cli_py),
                        "build-citation-lock",
                        "--canonical-files",
                        *[str(f) for f in canonical_files],
                        "--out",
                        str(citation_lock_file),
                    ],
                    cwd=project_root,
                )
            else:
                citation_lock_file.parent.mkdir(parents=True, exist_ok=True)
                citation_lock_file.write_text(json.dumps({"documents": {}}, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            if slot_file.exists() and not args.force:
                print(f"Slot map already exists at {slot_file} — skipping AI extraction (use --force to re-extract).")
            else:
                print(f"Using AI extractor (tool: {args.ai_tool}, model: {args.ai_model})...")
                ai_run_dir.mkdir(parents=True, exist_ok=True)

                run(
                    [
                        base_python,
                        str(cli_py),
                        "chunk",
                        "--adr-dir",
                        str(project_root / "ADR"),
                        "--out",
                        str(chunk_manifest),
                        "--max-chars",
                        str(args.ai_max_chars),
                        "--max-chunks",
                        str(args.ai_max_chunks),
                    ],
                    cwd=project_root,
                )

                extract_cmd = [
                    cursor_python,
                    str(cli_py),
                    "extract-ai",
                    "--adr-dir",
                    str(project_root / "ADR"),
                    "--project-yaml",
                    str(project_yaml),
                    "--templates",
                    *map(str, templates),
                    "--out",
                    str(slot_file),
                    "--run-dir",
                    str(ai_run_dir),
                    "--chunk-manifest",
                    str(chunk_manifest),
                    "--contract",
                    str(contract_file),
                    "--tool",
                    args.ai_tool,
                    "--model",
                    args.ai_model,
                    "--cursor-python",
                    cursor_python,
                    "--timeout",
                    str(args.ai_timeout),
                    "--retries",
                    str(args.ai_retries),
                    "--max-chars",
                    str(args.ai_max_chars),
                    "--max-chunks",
                    str(args.ai_max_chunks),
                    "--phase-max-chars",
                    str(args.ai_phase_max_chars),
                ]
                if args.skip_phase_refine:
                    extract_cmd.append("--skip-phase-refine")
                run(extract_cmd, cwd=project_root)

                run(
                    [
                        base_python,
                        str(cli_py),
                        "validate-slots",
                        "--slots",
                        str(slot_file),
                        "--phases",
                        "phase1",
                        "phase2",
                        "phase3",
                        "phase4",
                    ],
                    cwd=project_root,
                )
                print(f"AI slot extraction complete -> {slot_file}")

            def validate_call(outfile: Path, doc_key: str, phase: str = "") -> None:
                compare_arg: list[str] = []
                if canonical_dir:
                    expected = canonical_dir / doc_key
                    if expected.exists():
                        compare_arg = ["--expect-byte-equal-to", str(expected)]
                cmd = [
                    base_python,
                    str(cli_py),
                    "validate-hld",
                    "--file",
                    str(outfile),
                    "--contract",
                    str(contract_file),
                    "--slots",
                    str(slot_file),
                    "--citation-lock",
                    str(citation_lock_file),
                    "--document-key",
                    doc_key,
                    "--state-file",
                    str(state_hash_file),
                    *compare_arg,
                ]
                if phase:
                    cmd.extend(["--phase", phase])
                run(cmd, cwd=project_root)

            def render_section(section: str, include_phase: bool) -> None:
                template = template_dir / f"Template_OCP-V_HLD_DecisionJourney_{section}.md"
                outfile = draft_dir / f"draft_hld_{section}.md"
                if include_phase:
                    doc_key = phase_file_map[section]
                else:
                    doc_key = support_file_map[section]

                if not template.exists():
                    print(f"Skipping {section}; template not found: {template}")
                    return
                if outfile.exists() and not args.force:
                    print(f"Skipping {section}; output exists (use --force).")
                    return

                run(
                    [
                        base_python,
                        str(cli_py),
                        "render-phase",
                        "--template",
                        str(template),
                        "--slots",
                        str(slot_file),
                        "--out",
                        str(outfile),
                    ],
                    cwd=project_root,
                )
                validate_call(outfile, doc_key, phase=section if include_phase else "")
                print(f"Deterministic render complete: {outfile}")

            def validate_phase_only(phase: str) -> None:
                outfile = draft_dir / f"draft_hld_{phase}.md"
                doc_key = phase_file_map[phase]
                validate_call(outfile, doc_key, phase=phase)
                print(f"Validation complete: {outfile}")

            def stitch_combined() -> None:
                output = output_root / "HLD" / "markdown_files" / combined_deterministic_name
                compare_arg: list[str] = []
                if canonical_dir:
                    expected = canonical_dir / f"{base_prefix}_combined.md"
                    if expected.exists():
                        compare_arg = ["--expect-byte-equal-to", str(expected)]
                run(
                    [
                        base_python,
                        str(cli_py),
                        "stitch",
                        "--draft-dir",
                        str(draft_dir),
                        "--output",
                        str(output),
                        *compare_arg,
                    ],
                    cwd=project_root,
                )
                validate_call(output, combined_deterministic_name)
                print(f"Deterministic stitch complete: {output}")

            if args.stitch_only:
                stitch_combined()
                print(f"=== Done in {fmt_elapsed(run_start)} ===")
                return 0

            if args.validate_only:
                for phase in phases:
                    validate_phase_only(phase)
                stitch_combined()
                print(f"=== Done in {fmt_elapsed(run_start)} ===")
                return 0

            for phase in phases:
                render_section(phase, include_phase=True)
            for section in support_sections:
                render_section(section, include_phase=False)

            write_sections = phases + support_sections
            written: list[Path] = []
            dest_root = project_root / "HLD" / "markdown_files"
            for section in write_sections:
                src = draft_dir / f"draft_hld_{section}.md"
                if section in phase_file_map:
                    dest = dest_root / phase_file_map[section]
                else:
                    dest = dest_root / support_file_map[section]
                if not src.exists():
                    print(f"Skipping write-back for {section}; draft not found: {src}")
                    continue
                shutil.copy2(src, dest)
                written.append(dest)
                print(f"Rendered write-back: {dest}")

            if written:
                run(
                    [
                        base_python,
                        str(project_root / "scripts" / "lib" / "validate_placeholders.py"),
                        "--context",
                        "written HLD files",
                        *[str(p) for p in written],
                    ],
                    cwd=project_root,
                )
            print(f"Rendered write-back validation passed ({len(written)} file(s)).")

            stitch_combined()
            print(f"=== Done in {fmt_elapsed(run_start)} ===")
            return 0
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr


if __name__ == "__main__":
    raise SystemExit(main())
