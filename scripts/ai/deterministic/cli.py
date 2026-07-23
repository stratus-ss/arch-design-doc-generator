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


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


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
        "adr_files": [f.name for f in adr_files],
        "max_chars_per_chunk": args.max_chars,
        "max_chunks": args.max_chunks,
        "chunk_count": len(chunks),
        "chunks": chunks if args.include_text else [{k: v for k, v in c.items() if k != "text"} for c in chunks],
    }
    _write_json(out, manifest)
    print(f"Chunked {len(adr_files)} ADR file(s) into {len(chunks)} chunk(s) → {out}")
    return 0


def cmd_extract_ai(args: argparse.Namespace) -> int:
    argv = [
        "--adr-dir", args.adr_dir,
        "--project-yaml", args.project_yaml,
        "--templates", *args.templates,
        "--out", args.out,
        "--run-dir", args.run_dir,
        "--tool", args.tool,
        "--model", args.model,
        "--cursor-python", args.cursor_python,
        "--timeout", str(args.timeout),
        "--retries", str(args.retries),
        "--max-chars", str(args.max_chars),
        "--max-chunks", str(args.max_chunks),
        "--phase-max-chars", str(args.phase_max_chars),
        "--max-repair-rounds", str(args.max_repair_rounds),
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
    if args.skip_phase_refine:
        argv += ["--skip-phase-refine"]
    return slots.run_extract_ai(argv)


def cmd_validate_slots(args: argparse.Namespace) -> int:
    schema = Path(args.schema) if args.schema else None
    return slots.validate_slot_file(Path(args.slots), args.phases, schema)


def cmd_build_contract(args: argparse.Namespace) -> int:
    render.build_contract([Path(t) for t in args.templates], Path(args.out))
    return 0


def cmd_build_citation_lock(args: argparse.Namespace) -> int:
    render.build_citation_lock([Path(p) for p in args.canonical_files], Path(args.out))
    return 0


def cmd_render_phase(args: argparse.Namespace) -> int:
    render.render_phase(Path(args.template), Path(args.slots), Path(args.out))
    return 0


def cmd_stitch(args: argparse.Namespace) -> int:
    render.stitch_deterministic(Path(args.draft_dir), Path(args.output), args.expect_byte_equal_to)
    return 0


def cmd_validate_hld(args: argparse.Namespace) -> int:
    argv = [
        "--file", args.file,
        "--contract", args.contract,
        "--document-key", args.document_key,
        "--state-file", args.state_file,
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
    p = json.loads(slot_file.read_text(encoding="utf-8"))
    extractor = p.get("extractor", "rules")
    adr_files = p.get("adr_files", [])
    slots_map = p.get("slots", {})
    tbd = sorted(k for k, v in slots_map.items() if str(v) in ("{TBD}", ""))
    filled = {k: v for k, v in slots_map.items() if str(v) not in ("{TBD}", "")}
    print(f"Extractor : {extractor}")
    print(f"ADR files : {adr_files}")
    print(f"Slots     : {len(filled)} filled, {len(tbd)} unresolved\n")
    for k, v in sorted(filled.items()):
        print(f"  {k:<35} {v!r}")
    if tbd:
        print(f"\n  Unresolved ({len(tbd)}):")
        for k in tbd:
            print(f"    {k}")
    return 0


def cmd_inspect_chunks(args: argparse.Namespace) -> int:
    adr_dir = Path(args.adr_dir)
    files = slots.load_adr_files(adr_dir)
    if not files:
        print(f"No ADR files found in {adr_dir} (after template filter).", file=sys.stderr)
        return 1
    chunks = slots.build_chunks(files, args.max_chars, args.max_chunks)
    print(f"ADR directory : {adr_dir}")
    print(f"ADR files     : {[f.name for f in files]}")
    print(f"Chunks        : {len(chunks)}  (max {args.max_chars:,} chars each)\n")
    for c in chunks:
        print(f"  chunk_{c['chunk_index']}: {c['char_count']:>6,} chars  sources={c['sources']}")
    return 0


def cmd_test_repeatability(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    script = project_root / "scripts" / "ai" / "ai_draft_deterministic.py"
    if not script.exists():
        print(f"Missing script: {script}", file=sys.stderr)
        return 1

    all_hashes: list[dict[str, str]] = []
    for i in range(1, args.runs + 1):
        cmd = [sys.executable, str(script), "hld", "--extractor", "ai", "--force"]
        if args.phase:
            cmd += ["--phase", args.phase]
        if args.ai_tool:
            cmd += ["--ai-tool", args.ai_tool]
        if args.ai_model:
            cmd += ["--ai-model", args.ai_model]
        if args.canonical_dir:
            cmd += ["--canonical-dir", args.canonical_dir]
        result = subprocess.run(cmd, cwd=str(project_root), capture_output=True, text=True)
        if result.returncode != 0:
            print(result.stdout, file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            return result.returncode

        hashes: dict[str, str] = {}
        phases = [args.phase] if args.phase else ["phase1", "phase2", "phase3", "phase4"]
        for p in phases:
            f = project_root / "output" / "drafts_deterministic" / f"draft_hld_{p}.md"
            hashes[p] = hashlib.sha256(f.read_bytes()).hexdigest() if f.exists() else "MISSING"
        all_hashes.append(hashes)

    baseline = all_hashes[0] if all_hashes else {}
    drifts = []
    for idx, run_hashes in enumerate(all_hashes[1:], start=2):
        for k in sorted(set(baseline.keys()) | set(run_hashes.keys())):
            if baseline.get(k) != run_hashes.get(k):
                drifts.append(f"Run 1 vs Run {idx}: {k} mismatch")

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
        for d in drifts:
            print(d, file=sys.stderr)
        return 1
    print(f"PASS: All {args.runs} run(s) produced identical output hashes.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic pipeline CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("chunk")
    p.add_argument("--adr-dir", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--max-chars", type=int, default=12000)
    p.add_argument("--max-chunks", type=int, default=8)
    p.add_argument("--include-text", action="store_true", default=True)
    p.set_defaults(func=cmd_chunk)

    p = sub.add_parser("extract-ai")
    p.add_argument("--adr-dir", required=True)
    p.add_argument("--project-yaml", required=True)
    p.add_argument("--templates", nargs="+", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--run-dir", required=True)
    p.add_argument("--tool", default="cursor")
    p.add_argument("--model", default="claude-sonnet-4-6")
    p.add_argument("--cursor-python", default="python3")
    p.add_argument("--timeout", type=int, default=180)
    p.add_argument("--retries", type=int, default=3)
    p.add_argument("--max-chars", type=int, default=12000)
    p.add_argument("--max-chunks", type=int, default=8)
    p.add_argument("--phase-max-chars", type=int, default=24000)
    p.add_argument("--max-repair-rounds", type=int, default=2)
    p.add_argument("--prompt-global", default="")
    p.add_argument("--prompt-phase", default="")
    p.add_argument("--prompt-repair", default="")
    p.add_argument("--contract", default="")
    p.add_argument("--chunk-manifest", default="")
    p.add_argument("--skip-phase-refine", action="store_true")
    p.set_defaults(func=cmd_extract_ai)

    p = sub.add_parser("validate-slots")
    p.add_argument("--slots", required=True)
    p.add_argument("--schema", default="")
    p.add_argument("--phases", nargs="*", default=["phase1", "phase2", "phase3", "phase4"])
    p.set_defaults(func=cmd_validate_slots)

    p = sub.add_parser("build-contract")
    p.add_argument("--templates", nargs="+", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_build_contract)

    p = sub.add_parser("build-citation-lock")
    p.add_argument("--canonical-files", nargs="+", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_build_citation_lock)

    p = sub.add_parser("render-phase")
    p.add_argument("--template", required=True)
    p.add_argument("--slots", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_render_phase)

    p = sub.add_parser("stitch")
    p.add_argument("--draft-dir", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--expect-byte-equal-to", default="")
    p.set_defaults(func=cmd_stitch)

    p = sub.add_parser("validate-hld")
    p.add_argument("--file", required=True)
    p.add_argument("--contract", required=True)
    p.add_argument("--document-key", required=True)
    p.add_argument("--state-file", required=True)
    p.add_argument("--phase", default="")
    p.add_argument("--slots", default="")
    p.add_argument("--citation-lock", default="")
    p.add_argument("--expect-byte-equal-to", default="")
    p.set_defaults(func=cmd_validate_hld)

    p = sub.add_parser("inspect-slots")
    p.add_argument("--slots", default="output/.deterministic/slots/slot_map.json")
    p.set_defaults(func=cmd_inspect_slots)

    p = sub.add_parser("inspect-chunks")
    p.add_argument("--adr-dir", default="ADR")
    p.add_argument("--max-chars", type=int, default=12000)
    p.add_argument("--max-chunks", type=int, default=8)
    p.set_defaults(func=cmd_inspect_chunks)

    p = sub.add_parser("test-repeatability")
    p.add_argument("--project-root", required=True)
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--phase", default="")
    p.add_argument("--ai-tool", default="cursor")
    p.add_argument("--ai-model", default="claude-sonnet-4-6")
    p.add_argument("--canonical-dir", default="")
    p.add_argument("--out", default="")
    p.set_defaults(func=cmd_test_repeatability)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
