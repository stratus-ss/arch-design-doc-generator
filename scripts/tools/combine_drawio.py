#!/usr/bin/env python3
"""Combine individual .drawio files into a single multi-tab .drawio file.

Each input file contributes one tab (diagram page). The tab name is taken
from the <diagram name="..."> attribute in each source file.

Usage:
    python3 combine_drawio.py <folder>
    python3 combine_drawio.py --output COMBINED.drawio file1.drawio file2.drawio ...

When given a folder, groups files by prefix (the part before the first '_')
and produces one COMBINE_<PREFIX>.drawio per group. Existing COMBINE_* files
are removed before combining.
"""

import argparse
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


class DrawioCombiner:
    MXFILE_ATTRS = {
        "host": "Electron",
        "agent": "combine_drawio.py",
        "version": "29.6.6",
    }

    def __init__(self, output_path: str):
        self.output_path = Path(output_path).resolve()
        self.diagrams: list[ET.Element] = []
        self._seen_files: set[Path] = set()

    def is_output_file(self, path: str) -> bool:
        return Path(path).resolve() == self.output_path

    def add_file(self, path: str) -> str | None:
        """Parse a .drawio file and extract its <diagram> element.

        Returns the diagram name, or None if the file was already added.
        """
        resolved = Path(path).resolve()
        if resolved in self._seen_files:
            return None
        self._seen_files.add(resolved)

        tree = ET.parse(path)
        root = tree.getroot()

        if root.tag != "mxfile":
            raise ValueError(f"{path}: root element is <{root.tag}>, expected <mxfile>")

        diagram = root.find("diagram")
        if diagram is None:
            raise ValueError(f"{path}: no <diagram> element found")

        self.diagrams.append(diagram)
        return diagram.get("name", "(unnamed)")

    def write(self) -> None:
        """Build the combined <mxfile> and write to disk."""
        if not self.diagrams:
            raise RuntimeError("No diagrams to combine")

        mxfile = ET.Element("mxfile", {**self.MXFILE_ATTRS, "pages": str(len(self.diagrams))})

        for diagram in self.diagrams:
            mxfile.append(diagram)

        ET.indent(mxfile, space="  ")
        tree = ET.ElementTree(mxfile)
        ET.indent(tree, space="  ")
        tree.write(self.output_path, encoding="unicode", xml_declaration=False)

        with open(self.output_path, "a") as f:
            f.write("\n")


def get_prefix(filename: str) -> str:
    """Extract the prefix before the first underscore (e.g. 'HLD' from 'HLD_network.drawio')."""
    stem = Path(filename).stem
    if "_" in stem:
        return stem.split("_", 1)[0]
    return stem


def combine_folder(folder: Path) -> None:
    """Group .drawio files by prefix and combine each group, removing existing COMBINE_* files first."""
    existing = list(folder.glob("COMBINE_*.drawio"))
    for f in existing:
        print(f"  Removing existing: {f.name}")
        f.unlink()

    files = sorted(f for f in folder.glob("*.drawio") if not f.name.startswith("COMBINE_"))
    if not files:
        print(f"No .drawio files found in {folder}", file=sys.stderr)
        sys.exit(1)

    groups: dict[str, list[Path]] = defaultdict(list)
    for f in files:
        groups[get_prefix(f.name)].append(f)

    for prefix, group_files in sorted(groups.items()):
        output_path = folder / f"COMBINE_{prefix}.drawio"
        print(f"\n[{prefix}] -> {output_path.name}")

        combiner = DrawioCombiner(str(output_path))
        for filepath in group_files:
            name = combiner.add_file(str(filepath))
            if name is None:
                print(f"  Skipped (duplicate): {filepath.name}")
            else:
                print(f"  Added tab: {name}  <-- {filepath.name}")

        combiner.write()
        print(f"  Combined {len(combiner.diagrams)} tabs")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Combine individual .drawio files into a single multi-tab .drawio file."
    )
    parser.add_argument(
        "--output", "-o",
        help="Path for the combined .drawio output file (used with explicit file list)",
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="A single folder, or individual .drawio files to combine (order = tab order)",
    )
    args = parser.parse_args()

    # Folder mode: single positional arg that is a directory
    if len(args.paths) == 1 and Path(args.paths[0]).is_dir():
        if args.output:
            print("WARNING: --output is ignored in folder mode", file=sys.stderr)
        combine_folder(Path(args.paths[0]))
        return

    # Explicit file list mode
    if not args.output:
        print("ERROR: --output is required when specifying individual files", file=sys.stderr)
        sys.exit(1)

    combiner = DrawioCombiner(args.output)

    for filepath in args.paths:
        if not Path(filepath).is_file():
            print(f"ERROR: {filepath} not found", file=sys.stderr)
            sys.exit(1)
        if combiner.is_output_file(filepath):
            print(f"  Skipped (output file): {filepath}")
            continue
        name = combiner.add_file(filepath)
        if name is None:
            print(f"  Skipped (duplicate): {filepath}")
        else:
            print(f"  Added tab: {name}  <-- {filepath}")

    combiner.write()
    print(f"\nCombined {len(combiner.diagrams)} tabs -> {args.output}")


if __name__ == "__main__":
    main()
