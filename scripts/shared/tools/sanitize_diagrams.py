#!/usr/bin/env python3
"""
Sanitize .drawio diagrams by replacing client-specific references with
generic placeholders.

Default (no flags): in-place sanitization of templates/Diagrams/examples/.

  --from-output --yes  copy output/Diagrams/phase* into templates/Diagrams/examples/
  --from-output        print planned writes to stderr and exit 2 (write nothing)

Run from anywhere — paths are resolved relative to --root (default: repo root).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from config import find_project_yaml
from sanitize_diagrams_data import REPLACEMENTS

# Source -> example name mapping for diagrams with well-known example names
EXAMPLE_NAME_MAP = {
    "HLD_Phase1_Flow_BareMetal_to_Cluster.drawio": "HLD_Phase1_Flow.drawio",
    "HLD_Phase2_Flow_Platform_Build.drawio": "HLD_Phase2_Flow.drawio",
    "HLD_Phase3_Flow_Fleet_Operations.drawio": "HLD_Phase3_Flow.drawio",
    "HLD_Phase4_Flow_Migration.drawio": "HLD_Phase4_Flow.drawio",
    "HLD_Phase2_Storage_IO_Path.drawio": "HLD_Storage_IO_Path.drawio",
    "HLD_Phase2_Network_Bond_Architecture.drawio": "HLD_Network_Bond_Architecture.drawio",
    "HLD_Phase4_Migration_Wave_Pipeline.drawio": "HLD_Migration_Wave_Pipeline.drawio",
    "HLD_Phase4_Migration_Validation_Checkpoint.drawio": "HLD_Migration_Validation_Checkpoint.drawio",
    "HLD_Phase1_Master_Journey_Map.drawio": "HLD_Master_Journey_Map.drawio",
    "HLD_Phase3_Fleet_Management_Topology.drawio": "HLD_Fleet_Management_Topology.drawio",
    "HLD_Phase4_Backup_DR_Topology.drawio": "HLD_Backup_DR_Topology.drawio",
    "HLD_Phase1_Dependency_Overlay.drawio": "HLD_Decision_Dependency_Map.drawio",
}

CLIENT_PREFIX_PATTERN = re.compile(r"^[A-Za-z0-9-]+_(HLD_.+\.drawio|LLD_.+\.drawio)$")


def _examples_dir(root: Path) -> Path:
    return root / "templates" / "Diagrams" / "examples"


def _phase_dirs(root: Path) -> list[Path]:
    diagrams_dir = root / "output" / "Diagrams"
    return [
        diagrams_dir / "phase1",
        diagrams_dir / "phase2",
        diagrams_dir / "phase3",
        diagrams_dir / "phase4",
    ]


def sanitize_content(content: str) -> str:
    for pattern, replacement in REPLACEMENTS:
        content = re.sub(pattern, replacement, content)
    return content


def get_example_name(source_filename: str) -> str:
    if source_filename in EXAMPLE_NAME_MAP:
        return EXAMPLE_NAME_MAP[source_filename]
    return source_filename


def normalize_example_filename(filename: str) -> str:
    """Normalize client-prefixed filenames to generic names.

    Example: CustomerA_HLD_Observability_Stack.drawio -> HLD_Observability_Stack.drawio
    """
    if filename in EXAMPLE_NAME_MAP:
        return EXAMPLE_NAME_MAP[filename]
    match = CLIENT_PREFIX_PATTERN.match(filename)
    if match:
        return match.group(1)
    return filename


def collect_phase_diagrams(root: Path) -> list[tuple[Path, str]]:
    diagrams = []
    for phase_dir in _phase_dirs(root):
        if not phase_dir.exists():
            continue
        for f in sorted(phase_dir.glob("*.drawio")):
            if f.name.startswith("COMBINE") or f.name.startswith("."):
                continue
            diagrams.append((f, get_example_name(f.name)))
    return diagrams


def process_phase_diagrams(root: Path) -> None:
    diagrams = collect_phase_diagrams(root)
    print(f"Processing {len(diagrams)} phase diagrams...")

    examples = _examples_dir(root)
    examples.mkdir(parents=True, exist_ok=True)

    for source_path, target_name in diagrams:
        content = source_path.read_text(encoding="utf-8")
        sanitized = sanitize_content(content)
        target_path = examples / target_name
        target_path.write_text(sanitized, encoding="utf-8")
        print(f"  {source_path.name} -> {target_name}")


def process_existing_examples(root: Path) -> None:
    print("\nSanitizing existing examples...")

    examples = _examples_dir(root)
    for f in sorted(examples.glob("*.drawio")):
        content = f.read_text(encoding="utf-8")
        sanitized = sanitize_content(content)
        normalized_name = normalize_example_filename(f.name)
        target_path = examples / normalized_name

        if target_path != f:
            target_path.write_text(sanitized, encoding="utf-8")
            f.unlink()
            print(f"  {f.name} -> {normalized_name} (renamed + sanitized)")
        elif sanitized != content:
            f.write_text(sanitized, encoding="utf-8")
            print(f"  {f.name} (sanitized)")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sanitize drawio diagrams (in-place examples by default)."
    )
    parser.add_argument(
        "--from-output",
        action="store_true",
        help="Copy output/Diagrams/phase* into templates/Diagrams/examples/",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm writes when using --from-output",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Project root (default: directory containing project.yaml)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    root = args.root.resolve() if args.root else find_project_yaml().parent
    if args.from_output and not args.yes:
        examples_rel = "templates/Diagrams/examples"
        for source_path, target_name in collect_phase_diagrams(root):
            print(f"{source_path} -> {examples_rel}/{target_name}", file=sys.stderr)
        return 2
    print("=== Diagram Sanitization ===\n")
    if args.from_output and args.yes:
        process_phase_diagrams(root)
    else:
        process_existing_examples(root)
    print("\n=== Done ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
