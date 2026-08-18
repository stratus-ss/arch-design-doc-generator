#!/usr/bin/env python3
"""hc_merge.py — Merge multiple hc_results directories into one unified result.

Handles the case where multiple must-gather types produce overlapping but
complementary hc_results sets for the same cluster.

Merge strategy per file type:
  - _hc_error or _hc_not_found stubs: skip in favor of any real data
  - Kubernetes List objects (kind=List, items=[]): union items by metadata.uid
  - _hc_text captures: pick the version with the longest output
  - Other JSON: pick the largest file by byte size

Usage:
  python3 hc_merge.py dir1/hc_results dir2/hc_results dir3/hc_results -o ./merged
  python3 hc_merge.py run1.tar.gz run2.tar.gz -o ./merged --tar
"""

import argparse
import json
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path


def is_stub(payload):
    """Check if JSON data is an error or not-found stub."""
    if isinstance(payload, dict):
        return payload.get("_hc_error") or payload.get("_hc_not_found")
    return False


def is_kubernetes_list(payload):
    """Check if JSON data is a Kubernetes List object."""
    if isinstance(payload, dict):
        return payload.get("kind") == "List" and "items" in payload
    return False


def is_text_capture(payload):
    """Check if JSON data is a text capture envelope."""
    if isinstance(payload, dict):
        return payload.get("_hc_text") is True
    return False


def item_key(item):
    """Generate a dedup key for a Kubernetes resource item."""
    resource_metadata = item.get("metadata", {})
    uid = resource_metadata.get("uid")
    if uid:
        return uid
    name = resource_metadata.get("name", "")
    namespace = resource_metadata.get("namespace", "")
    kind = item.get("kind", "")
    return f"{kind}/{namespace}/{name}"


def item_freshness(item):
    """Return a sortable freshness indicator for conflict resolution."""
    resource_metadata = item.get("metadata", {})
    resource_version = resource_metadata.get("resourceVersion", "0")
    try:
        return int(resource_version)
    except (ValueError, TypeError):
        return 0


def merge_kubernetes_lists(versions):
    """Merge multiple Kubernetes List objects by unioning items arrays."""
    merged_items = {}
    base = None

    for payload in versions:
        if base is None:
            base = payload
        for item in payload.get("items", []):
            dedup_key = item_key(item)
            if dedup_key not in merged_items or item_freshness(item) > item_freshness(merged_items[dedup_key]):
                merged_items[dedup_key] = item

    result = dict(base)
    result["items"] = list(merged_items.values())
    return result


def merge_text_captures(versions):
    """Pick the text capture with the longest output."""
    best = versions[0]
    best_output_length = len(best.get("output", ""))
    for version in versions[1:]:
        output_length = len(version.get("output", ""))
        if output_length > best_output_length:
            best = version
            best_output_length = output_length
    return best


def load_json(path):
    """Load a JSON file, returning None on failure."""
    try:
        with open(path, "r") as json_file:
            return json.load(json_file)
    except (json.JSONDecodeError, OSError):
        return None


def discover_results_files(results_dir):
    """Get all JSON files in an hc_results directory (relative paths)."""
    files = set()
    results_path = Path(results_dir)
    for json_file in results_path.rglob("*.json"):
        relative_path = json_file.relative_to(results_path)
        if relative_path.name != "manifest.json" and not relative_path.name.endswith(".meta.json"):
            files.add(str(relative_path))
    return files


def extract_tarball(tarball_path, dest_dir):
    """Extract a tarball and return the hc_results directory within."""
    with tarfile.open(tarball_path, "r:gz") as tarball:
        tarball.extractall(dest_dir)

    dest = Path(dest_dir)
    if (dest / "hc_results").is_dir():
        return str(dest / "hc_results")
    for directory in dest.iterdir():
        if directory.is_dir() and (directory / "manifest.json").exists():
            return str(directory)
        hc_sub = directory / "hc_results"
        if hc_sub.is_dir():
            return str(hc_sub)
    return str(dest)


def resolve_input(input_path, temp_base_dir):
    """Resolve an input path to an hc_results directory."""
    resolved_path = Path(input_path)
    if resolved_path.is_file() and (resolved_path.suffix == ".gz" or ".tar" in resolved_path.name):
        extract_dir = tempfile.mkdtemp(dir=temp_base_dir)
        return extract_tarball(str(resolved_path), extract_dir)
    if resolved_path.is_dir():
        if (resolved_path / "manifest.json").exists():
            return str(resolved_path)
        hc_sub = resolved_path / "hc_results"
        if hc_sub.is_dir():
            return str(hc_sub)
        return str(resolved_path)
    return str(resolved_path)


def merge_file(relative_path, input_dirs):
    """Merge a single file across all input directories."""
    versions = []
    raw_bytes = []

    for input_dir in input_dirs:
        file_path = Path(input_dir) / relative_path
        if not file_path.exists():
            continue
        payload = load_json(file_path)
        if payload is None:
            continue
        if is_stub(payload):
            continue
        versions.append(payload)
        raw_bytes.append(file_path.stat().st_size)

    if not versions:
        for input_dir in input_dirs:
            file_path = Path(input_dir) / relative_path
            if file_path.exists():
                return load_json(file_path)
        return None

    if len(versions) == 1:
        return versions[0]

    if all(is_kubernetes_list(version) for version in versions):
        return merge_kubernetes_lists(versions)

    if all(is_text_capture(version) for version in versions):
        return merge_text_captures(versions)

    largest_index = raw_bytes.index(max(raw_bytes))
    return versions[largest_index]


def generate_manifest(output_dir):
    """Regenerate manifest.json for the merged output."""
    output_path = Path(output_dir)
    files = sorted(
        str(json_file.relative_to(output_path))
        for json_file in output_path.rglob("*.json")
        if json_file.name != "manifest.json" and not json_file.name.endswith(".meta.json")
    )

    categories = sorted(set(
        str(json_file.relative_to(output_path)).split("/")[0]
        for json_file in output_path.rglob("*.json")
        if json_file.name != "manifest.json" and not json_file.name.endswith(".meta.json")
        and "/" in str(json_file.relative_to(output_path))
    ))

    from datetime import datetime, timezone
    manifest = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "merged": True,
        "input_count": 0,
        "total_files": len(files),
        "categories": categories,
        "files": files,
    }
    return manifest


def aggregate_skip_logs(input_dirs, output_dir):
    """Concatenate skipped_commands.jsonl from each input dir into the output dir.

    Purely additive — does not read, write, or affect any file considered by
    merge_file()/is_stub()/merge_kubernetes_lists()/merge_text_captures(). Returns the
    number of ledger lines written (0 if no input had a ledger file).
    """
    lines = []
    for input_dir in input_dirs:
        ledger = Path(input_dir) / "skipped_commands.jsonl"
        if ledger.exists():
            lines.extend(ledger.read_text().splitlines())

    if not lines:
        return 0

    out_ledger = Path(output_dir) / "skipped_commands.jsonl"
    out_ledger.write_text("\n".join(lines) + "\n")
    return len(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Merge multiple hc_results directories into one unified result."
    )
    parser.add_argument(
        "inputs", nargs="+",
        help="hc_results directories or tarballs to merge"
    )
    parser.add_argument(
        "-o", "--output", default="./hc_results_merged",
        help="Output directory for merged results (default: ./hc_results_merged)"
    )
    parser.add_argument(
        "--tar", action="store_true",
        help="Also produce a .tar.gz of the merged results"
    )
    args = parser.parse_args()

    temp_base_dir = tempfile.mkdtemp(prefix="hc_merge_")

    try:
        input_dirs = [resolve_input(input_path, temp_base_dir) for input_path in args.inputs]

        for input_dir in input_dirs:
            if not Path(input_dir).is_dir():
                print(f"ERROR: Could not resolve input to a directory: {input_dir}", file=sys.stderr)
                sys.exit(1)

        all_files = set()
        for input_dir in input_dirs:
            all_files.update(discover_results_files(input_dir))

        if not all_files:
            print("ERROR: No JSON files found in any input directory.", file=sys.stderr)
            sys.exit(1)

        output_dir = Path(args.output)
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True)

        merged_count = 0
        for relative_path in sorted(all_files):
            result = merge_file(relative_path, input_dirs)
            if result is None:
                continue

            out_file = output_dir / relative_path
            out_file.parent.mkdir(parents=True, exist_ok=True)
            with open(out_file, "w") as json_file:
                json.dump(result, json_file, indent=2)
            merged_count += 1

        manifest = generate_manifest(str(output_dir))
        manifest["input_count"] = len(input_dirs)
        with open(output_dir / "manifest.json", "w") as manifest_file:
            json.dump(manifest, manifest_file, indent=2)

        skip_count = aggregate_skip_logs(input_dirs, output_dir)

        print(f"Merged {merged_count} files from {len(input_dirs)} inputs → {output_dir}")
        if skip_count:
            print(f"Skip ledger: {skip_count} entries → {output_dir / 'skipped_commands.jsonl'}")

        if args.tar:
            tar_path = str(output_dir) + ".tar.gz"
            with tarfile.open(tar_path, "w:gz") as tarball:
                tarball.add(str(output_dir), arcname="hc_results")
            print(f"Tarball: {tar_path}")

    finally:
        shutil.rmtree(temp_base_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
