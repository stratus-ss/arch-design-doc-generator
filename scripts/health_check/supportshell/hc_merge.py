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


def is_stub(data):
    """Check if JSON data is an error or not-found stub."""
    if isinstance(data, dict):
        return data.get("_hc_error") or data.get("_hc_not_found")
    return False


def is_k8s_list(data):
    """Check if JSON data is a Kubernetes List object."""
    if isinstance(data, dict):
        return data.get("kind") == "List" and "items" in data
    return False


def is_text_capture(data):
    """Check if JSON data is a text capture envelope."""
    if isinstance(data, dict):
        return data.get("_hc_text") is True
    return False


def item_key(item):
    """Generate a dedup key for a Kubernetes resource item."""
    meta = item.get("metadata", {})
    uid = meta.get("uid")
    if uid:
        return uid
    name = meta.get("name", "")
    ns = meta.get("namespace", "")
    kind = item.get("kind", "")
    return f"{kind}/{ns}/{name}"


def item_freshness(item):
    """Return a sortable freshness indicator for conflict resolution."""
    meta = item.get("metadata", {})
    rv = meta.get("resourceVersion", "0")
    try:
        return int(rv)
    except (ValueError, TypeError):
        return 0


def merge_k8s_lists(versions):
    """Merge multiple Kubernetes List objects by unioning items arrays."""
    merged_items = {}
    base = None

    for data in versions:
        if base is None:
            base = data
        for item in data.get("items", []):
            key = item_key(item)
            if key not in merged_items or item_freshness(item) > item_freshness(merged_items[key]):
                merged_items[key] = item

    result = dict(base)
    result["items"] = list(merged_items.values())
    return result


def merge_text_captures(versions):
    """Pick the text capture with the longest output."""
    best = versions[0]
    best_len = len(best.get("output", ""))
    for v in versions[1:]:
        vlen = len(v.get("output", ""))
        if vlen > best_len:
            best = v
            best_len = vlen
    return best


def load_json(path):
    """Load a JSON file, returning None on failure."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def discover_results_files(results_dir):
    """Get all JSON files in an hc_results directory (relative paths)."""
    files = set()
    results_path = Path(results_dir)
    for json_file in results_path.rglob("*.json"):
        rel = json_file.relative_to(results_path)
        if rel.name != "manifest.json" and not rel.name.endswith(".meta.json"):
            files.add(str(rel))
    return files


def extract_tarball(tarball_path, dest_dir):
    """Extract a tarball and return the hc_results directory within."""
    with tarfile.open(tarball_path, "r:gz") as tf:
        tf.extractall(dest_dir)

    dest = Path(dest_dir)
    if (dest / "hc_results").is_dir():
        return str(dest / "hc_results")
    for d in dest.iterdir():
        if d.is_dir() and (d / "manifest.json").exists():
            return str(d)
        hc_sub = d / "hc_results"
        if hc_sub.is_dir():
            return str(hc_sub)
    return str(dest)


def resolve_input(input_path, tmp_base):
    """Resolve an input path to an hc_results directory."""
    p = Path(input_path)
    if p.is_file() and (p.suffix == ".gz" or ".tar" in p.name):
        extract_dir = tempfile.mkdtemp(dir=tmp_base)
        return extract_tarball(str(p), extract_dir)
    if p.is_dir():
        if (p / "manifest.json").exists():
            return str(p)
        hc_sub = p / "hc_results"
        if hc_sub.is_dir():
            return str(hc_sub)
        return str(p)
    return str(p)


def merge_file(rel_path, input_dirs):
    """Merge a single file across all input directories."""
    versions = []
    raw_bytes = []

    for d in input_dirs:
        fpath = Path(d) / rel_path
        if not fpath.exists():
            continue
        data = load_json(fpath)
        if data is None:
            continue
        if is_stub(data):
            continue
        versions.append(data)
        raw_bytes.append(fpath.stat().st_size)

    if not versions:
        for d in input_dirs:
            fpath = Path(d) / rel_path
            if fpath.exists():
                return load_json(fpath)
        return None

    if len(versions) == 1:
        return versions[0]

    if all(is_k8s_list(v) for v in versions):
        return merge_k8s_lists(versions)

    if all(is_text_capture(v) for v in versions):
        return merge_text_captures(versions)

    largest_idx = raw_bytes.index(max(raw_bytes))
    return versions[largest_idx]


def generate_manifest(output_dir):
    """Regenerate manifest.json for the merged output."""
    output_path = Path(output_dir)
    files = sorted(
        str(f.relative_to(output_path))
        for f in output_path.rglob("*.json")
        if f.name != "manifest.json" and not f.name.endswith(".meta.json")
    )

    categories = sorted(set(
        str(f.relative_to(output_path)).split("/")[0]
        for f in output_path.rglob("*.json")
        if f.name != "manifest.json" and not f.name.endswith(".meta.json")
        and "/" in str(f.relative_to(output_path))
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
    merge_file()/is_stub()/merge_k8s_lists()/merge_text_captures(). Returns the
    number of ledger lines written (0 if no input had a ledger file).
    """
    lines = []
    for d in input_dirs:
        ledger = Path(d) / "skipped_commands.jsonl"
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

    tmp_base = tempfile.mkdtemp(prefix="hc_merge_")

    try:
        input_dirs = [resolve_input(inp, tmp_base) for inp in args.inputs]

        for d in input_dirs:
            if not Path(d).is_dir():
                print(f"ERROR: Could not resolve input to a directory: {d}", file=sys.stderr)
                sys.exit(1)

        all_files = set()
        for d in input_dirs:
            all_files.update(discover_results_files(d))

        if not all_files:
            print("ERROR: No JSON files found in any input directory.", file=sys.stderr)
            sys.exit(1)

        output_dir = Path(args.output)
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True)

        merged_count = 0
        for rel_path in sorted(all_files):
            result = merge_file(rel_path, input_dirs)
            if result is None:
                continue

            out_file = output_dir / rel_path
            out_file.parent.mkdir(parents=True, exist_ok=True)
            with open(out_file, "w") as f:
                json.dump(result, f, indent=2)
            merged_count += 1

        manifest = generate_manifest(str(output_dir))
        manifest["input_count"] = len(input_dirs)
        with open(output_dir / "manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)

        skip_count = aggregate_skip_logs(input_dirs, output_dir)

        print(f"Merged {merged_count} files from {len(input_dirs)} inputs → {output_dir}")
        if skip_count:
            print(f"Skip ledger: {skip_count} entries → {output_dir / 'skipped_commands.jsonl'}")

        if args.tar:
            tar_path = str(output_dir) + ".tar.gz"
            with tarfile.open(tar_path, "w:gz") as tf:
                tf.add(str(output_dir), arcname="hc_results")
            print(f"Tarball: {tar_path}")

    finally:
        shutil.rmtree(tmp_base, ignore_errors=True)


if __name__ == "__main__":
    main()
