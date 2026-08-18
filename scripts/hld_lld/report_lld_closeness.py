#!/usr/bin/env python3
"""Report LLD content-closeness vs a canonical fixture directory (not a CI gate)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SLOT_RE = re.compile(r"(?<!\$)\{([A-Z][A-Z0-9_]*)\}")
HEADING_RE = re.compile(r"^##\s+(LLD-\S+)", re.MULTILINE)


def _slot_counts(text: str) -> tuple[int, int]:
    tokens = SLOT_RE.findall(text)
    tbd = sum(1 for t in tokens if t == "TBD")
    other = sum(1 for t in tokens if t != "TBD")
    return tbd, other


def _lld_keys(name: str) -> str:
    marker = "_LLD_"
    idx = name.find(marker)
    if idx == -1:
        return name
    return name[idx + 1 :]


def compare_lld_file(rendered_path: Path, canonical_path: Path | None) -> dict:
    rendered = rendered_path.read_text(encoding="utf-8") if rendered_path.exists() else ""
    canonical = canonical_path.read_text(encoding="utf-8") if canonical_path and canonical_path.exists() else ""
    tbd, other_slots = _slot_counts(rendered)
    rendered_ids = HEADING_RE.findall(rendered)
    canonical_ids = HEADING_RE.findall(canonical)
    rendered_set = set(rendered_ids)
    canonical_set = set(canonical_ids)
    return {
        "rendered": rendered_path.name,
        "canonical": canonical_path.name if canonical_path else "(missing)",
        "tbd": tbd,
        "other_slots": other_slots,
        "shell_vars": rendered.count("${"),
        "missing_ids": sorted(canonical_set - rendered_set),
        "extra_ids": sorted(rendered_set - canonical_set),
    }


def _index_lld_files(directory: Path, skip_template_prefix: bool = False) -> dict[str, Path]:
    indexed: dict[str, Path] = {}
    for path in sorted(directory.glob("*.md")):
        if skip_template_prefix and path.name.startswith("Template_"):
            continue
        indexed[_lld_keys(path.name)] = path
    return indexed


def _pair_files(rendered_dir: Path, canonical_dir: Path) -> list[tuple[Path, Path | None]]:
    rendered_map = _index_lld_files(rendered_dir)
    canonical_map = _index_lld_files(canonical_dir, skip_template_prefix=True)
    pairs: list[tuple[Path, Path | None]] = []
    for key, rendered in sorted(rendered_map.items()):
        pairs.append((rendered, canonical_map.get(key)))
    return pairs


def _write_report(rows: list[dict], out_path: Path) -> None:
    lines = [
        "# LLD closeness report",
        "",
        "Not a byte-equality gate. Missing/extra LLD ids are informational.",
        "",
        "| Rendered | Canonical | `{TBD}` | other `{SLOT}` | `${` | missing LLD ids | extra LLD ids |",
        "|----------|-----------|---------|----------------|------|-----------------|---------------|",
    ]
    for row in rows:
        missing = ", ".join(row["missing_ids"]) if row["missing_ids"] else "—"
        extra = ", ".join(row["extra_ids"]) if row["extra_ids"] else "—"
        lines.append(
            f"| {row['rendered']} | {row['canonical']} | {row['tbd']} | "
            f"{row['other_slots']} | {row['shell_vars']} | {missing} | {extra} |"
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report LLD closeness vs a canonical directory.")
    parser.add_argument("--rendered-dir", default="output/LLD")
    parser.add_argument("--canonical-dir", required=True)
    parser.add_argument("--out", default="tmp/lld_closeness.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rendered_dir = Path(args.rendered_dir)
    canonical_dir = Path(args.canonical_dir)
    if not rendered_dir.is_dir():
        print(f"Error: rendered dir not found: {rendered_dir}", file=sys.stderr)
        return 1
    if not canonical_dir.is_dir():
        print(f"Error: canonical dir not found: {canonical_dir}", file=sys.stderr)
        return 1
    rows = [compare_lld_file(rendered, canonical) for rendered, canonical in _pair_files(rendered_dir, canonical_dir)]
    out_path = Path(args.out)
    _write_report(rows, out_path)
    print(f"Wrote {out_path} ({len(rows)} file pair(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
