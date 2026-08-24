#!/usr/bin/env python3
"""Split combined recommendation blobs into recommendation + verification keys.

Usage:
  python3 scripts/health_check/split_kb_verification.py --dry-run
  python3 scripts/health_check/split_kb_verification.py
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "shared" / "lib"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "health_check"))

from hc_report.kb_loader import (  # noqa: E402
    VERIFICATION_SPLIT_LABELS,
    split_recommendation_blob,
)

KB_DIR = REPO_ROOT / "scripts" / "health_check" / "hc_report" / "kb"
CHECK_TABLE_START = re.compile(r"^\[\[checks\]\]", re.MULTILINE)
UNKNOWN_VERIFICATION_HEADING = re.compile(
    r"^\*{0,2}verif(?:y|ication)\b.*",
    re.IGNORECASE,
)


@dataclass
class RewriteCounts:
    rewritten: int = 0
    skipped_alias: int = 0
    skipped_already_split: int = 0
    skipped_no_marker: int = 0
    proposed: list[str] = field(default_factory=list)


def escape_toml_basic_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def parse_toml_basic_string(source: str, start: int) -> tuple[str, int]:
    if start >= len(source) or source[start] != '"':
        raise ValueError("expected TOML basic string")
    index = start + 1
    while index < len(source):
        char = source[index]
        if char == "\\":
            index += 2
            continue
        if char == '"':
            literal = source[start : index + 1]
            parsed = tomllib.loads(f"value = {literal}")
            return str(parsed["value"]), index + 1
        if char == "\n":
            raise ValueError("unterminated TOML basic string")
        index += 1
    raise ValueError("unterminated TOML basic string")


def find_unknown_verification_label(blob: str) -> str:
    for line in blob.replace("\r\n", "\n").split("\n"):
        stripped = line.strip()
        if stripped in VERIFICATION_SPLIT_LABELS:
            continue
        if UNKNOWN_VERIFICATION_HEADING.fullmatch(stripped):
            return stripped
    return ""


def locate_basic_string_assignment(block: str, key: str) -> tuple[int, int, str] | None:
    pattern = re.compile(rf"^{re.escape(key)}\s*=\s*", re.MULTILINE)
    match = pattern.search(block)
    if match is None:
        return None
    rest_index = match.end()
    rest = block[rest_index:]
    if rest.startswith('"""') or rest.startswith("'''"):
        raise ValueError(f"{key} uses a triple-quoted string")
    if not rest.startswith('"'):
        raise ValueError(f"{key} is not a one-line basic string")
    _value, end_index = parse_toml_basic_string(block, rest_index)
    return match.start(), end_index, block[match.start() : end_index]


def replace_recommendation_assignment(
    block: str,
    rec_part: str,
    ver_part: str,
) -> str:
    located = locate_basic_string_assignment(block, "recommendation")
    if located is None:
        raise ValueError("missing recommendation assignment")
    start, end, _assignment = located
    new_assignment = f"recommendation = {escape_toml_basic_string(rec_part)}"
    if ver_part:
        new_assignment += f"\nverification = {escape_toml_basic_string(ver_part)}"
    return block[:start] + new_assignment + block[end:]


def preview_text(value: str) -> str:
    flattened = " ".join(value.split())
    if len(flattened) <= 80:
        return flattened
    return flattened[:80]


def rewrite_check_block(
    block: str,
    entry: dict,
    counts: RewriteCounts,
    dry_run: bool,
) -> str:
    check_id = str(entry.get("check_id", "")).strip()
    if str(entry.get("content_from", "")).strip():
        counts.skipped_alias += 1
        return block
    recommendation = str(entry.get("recommendation", ""))
    existing_verification = str(entry.get("verification", "")).strip()
    unknown_label = find_unknown_verification_label(recommendation)
    if unknown_label:
        raise ValueError(
            f"{check_id}: unknown verification label {unknown_label!r}"
        )
    rec_has_marker = False
    for line in recommendation.replace("\r\n", "\n").split("\n"):
        if line.strip() in VERIFICATION_SPLIT_LABELS:
            rec_has_marker = True
            break
    if existing_verification and rec_has_marker:
        raise ValueError(
            f"{check_id}: verification is set but recommendation still has a split label"
        )
    if existing_verification and not rec_has_marker:
        counts.skipped_already_split += 1
        return block
    rec_part, ver_part = split_recommendation_blob(recommendation)
    if not ver_part:
        counts.skipped_no_marker += 1
        return block
    counts.rewritten += 1
    counts.proposed.append(
        f"{check_id}: rec={preview_text(rec_part)!r} ver={preview_text(ver_part)!r}"
    )
    if dry_run:
        return block
    if locate_basic_string_assignment(block, "recommendation") is None:
        raise ValueError(f"{check_id}: recommendation is not a one-line basic string")
    return replace_recommendation_assignment(block, rec_part, ver_part)


def split_check_blocks(text: str) -> list[str]:
    starts = [match.start() for match in CHECK_TABLE_START.finditer(text)]
    if not starts:
        return [text]
    chunks: list[str] = []
    if starts[0] > 0:
        chunks.append(text[: starts[0]])
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(text)
        chunks.append(text[start:end])
    return chunks


def load_entry_from_block(block: str) -> dict | None:
    if not block.startswith("[[checks]]"):
        return None
    parsed = tomllib.loads(block)
    checks = parsed.get("checks", [])
    if not checks:
        return None
    return checks[0]


def process_file(path: Path, counts: RewriteCounts, dry_run: bool) -> None:
    original = path.read_text(encoding="utf-8")
    rewritten_chunks: list[str] = []
    for block in split_check_blocks(original):
        entry = load_entry_from_block(block)
        if entry is None:
            rewritten_chunks.append(block)
            continue
        rewritten_chunks.append(rewrite_check_block(block, entry, counts, dry_run))
    if dry_run:
        return
    new_text = "".join(rewritten_chunks)
    if new_text != original:
        path.write_text(new_text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Split KB recommendation blobs into recommendation and verification."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print proposed splits without writing TOML files.",
    )
    args = parser.parse_args()
    counts = RewriteCounts()
    try:
        for path in sorted(KB_DIR.glob("7_*.toml")):
            process_file(path, counts, args.dry_run)
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if args.dry_run:
        for line in counts.proposed:
            print(line)
    print(
        "rewritten="
        f"{counts.rewritten} skipped_alias={counts.skipped_alias} "
        f"skipped_already_split={counts.skipped_already_split} "
        f"skipped_no_marker={counts.skipped_no_marker}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
