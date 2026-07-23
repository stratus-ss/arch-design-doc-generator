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
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

PLACEHOLDER_RE = re.compile(r"\{([A-Z0-9_]+)\}")
JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]+?)\s*```")
HEADING_SPLIT_RE = re.compile(r"^#{1,3}\s+", re.MULTILINE)

PHASE_SLOTS: Dict[str, List[str]] = {
    "phase1": [
        "CLIENT", "OCP_VERSION", "VM_COUNT", "CLUSTER_COUNT", "HOST_COUNT",
        "SITE_COUNT", "SITE_PRIMARY", "SITE_SECONDARY", "SITE_LAB",
        "SERVER_HARDWARE", "POD_CIDR", "SVC_CIDR", "PODS_PER_NODE",
        "SWITCH_VENDOR", "BRANCH_COUNT", "BRANCH_HARDWARE",
        "BRANCH_WAN_BW", "INFRA_PLATFORM", "TIER_MIDDLE",
    ],
    "phase2": [
        "CLIENT", "BACKUP_VENDOR", "BLOCK_STORAGE_VENDOR", "BLOCK_CSI_DRIVER",
        "BLOCK_SC_NAME", "APM_VENDOR", "SIEM_PLATFORM", "NOC_PLATFORM",
        "OBJECT_STORAGE", "SECRET_MGMT_VENDOR", "ITSM_PLATFORM",
        "HW_MGMT_PLATFORM", "HW_MONITORING_VENDOR", "DNS_IPAM_VENDOR",
        "IMAGE_REGISTRY", "THANOS_RETENTION_TARGET", "THANOS_RETENTION_DECISION",
        "REPO_BOUNDARY_DECISION", "CONSOLE_ACCESS_NOTES", "CPU_OVERCOMMIT_TARGET",
        "DESCHEDULER_FINAL_PROFILE", "TIER_MIDDLE",
    ],
    "phase3": [
        "CLIENT", "SCANNING_VENDOR", "BRANCH_STORAGE_CAPACITY",
        "BRANCH_EGRESS_STRATEGY", "BRANCH_VNIC_MODEL", "AUDIT_PROFILE",
        "REMEDIATION_OPERATION_MODE", "TIER_MIDDLE",
    ],
    "phase4": [
        "CLIENT", "INFRA_PLATFORM", "MIGRATION_WINDOW", "MORATORIUM_SCHEDULE",
        "BAKE_PERIOD", "HOLDBACK_DURATION", "MIGRATION_ARTIFACT_STORAGE",
        "TIER_MIDDLE",
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

def run_claude(prompt: str, model: str, timeout: int) -> str:
    """Invoke `claude` CLI and return stdout."""
    cmd = ["claude", "--print", "--model", model]
    return _run_subprocess(cmd, stdin=prompt, timeout=timeout)


def run_codex(prompt: str, model: str, timeout: int) -> str:
    """Invoke `codex` CLI and return stdout."""
    cmd = ["codex", "--full-auto", "--model", model, "--stdin"]
    return _run_subprocess(cmd, stdin=prompt, timeout=timeout)


def run_cursor(prompt: str, model: str, timeout: int, cursor_python: str) -> str:
    """Invoke Cursor SDK (sync Python API) and return the response text.

    stderr is streamed directly to the terminal so the progress ticker is visible.
    stdout is captured and returned as the JSON result.
    """
    script = f"""
import sys, os, threading, time
try:
    from cursor_sdk import Agent, AgentOptions, LocalAgentOptions
except ImportError:
    sys.exit("cursor_sdk not installed")

# Workaround: cursor-sdk-bridge rejects CLI values starting with '-'.
# secrets.token_urlsafe can produce tokens with a leading '-', causing
# "Missing value for --tool-callback-auth-token". Patch to avoid that.
import cursor_sdk._tool_callback as _tc
_orig_token = _tc._new_auth_token
def _safe_auth_token():
    for _ in range(20):
        t = _orig_token()
        if not t.startswith("-"):
            return t
    return "A" + _orig_token().lstrip("-")
_tc._new_auth_token = _safe_auth_token

options = AgentOptions(
    api_key=os.environ.get("CURSOR_API_KEY", ""),
    model={model!r},
    local=LocalAgentOptions(cwd=os.getcwd()),
)

stop_event = threading.Event()
_elapsed = [0]
def _fmt(s):
    return f"{{s // 60}}m {{s % 60}}s" if s >= 60 else f"{{s}}s"
def _ticker():
    while not stop_event.is_set():
        time.sleep(5)
        _elapsed[0] += 5
        print(f"    ... {{_fmt(_elapsed[0])}} elapsed, waiting for AI response ...", file=sys.stderr, flush=True)
tick = threading.Thread(target=_ticker, daemon=True)
tick.start()

try:
    result = Agent.prompt({json.dumps(prompt)}, options)
finally:
    stop_event.set()
    tick.join(timeout=1)

if result.status == "error":
    print(f"cursor agent run failed: {{result.id}}", file=sys.stderr)
    sys.exit(2)
print(result.result or "", end="")
"""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(script)
        tmp = f.name
    try:
        env = {**os.environ, "CURSOR_API_KEY": os.environ.get("CURSOR_API_KEY", "")}
        proc = subprocess.Popen(
            [cursor_python, tmp],
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
            env=env,
        )
        try:
            stdout, _ = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            raise RuntimeError(f"cursor_sdk timed out after {timeout}s")
        if proc.returncode != 0:
            raise RuntimeError(f"cursor_sdk exited {proc.returncode}")
        return stdout
    finally:
        Path(tmp).unlink(missing_ok=True)


def _run_subprocess(cmd: List[str], stdin: str, timeout: int) -> str:
    result = subprocess.run(
        cmd, input=stdin, capture_output=True, text=True, timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{cmd[0]} exited {result.returncode}: {result.stderr.strip()[:500]}"
        )
    return result.stdout


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
        "confidence": entry.get("confidence", "low")
            if entry.get("confidence") in ("high", "medium", "low") else "low",
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

def invoke_ai(prompt: str, args: argparse.Namespace) -> str:
    tool = args.tool
    model = args.model
    timeout = args.timeout
    retries = args.retries

    last_err: Exception = RuntimeError("no attempts made")
    for attempt in range(1, retries + 1):
        try:
            if tool == "claude":
                return run_claude(prompt, model, timeout)
            elif tool == "codex":
                return run_codex(prompt, model, timeout)
            elif tool == "cursor":
                return run_cursor(prompt, model, timeout, args.cursor_python)
            else:
                raise ValueError(f"Unknown tool: {tool}")
        except Exception as exc:
            last_err = exc
            if attempt < retries:
                wait = 2 ** attempt
                print(f"  [attempt {attempt}/{retries}] Error: {exc}. Retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)
    raise last_err


def run_global_prompt(chunks: List[dict], prompt_template: str, args: argparse.Namespace) -> Dict[str, Any]:
    """Run Prompt A across all ADR chunks and merge results."""
    merged: Dict[str, Any] = {}
    for chunk in chunks:
        label = chunk.get("label", f"CHUNK_{chunk.get('chunk_index', 0)}")
        text = chunk.get("text", "")
        print(f"  [Prompt A] Processing {label} ({len(text)} chars)...", file=sys.stderr)

        prompt = fill_prompt(prompt_template, {
            "ADR_CHUNK_LABEL": label,
            "ADR_CONTENT": text,
        })

        raw = invoke_ai(prompt, args)
        parsed = parse_json_response(raw)

        if parsed is None:
            print(f"  [Prompt A] Warning: could not parse JSON from {label}. Skipping.", file=sys.stderr)
            continue

        normalized = {k: normalize_slot_entry(v, k) for k, v in parsed.items()}
        merged = merge_slots(merged, normalized)

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

    phase_contract_json = json.dumps(
        contract.get("contracts", {}).get(phase, {}), indent=2
    )

    global_phase_slots = {k: global_slots.get(k, {"value": "", "confidence": "low", "evidence_excerpt": "", "evidence_source": "derived_default"})
                          for k in phase_slot_names}

    combined_text = "\n\n".join(c.get("text", "") for c in chunks)
    label = f"ALL_ADR_CHUNKS ({len(combined_text)} chars)"
    print(f"  [Prompt B:{phase}] Refining {len(phase_slot_names)} slots...", file=sys.stderr)

    prompt = fill_prompt(prompt_template, {
        "PHASE": phase,
        "PHASE_CONTRACT": phase_contract_json,
        "PHASE_SLOT_LIST": "\n".join(f"- `{s}`" for s in phase_slot_names),
        "GLOBAL_SLOTS_JSON": json.dumps(global_phase_slots, indent=2),
        "ADR_CHUNK_LABEL": label,
        "ADR_CONTENT": combined_text[:args.phase_max_chars],
    })

    raw = invoke_ai(prompt, args)
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

    prompt = fill_prompt(prompt_template, {
        "VALIDATION_ERRORS_JSON": json.dumps(errors, indent=2),
        "SLOT_JSON_WITH_ERRORS": json.dumps(current_slots, indent=2),
        "ADR_CHUNK_LABEL": "ALL_ADR_CHUNKS",
        "ADR_CONTENT": combined_text[:args.phase_max_chars],
    })

    raw = invoke_ai(prompt, args)
    parsed = parse_json_response(raw)

    if parsed is None:
        print("  [Prompt C] Warning: could not parse repaired JSON.", file=sys.stderr)
        return current_slots

    return {k: normalize_slot_entry(v, k) for k, v in parsed.items()}


def collect_all_placeholders(template_paths: List[Path]) -> List[str]:
    placeholders = set()
    for path in template_paths:
        if path.exists():
            placeholders.update(PLACEHOLDER_RE.findall(path.read_text(encoding="utf-8")))
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
    parser = argparse.ArgumentParser(
        description="AI-first ADR-to-slot extraction (multi-stage pipeline)."
    )
    parser.add_argument("--adr-dir", required=True, help="ADR directory (*.md, excluding templates).")
    parser.add_argument("--project-yaml", required=True, help="project.yaml path.")
    parser.add_argument("--templates", nargs="+", required=True, help="Template phase files.")
    parser.add_argument("--out", required=True, help="Output slots JSON file.")
    parser.add_argument("--run-dir", required=True, help="Run artifact directory (persists raw AI outputs).")
    parser.add_argument("--chunk-manifest", default="", help="Pre-built chunk manifest JSON. Auto-built if not provided.")
    parser.add_argument("--contract", default="", help="Template contract JSON from deterministic cli build-contract.")

    parser.add_argument("--tool", default="cursor", choices=["claude", "codex", "cursor"],
                        help="AI tool to use (default: cursor).")
    parser.add_argument("--model", default="claude-sonnet-4-6", help="Model name (default: claude-sonnet-4-6).")
    parser.add_argument("--cursor-python", default="python3", help="Python executable for cursor SDK.")
    parser.add_argument("--timeout", type=int, default=180, help="Per-call timeout (seconds).")
    parser.add_argument("--retries", type=int, default=3, help="Retry attempts per AI call.")
    parser.add_argument("--max-chars", type=int, default=12000, help="Max chars per ADR chunk.")
    parser.add_argument("--max-chunks", type=int, default=8, help="Max ADR chunks for Prompt A.")
    parser.add_argument("--phase-max-chars", type=int, default=24000,
                        help="Max chars of ADR context fed to Prompt B/C (default: 24000).")
    parser.add_argument("--skip-phase-refine", action="store_true",
                        help="Skip Prompt B per-phase refinement (faster, lower quality).")
    parser.add_argument("--max-repair-rounds", type=int, default=2,
                        help="Maximum Prompt C repair rounds (default: 2).")

    parser.add_argument(
        "--prompt-global", default="",
        help="Path to Prompt A template (default: auto-detected from scripts/ai/deterministic/prompts/).",
    )
    parser.add_argument(
        "--prompt-phase", default="",
        help="Path to Prompt B template.",
    )
    parser.add_argument(
        "--prompt-repair", default="",
        help="Path to Prompt C template.",
    )
    return parser.parse_args()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    # Resolve prompt paths relative to this script's location if not provided.
    script_dir = Path(__file__).parent
    prompts_dir = script_dir / "prompts"

    prompt_global_path = Path(args.prompt_global) if args.prompt_global else prompts_dir / "extract_hld_slots_global.md"
    prompt_phase_path = Path(args.prompt_phase) if args.prompt_phase else prompts_dir / "extract_hld_slots_phase.md"
    prompt_repair_path = Path(args.prompt_repair) if args.prompt_repair else prompts_dir / "extract_hld_slots_repair.md"

    for p in [prompt_global_path, prompt_phase_path, prompt_repair_path]:
        if not p.exists():
            raise SystemExit(f"Prompt file not found: {p}")

    prompt_global = prompt_global_path.read_text(encoding="utf-8")
    prompt_phase = prompt_phase_path.read_text(encoding="utf-8")
    prompt_repair = prompt_repair_path.read_text(encoding="utf-8")

    adr_dir = Path(args.adr_dir)
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    # ── Load or build chunk manifest ─────────────────────────────────────
    if args.chunk_manifest and Path(args.chunk_manifest).exists():
        manifest = json.loads(Path(args.chunk_manifest).read_text(encoding="utf-8"))
        chunks = manifest.get("chunks", [])
        print(f"Loaded chunk manifest: {len(chunks)} chunk(s).", file=sys.stderr)
    else:
        adr_files = load_adr_files(adr_dir)
        if not adr_files:
            raise SystemExit(f"No ADR files found in {adr_dir} (after template filter).")
        chunks = build_chunks(adr_files, args.max_chars, args.max_chunks)
        print(f"Built {len(chunks)} chunk(s) from {len(adr_files)} ADR file(s).", file=sys.stderr)
        manifest = {
            "adr_files": [f.name for f in adr_files],
            "chunk_count": len(chunks),
            "chunks": chunks,
        }
        manifest_path = run_dir / "chunk_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    # ── Load project.yaml client info ────────────────────────────────────
    import yaml
    cfg = yaml.safe_load(Path(args.project_yaml).read_text(encoding="utf-8")) or {}
    client_name = str(cfg.get("client_name", "")).strip()
    project_code = str(cfg.get("project_code", "OCP-V")).strip() or "OCP-V"

    # ── Load template contract ────────────────────────────────────────────
    contract: dict = {}
    if args.contract and Path(args.contract).exists():
        contract = json.loads(Path(args.contract).read_text(encoding="utf-8"))

    # ── Prompt A: Global slot extraction ─────────────────────────────────
    print("=== Stage A: Global slot extraction ===", file=sys.stderr)
    global_slots = run_global_prompt(chunks, prompt_global, args)
    (run_dir / "global_slots_raw.json").write_text(
        json.dumps(global_slots, indent=2) + "\n", encoding="utf-8"
    )

    # Bootstrap identity slots from project.yaml
    for slot, val in [("CLIENT", client_name), ("CLIENT_NAME", client_name), ("PROJECT_CODE", project_code)]:
        if client_name and (slot not in global_slots or not global_slots[slot].get("value")):
            global_slots[slot] = {
                "value": val, "confidence": "high",
                "evidence_excerpt": "", "evidence_source": "project.yaml",
            }

    # ── Prompt B: Per-phase refinement ───────────────────────────────────
    merged_slots = dict(global_slots)
    if not args.skip_phase_refine:
        print("=== Stage B: Per-phase slot refinement ===", file=sys.stderr)
        for phase in ("phase1", "phase2", "phase3", "phase4"):
            phase_updates = run_phase_prompt(phase, merged_slots, contract, chunks, prompt_phase, args)
            merged_slots = merge_slots(merged_slots, phase_updates)
        (run_dir / "merged_slots_after_phase_refine.json").write_text(
            json.dumps(merged_slots, indent=2) + "\n", encoding="utf-8"
        )

    # ── Schema validation + Prompt C repair ──────────────────────────────
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
        repaired = run_repair_prompt(errors, merged_slots, chunks, prompt_repair, args)
        merged_slots = repaired
    else:
        errors = validate_slots_against_schema(merged_slots, schema)
        if errors:
            print(f"  Warning: {len(errors)} schema error(s) remain after max repair rounds.", file=sys.stderr)

    (run_dir / "final_slots_evidence.json").write_text(
        json.dumps(merged_slots, indent=2) + "\n", encoding="utf-8"
    )

    # ── Fill in any remaining template placeholders with {TBD} ───────────
    template_paths = [Path(t) for t in args.templates]
    all_placeholders = collect_all_placeholders(template_paths)
    flat_slots = flatten_for_render(merged_slots)

    for token in all_placeholders:
        if token not in flat_slots or not flat_slots[token]:
            flat_slots[token] = "{TBD}"

    # ── Write final output (compatible with deterministic render) ─────────
    adr_files_used = manifest.get("adr_files", [])
    payload = {
        "extractor": "ai",
        "tool": args.tool,
        "model": args.model,
        "adr_files": adr_files_used,
        "slots": {k: flat_slots[k] for k in sorted(flat_slots)},
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"AI extraction complete: {len(flat_slots)} slots → {out_path}", file=sys.stderr)


def validate_slots_against_schema(slots: Dict[str, Any], schema: dict) -> List[dict]:
    """Basic schema validation returning list of error dicts."""
    errors: List[dict] = []
    valid_confidences = {"high", "medium", "low"}
    schema_slots = schema.get("slots", {})

    for slot_name, entry in slots.items():
        if slot_name not in schema_slots:
            errors.append({"type": "unknown_key", "slot": slot_name,
                           "message": f"Slot '{slot_name}' not in schema."})
            continue
        if not isinstance(entry, dict):
            errors.append({"type": "missing_evidence_field", "slot": slot_name,
                           "message": "Slot entry must be a dict with value/confidence/evidence_excerpt/evidence_source."})
            continue
        for field in ("value", "confidence", "evidence_excerpt", "evidence_source"):
            if field not in entry:
                errors.append({"type": "missing_evidence_field", "slot": slot_name,
                               "message": f"Missing required field '{field}'."})
        if "confidence" in entry and entry["confidence"] not in valid_confidences:
            errors.append({"type": "invalid_confidence", "slot": slot_name,
                           "message": f"Invalid confidence '{entry['confidence']}'. Must be high/medium/low."})
        if "value" in entry and not isinstance(entry["value"], str):
            errors.append({"type": "invalid_value_format", "slot": slot_name,
                           "message": "Value must be a string."})

    return errors


def validate_slot_file(slots_file: Path, phases: List[str], schema_file: Path | None = None) -> int:
    schema_path = schema_file or (Path(__file__).parent / "slot_schema.json")
    payload = json.loads(slots_file.read_text(encoding="utf-8"))
    raw_slots = payload.get("slots", payload)
    schema = json.loads(schema_path.read_text(encoding="utf-8")) if schema_path.exists() else {"slots": {}}
    is_flat = bool(raw_slots) and all(not isinstance(v, dict) for v in raw_slots.values())

    if is_flat:
        slots = {k: str(v).strip() if v is not None else "" for k, v in raw_slots.items()}
        errors: List[dict] = []
        warnings: List[str] = []
    else:
        slots = raw_slots
        errors = validate_slots_against_schema(slots, schema)
        warnings = []

    required_map = schema.get("required_slots_for_phase", {})
    for phase in phases:
        for slot_name in required_map.get(phase, []):
            if slot_name not in slots:
                errors.append(
                    {
                        "type": "missing_required_slot",
                        "slot": slot_name,
                        "message": f"Required slot '{slot_name}' missing for {phase}.",
                    }
                )
            elif is_flat and str(slots.get(slot_name, "")).strip() in ("", "{TBD}"):
                warnings.append(f"Required slot '{slot_name}' unresolved for {phase}.")

    if errors:
        for e in errors:
            print(f"ERROR: {e['message']}", file=sys.stderr)
        return 1
    for w in warnings:
        print(f"WARN: {w}", file=sys.stderr)
    print("Schema validation: PASS", file=sys.stderr)
    return 0


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
