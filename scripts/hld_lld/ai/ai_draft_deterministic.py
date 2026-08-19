#!/usr/bin/env python3
"""Deterministic template-fill HLD drafting lane."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import yaml
from ai_invoke import ensure_cursor_key, ensure_cursor_sdk
from client_prefix import derive_hld_lld_file_prefix
from config import get_client_identity

_DET_DIR = Path(__file__).resolve().parent / "deterministic"
if str(_DET_DIR) not in sys.path:
    sys.path.insert(0, str(_DET_DIR))

from markdown_utils import PLACEHOLDER_TOKEN_RE, apply_yaml_overlay, render_drawio_tree  # noqa: E402
from slot_cache import (  # noqa: E402
    build_fingerprint,
    decide_extraction,
    format_decision,
    hash_file,
    hash_text,
    load_fingerprint,
    save_fingerprint,
)


class TeeStream:
    def __init__(self, original, log_file) -> None:
        self.original = original
        self.log_file = log_file

    def write(self, data: str) -> int:
        self.original.write(data)
        self.log_file.write(data)
        self.log_file.flush()
        return len(data)

    def flush(self) -> None:
        self.original.flush()
        self.log_file.flush()


_ORCHESTRATION_TIMEOUT_SECS = 7200


def run(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    subprocess.run(cmd, check=True, cwd=str(cwd), env=env, timeout=_ORCHESTRATION_TIMEOUT_SECS)


def _force_rerun_hint() -> str:
    """GNU make rejects `--force`; recipes export MAKEFLAGS."""
    if "MAKEFLAGS" in os.environ:
        return "FORCE=1"
    return "--force"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Deterministic HLD drafting pipeline.",
    )
    parser.add_argument("doc_type", choices=["hld"])
    parser.add_argument("--phase", default="")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-extract the slot map even when extraction inputs are unchanged. From Make use FORCE=1, not --force.",
    )
    parser.add_argument("--stitch-only", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--canonical-dir", default="")
    parser.add_argument("--extractor", default="ai")
    parser.add_argument("--ai-tool", default=os.environ.get("AI_TOOL", "cursor"), choices=["claude", "codex", "cursor"])
    parser.add_argument(
        "--ai-model",
        default=os.environ.get("AI_MODEL") or os.environ.get("CURSOR_MODEL") or "claude-sonnet-4-6",
    )
    parser.add_argument("--ai-max-chars", type=int, default=12000)
    parser.add_argument("--ai-max-chunks", type=int, default=8)
    parser.add_argument("--ai-phase-max-chars", type=int, default=24000)
    parser.add_argument("--ai-retries", type=int, default=3)
    parser.add_argument("--ai-timeout", type=int, default=900)
    parser.add_argument(
        "--adr-mode",
        choices=["auto", "chunked"],
        default="auto",
        help="auto: one full-ADR Prompt A chunk, then 8x12k fallback on timeout/parse fail.",
    )
    parser.add_argument(
        "--refine-phases",
        action="store_true",
        help="Run Prompt B per-phase refine (off by default).",
    )
    return parser.parse_args()


def fmt_elapsed(start: float) -> str:
    secs = int(time.time() - start)
    hours, rem = divmod(secs, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


@dataclass
class DraftContext:
    """Shared paths/config for a single deterministic-drafting run."""

    project_root: Path
    base_python: str
    cli_py: Path
    template_dir: Path
    draft_dir: Path
    output_root: Path
    state_dir: Path
    contract_file: Path
    citation_lock_file: Path
    slot_file: Path
    state_hash_file: Path
    phase_file_map: dict[str, str]
    support_file_map: dict[str, str]
    base_prefix: str
    combined_deterministic_name: str
    canonical_dir: Path | None
    force: bool


def _load_config(project_yaml: Path) -> tuple[dict, str, str]:
    if not project_yaml.exists():
        raise SystemExit(f"Error: project.yaml not found at {project_yaml}")
    config = yaml.safe_load(project_yaml.read_text(encoding="utf-8")) or {}
    client_name, project_code = get_client_identity(config)
    if not client_name:
        raise SystemExit("Error: project.yaml missing client_name")
    return config, client_name, project_code


def _build_file_maps(config: dict) -> tuple[dict[str, str], dict[str, str], str, str]:
    hld_section = config.get("hld", {})
    hld_phase_files: list[str] = hld_section.get("phase_files", [])
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
    return phase_file_map, support_file_map, base_prefix, combined_deterministic_name


def _build_context(args: argparse.Namespace, project_root: Path, config: dict) -> DraftContext:
    phase_file_map, support_file_map, base_prefix, combined_deterministic_name = _build_file_maps(config)

    deter_dir = project_root / "scripts" / "hld_lld" / "ai" / "deterministic"
    output_root = Path(os.environ.get("OUTPUT_ROOT", str(project_root / "output")))
    state_dir = output_root / ".deterministic"

    return DraftContext(
        project_root=project_root,
        base_python=os.environ.get("PYTHON", "python3"),
        cli_py=deter_dir / "cli.py",
        template_dir=project_root / "templates" / "HLD" / "markdown_files",
        draft_dir=output_root / "drafts_deterministic",
        output_root=output_root,
        state_dir=state_dir,
        contract_file=state_dir / "contracts" / "template_contracts.json",
        citation_lock_file=state_dir / "locks" / "citation_lock.json",
        slot_file=state_dir / "slots" / "slot_map.json",
        state_hash_file=state_dir / "state_hashes.json",
        phase_file_map=phase_file_map,
        support_file_map=support_file_map,
        base_prefix=base_prefix,
        combined_deterministic_name=combined_deterministic_name,
        canonical_dir=Path(args.canonical_dir) if args.canonical_dir else None,
        force=args.force,
    )


def _ensure_dirs(context: DraftContext) -> None:
    context.draft_dir.mkdir(parents=True, exist_ok=True)
    (context.state_dir / "contracts").mkdir(parents=True, exist_ok=True)
    (context.state_dir / "locks").mkdir(parents=True, exist_ok=True)
    (context.state_dir / "slots").mkdir(parents=True, exist_ok=True)
    (context.output_root / "HLD" / "markdown_files").mkdir(parents=True, exist_ok=True)


def _discover_canonical_files(canonical_dir: Path | None, client_name: str, project_code: str) -> list[Path]:
    canonical_files: list[Path] = []
    if canonical_dir:
        prefix = derive_hld_lld_file_prefix(client_name)
        for phase in ["phase1", "phase2", "phase3", "phase4"]:
            canonical_file = canonical_dir / f"{prefix}_{project_code}_HLD_DecisionJourney_{phase}.md"
            if canonical_file.exists():
                canonical_files.append(canonical_file)
        combined = canonical_dir / f"{prefix}_{project_code}_HLD_DecisionJourney_combined.md"
        if combined.exists():
            canonical_files.append(combined)
    return canonical_files


def _build_citation_lock(context: DraftContext, canonical_files: list[Path]) -> None:
    if canonical_files:
        run(
            [
                context.base_python,
                str(context.cli_py),
                "build-citation-lock",
                "--canonical-files",
                *[str(canonical_file) for canonical_file in canonical_files],
                "--out",
                str(context.citation_lock_file),
            ],
            cwd=context.project_root,
        )
    else:
        context.citation_lock_file.parent.mkdir(parents=True, exist_ok=True)
        context.citation_lock_file.write_text(
            json.dumps({"documents": {}}, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


def _placeholder_digest(templates: list[Path]) -> str:
    tokens: set[str] = set()
    for template in templates:
        if template.is_file():
            tokens.update(PLACEHOLDER_TOKEN_RE.findall(template.read_text(encoding="utf-8")))
    return hash_text("\n".join(sorted(tokens)))


def _slot_input_parts(
    context: DraftContext,
    args: argparse.Namespace,
    project_yaml: Path,
    templates: list[Path],
) -> dict[str, str]:
    parts: dict[str, str] = {}
    adr_dir = context.project_root / "ADR"
    if adr_dir.is_dir():
        for path in sorted(adr_dir.glob("*.md")):
            if "template" in path.name.lower():
                continue
            parts[path.relative_to(context.project_root).as_posix()] = hash_file(path)
    parts["project.yaml"] = hash_file(project_yaml)
    parts["slot_schema.json"] = hash_file(context.cli_py.parent / "slot_schema.json")
    prompts_dir = context.cli_py.parent / "prompts"
    if prompts_dir.is_dir():
        for path in sorted(prompts_dir.glob("*.md")):
            parts[f"prompts/{path.name}"] = hash_file(path)
    parts["hld_placeholders"] = _placeholder_digest(templates)
    refine = "refine" if args.refine_phases else "skip-refine"
    parts["extractor"] = "|".join(
        [
            str(args.ai_tool),
            str(args.ai_model),
            str(args.ai_max_chars),
            str(args.ai_max_chunks),
            str(args.ai_phase_max_chars),
            str(args.adr_mode),
            refine,
        ]
    )
    return parts


def _rebind_yaml_overlay(slot_file: Path, project_yaml: Path) -> None:
    """Re-apply project.yaml overlay on a fingerprint-skip without re-extracting."""
    if not slot_file.exists():
        return
    config = yaml.safe_load(project_yaml.read_text(encoding="utf-8")) or {}
    payload = json.loads(slot_file.read_text(encoding="utf-8"))
    slots = payload.get("slots", payload)
    if not isinstance(slots, dict):
        return
    apply_yaml_overlay(slots, config)
    for key, raw in list(slots.items()):
        if isinstance(raw, dict):
            slots[key] = str(raw.get("value", "")).strip()
    if "slots" in payload:
        payload["slots"] = slots
        slot_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return
    slot_file.write_text(json.dumps(slots, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run_ai_extraction(
    context: DraftContext,
    args: argparse.Namespace,
    project_yaml: Path,
    templates: list[Path],
    ai_run_dir: Path,
    chunk_manifest: Path,
    cursor_python: str,
) -> None:
    fingerprint_path = context.slot_file.with_name("slot_map.fingerprint.json")
    current = build_fingerprint(_slot_input_parts(context, args, project_yaml, templates))
    stored = load_fingerprint(fingerprint_path)
    decision = decide_extraction(
        slot_exists=context.slot_file.exists(),
        force=bool(args.force),
        stored=stored,
        current=current,
    )
    print(format_decision(decision, context.slot_file, _force_rerun_hint()))
    if decision.action == "skip":
        if decision.status == "untracked":
            save_fingerprint(fingerprint_path, current)
            print("  recorded: input fingerprint for future skip/stale decisions")
        _rebind_yaml_overlay(context.slot_file, project_yaml)
        return

    print(f"Using AI extractor (tool: {args.ai_tool}, model: {args.ai_model})...")
    ai_run_dir.mkdir(parents=True, exist_ok=True)

    run(
        [
            context.base_python,
            str(context.cli_py),
            "chunk",
            "--adr-dir",
            str(context.project_root / "ADR"),
            "--out",
            str(chunk_manifest),
            "--max-chars",
            str(args.ai_max_chars),
            "--max-chunks",
            str(args.ai_max_chunks),
        ],
        cwd=context.project_root,
    )

    extract_cmd = [
        cursor_python,
        str(context.cli_py),
        "extract-ai",
        "--adr-dir",
        str(context.project_root / "ADR"),
        "--project-yaml",
        str(project_yaml),
        "--templates",
        *map(str, templates),
        "--out",
        str(context.slot_file),
        "--run-dir",
        str(ai_run_dir),
        "--chunk-manifest",
        str(chunk_manifest),
        "--contract",
        str(context.contract_file),
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
        "--adr-mode",
        str(args.adr_mode),
    ]
    if args.refine_phases:
        extract_cmd.append("--refine-phases")
    run(extract_cmd, cwd=context.project_root)

    run(
        [
            context.base_python,
            str(context.cli_py),
            "validate-slots",
            "--slots",
            str(context.slot_file),
            "--phases",
            "phase1",
            "phase2",
            "phase3",
            "phase4",
        ],
        cwd=context.project_root,
    )
    save_fingerprint(fingerprint_path, current)
    print(f"AI slot extraction complete -> {context.slot_file}")


def validate_call(context: DraftContext, outfile: Path, doc_key: str, phase: str = "") -> None:
    compare_arg: list[str] = []
    if context.canonical_dir:
        expected = context.canonical_dir / doc_key
        if expected.exists():
            compare_arg = ["--expect-byte-equal-to", str(expected)]
    cmd = [
        context.base_python,
        str(context.cli_py),
        "validate-hld",
        "--file",
        str(outfile),
        "--contract",
        str(context.contract_file),
        "--slots",
        str(context.slot_file),
        "--citation-lock",
        str(context.citation_lock_file),
        "--document-key",
        doc_key,
        "--state-file",
        str(context.state_hash_file),
        *compare_arg,
    ]
    if phase:
        cmd.extend(["--phase", phase])
    run(cmd, cwd=context.project_root)


def render_section(context: DraftContext, section: str, include_phase: bool) -> None:
    template = context.template_dir / f"Template_OCP-V_HLD_DecisionJourney_{section}.md"
    outfile = context.draft_dir / f"draft_hld_{section}.md"
    doc_key = context.phase_file_map[section] if include_phase else context.support_file_map[section]

    if not template.exists():
        print(f"Skipping {section}; template not found: {template}")
        return

    run(
        [
            context.base_python,
            str(context.cli_py),
            "render-phase",
            "--template",
            str(template),
            "--slots",
            str(context.slot_file),
            "--out",
            str(outfile),
        ],
        cwd=context.project_root,
    )
    validate_call(context, outfile, doc_key, phase=section if include_phase else "")
    print(f"Deterministic render complete: {outfile}")


def validate_phase_only(context: DraftContext, phase: str) -> None:
    outfile = context.draft_dir / f"draft_hld_{phase}.md"
    doc_key = context.phase_file_map[phase]
    validate_call(context, outfile, doc_key, phase=phase)
    print(f"Validation complete: {outfile}")


def stitch_combined(context: DraftContext) -> None:
    output = context.output_root / "HLD" / "markdown_files" / context.combined_deterministic_name
    compare_arg: list[str] = []
    if context.canonical_dir:
        expected = context.canonical_dir / f"{context.base_prefix}_combined.md"
        if expected.exists():
            compare_arg = ["--expect-byte-equal-to", str(expected)]
    run(
        [
            context.base_python,
            str(context.cli_py),
            "stitch",
            "--draft-dir",
            str(context.draft_dir),
            "--output",
            str(output),
            *compare_arg,
        ],
        cwd=context.project_root,
    )
    validate_call(context, output, context.combined_deterministic_name)
    print(f"Deterministic stitch complete: {output}")


def _write_back_and_validate(context: DraftContext, phases: list[str], support_sections: list[str]) -> None:
    write_sections = phases + support_sections
    written: list[Path] = []
    dest_root = context.output_root / "HLD" / "markdown_files"
    for section in write_sections:
        source = context.draft_dir / f"draft_hld_{section}.md"
        if section in context.phase_file_map:
            dest = dest_root / context.phase_file_map[section]
        else:
            dest = dest_root / context.support_file_map[section]
        if not source.exists():
            print(f"Skipping write-back for {section}; draft not found: {source}")
            continue
        shutil.copy2(source, dest)
        written.append(dest)
        print(f"Rendered write-back: {dest}")

    if written:
        run(
            [
                context.base_python,
                str(context.project_root / "scripts" / "shared" / "lib" / "validate_placeholders.py"),
                "--context",
                "written HLD files",
                *[str(written_path) for written_path in written],
            ],
            cwd=context.project_root,
        )
    print(f"Rendered write-back validation passed ({len(written)} file(s)).")


def _lld_template_for_dest(template_dir: Path, dest_name: str) -> Path | None:
    for tmpl in sorted(template_dir.glob("Template_OCP-V_LLD_*.md")):
        suffix = tmpl.name.removeprefix("Template_")
        if dest_name.endswith(suffix):
            return tmpl
    return None


def _render_lld_from_slots(context: DraftContext, config: dict) -> None:
    """Render generic LLD templates into output/LLD using the same slot map as HLD.

    Always overwrites destination files. Setup copies unfilled templates into
    output/LLD; skipping those would leave LLD unfilled unless FORCE=1, which
    also re-runs AI extraction.
    """
    template_dir = context.project_root / "templates" / "LLD"
    dest_dir = context.output_root / "LLD"
    dest_dir.mkdir(parents=True, exist_ok=True)
    for phase in config.get("phases", []):
        dest_name = str(phase.get("lld_file", "")).strip()
        if not dest_name:
            continue
        template = _lld_template_for_dest(template_dir, dest_name)
        if template is None or not template.exists():
            print(f"Skipping LLD {dest_name}; template not found.")
            continue
        dest = dest_dir / dest_name
        run(
            [
                context.base_python,
                str(context.cli_py),
                "render-phase",
                "--template",
                str(template),
                "--slots",
                str(context.slot_file),
                "--out",
                str(dest),
            ],
            cwd=context.project_root,
        )
        print(f"LLD render complete: {dest}")


def _render_drawio_from_slots(context: DraftContext) -> None:
    """Stamp templates/Diagrams/examples into output/Diagrams. Always overwrites."""
    examples = context.project_root / "templates" / "Diagrams" / "examples"
    dest = context.output_root / "Diagrams"
    if not context.slot_file.exists():
        print(f"Skipping drawio render; slot map not found: {context.slot_file}")
        return
    payload = json.loads(context.slot_file.read_text(encoding="utf-8"))
    slots = payload.get("slots", payload)
    if not isinstance(slots, dict):
        print("Skipping drawio render; slot map is not an object.")
        return
    count = render_drawio_tree(examples, dest, slots)
    print(f"Drawio render complete: {count} file(s) -> {dest}")


def _run_pipeline(
    context: DraftContext,
    args: argparse.Namespace,
    project_yaml: Path,
    config: dict,
    client_name: str,
    project_code: str,
    cursor_python: str,
    run_start: float,
) -> int:
    phases = ["phase1", "phase2", "phase3", "phase4"]
    if args.phase:
        if args.phase not in phases:
            raise SystemExit(f"Unsupported phase: {args.phase} (expected phase1..phase4)")
        phases = [args.phase]
    support_sections = ["preamble", "appendix"]

    templates = [context.template_dir / f"Template_OCP-V_HLD_DecisionJourney_phase{phase_number}.md" for phase_number in range(1, 5)]

    run(
        [
            context.base_python,
            str(context.cli_py),
            "build-contract",
            "--templates",
            *map(str, templates),
            "--out",
            str(context.contract_file),
        ],
        cwd=context.project_root,
    )

    canonical_files = _discover_canonical_files(context.canonical_dir, client_name, project_code)
    _build_citation_lock(context, canonical_files)

    run_timestamp = time.strftime("%Y%m%dT%H%M%S")
    ai_run_dir = context.state_dir / "runs" / f"{run_timestamp}_{args.extractor}"
    chunk_manifest = context.state_dir / "slots" / "chunk_manifest.json"
    _run_ai_extraction(context, args, project_yaml, templates, ai_run_dir, chunk_manifest, cursor_python)

    if args.stitch_only:
        stitch_combined(context)
        print(f"=== Done in {fmt_elapsed(run_start)} ===")
        return 0

    if args.validate_only:
        for phase in phases:
            validate_phase_only(context, phase)
        stitch_combined(context)
        print(f"=== Done in {fmt_elapsed(run_start)} ===")
        return 0

    for phase in phases:
        render_section(context, phase, include_phase=True)
    for section in support_sections:
        render_section(context, section, include_phase=False)

    _write_back_and_validate(context, phases, support_sections)
    _render_lld_from_slots(context, config)
    _render_drawio_from_slots(context)

    stitch_combined(context)
    print(f"=== Done in {fmt_elapsed(run_start)} ===")
    return 0


def main() -> int:
    args = parse_args()
    if args.extractor != "ai":
        raise SystemExit(f"Error: only --extractor ai is supported after cleanup (got: {args.extractor})")
    if str(args.ai_tool).strip().lower() in {"", "no", "none", "off"}:
        raise SystemExit(
            "Error: AI pathways are disabled by default in this repository configuration. "
            "Set --ai-tool and --ai-model to real values to re-enable."
        )
    if str(args.ai_model).strip().lower() in {"", "no", "none", "off"}:
        raise SystemExit(
            "Error: AI pathways are disabled by default in this repository configuration. "
            "Set --ai-model to a real value to re-enable."
        )

    project_root = Path(__file__).resolve().parents[3]
    project_yaml = project_root / "project.yaml"
    config, client_name, project_code = _load_config(project_yaml)
    context = _build_context(args, project_root, config)

    cursor_python = "python3"
    if args.ai_tool == "cursor":
        cursor_python = ensure_cursor_sdk(project_root)
        ensure_cursor_key()

    _ensure_dirs(context)

    log_file = context.state_dir / "last_run.log"
    run_start = time.time()
    with open(log_file, "a", encoding="utf-8") as log_file:
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        sys.stdout = TeeStream(original_stdout, log_file)
        sys.stderr = TeeStream(original_stderr, log_file)
        try:
            print(f"=== Run started: {time.ctime()} (log: {log_file}) ===")
            return _run_pipeline(context, args, project_yaml, config, client_name, project_code, cursor_python, run_start)
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr


if __name__ == "__main__":
    raise SystemExit(main())
