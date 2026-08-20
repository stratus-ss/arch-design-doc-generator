#!/usr/bin/env python3
"""hc_investigate.py — trace a report finding/check back to raw evidence.

Re-derives the same in-memory model the report generator uses (load_results ->
evaluate_checks -> derive_findings) fresh from --results-dir, resolves a
CheckResult from --finding-id / --check-id / --query, locates the raw JSON
file(s) that produced it via a 3-tier lookup, and pretty-prints the evidence.
Read-only: never writes to --results-dir.

Usage:
    python3 scripts/health_check/hc_investigate.py --results-dir output/hc_collect/2026-07-28 \
        --finding-id 6.2.3.1
    python3 scripts/health_check/hc_investigate.py --results-dir output/hc_collect/2026-07-28 \
        --query "Available Updates"
    python3 scripts/health_check/hc_investigate.py --results-dir output/hc_collect/2026-07-28 \
        --check-id 7.1.identity.updates
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from config import find_project_yaml, get_health_check_config, load_config
from hc_report.cli import (
    _discover_tsr_html_if_needed,
    _parse_tsr_html_runtime,
    _resolve_check_expansion_options,
    _resolve_tsr_html_path,
)
from hc_report.evaluators import evaluate_checks
from hc_report.evaluators._common import _CATEGORY_MAP, _resource_metadata
from hc_report.findings import derive_findings
from hc_report.loader import load_results
from hc_report.metadata import derive_metadata
from hc_report.models import CheckResult, Finding

_REVERSE_CATEGORY_MAP = {
    category_id: category_key
    for category_key, (category_id, _) in _CATEGORY_MAP.items()
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Trace a health-check report finding/check back to raw JSON evidence."
    )
    parser.add_argument("--config", type=Path, default=None,
                        help="Optional path to project.yaml (default: auto-detect)")
    parser.add_argument("--results-dir", type=Path, required=True,
                        help="Collection results directory (e.g. output/hc_collect/<date>)")
    parser.add_argument(
        "--check-profile",
        default=None,
        choices=["core", "extended", "advisory"],
        help="Check expansion profile: core, extended, or advisory.",
    )
    parser.add_argument(
        "--ccx-baseline-status",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Use catalog baseline status hints when live CCX data is unavailable.",
    )
    parser.add_argument(
        "--catalog-path",
        type=Path,
        default=None,
        help="Optional path to TSR/CCX crosswalk catalog JSON.",
    )
    parser.add_argument(
        "--tsr-html",
        type=Path,
        default=None,
        help="Optional path to TSR HTML export for runtime parity scoring.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--finding-id", help="Finding id as shown in the report, e.g. 6.2.3.1")
    group.add_argument("--query", help="Substring to match against check/finding description text")
    group.add_argument("--check-id", help="Internal check id, e.g. 7.1.identity.updates")
    return parser.parse_args()


def _find_check_by_id(checks: list[CheckResult], check_id: str) -> CheckResult | None:
    for check in checks:
        if check.check_id == check_id:
            return check
    return None


def _find_finding_by_id(findings: list[Finding], finding_id: str) -> Finding | None:
    for finding in findings:
        if finding.id == finding_id:
            return finding
    return None


def resolve_check(checks: list[CheckResult], findings: list[Finding], args: argparse.Namespace) -> CheckResult:
    if args.check_id:
        check = _find_check_by_id(checks, args.check_id)
        if check is None:
            print(f"Error: no check found with check_id '{args.check_id}'", file=sys.stderr)
            sys.exit(1)
        return check

    if args.finding_id:
        finding = _find_finding_by_id(findings, args.finding_id)
        if finding is None:
            print(f"Error: no finding found with id '{args.finding_id}'", file=sys.stderr)
            sys.exit(1)
        check = _find_check_by_id(checks, finding.check_id)
        if check is None:
            print(f"Error: finding '{args.finding_id}' references check_id "
                  f"'{finding.check_id}', which no longer exists among evaluated checks",
                  file=sys.stderr)
            sys.exit(1)
        return check

    query_lower = args.query.lower()
    matches = []
    for check in checks:
        if query_lower in check.description.lower():
            matches.append(check)
    if not matches:
        print(f"No check found matching query '{args.query}'", file=sys.stderr)
        sys.exit(1)
    if len(matches) > 1:
        print(f"Ambiguous query '{args.query}' — {len(matches)} matches. "
              "Narrow with --check-id:", file=sys.stderr)
        for check in matches:
            print(f"  {check.check_id:35s} [{check.status:15s}] {check.description}", file=sys.stderr)
        sys.exit(1)
    return matches[0]


def locate_evidence(check: CheckResult, results_dir: Path) -> list[Path]:
    """3-tier raw evidence lookup: direct filename -> topic glob -> literal grep."""
    category_key = _REVERSE_CATEGORY_MAP.get(check.category_id)
    if category_key is None:
        return []
    category_dir = results_dir / category_key
    if not category_dir.is_dir():
        return []

    if check.resource_name:
        direct = category_dir / f"{check.resource_name}.json"
        if direct.exists():
            return [direct]

    id_parts = check.check_id.split(".")
    if len(id_parts) >= 2:
        topic = id_parts[1]
        glob_matches = []
        for json_path in sorted(category_dir.glob(f"{topic}*.json")):
            if not json_path.name.endswith(".meta.json"):
                glob_matches.append(json_path)
        if glob_matches:
            return glob_matches

    if check.resource_name:
        needle = f'"{check.resource_name}"'
        grep_matches = []
        for json_path in sorted(category_dir.glob("*.json")):
            if json_path.name.endswith(".meta.json"):
                continue
            if needle in json_path.read_text(encoding="utf-8"):
                grep_matches.append(json_path)
        if grep_matches:
            return grep_matches

    return []


def load_command_metadata(files: list[Path]) -> list[dict]:
    """Load command metadata sidecars (`<name>.meta.json`) for evidence files."""
    metadata: list[dict] = []
    for evidence_file in files:
        meta_file = evidence_file.with_suffix(".meta.json")
        if not meta_file.exists():
            continue
        try:
            data = json.loads(meta_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        data["evidence_file"] = str(evidence_file)
        metadata.append(data)
    return metadata


def _extract_item(data: dict, resource_name: str) -> tuple[dict, str]:
    """For a K8s List, return the item matching resource_name (or the first item)."""
    if isinstance(data, dict) and "items" in data:
        items = data.get("items", [])
        for item in items:
            if _resource_metadata(item).get("name") == resource_name:
                return item, ""
        if items:
            return items[0], f"(no item named '{resource_name}' — showing first of {len(items)} items)"
        return data, ""
    return data, ""


def print_evidence(check: CheckResult, files: list[Path]) -> None:
    print(f"Check      : {check.check_id}")
    print(f"Description: {check.description}")
    print(f"Status     : {check.status}")
    print(f"Evidence   : {check.evidence}")
    print()

    metadata = load_command_metadata(files)
    if metadata:
        print("Collection Command(s):")
        for entry in metadata:
            script = str(entry.get("script", "")).strip() or "unknown"
            chapter = str(entry.get("chapter", "")).strip()
            command = str(entry.get("command", "")).strip() or "unknown"
            timestamp = str(entry.get("timestamp", "")).strip()
            script_label = f"{script} (Chapter {chapter})" if chapter and chapter != "unknown" else script
            print(f"  Script : {script_label}")
            print(f"  Command: {command}")
            if timestamp:
                print(f"  Time   : {timestamp}")
            print(f"  Source : {entry.get('evidence_file', 'unknown')}")
            print()
    elif files:
        print("Collection Command(s):")
        print("  (no command metadata available — re-run collection to populate)")
        print()

    if not files:
        print("No raw evidence file located (tiers 1-3 all missed). "
              "This check may be derived from multiple files or synthesized data.")
        return

    for evidence_file in files:
        print(f"Evidence file: {evidence_file}")
        try:
            data = json.loads(evidence_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print("  (file is not valid JSON)")
            continue
        item, note = _extract_item(data, check.resource_name)
        if note:
            print(f"  {note}")
        print(json.dumps(item, indent=2, ensure_ascii=False))
        print()


def print_skip_ledger_matches(check: CheckResult, results_dir: Path) -> None:
    ledger = results_dir / "skipped_commands.jsonl"
    if not ledger.exists():
        return

    check_name = check.check_id.split(".")[-1]
    matches = []
    for line in ledger.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("check_name") == check_name:
            matches.append(entry)

    if matches:
        print(f"Skip ledger matches (check_name='{check_name}'):")
        for entry in matches:
            print(f"  {json.dumps(entry, ensure_ascii=False)}")


def _default_output_dir(results_dir: Path) -> Path:
    return results_dir.parent.parent / "Health_Check_Report"


def _resolve_runtime_options(
    args: argparse.Namespace, results: dict
) -> tuple[Path, Path | None, str]:
    try:
        config_path = args.config or find_project_yaml(args.results_dir)
    except FileNotFoundError:
        args.check_profile = str(args.check_profile or "advisory").lower()
        if args.ccx_baseline_status is None:
            args.ccx_baseline_status = False
        if args.tsr_html and not args.tsr_html.exists():
            print(f"Error: TSR HTML not found at {args.tsr_html}", file=sys.stderr)
            sys.exit(1)
        return (
            _default_output_dir(args.results_dir),
            _parse_tsr_html_runtime(args, _default_output_dir(args.results_dir)),
            "",
        )

    project_root = config_path.parent
    config = load_config(config_path)
    hc_config = get_health_check_config(config)
    _resolve_check_expansion_options(args, hc_config, project_root)
    _resolve_tsr_html_path(args, hc_config, project_root)
    meta = derive_metadata(results, config)
    _discover_tsr_html_if_needed(args, project_root, hc_config, results, meta)
    output_dir = project_root / hc_config.get("output_report_path", "output/Health_Check_Report/")
    return output_dir, _parse_tsr_html_runtime(args, output_dir), str(meta.get("ocp_version", ""))


def _load_checks_and_findings(
    args: argparse.Namespace,
) -> tuple[list[CheckResult], list[Finding]]:
    print(f"Loading results from: {args.results_dir}")
    results = load_results(args.results_dir)
    _output_dir, tsr_runtime_path, ocp_version = _resolve_runtime_options(args, results)
    checks = evaluate_checks(
        results,
        check_profile=str(args.check_profile or "advisory").lower(),
        use_ccx_baseline_status=bool(args.ccx_baseline_status),
        catalog_path=args.catalog_path,
        tsr_runtime_path=tsr_runtime_path,
    )
    findings = derive_findings(checks, ocp_version=ocp_version)
    return checks, findings


def main() -> None:
    args = parse_args()

    if not args.results_dir.is_dir():
        print(f"Error: results directory not found at {args.results_dir}", file=sys.stderr)
        sys.exit(2)

    checks, findings = _load_checks_and_findings(args)

    check = resolve_check(checks, findings, args)
    files = locate_evidence(check, args.results_dir)

    print()
    print_evidence(check, files)
    print_skip_ledger_matches(check, args.results_dir)


if __name__ == "__main__":
    main()
