"""CLI argument parsing and entry point logic for the HC report generator."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

import yaml
from config import find_project_yaml, get_health_check_config, load_config

from hc_report.evaluators import evaluate_checks
from hc_report.findings import derive_findings_with_tsr
from hc_report.loader import load_results, resolve_cluster_targets
from hc_report.metadata import derive_metadata
from hc_report.omit_findings import (
    apply_finding_omit,
    compact_finding_ids,
    load_omit_check_ids,
    pruned_report_path,
)
from hc_report.parity import discover_tsr_html
from hc_report.renderer import find_unfilled_slots, render_report
from hc_report.tsr_parser import parse_tsr_html

_OCP_MINOR_RE = re.compile(r"^(\d+\.\d+)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate branded HC report from collected cluster data."
    )
    parser.add_argument("--results-dir", type=Path, default=None,
                        help="Path to collection results directory (from hc_collect.sh)")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Output directory for rendered report")
    parser.add_argument("--config", type=Path, default=None,
                        help="Path to project.yaml (default: auto-detect)")
    parser.add_argument("--template", type=Path, default=None,
                        help="Path to report template markdown")
    parser.add_argument("--exec-summary", type=str, default=None,
                        help="Executive summary text (overrides the generated summary)")
    parser.add_argument(
        "--check-profile",
        default=None,
        choices=["core", "extended", "advisory"],
        help="Check expansion profile: core (legacy), extended (core+TSR), advisory (extended+CCX).",
    )
    parser.add_argument(
        "--ccx-baseline-status",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Use baseline status hints from the TSR/CCX catalog when live CCX payload is unavailable.",
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
        help="Path to TSR HTML export for runtime parity scoring (replaces placeholder statuses).",
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Use placeholder executive summary (edit before delivery)")
    parser.add_argument(
        "--omit-check-ids",
        type=Path,
        default=None,
        help="Path to a check-ID list; write {stem}_pruned.md with those Chapter 6 findings removed",
    )
    parser.add_argument(
        "--omit-strict",
        action="store_true",
        help="Exit 1 if any omit check ID is not present on a derived finding",
    )
    return parser.parse_args()


def _extract_minor_version(full_version: str) -> str:
    match = _OCP_MINOR_RE.match(str(full_version).strip())
    if match:
        return match.group(1)
    return "latest"


def _load_config_paths(
    args: argparse.Namespace, project_root: Path
) -> tuple[dict, Path, Path, Path]:
    config_path = args.config or project_root / "project.yaml"
    config = load_config(config_path) if config_path.exists() else {}
    hc_config = get_health_check_config(config)
    results_dir = args.results_dir or project_root / hc_config.get(
        "output_collect_path", "output/hc_collect/"
    )
    output_dir = args.output_dir or project_root / hc_config.get(
        "output_report_path", "output/Health_Check_Report/"
    )
    template_path = args.template or project_root / "templates/Health_Check/Template_HC_Report.md"
    return config, results_dir, output_dir, template_path


def _resolve_tsr_html_dir(project_root: Path, hc_config: dict) -> Path:
    raw_dir = os.environ.get("HC_TSR_HTML_DIR") or hc_config.get("tsr_html_dir") or "output/tsr_html"
    path = Path(str(raw_dir))
    return path if path.is_absolute() else project_root / path


def _default_exec_summary(meta: dict, checks: list, pcount: Counter) -> str:
    return (
        f"Cluster **{meta['cluster_name']}** running OpenShift {meta['ocp_version']} on channel "
        f"{meta['channel']} was assessed on {meta['capture_date']}. "
        f"{len(checks)} checks were performed across 9 assessment categories. "
        f"The assessment identified {pcount.get('P0', 0)} critical (P0), "
        f"{pcount.get('P1', 0)} high (P1), {pcount.get('P2', 0)} medium (P2), "
        f"and {pcount.get('P3', 0)} low (P3) findings.\n\n"
        "**Note for consultant:** Replace this paragraph with a narrative executive summary "
        "before delivering to the customer. Pass --exec-summary on the command line."
    )


def _classify_cluster_health(pcount: Counter) -> str:
    if pcount.get("P0", 0) > 0:
        return "Critical and at risk"
    if pcount.get("P1", 0) > 0:
        return "Degraded and at risk"
    if pcount.get("P2", 0) > 0:
        return "Needs attention"
    return "Stable"


def _default_findings_narrative(meta: dict, checks: list, pcount: Counter) -> str:
    health_state = _classify_cluster_health(pcount)
    return (
        f"The overall health of cluster **{meta['cluster_name']}** is assessed as **{health_state}** "
        f"based on data captured on {meta['capture_date']}. "
        f"{len(checks)} checks were evaluated, resulting in {pcount.get('P0', 0)} P0, "
        f"{pcount.get('P1', 0)} P1, {pcount.get('P2', 0)} P2, and {pcount.get('P3', 0)} P3 findings.\n\n"
        "Priority should focus on resolving P0 and P1 findings first, then addressing recurring P2 "
        "conditions that could degrade stability over time."
    )


def _resolve_mg_label(mg_source: str, patterns: dict) -> str:
    lowered = mg_source.lower()
    for label, keywords in patterns.items():
        for keyword in keywords:
            if keyword.lower() in lowered:
                return label
    return "unknown"


def _load_mg_reference(project_root: Path) -> tuple[list[dict], dict]:
    mg_cfg_path = project_root / "scripts" / "health_check" / "mg_short_names.yaml"
    if not mg_cfg_path.exists():
        return [], {}
    try:
        data = yaml.safe_load(mg_cfg_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return [], {}
    standard = data.get("standard_must_gathers", [])
    patterns = data.get("patterns", {})
    if not isinstance(standard, list):
        standard = []
    if not isinstance(patterns, dict):
        patterns = {}
    return standard, patterns


def _collect_mg_labels(results_dir: Path, patterns: dict) -> set[str]:
    labels: set[str] = set()
    ledger_path = results_dir / "skipped_commands.jsonl"
    if not ledger_path.exists():
        return labels

    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        mg_source = str(entry.get("mg_source", "")).strip()
        if not mg_source:
            continue
        label = _resolve_mg_label(mg_source, patterns)
        if label != "unknown":
            labels.add(label)
    return labels


def _build_data_collection_method(project_root: Path, results_dir: Path, manifest: dict) -> str:
    standard_must_gathers, patterns = _load_mg_reference(project_root)
    timestamp = manifest.get("timestamp", "unknown")
    cluster_api = manifest.get("cluster_server", "unknown")

    if not standard_must_gathers:
        return (
            "Data was collected using the `hc_collect.sh` automation scripts from the "
            "`arch-design-doc-generator` toolkit. All checks use read-only CLI commands.\n\n"
            f"Collection timestamp: {timestamp}\n"
            f"Cluster API: {cluster_api}"
        )

    collected_labels = _collect_mg_labels(results_dir, patterns)
    supportshell_mode = bool((results_dir / "skipped_commands.jsonl").exists() or manifest.get("merged"))
    lines = [
        "| Must Gather Image | Status | Reason |",
        "|-------------------|--------|--------|",
    ]

    for item in standard_must_gathers:
        label = str(item.get("label", "")).strip()
        image = str(item.get("image", "")).strip()
        requirement = str(item.get("requirement", "optional")).strip().lower()
        if not label or not image:
            continue

        if label in collected_labels:
            status = "🟢 PASS"
            if requirement == "mandatory":
                reason = "is mandatory and is available"
            elif requirement == "required":
                reason = "is required and is available"
            else:
                reason = "is optional and is available"
        else:
            if requirement == "mandatory" and supportshell_mode:
                status = "🔴 FAIL"
                reason = "is mandatory but was not found"
            else:
                status = "⚪ NOT APPLICABLE"
                reason = "is not needed and is not available"
        lines.append(f"| {image} | {status} | {reason} |")

    lines.extend([
        "",
        f"Collection timestamp: {timestamp}",
        f"Cluster API: {cluster_api}",
    ])
    if not supportshell_mode:
        lines.extend([
            "",
            "_Note: Must-gather availability is primarily for supportshell collections. "
            "This run appears to use the live-cluster collection path._",
        ])
    return "\n".join(lines)


def _make_findings_narrative(
    args: argparse.Namespace, meta: dict, checks: list, findings: list, pcount: Counter
) -> str:
    return _default_findings_narrative(meta, checks, pcount)


def _make_exec_summary(
    args: argparse.Namespace, meta: dict, checks: list, findings: list, pcount: Counter
) -> str:
    if args.exec_summary:
        return args.exec_summary
    return _default_exec_summary(meta, checks, pcount)


def _write_outputs(
    output_dir: Path, rendered: str, meta: dict,
    checks: list, findings: list, pcount: Counter,
    check_profile: str,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    cluster_safe = meta["cluster_name"].replace(" ", "_").replace("/", "_")
    client_prefix = meta["client_prefix"]
    output_file = output_dir / f"{client_prefix}_OpenShift_Health_Check_{cluster_safe}.md"
    output_file.write_text(rendered, encoding="utf-8")

    audit_file = output_dir / f"{client_prefix}_HC_audit_{cluster_safe}.json"
    audit_file.write_text(json.dumps({
        "metadata": meta,
        "check_profile": check_profile,
        "check_summary": dict(Counter(check.status for check in checks)),
        "finding_summary": dict(pcount),
        "checks": [
            {"id": check.check_id, "desc": check.description, "status": check.status,
             "evidence": check.evidence, "resource_name": check.resource_name,
             "source": check.source, "tsr_ref": check.tsr_ref, "tags": check.tags,
             "doc_ref": check.doc_ref, "scoring_basis": check.scoring_basis}
            for check in checks
        ],
        "findings": [
            {"id": finding.id, "title": finding.title, "priority": finding.priority,
             "description": finding.description, "recommendation": finding.recommendation,
             "check_id": finding.check_id}
            for finding in findings
        ],
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    return output_file


def _resolve_check_expansion_options(
    args: argparse.Namespace, hc_config: dict, project_root: Path
) -> None:
    """Resolve --check-profile / --ccx-baseline-status / --catalog-path from CLI > config > env."""
    args.check_profile = str(
        args.check_profile
        or hc_config.get("check_profile")
        or os.environ.get("HC_CHECK_PROFILE", "advisory")
    ).lower()
    if args.ccx_baseline_status is None:
        args.ccx_baseline_status = bool(hc_config.get("ccx_baseline_status", False))
    if args.catalog_path is None and hc_config.get("tsr_ccx_catalog_path"):
        args.catalog_path = project_root / str(hc_config["tsr_ccx_catalog_path"])


def _resolve_tsr_html_path(
    args: argparse.Namespace, hc_config: dict, project_root: Path
) -> None:
    """Resolve --tsr-html from CLI > env var > config > None; hard-exit if given path is missing."""
    if args.tsr_html is None:
        env_tsr = os.environ.get("HC_TSR_HTML")
        if env_tsr:
            args.tsr_html = Path(env_tsr)
        elif hc_config.get("tsr_html_path"):
            args.tsr_html = project_root / str(hc_config["tsr_html_path"])
    if args.tsr_html and not args.tsr_html.exists():
        print(f"Error: TSR HTML not found at {args.tsr_html}", file=sys.stderr)
        sys.exit(1)


def _discover_tsr_html_if_needed(
    args: argparse.Namespace, project_root: Path, hc_config: dict, meta: dict
) -> None:
    """Auto-discover a matching TSR HTML export when none was resolved explicitly."""
    if args.tsr_html is not None:
        return
    cluster_id = str(meta.get("cluster_id") or "").strip()
    tsr_html_dir = _resolve_tsr_html_dir(project_root, hc_config)
    discovered_tsr = discover_tsr_html(tsr_html_dir, cluster_id, meta["cluster_name"])
    if discovered_tsr is not None:
        args.tsr_html = discovered_tsr
        print(f"  Auto-discovered TSR HTML: {discovered_tsr}")
        return
    cluster_id_hint = f"{cluster_id[:8]}..." if cluster_id else "unknown"
    print(
        "Advisory: No matching TSR HTML found for cluster "
        f"{meta['cluster_name']} ({cluster_id_hint}) in {tsr_html_dir}. "
        "Place TSR HTML exports there for full CCX/parity coverage. "
        "Proceeding with SKIPPED status for unresolvable checks.",
        file=sys.stderr,
    )


def _parse_tsr_html_runtime(args: argparse.Namespace, output_dir: Path) -> Path | None:
    """Parse the resolved TSR HTML (if any) and persist the runtime JSON for parity matching."""
    if not args.tsr_html:
        return None
    print(f"  Parsing TSR HTML: {args.tsr_html}")
    tsr_html_text = args.tsr_html.read_text(encoding="utf-8", errors="ignore")
    tsr_parsed = parse_tsr_html(tsr_html_text)
    tsr_runtime_path = output_dir / "tsr_parsed_runtime.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    tsr_runtime_path.write_text(
        json.dumps(tsr_parsed, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  TSR parsed: {len(tsr_parsed)} checks → {tsr_runtime_path}")
    return tsr_runtime_path


def _generate_single_report(
    args: argparse.Namespace, config: dict, hc_config: dict,
    results_dir: Path, output_dir: Path, template_path: Path,
    project_root: Path, cluster_label: str | None = None,
) -> tuple[Path, list[str]]:
    """Generate a report for a single cluster's results. Returns (output_file, unfilled_slots)."""
    print(f"Loading results from: {results_dir}")
    results = load_results(results_dir)
    manifest = results.get("_manifest", {})
    print(f"  {manifest.get('total_files', '?')} files across "
          f"{len(manifest.get('categories', []))} categories")

    print("Deriving cluster metadata...")
    meta = derive_metadata(results, config)
    if cluster_label:
        meta["cluster_name"] = cluster_label
    print(f"  Cluster: {meta['cluster_name']}, OCP: {meta['ocp_version']}, Channel: {meta['channel']}")
    ocp_minor = _extract_minor_version(meta.get("ocp_version", ""))

    _discover_tsr_html_if_needed(args, project_root, hc_config, meta)

    print("Evaluating checks...")
    tsr_runtime_path = _parse_tsr_html_runtime(args, output_dir)

    checks = evaluate_checks(
        results,
        check_profile=args.check_profile,
        use_ccx_baseline_status=args.ccx_baseline_status,
        catalog_path=args.catalog_path,
        tsr_runtime_path=tsr_runtime_path,
    )
    print(f"  {len(checks)} checks evaluated")

    print("Deriving findings...")
    findings = derive_findings_with_tsr(checks, tsr_runtime_path, ocp_version=ocp_minor)
    pcount = Counter(finding.priority for finding in findings)
    print(f"  {len(findings)} findings: P0={pcount.get('P0',0)} P1={pcount.get('P1',0)} "
          f"P2={pcount.get('P2',0)} P3={pcount.get('P3',0)}")

    exec_summary = _make_exec_summary(args, meta, checks, findings, pcount)
    findings_narrative = _make_findings_narrative(args, meta, checks, findings, pcount)

    data_collection_method = _build_data_collection_method(project_root, results_dir, manifest)

    print("Rendering report template...")
    template_text = template_path.read_text(encoding="utf-8")
    rendered = render_report(
        template_text,
        meta,
        checks,
        findings,
        exec_summary,
        findings_narrative,
        data_collection_method,
        ocp_version=ocp_minor,
    )

    unfilled = find_unfilled_slots(rendered)
    if unfilled:
        print(f"Warning: {len(unfilled)} unfilled slots: {unfilled}", file=sys.stderr)

    output_file = _write_outputs(output_dir, rendered, meta, checks, findings, pcount, args.check_profile)
    print(f"Report written to: {output_file}")
    _write_pruned_report(
        args,
        output_file,
        template_text,
        meta,
        checks,
        findings,
        ocp_minor,
        data_collection_method,
    )
    return output_file, unfilled


def _write_pruned_report(
    args: argparse.Namespace,
    output_file: Path,
    template_text: str,
    meta: dict,
    checks: list,
    findings: list,
    ocp_minor: str,
    data_collection_method: str,
) -> None:
    pruned_path = pruned_report_path(output_file)
    if args.omit_check_ids is None:
        pruned_path.unlink(missing_ok=True)
        return
    try:
        omit_ids = load_omit_check_ids(args.omit_check_ids)
    except FileNotFoundError:
        print(
            f"Error: omit check-id file not found: {args.omit_check_ids}",
            file=sys.stderr,
        )
        sys.exit(1)
    if not omit_ids:
        pruned_path.unlink(missing_ok=True)
        return
    result = apply_finding_omit(findings, omit_ids)
    for unmatched_id in result.unmatched:
        print(
            f"Warning: omit check ID not in Chapter 6 findings: {unmatched_id}",
            file=sys.stderr,
        )
    if args.omit_strict and result.unmatched:
        sys.exit(1)
    pruned_findings = compact_finding_ids(result.kept)
    pruned_pcount = Counter(finding.priority for finding in pruned_findings)
    exec_summary = _make_exec_summary(
        args, meta, checks, pruned_findings, pruned_pcount
    )
    findings_narrative = _make_findings_narrative(
        args, meta, checks, pruned_findings, pruned_pcount
    )
    pruned_rendered = render_report(
        template_text,
        meta,
        checks,
        pruned_findings,
        exec_summary,
        findings_narrative,
        data_collection_method,
        ocp_version=ocp_minor,
    )
    pruned_path.write_text(pruned_rendered, encoding="utf-8")
    print(f"Pruned report written to: {pruned_path}")


def main() -> None:
    args = parse_args()
    project_root = find_project_yaml().parent
    config, results_dir, output_dir, template_path = _load_config_paths(args, project_root)
    hc_config = get_health_check_config(config)
    _resolve_check_expansion_options(args, hc_config, project_root)
    _resolve_tsr_html_path(args, hc_config, project_root)

    if not template_path.exists():
        print(f"Error: template not found at {template_path}", file=sys.stderr)
        sys.exit(1)
    if not results_dir.exists():
        print(f"Error: results directory not found at {results_dir}", file=sys.stderr)
        print("Run 'make hc-collect' or 'bash scripts/health_check/collect/hc_collect.sh' first.",
              file=sys.stderr)
        sys.exit(1)

    targets = resolve_cluster_targets(results_dir)
    multi = len(targets) > 1

    if multi:
        cluster_names = ", ".join(name for name, _ in targets)
        print(f"Multi-cluster detected: {cluster_names}")
        print(f"Generating {len(targets)} reports...")
        print("")

    any_unfilled = False
    explicit_tsr_html = args.tsr_html
    for cluster_name, cluster_results_dir in targets:
        args.tsr_html = explicit_tsr_html
        cluster_output_dir = output_dir / cluster_name if cluster_name else output_dir
        if multi:
            print(f"{'=' * 60}")
            print(f"  Cluster: {cluster_name}")
            print(f"{'=' * 60}")

        _, unfilled = _generate_single_report(
            args, config, hc_config,
            cluster_results_dir, cluster_output_dir, template_path,
            project_root, cluster_label=cluster_name,
        )
        if unfilled:
            any_unfilled = True
        if multi:
            print("")

    if multi:
        print(f"All {len(targets)} cluster reports generated under: {output_dir}")

    if any_unfilled:
        sys.exit(1)
