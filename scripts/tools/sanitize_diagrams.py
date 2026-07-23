#!/usr/bin/env python3
"""
Sanitize .drawio diagrams by replacing client-specific references with
generic placeholders.

Processes:
  1. All HLD + LLD .drawio files from Diagrams/phase1-4/ -> Diagrams/examples/
  2. Existing files in Diagrams/examples/ (in-place sanitization)
  3. Renames client-prefixed files to generic names

Run from anywhere — paths are resolved relative to the repo root.
"""

import re
from pathlib import Path

from sanitize_diagrams_data import REPLACEMENTS

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent

DIAGRAMS_DIR = PROJECT_ROOT / "Diagrams"
EXAMPLES_DIR = DIAGRAMS_DIR / "examples"

PHASE_DIRS = [
    DIAGRAMS_DIR / "phase1",
    DIAGRAMS_DIR / "phase2",
    DIAGRAMS_DIR / "phase3",
    DIAGRAMS_DIR / "phase4",
]

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


def collect_phase_diagrams() -> list[tuple[Path, str]]:
    diagrams = []
    for phase_dir in PHASE_DIRS:
        if not phase_dir.exists():
            continue
        for f in sorted(phase_dir.glob("*.drawio")):
            if f.name.startswith("COMBINE") or f.name.startswith("."):
                continue
            diagrams.append((f, get_example_name(f.name)))
    return diagrams


def process_phase_diagrams() -> None:
    diagrams = collect_phase_diagrams()
    print(f"Processing {len(diagrams)} phase diagrams...")

    EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)

    for source_path, target_name in diagrams:
        content = source_path.read_text(encoding="utf-8")
        sanitized = sanitize_content(content)
        target_path = EXAMPLES_DIR / target_name
        target_path.write_text(sanitized, encoding="utf-8")
        print(f"  {source_path.name} -> {target_name}")


def process_existing_examples() -> None:
    print("\nSanitizing existing examples...")

    for f in sorted(EXAMPLES_DIR.glob("*.drawio")):
        content = f.read_text(encoding="utf-8")
        sanitized = sanitize_content(content)
        normalized_name = normalize_example_filename(f.name)
        target_path = EXAMPLES_DIR / normalized_name

        if target_path != f:
            target_path.write_text(sanitized, encoding="utf-8")
            f.unlink()
            print(f"  {f.name} -> {normalized_name} (renamed + sanitized)")
        elif sanitized != content:
            f.write_text(sanitized, encoding="utf-8")
            print(f"  {f.name} (sanitized)")


def main() -> None:
    print("=== Diagram Sanitization ===\n")
    process_phase_diagrams()
    process_existing_examples()
    print("\n=== Done ===")


if __name__ == "__main__":
    main()
