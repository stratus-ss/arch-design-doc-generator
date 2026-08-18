#!/usr/bin/env python3
"""AI-first ADR-to-slot extraction pipeline.

Multi-stage approach:
  Prompt A (global): Extract all slots from chunked ADR context.
  Prompt B (phase):  Refine phase-specific slots against phase contract.
  Prompt C (repair): Fix schema validation errors and retry.

Outputs normalized slot JSON suitable for deterministic template rendering.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from slot_validate import validate_slot_file, validate_slots_against_schema

from ai_invoke import (  # noqa: F401 — re-exported for backward compatibility (module-level access via `slots.run_cursor` etc.)
    _run_subprocess,
    run_claude,
    run_codex,
    run_cursor,
)
from ai_invoke import invoke_ai as _invoke_ai_shared
from markdown_utils import (
    PLACEHOLDER_TOKEN_RE,
    apply_derived_slots,
    apply_yaml_overlay,
    empty_required_slots,
)

JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]+?)\s*```")
HEADING_SPLIT_RE = re.compile(r"^#{1,3}\s+", re.MULTILINE)
SINGLE_PASS_MAX_CHARS = 10_000_000
SINGLE_PASS_MAX_CHUNKS = 1


class PromptAFailed(Exception):
    """Prompt A timed out or produced no parseable JSON."""


PHASE_SLOTS: Dict[str, List[str]] = {
    "phase1": [
        "CLIENT",
        "OCP_VERSION",
        "VM_COUNT",
        "CLUSTER_COUNT",
        "HOST_COUNT",
        "SITE_COUNT",
        "SITE_PRIMARY",
        "SITE_SECONDARY",
        "SITE_LAB",
        "SERVER_HARDWARE",
        "POD_CIDR",
        "SVC_CIDR",
        "PODS_PER_NODE",
        "SWITCH_VENDOR",
        "BRANCH_COUNT",
        "BRANCH_HARDWARE",
        "BRANCH_WAN_BW",
        "INFRA_PLATFORM",
        "TIER_COUNT",
        "TIER_PRIMARY",
        "TIER_MIDDLE",
        "TIER_EDGE",
        "GITOPS_HOST",
    ],
    "phase2": [
        "CLIENT",
        "BACKUP_VENDOR",
        "BLOCK_STORAGE_VENDOR",
        "BLOCK_CSI_DRIVER",
        "BLOCK_SC_NAME",
        "APM_VENDOR",
        "SIEM_PLATFORM",
        "NOC_PLATFORM",
        "OBJECT_STORAGE",
        "SECRET_MGMT_VENDOR",
        "ITSM_PLATFORM",
        "HW_MGMT_PLATFORM",
        "HW_MONITORING_VENDOR",
        "DNS_IPAM_VENDOR",
        "IMAGE_REGISTRY",
        "THANOS_RETENTION_TARGET",
        "THANOS_RETENTION_DECISION",
        "REPO_BOUNDARY_DECISION",
        "CONSOLE_ACCESS_NOTES",
        "CPU_OVERCOMMIT_TARGET",
        "DESCHEDULER_FINAL_PROFILE",
        "TIER_COUNT",
        "TIER_PRIMARY",
        "TIER_MIDDLE",
        "TIER_EDGE",
    ],
    "phase3": [
        "CLIENT",
        "SCANNING_VENDOR",
        "BRANCH_STORAGE_CAPACITY",
        "BRANCH_EGRESS_STRATEGY",
        "BRANCH_VNIC_MODEL",
        "AUDIT_PROFILE",
        "REMEDIATION_OPERATION_MODE",
        "TIER_COUNT",
        "TIER_PRIMARY",
        "TIER_MIDDLE",
        "TIER_EDGE",
    ],
    "phase4": [
        "CLIENT",
        "INFRA_PLATFORM",
        "MIGRATION_WINDOW",
        "MORATORIUM_SCHEDULE",
        "BAKE_PERIOD",
        "HOLDBACK_DURATION",
        "MIGRATION_ARTIFACT_STORAGE",
        "TIER_COUNT",
        "TIER_PRIMARY",
        "TIER_MIDDLE",
        "TIER_EDGE",
    ],
}


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_adr_files(adr_dir: Path) -> List[Path]:
    return sorted(p for p in adr_dir.glob("*.md") if "template" not in p.name.lower())


def split_at_headings(text: str) -> List[str]:
    boundaries = [m.start() for m in HEADING_SPLIT_RE.finditer(text)]
    if not boundaries or boundaries[0] != 0:
        boundaries = [0] + boundaries
    sections: List[str] = []
    for i, start in enumerate(boundaries):
        end = boundaries[i + 1] if i + 1 < len(boundaries) else len(text)
        sections.append(text[start:end])
    return sections


def build_chunks(adr_files: List[Path], max_chars: int, max_chunks: int) -> List[dict]:
    all_sections: List[tuple[str, str]] = []
    for f in adr_files:
        text = f.read_text(encoding="utf-8")
        for section_text in split_at_headings(text):
            all_sections.append((f.name, section_text))

    chunks: List[dict] = []
    current_parts: List[tuple[str, str]] = []
    current_chars = 0

    for source_file, section in all_sections:
        section_len = len(section)
        if current_parts and (current_chars + section_len > max_chars):
            text = "\n\n".join(s for _, s in current_parts)
            chunks.append(
                {
                    "chunk_index": len(chunks),
                    "label": f"ADR_CHUNK_{len(chunks)}",
                    "sources": sorted({src for src, _ in current_parts}),
                    "char_count": len(text),
                    "sha256": _sha256_text(text),
                    "text": text,
                }
            )
            current_parts = []
            current_chars = 0
            if len(chunks) >= max_chunks:
                break
        current_parts.append((source_file, section))
        current_chars += section_len

    if current_parts and len(chunks) < max_chunks:
        text = "\n\n".join(s for _, s in current_parts)
        chunks.append(
            {
                "chunk_index": len(chunks),
                "label": f"ADR_CHUNK_{len(chunks)}",
                "sources": sorted({src for src, _ in current_parts}),
                "char_count": len(text),
                "sha256": _sha256_text(text),
                "text": text,
            }
        )
    return chunks


# ── AI tool invocation ────────────────────────────────────────────────────────
# run_claude, run_codex, run_cursor, invoke_ai moved to scripts/shared/lib/ai_invoke.py
# (imported at top of this file) so the HLD/LLD pipeline has one invocation implementation.

# ── Prompt templating ─────────────────────────────────────────────────────────


def fill_prompt(template: str, variables: Dict[str, str]) -> str:
    """Replace {{VAR}} placeholders in prompt templates."""
    for key, val in variables.items():
        template = template.replace(f"{{{{{key}}}}}", val)
    return template


# ── JSON parsing ──────────────────────────────────────────────────────────────


def parse_json_response(raw: str) -> Optional[Dict[str, Any]]:
    """Extract and parse the first valid JSON object from an AI response."""
    raw = raw.strip()
    if raw.startswith("{"):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

    fence_match = JSON_FENCE_RE.search(raw)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    brace_start = raw.find("{")
    brace_end = raw.rfind("}")
    if brace_start != -1 and brace_end != -1:
        try:
            return json.loads(raw[brace_start : brace_end + 1])
        except json.JSONDecodeError:
            pass

    return None


# ── Schema normalization ──────────────────────────────────────────────────────


def normalize_slot_entry(entry: Any, slot_name: str) -> Dict[str, str]:
    """Ensure a slot entry conforms to the evidence envelope schema."""
    if not isinstance(entry, dict):
        entry = {"value": str(entry) if entry else ""}

    return {
        "value": str(entry.get("value", "")).strip(),
        "confidence": entry.get("confidence", "low") if entry.get("confidence") in ("high", "medium", "low") else "low",
        "evidence_excerpt": str(entry.get("evidence_excerpt", ""))[:120],
        "evidence_source": str(entry.get("evidence_source", "")) or "derived_default",
    }


def merge_slots(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    """Merge update into base, preferring higher-confidence values.

    Tie-break rule: when confidence is equal, prefer entries with a non-empty
    evidence_excerpt (grounded in ADR text) over those without, and prefer
    non-empty values over empty ones. This prevents an early chunk claiming
    "high" confidence on an empty excerpt from blocking a later, better answer.
    """
    CONF_RANK = {"high": 3, "medium": 2, "low": 1}
    merged = dict(base)
    for k, v in update.items():
        if not isinstance(v, dict):
            continue
        existing = base.get(k)
        if not existing:
            merged[k] = v
            continue
        existing_rank = CONF_RANK.get(existing.get("confidence", "low"), 0)
        new_rank = CONF_RANK.get(v.get("confidence", "low"), 0)
        if new_rank > existing_rank:
            merged[k] = v
        elif new_rank == existing_rank:
            new_has_evidence = bool(v.get("evidence_excerpt", "").strip())
            old_has_evidence = bool(existing.get("evidence_excerpt", "").strip())
            new_has_value = bool(str(v.get("value", "")).strip())
            old_has_value = bool(str(existing.get("value", "")).strip())
            # Prefer grounded evidence over empty excerpt
            if new_has_evidence and not old_has_evidence:
                merged[k] = v
            # Prefer non-empty value over empty when both have (or lack) excerpts
            elif new_has_value and not old_has_value and not old_has_evidence:
                merged[k] = v
    return merged


# ── Core pipeline ─────────────────────────────────────────────────────────────
# invoke_ai moved to scripts/shared/lib/ai_invoke.py (imported as _invoke_ai_shared
# at top of this file); call sites below pass args.* fields explicitly since the
# shared function no longer takes an argparse.Namespace.


def run_global_prompt(chunks: List[dict], prompt_template: str, args: argparse.Namespace) -> Dict[str, Any]:
    """Run Prompt A across all ADR chunks and merge results."""
    merged: Dict[str, Any] = {}
    parsed_any = False
    for chunk in chunks:
        label = chunk.get("label", f"CHUNK_{chunk.get('chunk_index', 0)}")
        text = chunk.get("text", "")
        print(f"  [Prompt A] Processing {label} ({len(text)} chars)...", file=sys.stderr)

        prompt = fill_prompt(
            prompt_template,
            {
                "ADR_CHUNK_LABEL": label,
                "ADR_CONTENT": text,
            },
        )

        try:
            raw = _invoke_ai_shared(prompt, args.tool, args.model, args.timeout, args.retries, args.cursor_python)
        except RuntimeError as exc:
            raise PromptAFailed(str(exc)) from exc
        parsed = parse_json_response(raw)

        if parsed is None:
            print(f"  [Prompt A] Warning: could not parse JSON from {label}. Skipping.", file=sys.stderr)
            continue

        parsed_any = True
        normalized = {k: normalize_slot_entry(v, k) for k, v in parsed.items()}
        merged = merge_slots(merged, normalized)

    if not parsed_any:
        raise PromptAFailed("Prompt A JSON parse failed for all chunks")
    return merged


def run_phase_prompt(
    phase: str,
    global_slots: Dict[str, Any],
    contract: dict,
    chunks: List[dict],
    prompt_template: str,
    args: argparse.Namespace,
) -> Dict[str, Any]:
    """Run Prompt B for a specific phase and return refined slots."""
    phase_slot_names = PHASE_SLOTS.get(phase, [])
    if not phase_slot_names:
        return {}

    phase_contract_json = json.dumps(contract.get("contracts", {}).get(phase, {}), indent=2)

    default_slot = {"value": "", "confidence": "low", "evidence_excerpt": "", "evidence_source": "derived_default"}
    global_phase_slots = {k: global_slots.get(k, default_slot) for k in phase_slot_names}

    combined_text = "\n\n".join(c.get("text", "") for c in chunks)
    label = f"ALL_ADR_CHUNKS ({len(combined_text)} chars)"
    print(f"  [Prompt B:{phase}] Refining {len(phase_slot_names)} slots...", file=sys.stderr)

    prompt = fill_prompt(
        prompt_template,
        {
            "PHASE": phase,
            "PHASE_CONTRACT": phase_contract_json,
            "PHASE_SLOT_LIST": "\n".join(f"- `{s}`" for s in phase_slot_names),
            "GLOBAL_SLOTS_JSON": json.dumps(global_phase_slots, indent=2),
            "ADR_CHUNK_LABEL": label,
            "ADR_CONTENT": combined_text[: args.phase_max_chars],
        },
    )

    raw = _invoke_ai_shared(prompt, args.tool, args.model, args.timeout, args.retries, args.cursor_python)
    parsed = parse_json_response(raw)

    if parsed is None:
        print(f"  [Prompt B:{phase}] Warning: could not parse JSON. Keeping global values.", file=sys.stderr)
        return {}

    return {k: normalize_slot_entry(v, k) for k, v in parsed.items() if k in phase_slot_names}


def run_repair_prompt(
    errors: List[dict],
    current_slots: Dict[str, Any],
    chunks: List[dict],
    prompt_template: str,
    args: argparse.Namespace,
) -> Dict[str, Any]:
    """Run Prompt C to repair schema validation errors."""
    combined_text = "\n\n".join(c.get("text", "") for c in chunks)
    print(f"  [Prompt C] Repairing {len(errors)} error(s)...", file=sys.stderr)

    prompt = fill_prompt(
        prompt_template,
        {
            "VALIDATION_ERRORS_JSON": json.dumps(errors, indent=2),
            "SLOT_JSON_WITH_ERRORS": json.dumps(current_slots, indent=2),
            "ADR_CHUNK_LABEL": "ALL_ADR_CHUNKS",
            "ADR_CONTENT": combined_text[: args.phase_max_chars],
        },
    )

    raw = _invoke_ai_shared(prompt, args.tool, args.model, args.timeout, args.retries, args.cursor_python)
    parsed = parse_json_response(raw)

    if parsed is None:
        print("  [Prompt C] Warning: could not parse repaired JSON.", file=sys.stderr)
        return current_slots

    return {k: normalize_slot_entry(v, k) for k, v in parsed.items()}


def run_empty_slot_repair(
    merged_slots: Dict[str, Any],
    chunks: List[dict],
    prompt_template: str,
    args: argparse.Namespace,
    run_dir: Path,
    schema: dict,
) -> Dict[str, Any]:
    """One Prompt A-style call for empty required slots. Skip if none empty."""
    empty_keys = empty_required_slots(merged_slots, schema)
    if not empty_keys:
        print("empty-repair: skip, 0 empty required", file=sys.stderr)
        return merged_slots

    print(f"=== Stage D: Empty-required slot repair ({len(empty_keys)} keys) ===", file=sys.stderr)
    combined_text = "\n\n".join(c.get("text", "") for c in chunks)
    prompt = fill_prompt(
        prompt_template,
        {
            "EMPTY_SLOT_LIST": "\n".join(f"- `{key}`" for key in empty_keys),
            "ADR_CHUNK_LABEL": "FULL_ADR",
            "ADR_CONTENT": combined_text,
        },
    )
    raw = _invoke_ai_shared(prompt, args.tool, args.model, args.timeout, args.retries, args.cursor_python)
    parsed = parse_json_response(raw)
    if parsed is None:
        print("  [empty-repair] Warning: could not parse JSON. Keeping current values.", file=sys.stderr)
        return merged_slots
    allowed = set(empty_keys)
    updates = {k: normalize_slot_entry(v, k) for k, v in parsed.items() if k in allowed}
    (run_dir / "empty_repair_raw.json").write_text(json.dumps(updates, indent=2) + "\n", encoding="utf-8")
    return merge_slots(merged_slots, updates)


def collect_all_placeholders(template_paths: List[Path]) -> List[str]:
    placeholders = set()
    for path in template_paths:
        if path.exists():
            placeholders.update(PLACEHOLDER_TOKEN_RE.findall(path.read_text(encoding="utf-8")))
    return sorted(placeholders)


def flatten_for_render(evidence_slots: Dict[str, Any]) -> Dict[str, str]:
    """Convert evidence-envelope slots to simple str->str for deterministic render."""
    result: Dict[str, str] = {}
    for k, v in evidence_slots.items():
        if isinstance(v, dict):
            result[k] = str(v.get("value", "")).strip()
        else:
            result[k] = str(v).strip()
    return result


# ── Argument parsing ──────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI-first ADR-to-slot extraction (multi-stage pipeline).")
    parser.add_argument("--adr-dir", required=True, help="ADR directory (*.md, excluding templates).")
    parser.add_argument("--project-yaml", required=True, help="project.yaml path.")
    parser.add_argument("--templates", nargs="+", required=True, help="Template phase files.")
    parser.add_argument("--out", required=True, help="Output slots JSON file.")
    parser.add_argument("--run-dir", required=True, help="Run artifact directory (persists raw AI outputs).")
    parser.add_argument(
        "--chunk-manifest", default="", help="Pre-built chunk manifest JSON. Auto-built if not provided."
    )
    parser.add_argument("--contract", default="", help="Template contract JSON from deterministic cli build-contract.")

    parser.add_argument(
        "--tool", default="cursor", choices=["claude", "codex", "cursor"], help="AI tool to use (default: cursor)."
    )
    parser.add_argument("--model", default="claude-sonnet-4-6", help="Model name (default: claude-sonnet-4-6).")
    parser.add_argument("--cursor-python", default="python3", help="Python executable for cursor SDK.")
    parser.add_argument(
        "--timeout", type=int, default=900, help="Per-call timeout in seconds (single-pass Prompt A needs ~15m)."
    )
    parser.add_argument("--retries", type=int, default=3, help="Retry attempts per AI call.")
    parser.add_argument("--max-chars", type=int, default=12000, help="Max chars per ADR chunk (chunked mode).")
    parser.add_argument("--max-chunks", type=int, default=8, help="Max ADR chunks for Prompt A (chunked mode).")
    parser.add_argument(
        "--phase-max-chars",
        type=int,
        default=24000,
        help="Max chars of ADR context fed to Prompt B/C (default: 24000).",
    )
    parser.add_argument(
        "--adr-mode",
        choices=["auto", "chunked"],
        default="auto",
        help="auto: one full-ADR chunk then chunked fallback; chunked: 8x12k only.",
    )
    parser.add_argument(
        "--refine-phases",
        action="store_true",
        help="Run Prompt B per-phase refinement (off by default).",
    )
    parser.add_argument("--max-repair-rounds", type=int, default=2, help="Maximum Prompt C repair rounds (default: 2).")

    parser.add_argument(
        "--prompt-global",
        default="",
        help="Path to Prompt A template (default: auto-detected from scripts/hld_lld/ai/deterministic/prompts/).",
    )
    parser.add_argument(
        "--prompt-phase",
        default="",
        help="Path to Prompt B template.",
    )
    parser.add_argument(
        "--prompt-repair",
        default="",
        help="Path to Prompt C template.",
    )
    return parser.parse_args()


# ── Main ──────────────────────────────────────────────────────────────────────


def _load_prompts(args: argparse.Namespace, prompts_dir: Path) -> tuple[str, str, str, str]:
    prompt_global_path = Path(args.prompt_global) if args.prompt_global else prompts_dir / "extract_hld_slots_global.md"
    prompt_phase_path = Path(args.prompt_phase) if args.prompt_phase else prompts_dir / "extract_hld_slots_phase.md"
    prompt_repair_path = Path(args.prompt_repair) if args.prompt_repair else prompts_dir / "extract_hld_slots_repair.md"
    prompt_empty_path = prompts_dir / "extract_hld_slots_empty.md"

    for p in [prompt_global_path, prompt_phase_path, prompt_repair_path, prompt_empty_path]:
        if not p.exists():
            raise SystemExit(f"Prompt file not found: {p}")

    return (
        prompt_global_path.read_text(encoding="utf-8"),
        prompt_phase_path.read_text(encoding="utf-8"),
        prompt_repair_path.read_text(encoding="utf-8"),
        prompt_empty_path.read_text(encoding="utf-8"),
    )


def _write_chunk_manifest(run_dir: Path, adr_files: List[Path], chunks: List[dict]) -> dict:
    manifest = {
        "adr_files": [f.name for f in adr_files],
        "chunk_count": len(chunks),
        "chunks": chunks,
    }
    (run_dir / "chunk_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _load_or_build_chunks(args: argparse.Namespace, adr_dir: Path, run_dir: Path) -> dict:
    adr_mode = getattr(args, "adr_mode", "auto")
    use_manifest = adr_mode == "chunked" and args.chunk_manifest and Path(args.chunk_manifest).exists()
    if use_manifest:
        manifest = json.loads(Path(args.chunk_manifest).read_text(encoding="utf-8"))
        print(f"Loaded chunk manifest: {len(manifest.get('chunks', []))} chunk(s).", file=sys.stderr)
        return manifest

    adr_files = load_adr_files(adr_dir)
    if not adr_files:
        raise SystemExit(f"No ADR files found in {adr_dir} (after template filter).")
    if adr_mode == "chunked":
        chunks = build_chunks(adr_files, args.max_chars, args.max_chunks)
    else:
        chunks = build_chunks(adr_files, SINGLE_PASS_MAX_CHARS, SINGLE_PASS_MAX_CHUNKS)
    print(f"Built {len(chunks)} chunk(s) from {len(adr_files)} ADR file(s) (adr_mode={adr_mode}).", file=sys.stderr)
    return _write_chunk_manifest(run_dir, adr_files, chunks)


def _extract_global_slots_with_fallback(
    chunks: list,
    prompt_global: str,
    args: argparse.Namespace,
    client_name: str,
    project_code: str,
    run_dir: Path,
    adr_dir: Path,
) -> tuple[dict, list, str]:
    adr_mode = getattr(args, "adr_mode", "auto")
    try:
        global_slots = _extract_global_slots(chunks, prompt_global, args, client_name, project_code, run_dir)
        used = "chunked" if adr_mode == "chunked" else "single"
        return global_slots, chunks, used
    except PromptAFailed as exc:
        if adr_mode == "chunked":
            raise SystemExit(f"Prompt A failed in chunked mode: {exc}") from exc
        print(f"Single-pass Prompt A failed ({exc}). Retrying with 8x12k chunks.", file=sys.stderr)
        adr_files = load_adr_files(adr_dir)
        chunks = build_chunks(adr_files, args.max_chars, args.max_chunks)
        _write_chunk_manifest(run_dir, adr_files, chunks)
        global_slots = _extract_global_slots(chunks, prompt_global, args, client_name, project_code, run_dir)
        return global_slots, chunks, "chunked"


def _extract_global_slots(
    chunks: list, prompt_global: str, args: argparse.Namespace, client_name: str, project_code: str, run_dir: Path
) -> dict:
    print("=== Stage A: Global slot extraction ===", file=sys.stderr)
    global_slots = run_global_prompt(chunks, prompt_global, args)
    (run_dir / "global_slots_raw.json").write_text(json.dumps(global_slots, indent=2) + "\n", encoding="utf-8")

    for slot, val in [("CLIENT", client_name), ("CLIENT_NAME", client_name), ("PROJECT_CODE", project_code)]:
        if client_name and (slot not in global_slots or not global_slots[slot].get("value")):
            global_slots[slot] = {
                "value": val,
                "confidence": "high",
                "evidence_excerpt": "",
                "evidence_source": "project.yaml",
            }
    return global_slots


def _refine_phases(
    global_slots: dict, contract: dict, chunks: list, prompt_phase: str, args: argparse.Namespace, run_dir: Path
) -> dict:
    merged_slots = dict(global_slots)
    if not getattr(args, "refine_phases", False):
        return merged_slots
    print("=== Stage B: Per-phase slot refinement ===", file=sys.stderr)
    for phase in ("phase1", "phase2", "phase3", "phase4"):
        phase_updates = run_phase_prompt(phase, merged_slots, contract, chunks, prompt_phase, args)
        merged_slots = merge_slots(merged_slots, phase_updates)
    (run_dir / "merged_slots_after_phase_refine.json").write_text(
        json.dumps(merged_slots, indent=2) + "\n", encoding="utf-8"
    )
    return merged_slots


def _validate_and_repair(
    merged_slots: dict, chunks: list, prompt_repair: str, args: argparse.Namespace, run_dir: Path
) -> dict:
    print("=== Stage C: Schema validation + repair ===", file=sys.stderr)
    schema_path = Path(__file__).parent / "slot_schema.json"
    schema: dict = {}
    if schema_path.exists():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

    for repair_round in range(1, args.max_repair_rounds + 1):
        errors = validate_slots_against_schema(merged_slots, schema)
        if not errors:
            print(f"  Schema validation passed (round {repair_round}).", file=sys.stderr)
            break
        print(f"  [Round {repair_round}] {len(errors)} validation error(s). Running repair...", file=sys.stderr)
        (run_dir / f"validation_errors_round{repair_round}.json").write_text(
            json.dumps(errors, indent=2) + "\n", encoding="utf-8"
        )
        merged_slots = run_repair_prompt(errors, merged_slots, chunks, prompt_repair, args)
    else:
        errors = validate_slots_against_schema(merged_slots, schema)
        if errors:
            print(f"  Warning: {len(errors)} schema error(s) remain after max repair rounds.", file=sys.stderr)

    (run_dir / "final_slots_evidence.json").write_text(json.dumps(merged_slots, indent=2) + "\n", encoding="utf-8")
    return merged_slots


def _finalize_and_write(merged_slots: dict, manifest: dict, args: argparse.Namespace) -> None:
    merged_slots = apply_derived_slots(merged_slots)
    template_paths = [Path(t) for t in args.templates]
    all_placeholders = collect_all_placeholders(template_paths)
    flat_slots = flatten_for_render(merged_slots)

    for token in all_placeholders:
        if token not in flat_slots or not flat_slots[token]:
            flat_slots[token] = "{TBD}"

    payload = {
        "extractor": "ai",
        "tool": args.tool,
        "model": args.model,
        "adr_files": manifest.get("adr_files", []),
        "slots": {k: flat_slots[k] for k in sorted(flat_slots)},
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"AI extraction complete: {len(flat_slots)} slots → {out_path}", file=sys.stderr)


def main() -> None:
    args = parse_args()

    script_dir = Path(__file__).parent
    prompt_global, prompt_phase, prompt_repair, prompt_empty = _load_prompts(args, script_dir / "prompts")

    adr_dir = Path(args.adr_dir)
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest = _load_or_build_chunks(args, adr_dir, run_dir)
    chunks = manifest.get("chunks", [])

    import yaml
    from config import get_client_identity

    cfg = yaml.safe_load(Path(args.project_yaml).read_text(encoding="utf-8")) or {}
    client_name, project_code = get_client_identity(cfg)

    contract: dict = {}
    if args.contract and Path(args.contract).exists():
        contract = json.loads(Path(args.contract).read_text(encoding="utf-8"))

    global_slots, chunks, adr_mode_used = _extract_global_slots_with_fallback(
        chunks, prompt_global, args, client_name, project_code, run_dir, adr_dir
    )
    (run_dir / "adr_mode_used").write_text(adr_mode_used + "\n", encoding="utf-8")
    manifest["chunks"] = chunks
    manifest["chunk_count"] = len(chunks)
    manifest["adr_mode_used"] = adr_mode_used
    merged_slots = _refine_phases(global_slots, contract, chunks, prompt_phase, args, run_dir)
    merged_slots = apply_yaml_overlay(merged_slots, cfg)
    schema_path = Path(__file__).parent / "slot_schema.json"
    schema: dict = json.loads(schema_path.read_text(encoding="utf-8")) if schema_path.exists() else {}
    merged_slots = run_empty_slot_repair(merged_slots, chunks, prompt_empty, args, run_dir, schema)
    merged_slots = _validate_and_repair(merged_slots, chunks, prompt_repair, args, run_dir)
    _finalize_and_write(merged_slots, manifest, args)


def run_extract_ai(argv: List[str] | None = None) -> int:
    old_argv = sys.argv[:]
    try:
        sys.argv = [old_argv[0]] + (argv or [])
        main()
        return 0
    finally:
        sys.argv = old_argv


if __name__ == "__main__":
    main()
