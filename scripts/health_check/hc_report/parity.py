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


def discover_tsr_html(tsr_dir: Path, cluster_id: str, cluster_name: str) -> Path | None:
    """Find the best-matching TSR HTML file for the current cluster."""
    if not tsr_dir.is_dir():
        return None

    cluster_id = str(cluster_id).strip()
    cluster_name = str(cluster_name).strip()
    id_matches: list[Path] = []
    name_matches: list[Path] = []
    overlap = max(len(cluster_id), len(cluster_name), 1) - 1

    for path in tsr_dir.glob("*.html"):
        if not path.is_file():
            continue
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as handle:
                tail = ""
                has_name_match = False
                while True:
                    chunk = handle.read(50_000)
                    if not chunk:
                        break
                    snippet = tail + chunk
                    if cluster_id and cluster_id in snippet:
                        id_matches.append(path)
                        break
                    if cluster_name and cluster_name in snippet:
                        has_name_match = True
                    tail = snippet[-overlap:] if overlap else ""
        except OSError:
            continue

        if path in id_matches:
            continue
        if has_name_match:
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


def _tsr_fail_missed_by_native(
    norm_title: str, tsr_runtime: dict[str, dict], existing_desc_fail: set[str]
) -> bool:
    """True when the TSR authoritatively FAILs a check whose title matches an
    existing native check, but no native check with that same title already
    reports FAIL — i.e. the native evaluation missed (or was inconclusive
    about) a real problem the TSR caught. Per project policy, the TSR is
    authoritative unless we have direct documentation proof to the contrary,
    so this FAIL must still surface even though a same-titled native check
    already exists (it is added as a distinct row, not merged into the
    native one, to avoid silently overwriting native evaluation logic).
    """
    tsr_record = tsr_runtime.get(norm_title)
    if not tsr_record:
        return False
    return _status(str(tsr_record.get("status", ""))) == "FAIL" and norm_title not in existing_desc_fail


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
    dedup is bypassed only when the TSR authoritatively FAILs the check and no
    existing native check of the same title already reports FAIL — see
    _tsr_fail_missed_by_native().
    """
    catalog = _load_catalog(catalog_path)
    if not catalog:
        return checks

    existing_ids = {check.check_id for check in checks}
    existing_desc = {_normalize(check.description) for check in checks}
    existing_desc_fail = {
        _normalize(check.description) for check in checks if check.status == "FAIL"
    }
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
            if not _tsr_fail_missed_by_native(norm_title, tsr_runtime, existing_desc_fail):
                continue

        category_id = str(entry.get("category_id", "7.7"))
        category_name = str(entry.get("category_name", "Security and Compliance"))
        tags = entry.get("tags", []) if isinstance(entry.get("tags"), list) else []
        tsr_ref = str(entry.get("tsr_ref", ""))

        status = "SKIPPED"
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
        if status == "FAIL":
            existing_desc_fail.add(norm_title)

    return expanded
