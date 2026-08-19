#!/usr/bin/env python3
"""Unified deterministic pipeline CLI."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import render
import slots

_REPEATABILITY_TIMEOUT_SECS = 7200


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _chunks_without_text(chunks: list) -> list:
    out = []
    for chunk in chunks:
        slim = {key: value for key, value in chunk.items() if key != "text"}
        out.append(slim)
    return out


def cmd_chunk(args: argparse.Namespace) -> int:
    adr_dir = Path(args.adr_dir)
    out = Path(args.out)
    adr_files = slots.load_adr_files(adr_dir)
    if not adr_files:
        print(f"No ADR files found in {adr_dir} (after template filter).", file=sys.stderr)
        return 1
    chunks = slots.build_chunks(adr_files, args.max_chars, args.max_chunks)
    manifest = {
        "adr_dir": str(adr_dir),
        "adr_files": [adr_file.name for adr_file in adr_files],
        "max_chars_per_chunk": args.max_chars,
        "max_chunks": args.max_chunks,
        "chunk_count": len(chunks),
        "chunks": chunks if args.include_text else _chunks_without_text(chunks),
    }
    _write_json(out, manifest)
    print(f"Chunked {len(adr_files)} ADR file(s) into {len(chunks)} chunk(s) → {out}")
    return 0


def cmd_extract_ai(args: argparse.Namespace) -> int:
    argv = [
        "--adr-dir",
        args.adr_dir,
        "--project-yaml",
        args.project_yaml,
        "--templates",
        *args.templates,
        "--out",
        args.out,
        "--run-dir",
        args.run_dir,
        "--tool",
        args.tool,
        "--model",
        args.model,
        "--cursor-python",
        args.cursor_python,
        "--timeout",
        str(args.timeout),
        "--retries",
        str(args.retries),
        "--max-chars",
        str(args.max_chars),
        "--max-chunks",
        str(args.max_chunks),
        "--phase-max-chars",
        str(args.phase_max_chars),
        "--max-repair-rounds",
        str(args.max_repair_rounds),
        "--adr-mode",
        args.adr_mode,
    ]
    if args.prompt_global:
        argv += ["--prompt-global", args.prompt_global]
    if args.prompt_phase:
        argv += ["--prompt-phase", args.prompt_phase]
    if args.prompt_repair:
        argv += ["--prompt-repair", args.prompt_repair]
    if args.contract:
        argv += ["--contract", args.contract]
    if args.chunk_manifest:
        argv += ["--chunk-manifest", args.chunk_manifest]
    if args.refine_phases:
        argv += ["--refine-phases"]
    return slots.run_extract_ai(argv)


def cmd_validate_slots(args: argparse.Namespace) -> int:
    schema = Path(args.schema) if args.schema else None
    return slots.validate_slot_file(Path(args.slots), args.phases, schema)


def cmd_build_contract(args: argparse.Namespace) -> int:
    render.build_contract([Path(template_path) for template_path in args.templates], Path(args.out))
    return 0


def cmd_build_citation_lock(args: argparse.Namespace) -> int:
    render.build_citation_lock([Path(canonical_path) for canonical_path in args.canonical_files], Path(args.out))
    return 0


def cmd_render_phase(args: argparse.Namespace) -> int:
    render.render_phase(Path(args.template), Path(args.slots), Path(args.out))
    return 0


def cmd_stitch(args: argparse.Namespace) -> int:
    render.stitch_deterministic(Path(args.draft_dir), Path(args.output), args.expect_byte_equal_to)
    return 0


def cmd_validate_hld(args: argparse.Namespace) -> int:
    argv = [
        "--file",
        args.file,
        "--contract",
        args.contract,
        "--document-key",
        args.document_key,
        "--state-file",
        args.state_file,
    ]
    if args.phase:
        argv += ["--phase", args.phase]
    if args.slots:
        argv += ["--slots", args.slots]
    if args.citation_lock:
        argv += ["--citation-lock", args.citation_lock]
    if args.expect_byte_equal_to:
        argv += ["--expect-byte-equal-to", args.expect_byte_equal_to]
    return render.run_validate_hld(argv)


def cmd_inspect_slots(args: argparse.Namespace) -> int:
    slot_file = Path(args.slots)
    if not slot_file.exists():
        print("No slot map found. Run draft-hld-ai-normalize first.", file=sys.stderr)
        return 1
    payload = json.loads(slot_file.read_text(encoding="utf-8"))
    extractor = payload.get("extractor", "rules")
    adr_files = payload.get("adr_files", [])
    slots_map = payload.get("slots", {})
    tbd = sorted(key for key, value in slots_map.items() if str(value) in ("{TBD}", ""))
    filled = {key: value for key, value in slots_map.items() if str(value) not in ("{TBD}", "")}
    print(f"Extractor : {extractor}")
    print(f"ADR files : {adr_files}")
    print(f"Slots     : {len(filled)} filled, {len(tbd)} unresolved\n")
    for key, value in sorted(filled.items()):
        print(f"  {key:<35} {value!r}")
    if tbd:
        print(f"\n  Unresolved ({len(tbd)}):")
        for key in tbd:
            print(f"    {key}")
    return 0


def cmd_inspect_chunks(args: argparse.Namespace) -> int:
    adr_dir = Path(args.adr_dir)
    files = slots.load_adr_files(adr_dir)
    if not files:
        print(f"No ADR files found in {adr_dir} (after template filter).", file=sys.stderr)
        return 1
    chunks = slots.build_chunks(files, args.max_chars, args.max_chunks)
    print(f"ADR directory : {adr_dir}")
    print(f"ADR files     : {[adr_file.name for adr_file in files]}")
    print(f"Chunks        : {len(chunks)}  (max {args.max_chars:,} chars each)\n")
    for chunk in chunks:
        print(f"  chunk_{chunk['chunk_index']}: {chunk['char_count']:>6,} chars  sources={chunk['sources']}")
    return 0


def _build_repeatability_cmd(args: argparse.Namespace, script: Path) -> list[str]:
    cmd = [sys.executable, str(script), "hld", "--extractor", "ai", "--force"]
    if args.phase:
        cmd += ["--phase", args.phase]
    if args.ai_tool:
        cmd += ["--ai-tool", args.ai_tool]
    if args.ai_model:
        cmd += ["--ai-model", args.ai_model]
    if args.canonical_dir:
        cmd += ["--canonical-dir", args.canonical_dir]
    return cmd


def _hash_phase_outputs(project_root: Path, phases: list[str]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for phase in phases:
        draft_file = project_root / "output" / "drafts_deterministic" / f"draft_hld_{phase}.md"
        hashes[phase] = hashlib.sha256(draft_file.read_bytes()).hexdigest() if draft_file.exists() else "MISSING"
    return hashes


def _run_repeatability_pass(
    args: argparse.Namespace, project_root: Path, script: Path
) -> tuple[dict[str, str] | None, int]:
    """Run one repeatability iteration. Returns (hashes, returncode); hashes is None on failure."""
    cmd = _build_repeatability_cmd(args, script)
    result = subprocess.run(
        cmd,
        cwd=str(project_root),
        capture_output=True,
        text=True,
        timeout=_REPEATABILITY_TIMEOUT_SECS,
    )
    if result.returncode != 0:
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        return None, result.returncode
    phases = [args.phase] if args.phase else ["phase1", "phase2", "phase3", "phase4"]
    return _hash_phase_outputs(project_root, phases), 0


def _find_hash_drifts(all_hashes: list[dict[str, str]]) -> list[str]:
    baseline = all_hashes[0] if all_hashes else {}
    drifts = []
    for index, run_hashes in enumerate(all_hashes[1:], start=2):
        for key in sorted(set(baseline.keys()) | set(run_hashes.keys())):
            if baseline.get(key) != run_hashes.get(key):
                drifts.append(f"Run 1 vs Run {index}: {key} mismatch")
    return drifts


def cmd_test_repeatability(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    script = project_root / "scripts" / "hld_lld" / "ai" / "ai_draft_deterministic.py"
    if not script.exists():
        print(f"Missing script: {script}", file=sys.stderr)
        return 1

    all_hashes: list[dict[str, str]] = []
    for _ in range(1, args.runs + 1):
        hashes, return_code = _run_repeatability_pass(args, project_root, script)
        if hashes is None:
            return return_code
        all_hashes.append(hashes)

    drifts = _find_hash_drifts(all_hashes)

    payload = {
        "runs": args.runs,
        "phase": args.phase or "all",
        "run_hashes": all_hashes,
        "drifts": drifts,
        "result": "PASS" if not drifts else "FAIL",
    }
    if args.out:
        _write_json(Path(args.out), payload)
    if drifts:
        for drift in drifts:
            print(drift, file=sys.stderr)
        return 1
    print(f"PASS: All {args.runs} run(s) produced identical output hashes.")
    return 0


def _add_extraction_subparsers(sub: argparse._SubParsersAction) -> None:
    """Subcommands for chunking ADRs and extracting slots: chunk, extract-ai, validate-slots."""
    subparser = sub.add_parser("chunk")
    subparser.add_argument("--adr-dir", required=True)
    subparser.add_argument("--out", required=True)
    subparser.add_argument("--max-chars", type=int, default=12000)
    subparser.add_argument("--max-chunks", type=int, default=8)
    subparser.add_argument("--include-text", action=argparse.BooleanOptionalAction, default=True)
    subparser.set_defaults(func=cmd_chunk)

    subparser = sub.add_parser("extract-ai")
    subparser.add_argument("--adr-dir", required=True)
    subparser.add_argument("--project-yaml", required=True)
    subparser.add_argument("--templates", nargs="+", required=True)
    subparser.add_argument("--out", required=True)
    subparser.add_argument("--run-dir", required=True)
    subparser.add_argument("--tool", default="cursor")
    subparser.add_argument("--model", default="claude-sonnet-4-6")
    subparser.add_argument("--cursor-python", default="python3")
    subparser.add_argument("--timeout", type=int, default=900)
    subparser.add_argument("--retries", type=int, default=3)
    subparser.add_argument("--max-chars", type=int, default=12000)
    subparser.add_argument("--max-chunks", type=int, default=8)
    subparser.add_argument("--phase-max-chars", type=int, default=24000)
    subparser.add_argument("--max-repair-rounds", type=int, default=2)
    subparser.add_argument("--prompt-global", default="")
    subparser.add_argument("--prompt-phase", default="")
    subparser.add_argument("--prompt-repair", default="")
    subparser.add_argument("--contract", default="")
    subparser.add_argument("--chunk-manifest", default="")
    subparser.add_argument("--adr-mode", choices=["auto", "chunked"], default="auto")
    subparser.add_argument("--refine-phases", action="store_true")
    subparser.set_defaults(func=cmd_extract_ai)

    subparser = sub.add_parser("validate-slots")
    subparser.add_argument("--slots", required=True)
    subparser.add_argument("--schema", default="")
    subparser.add_argument("--phases", nargs="*", default=["phase1", "phase2", "phase3", "phase4"])
    subparser.set_defaults(func=cmd_validate_slots)


def _add_render_subparsers(sub: argparse._SubParsersAction) -> None:
    """Subcommands for rendering and validating HLD output: build-contract through validate-hld."""
    subparser = sub.add_parser("build-contract")
    subparser.add_argument("--templates", nargs="+", required=True)
    subparser.add_argument("--out", required=True)
    subparser.set_defaults(func=cmd_build_contract)

    subparser = sub.add_parser("build-citation-lock")
    subparser.add_argument("--canonical-files", nargs="+", required=True)
    subparser.add_argument("--out", required=True)
    subparser.set_defaults(func=cmd_build_citation_lock)

    subparser = sub.add_parser("render-phase")
    subparser.add_argument("--template", required=True)
    subparser.add_argument("--slots", required=True)
    subparser.add_argument("--out", required=True)
    subparser.set_defaults(func=cmd_render_phase)

    subparser = sub.add_parser("stitch")
    subparser.add_argument("--draft-dir", required=True)
    subparser.add_argument("--output", required=True)
    subparser.add_argument("--expect-byte-equal-to", default="")
    subparser.set_defaults(func=cmd_stitch)

    subparser = sub.add_parser("validate-hld")
    subparser.add_argument("--file", required=True)
    subparser.add_argument("--contract", required=True)
    subparser.add_argument("--document-key", required=True)
    subparser.add_argument("--state-file", required=True)
    subparser.add_argument("--phase", default="")
    subparser.add_argument("--slots", default="")
    subparser.add_argument("--citation-lock", default="")
    subparser.add_argument("--expect-byte-equal-to", default="")
    subparser.set_defaults(func=cmd_validate_hld)


def _add_inspect_subparsers(sub: argparse._SubParsersAction) -> None:
    """Subcommands for read-only inspection: inspect-slots, inspect-chunks."""
    subparser = sub.add_parser("inspect-slots")
    subparser.add_argument("--slots", default="output/.deterministic/slots/slot_map.json")
    subparser.set_defaults(func=cmd_inspect_slots)

    subparser = sub.add_parser("inspect-chunks")
    subparser.add_argument("--adr-dir", default="ADR")
    subparser.add_argument("--max-chars", type=int, default=12000)
    subparser.add_argument("--max-chunks", type=int, default=8)
    subparser.set_defaults(func=cmd_inspect_chunks)


def _add_test_subparser(sub: argparse._SubParsersAction) -> None:
    """Subcommand for repeatability testing: test-repeatability."""
    subparser = sub.add_parser("test-repeatability")
    subparser.add_argument("--project-root", required=True)
    subparser.add_argument("--runs", type=int, default=3)
    subparser.add_argument("--phase", default="")
    subparser.add_argument("--ai-tool", default="cursor")
    subparser.add_argument("--ai-model", default="claude-sonnet-4-6")
    subparser.add_argument("--canonical-dir", default="")
    subparser.add_argument("--out", default="")
    subparser.set_defaults(func=cmd_test_repeatability)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic pipeline CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    _add_extraction_subparsers(sub)
    _add_render_subparsers(sub)
    _add_inspect_subparsers(sub)
    _add_test_subparser(sub)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
