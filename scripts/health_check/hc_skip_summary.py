#!/usr/bin/env python3
"""hc_skip_summary.py — render skipped_commands.jsonl into a readable YAML summary.

Groups the debug ledger produced by the supportshell collection path as
    <short_must_gather_name>:
      <category>:
        <check_name>: <command>

using scripts/health_check/mg_short_names.yaml to turn a full must-gather
image/digest string into a short, recognizable label (e.g. "cnv", "ocp").

Usage:
    python3 scripts/health_check/hc_skip_summary.py \
        --ledger output/hc_collect/2026-07-28/skipped_commands.jsonl \
        [--output <path>] [--errors-only] [--mg-map <path>]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

_DEFAULT_MAP = Path(__file__).parent / "mg_short_names.yaml"
_SHA_RE = re.compile(r"-sha256-[0-9a-f]{10,}$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render skipped_commands.jsonl into a readable YAML summary."
    )
    parser.add_argument("--ledger", type=Path, required=True,
                        help="Path to skipped_commands.jsonl")
    parser.add_argument("--output", type=Path, default=None,
                        help="Output YAML path (default: alongside --ledger)")
    parser.add_argument("--errors-only", action="store_true",
                        help="Only include outcome == 'error' entries")
    parser.add_argument("--mg-map", type=Path, default=_DEFAULT_MAP,
                        help="Path to the must-gather short-name pattern table")
    return parser.parse_args()


def load_mg_map(path: Path) -> dict:
    if not path.exists():
        print(f"Error: mg-map not found at {path}", file=sys.stderr)
        sys.exit(2)
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _strip_known_prefix(value: str, prefixes: list[str]) -> str:
    for prefix in prefixes:
        if value.startswith(prefix):
            return value[len(prefix):]
    return value


def _strip_known_suffix(value: str, suffixes: list[str]) -> str:
    for suffix in suffixes:
        if value.endswith(suffix):
            return value[: -len(suffix)]
    return value


def resolve_short_name(mg_source: str, mg_map: dict, mg_map_path: Path) -> str:
    """Resolve a full must-gather image/digest string to a short label.

    First tries a substring match against mg_map["patterns"] (first match
    wins). Falls back to stripping the sha256 digest suffix, a known
    registry prefix, and a known trailing suffix, then keeping the last two
    dash-separated segments — printing a WARN so the pattern table can be
    extended.
    """
    lowered = mg_source.lower()
    for label, keywords in (mg_map.get("patterns") or {}).items():
        matched = False
        for keyword in keywords:
            if keyword.lower() in lowered:
                matched = True
                break
        if matched:
            return label

    stripped = _SHA_RE.sub("", mg_source)
    stripped = _strip_known_prefix(stripped, mg_map.get("registry_prefixes") or [])
    stripped = _strip_known_suffix(stripped, mg_map.get("strip_suffixes") or [])
    segments = []
    for segment in stripped.split("-"):
        if segment:
            segments.append(segment)
    short = "-".join(segments[-2:]) if segments else stripped

    print(
        f"WARN: no pattern matched for '{mg_source}' — falling back to '{short}'. "
        f"Consider adding it to {mg_map_path}.",
        file=sys.stderr,
    )
    return short


def build_summary(ledger_path: Path, mg_map: dict, mg_map_path: Path, errors_only: bool) -> dict:
    summary: dict = {}
    short_name_cache: dict[str, str] = {}

    with ledger_path.open(encoding="utf-8") as ledger_file:
        for line_number, raw_line in enumerate(ledger_file, start=1):
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                entry = json.loads(raw_line)
            except json.JSONDecodeError:
                print(f"WARN: skipping malformed JSON on line {line_number} of {ledger_path}",
                      file=sys.stderr)
                continue

            if errors_only and entry.get("outcome") != "error":
                continue

            mg_source = entry.get("mg_source", "unknown")
            if mg_source not in short_name_cache:
                short_name_cache[mg_source] = resolve_short_name(mg_source, mg_map, mg_map_path)
            short_name = short_name_cache[mg_source]

            category = entry.get("category", "unknown")
            check_name = entry.get("check_name", "unknown")
            command = entry.get("command", "")

            summary.setdefault(short_name, {}).setdefault(category, {})[check_name] = command

    return summary


def main() -> None:
    args = parse_args()

    if not args.ledger.exists():
        print(f"Error: ledger not found at {args.ledger}", file=sys.stderr)
        sys.exit(2)

    mg_map = load_mg_map(args.mg_map)
    summary = build_summary(args.ledger, mg_map, args.mg_map, args.errors_only)

    rendered = yaml.safe_dump(summary, sort_keys=False, default_flow_style=False, allow_unicode=True)

    output_path = args.output or args.ledger.with_name("skipped_commands_summary.yaml")
    output_path.write_text(rendered, encoding="utf-8")

    print(rendered)
    print(f"Summary written to: {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
