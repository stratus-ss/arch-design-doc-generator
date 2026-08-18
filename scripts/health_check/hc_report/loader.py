"""Load collected JSON results from the hc_collect output directory."""
from __future__ import annotations

import json
import re
from pathlib import Path

_DATED_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _find_dated_subdir(results_dir: Path) -> Path | None:
    """Return the most recent YYYY-MM-DD staging subdirectory, if any.

    `hc-fetch-results` / `hc-report-from-supportshell` stage results under
    `<HC_COLLECT_OUT>/<date>/` rather than directly in `HC_COLLECT_OUT`. If the
    caller points `hc-report` at the parent dir instead of the dated one (e.g.
    a bare `make hc-report` on a later day), fall back to the latest dated
    subdirectory instead of silently loading zero files.
    """
    dated = [
        dated_dir
        for dated_dir in results_dir.iterdir()
        if dated_dir.is_dir() and _DATED_DIR_RE.match(dated_dir.name)
    ]
    return sorted(dated)[-1] if dated else None


def _first_item(data: dict) -> dict:
    """Return the first item from a Kubernetes List, or the object itself."""
    if data.get("kind") in ("List", "ClusterVersionList") or (
        "items" in data and not data.get("kind", "").endswith(
            ("Version", "Operator", "Network", "OAuth")
        )
    ):
        items = data.get("items", [])
        return items[0] if items else {}
    return data


def _scan_results_dir(results_dir: Path) -> list[str]:
    """Fallback: scan directory for category/name.json files when manifest is absent."""
    files = []
    for cat_dir in sorted(results_dir.iterdir()):
        if not cat_dir.is_dir():
            continue
        for json_file in sorted(cat_dir.glob("*.json")):
            if json_file.name == "manifest.json":
                continue
            if json_file.name.endswith(".meta.json"):
                continue
            files.append(f"{cat_dir.name}/{json_file.name}")
    return files


def _find_cluster_result_dirs(results_dir: Path) -> list[Path]:
    """Return immediate child directories that look like per-cluster result roots."""
    cluster_dirs: list[Path] = []
    for child in sorted(results_dir.iterdir()):
        if not child.is_dir():
            continue
        if (child / "manifest.json").exists() or _scan_results_dir(child):
            cluster_dirs.append(child)
    return cluster_dirs


def _print_fallback_note(results_dir: Path, resolved_dir: Path, label: str) -> None:
    print(f"  Note: no results directly under {results_dir} — "
          f"using {label} {resolved_dir} instead")
    print(f"  (pass --results-dir {resolved_dir} / HC_COLLECT_OUT={resolved_dir} to silence this note)")


def _resolve_results_dir(results_dir: Path) -> Path:
    manifest_path = results_dir / "manifest.json"
    if manifest_path.exists() or _scan_results_dir(results_dir):
        return results_dir

    dated_dir = _find_dated_subdir(results_dir)
    if dated_dir is not None:
        _print_fallback_note(results_dir, dated_dir, "dated subdirectory")
        results_dir = dated_dir
        manifest_path = results_dir / "manifest.json"
        if manifest_path.exists() or _scan_results_dir(results_dir):
            return results_dir

    cluster_dirs = _find_cluster_result_dirs(results_dir)
    if len(cluster_dirs) == 1:
        cluster_dir = cluster_dirs[0]
        _print_fallback_note(results_dir, cluster_dir, "cluster subdirectory")
        return cluster_dir
    if len(cluster_dirs) > 1:
        cluster_names = ", ".join(child.name for child in cluster_dirs)
        print(f"  Error: multiple cluster result directories found under {results_dir}: {cluster_names}")
        print("  Re-run with --results-dir <...>/<cluster_name> or set "
              "HC_COLLECT_OUT=<...>/<cluster_name> to pick one cluster explicitly.")
        raise SystemExit(2)

    return results_dir


def resolve_cluster_targets(results_dir: Path) -> list[tuple[str | None, Path]]:
    """Return a list of (cluster_name, resolved_path) for report iteration.

    Single-cluster or direct results: returns [(None, path)].
    Multi-cluster layout: returns [("cluster_a", path_a), ("cluster_b", path_b), ...].
    """
    if not results_dir.is_dir():
        return [(None, results_dir)]

    manifest_path = results_dir / "manifest.json"
    if manifest_path.exists() or _scan_results_dir(results_dir):
        return [(None, results_dir)]

    dated_dir = _find_dated_subdir(results_dir)
    if dated_dir is not None:
        results_dir = dated_dir
        if (results_dir / "manifest.json").exists() or _scan_results_dir(results_dir):
            return [(None, results_dir)]

    cluster_dirs = _find_cluster_result_dirs(results_dir)
    if len(cluster_dirs) > 1:
        return [(cluster_dir.name, cluster_dir) for cluster_dir in cluster_dirs]
    if len(cluster_dirs) == 1:
        return [(None, cluster_dirs[0])]

    return [(None, results_dir)]


def _initialize_result_index(results_dir: Path) -> tuple[dict, list[str]]:
    manifest_path = results_dir / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return {"_manifest": manifest}, manifest.get("files", [])

    file_list = _scan_results_dir(results_dir)
    results = {"_manifest": {"scanned": True, "files": file_list}}
    if file_list:
        print(f"  Note: No manifest.json found — scanned directory ({len(file_list)} files)")
    return results, file_list


def _populate_results(results_dir: Path, file_list: list[str], results: dict) -> None:
    for relative_path in file_list:
        full_path = results_dir / relative_path
        if not full_path.exists():
            continue
        try:
            payload = json.loads(full_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {"_hc_error": True, "note": "invalid JSON"}

        parts = relative_path.split("/")
        if len(parts) != 2:
            continue
        category, file_name = parts
        check_name = file_name.replace(".json", "")
        if category not in results:
            results[category] = {}
        results[category][check_name] = payload


def load_results(results_dir: Path) -> dict:
    """Load all collected JSON files into a keyed dict.

    Accepts either a results directory with a manifest.json (produced by
    hc_collect.sh / hc_collect_multi.sh + hc_merge.py) or a bare directory
    of category sub-folders — whichever layout is present.
    """
    if not results_dir.is_dir():
        print(f"  Error: results directory not found at {results_dir}")
        print("  Run 'make hc-collect' or 'bash scripts/health_check/collect/hc_collect.sh' first.")
        raise SystemExit(2)

    results_dir = _resolve_results_dir(results_dir)
    results, file_list = _initialize_result_index(results_dir)
    _populate_results(results_dir, file_list, results)

    if not file_list:
        print(f"  Error: no collected JSON files found under {results_dir}")
        print("  This usually means HC_COLLECT_OUT / --results-dir points at the wrong")
        print("  directory — supportshell/must-gather fetches stage into a dated")
        print("  subfolder (e.g. output/hc_collect/<YYYY-MM-DD>/). Run "
              f"'ls {results_dir}' to check, or re-run 'make hc-fetch-results' / "
              "'make hc-collect'.")
        raise SystemExit(2)

    return results
