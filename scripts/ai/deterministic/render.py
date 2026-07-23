#!/usr/bin/env python3
"""Validate deterministic HLD outputs for structure, citations, and byte stability."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from markdown_utils import (
    PLACEHOLDER_RE,
    load_json,
    parse_headings_and_tables,
    parse_section_citations,
    render_contract_text as shared_render_contract_text,
    sha256_text,
)


def phase_id_from_filename(path: Path) -> str:
    match = re.search(r"(phase[1-4])", path.name, flags=re.IGNORECASE)
    if not match:
        raise ValueError(f"Unable to infer phase id from template filename: {path}")
    return match.group(1).lower()


def parse_markdown_contract(text: str) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    parsed_headings, parsed_tables = parse_headings_and_tables(text)
    headings: List[Dict[str, object]] = [{"level": level, "title": title} for level, title in parsed_headings]
    tables: List[Dict[str, object]] = []
    for heading_path, header, row_count in parsed_tables:
        tables.append(
            {
                "heading_path": heading_path.split(" > ") if heading_path else [],
                "header": header,
                "row_count": row_count,
            }
        )
    return headings, tables


def build_contract(template_paths: List[Path], out: Path) -> None:
    docs: Dict[str, object] = {}
    for template_path in sorted(template_paths, key=lambda p: p.name):
        text = template_path.read_text(encoding="utf-8")
        phase_id = phase_id_from_filename(template_path)
        headings, tables = parse_markdown_contract(text)
        docs[phase_id] = {
            "template_file": str(template_path),
            "template_sha256": sha256_text(text),
            "headings": headings,
            "tables": tables,
        }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"contracts": docs}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_citation_lock(canonical_paths: List[Path], out: Path) -> None:
    documents: Dict[str, object] = {}
    for canonical_path in sorted(canonical_paths, key=lambda p: p.name):
        text = canonical_path.read_text(encoding="utf-8")
        documents[canonical_path.name] = {
            "file": str(canonical_path),
            "sha256": sha256_text(text),
            "section_citations": parse_section_citations(text),
            "full_text": text if text.endswith("\n") else text + "\n",
        }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"documents": documents}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_phase(template_path: Path, slots_path: Path, out_path: Path) -> None:
    template_text = template_path.read_text(encoding="utf-8")
    slot_payload = load_json(slots_path)
    slot_map = slot_payload.get("slots", {})

    def replace_placeholder(match: re.Match[str]) -> str:
        token = match.group(1)
        raw = slot_map.get(token, "")
        if isinstance(raw, dict):
            value = str(raw.get("value", "")).strip()
        else:
            value = str(raw).strip()
        return value if value else "{TBD}"

    placeholder_token_re = re.compile(r"\{([A-Z0-9_]+)\}")
    escaped_placeholder_token_re = re.compile(r"\\\{([A-Z0-9_]+)\\\}")
    rendered = placeholder_token_re.sub(replace_placeholder, template_text)
    rendered = escaped_placeholder_token_re.sub(replace_placeholder, rendered)
    if not rendered.endswith("\n"):
        rendered += "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered, encoding="utf-8")


def stitch_deterministic(draft_dir: Path, output_path: Path, expect_byte_equal_to: str = "") -> None:
    phase_files = [draft_dir / f"draft_hld_phase{n}.md" for n in (1, 2, 3, 4)]
    missing = [str(p) for p in phase_files if not p.exists()]
    if missing:
        raise SystemExit(f"Missing deterministic phase files: {', '.join(missing)}")

    pieces = []
    for phase_file in phase_files:
        text = phase_file.read_text(encoding="utf-8")
        pieces.append(text.rstrip("\n"))
    combined = "\n\n".join(pieces) + "\n"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(combined, encoding="utf-8")

    if expect_byte_equal_to:
        expected_path = Path(expect_byte_equal_to)
        if expected_path.exists() and output_path.read_bytes() != expected_path.read_bytes():
            raise SystemExit(
                f"Deterministic combined output does not match expected canonical file: {expected_path}"
            )

def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="Rendered markdown output to validate.")
    parser.add_argument("--contract", required=True, help="Template contract JSON path.")
    parser.add_argument("--slots", default="", help="Optional slot map JSON path.")
    parser.add_argument("--citation-lock", default="", help="Optional citation lock JSON path.")
    parser.add_argument("--document-key", required=True, help="Document key in citation lock.")
    parser.add_argument("--state-file", required=True, help="State JSON for hash stability checks.")
    parser.add_argument("--phase", default="", help="phase1..phase4 for phase contract checks.")
    parser.add_argument("--expect-byte-equal-to", default="", help="Optional file path for strict byte equality.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    target_path = Path(args.file)
    target_text = target_path.read_text(encoding="utf-8")
    target_bytes = target_path.read_bytes()

    matched_expected_bytes = False
    if args.expect_byte_equal_to:
        expected_path = Path(args.expect_byte_equal_to)
        if expected_path.exists():
            expected_bytes = expected_path.read_bytes()
            if target_bytes != expected_bytes:
                fail(f"Byte mismatch against expected file: {expected_path}")
            matched_expected_bytes = True

    if not matched_expected_bytes:
        unresolved = [p for p in PLACEHOLDER_RE.findall(target_text) if p != "{TBD}"]
        if unresolved:
            fail(f"Unresolved placeholders remain in {target_path.name}: {sorted(set(unresolved))}")

    contract_payload = load_json(Path(args.contract))
    slot_map = {}
    if args.slots:
        slot_map = load_json(Path(args.slots)).get("slots", {})
    lock_payload = {}
    if args.citation_lock:
        lock_payload = load_json(Path(args.citation_lock))

    def render_contract_text(value: str) -> str:
        return shared_render_contract_text(value, slot_map)

    if args.phase and not matched_expected_bytes:
        expected = contract_payload.get("contracts", {}).get(args.phase)
        if not expected:
            fail(f"Missing contract for phase '{args.phase}'.")

        got_headings, got_tables = parse_headings_and_tables(target_text)
        expected_headings = [(h["level"], render_contract_text(h["title"])) for h in expected.get("headings", [])]
        expected_tables = [
            (
                render_contract_text(" > ".join(t["heading_path"])),
                render_contract_text(t["header"].strip()),
                int(t["row_count"]),
            )
            for t in expected.get("tables", [])
        ]

        if got_headings != expected_headings:
            fail(f"Heading contract mismatch for {args.phase}.")
        if got_tables != expected_tables:
            fail(f"Table contract mismatch for {args.phase}.")

    if lock_payload:
        doc_lock = lock_payload.get("documents", {}).get(args.document_key, {})
        expected_citations = doc_lock.get("section_citations", {})
        got_citations = parse_section_citations(target_text)
        if not matched_expected_bytes:
            for section_path, citations in expected_citations.items():
                if got_citations.get(section_path, []) != citations:
                    fail(f"Citation mismatch at section '{section_path}' in {args.document_key}.")

    state_path = Path(args.state_file)
    state: Dict[str, str] = {}
    if state_path.exists():
        state = load_json(state_path)
    current_hash = sha256_text(target_text)
    prior_hash = state.get(args.document_key, "")
    if prior_hash and prior_hash != current_hash:
        fail(f"Determinism drift for {args.document_key}: prior hash != current hash.")
    state[args.document_key] = current_hash
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_validate_hld(argv: List[str] | None = None) -> int:
    old_argv = sys.argv[:]
    try:
        sys.argv = [old_argv[0]] + (argv or [])
        main()
        return 0
    finally:
        sys.argv = old_argv


if __name__ == "__main__":
    main()
