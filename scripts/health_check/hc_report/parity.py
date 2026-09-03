"""TSR/CCX parity expansion helpers."""
from __future__ import annotations

import json
import re
from pathlib import Path

from hc_report.models import CheckResult

_STATUS_MAP = {
    "PASS": "PASS",
    "FAIL": "FAIL",
    "WARNING": "WARNING",
    "WARN": "WARNING",
    "INFO": "INFO",
    "SKIP": "SKIPPED",
    "SKIPPED": "SKIPPED",
    "NOT_APPLICABLE": "NOT_APPLICABLE",
    "NA": "NOT_APPLICABLE",
}


def _default_catalog_path() -> Path:
    return Path(__file__).resolve().parent / "catalogs" / "tsr_ccx_crosswalk.json"


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _load_catalog(catalog_path: Path | None = None) -> list[dict]:
    path = catalog_path or _default_catalog_path()
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("entries", [])
    return entries if isinstance(entries, list) else []


def load_tsr_runtime(tsr_json_path: Path) -> dict[str, dict]:
    """Load parsed TSR HTML output JSON into a lookup keyed by normalized title."""
    if not tsr_json_path.exists():
        return {}
    data = json.loads(tsr_json_path.read_text(encoding="utf-8"))
    records: dict[str, dict] = {}
    entries = data if isinstance(data, list) else data.get("checks", [])
    for row in entries:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title", "")).strip()
        if title:
            records[_normalize(title)] = row
    return records


_TSR_HTML_HEADER_CHARS = 100_000
_TSR_CLUSTER_ID = re.compile(
    r"Cluster ID:</strong>\s*"
    r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
    re.IGNORECASE,
)
_TSR_CLUSTER_NAME = re.compile(
    r"Cluster Name:</strong>\s*([^<]+)",
    re.IGNORECASE,
)


def _parse_tsr_html_cluster_header(header_text: str) -> tuple[str, str]:
    """Return (cluster_id, cluster_name) from TSR HTML header fields."""
    id_match = _TSR_CLUSTER_ID.search(header_text)
    name_match = _TSR_CLUSTER_NAME.search(header_text)
    parsed_id = id_match.group(1).lower() if id_match else ""
    parsed_name = name_match.group(1).strip() if name_match else ""
    return parsed_id, parsed_name


def _cluster_names_match(collect_name: str, html_name: str) -> bool:
    """True when collect infrastructureName and TSR Cluster Name refer to the same cluster.

    TSR prints the short name (``prod-ocp-01``); OpenShift infrastructureName
    often adds a five-character suffix (``prod-ocp-01-abc12``).
    """
    if not collect_name or not html_name:
        return False
    collect_folded = collect_name.casefold()
    html_folded = html_name.casefold()
    if collect_folded == html_folded:
        return True
    return collect_folded.startswith(html_folded + "-") or html_folded.startswith(
        collect_folded + "-"
    )


def discover_tsr_html(tsr_dir: Path, cluster_id: str, cluster_name: str) -> Path | None:
    """Find the TSR HTML whose Cluster ID header matches this cluster.

    Cluster Name is a fallback only (exact or infrastructureName suffix).
    Filenames are not used.
    """
    if not tsr_dir.is_dir():
        return None

    cluster_id = str(cluster_id).strip().lower()
    cluster_name = str(cluster_name).strip()
    id_matches: list[Path] = []
    name_matches: list[Path] = []

    for path in tsr_dir.glob("*.html"):
        if not path.is_file():
            continue
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as handle:
                header_text = handle.read(_TSR_HTML_HEADER_CHARS)
        except OSError:
            continue
        html_cluster_id, html_cluster_name = _parse_tsr_html_cluster_header(header_text)
        if cluster_id and html_cluster_id and cluster_id == html_cluster_id:
            id_matches.append(path)
            continue
        if _cluster_names_match(cluster_name, html_cluster_name):
            name_matches.append(path)

    if id_matches:
        return max(id_matches, key=lambda candidate: candidate.stat().st_mtime)
    if name_matches:
        return max(name_matches, key=lambda candidate: candidate.stat().st_mtime)
    return None


def _collect_runtime_ccx(results: dict) -> dict[str, dict]:
    """Load optional runtime CCX records from 12_ccx/ccx_rules.json."""
    records: dict[str, dict] = {}
    payload = results.get("12_ccx", {}).get("ccx_rules")
    if not isinstance(payload, dict):
        return records
    if payload.get("_hc_error") or payload.get("_hc_not_found"):
        return records

    runtime_entries = []
    if isinstance(payload.get("rules"), list):
        runtime_entries = payload["rules"]
    elif isinstance(payload.get("entries"), list):
        runtime_entries = payload["entries"]
    elif isinstance(payload.get("items"), list):
        runtime_entries = payload["items"]

    for row in runtime_entries:
        if not isinstance(row, dict):
            continue
        title = str(row.get("check") or row.get("title") or "").strip()
        if not title:
            continue
        records[_normalize(title)] = row
    return records


def _status(value: str, fallback: str = "SKIPPED") -> str:
    return _STATUS_MAP.get(str(value).upper(), fallback)


def _normalize_tags(raw_tags) -> list[str]:
    tags: list[str] = []
    if not isinstance(raw_tags, list):
        return tags
    for tag in raw_tags:
        cleaned = str(tag).strip().lower()
        if cleaned:
            tags.append(cleaned)
    return tags


def _resolve_ccx_status(
    entry: dict, title: str, norm_title: str, runtime_ccx: dict[str, dict], use_ccx_baseline_status: bool,
) -> tuple[str, str, list]:
    """Resolve (status, evidence, tags) for a CCX-sourced catalog entry with no
    matching TSR runtime record. Extracted from expand_with_parity_checks() to
    keep that function's branch count within the complexity budget.
    """
    runtime = runtime_ccx.get(norm_title)
    if runtime:
        status = _status(str(runtime.get("status", "SKIPPED")))
        message = str(runtime.get("message", "")).strip()
        evidence = message or "CCX runtime rule result captured from 12_ccx/ccx_rules."
        tags = _normalize_tags(runtime.get("tags", []))
        return status, evidence, tags
    if use_ccx_baseline_status:
        status = _status(str(entry.get("status_hint", "SKIPPED")))
        evidence = (
            "No live CCX/Insights data collected "
            "(12_ccx/ccx_rules.json absent or empty). This check requires "
            "Red Hat Insights data to evaluate. Run insights-client or review "
            "via console.redhat.com/insights. Catalog status_hint was "
            f"'{entry.get('status_hint', 'FAIL')}' and was applied because "
            "--ccx-baseline-status is enabled."
        )
        return status, evidence, []
    evidence = (
        f"CCX/Insights check '{title}' has no live data available. "
        "Collect Insights data or provide a matching TSR HTML via "
        "--tsr-html or the configured TSR HTML directory."
    )
    return "SKIPPED", evidence, []


def _tsr_keeps_row_with_native_title(norm_title: str, tsr_runtime: dict[str, dict]) -> bool:
    """True when a TSR FAIL or WARNING must keep its catalog row even if a
    native check already uses the same normalized title.
    """
    tsr_record = tsr_runtime.get(norm_title)
    if not tsr_record:
        return False
    status = _status(str(tsr_record.get("status", "")))
    return status in ("FAIL", "WARNING")


def expand_with_parity_checks(
    checks: list[CheckResult],
    results: dict,
    *,
    include_tsr: bool,
    include_ccx: bool,
    use_ccx_baseline_status: bool,
    catalog_path: Path | None = None,
    tsr_runtime_path: Path | None = None,
) -> list[CheckResult]:
    """Append parity checks from the TSR/CCX catalog without removing existing checks.

    When tsr_runtime_path is provided, parsed TSR HTML data is used as the
    authoritative status+evidence source, overriding catalog placeholders.

    Title-match deduplication (an existing native check already covers this
    TSR title) is normally used to avoid duplicate report rows. That
    dedup is bypassed when the TSR runtime status is FAIL or WARNING — see
    _tsr_keeps_row_with_native_title().
    """
    catalog = _load_catalog(catalog_path)
    if not catalog:
        return checks

    existing_ids = {check.check_id for check in checks}
    existing_desc = {_normalize(check.description) for check in checks}
    runtime_ccx = _collect_runtime_ccx(results)
    tsr_runtime = load_tsr_runtime(tsr_runtime_path) if tsr_runtime_path else {}
    expanded = list(checks)

    for entry in catalog:
        source = str(entry.get("source", "tsr")).lower()
        if source == "tsr" and not include_tsr:
            continue
        if source == "ccx" and not include_ccx:
            continue

        check_id = str(entry.get("check_id", "")).strip()
        title = str(entry.get("title", "")).strip()
        if not check_id or not title:
            continue
        if check_id in existing_ids:
            continue
        norm_title = _normalize(title)
        if source == "tsr" and norm_title in existing_desc:
            if not _tsr_keeps_row_with_native_title(norm_title, tsr_runtime):
                continue

        category_id = str(entry.get("category_id", "7.7"))
        category_name = str(entry.get("category_name", "Security and Compliance"))
        tags = entry.get("tags", []) if isinstance(entry.get("tags"), list) else []
        tsr_ref = str(entry.get("tsr_ref", ""))

        status = "SKIPPED"
        # Fallback evidence sentences below are detected by
        # renderer._CATALOG_FALLBACK_MARKERS to suppress them from the
        # client-facing Chapter 7 Result column.  Keep both sides in sync.
        if tsr_runtime_path is None:
            evidence = (
                f"No TSR runtime data supplied for '{title}'. This check is mapped in the "
                "TSR/CCX catalog but has no native deterministic evaluator yet, so it can only "
                "be scored from a TSR HTML export. Pass --tsr-html <path-to-export.html> to "
                "score this check from the cluster's TSR report, or omit --check-profile "
                "extended/advisory to exclude unscored TSR parity checks from the report."
            )
        else:
            evidence = (
                f"'{title}' was not found in the supplied TSR HTML export ({tsr_runtime_path}). "
                "This check is mapped in the TSR/CCX catalog but has no native deterministic "
                "evaluator yet, and the TSR export did not contain a matching entry — verify the "
                "TSR HTML corresponds to this cluster/session, or check for a title mismatch."
            )

        tsr_record = tsr_runtime.get(norm_title)
        if tsr_record:
            status = _status(str(tsr_record.get("status", "SKIPPED")))
            parsed_evidence = str(tsr_record.get("evidence", "")).strip()
            evidence = parsed_evidence or f"Status from TSR HTML: {status}"
            parsed_tags = tsr_record.get("tags", [])
            if isinstance(parsed_tags, list) and parsed_tags:
                tags = _normalize_tags(parsed_tags)
        elif source == "ccx":
            status, evidence, ccx_tags = _resolve_ccx_status(
                entry, title, norm_title, runtime_ccx, use_ccx_baseline_status,
            )
            if ccx_tags:
                tags = ccx_tags

        expanded.append(
            CheckResult(
                category_id=category_id,
                category_name=category_name,
                check_id=check_id,
                description=title,
                status=status,
                evidence=evidence,
                source=source,
                tsr_ref=tsr_ref,
                tags=_normalize_tags(tags),
            )
        )
        existing_ids.add(check_id)
        existing_desc.add(norm_title)

    return expanded
