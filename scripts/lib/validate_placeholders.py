#!/usr/bin/env python3
"""Validate generated markdown files do not contain unresolved placeholders."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


PLACEHOLDER_RE = re.compile(r"\{[A-Z][A-Z0-9_]+\}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ensure generated files have no unresolved placeholders."
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="Markdown files to validate.",
    )
    parser.add_argument(
        "--context",
        default="generated output",
        help="Human-readable context for error messages.",
    )
    args = parser.parse_args()

    errors: list[str] = []
    for file_arg in args.files:
        path = Path(file_arg)
        if not path.exists():
            errors.append(f"{path} (missing)")
            continue
        text = path.read_text(encoding="utf-8")
        tokens = sorted({m.group(0) for m in PLACEHOLDER_RE.finditer(text) if m.group(0) != "{TBD}"})
        if tokens:
            errors.append(f"{path}: {', '.join(tokens)}")

    if errors:
        print(f"Error: unreplaced placeholders found in {args.context}:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
