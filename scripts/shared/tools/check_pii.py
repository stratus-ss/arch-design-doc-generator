#!/usr/bin/env python3
"""Scan files for credential material, non-example emails, and local denylist hits.

Used by `make check-pii` and `.githooks/pre-commit`. Does not rewrite files.

Engagement-specific substrings belong in gitignored `.pii_forbidden.txt`,
not in this script. Copy `.pii_forbidden.example.txt` to start a local list.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

SKIP_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".pdf",
    ".xlsx",
    ".pyc",
    ".woff",
    ".woff2",
}

SKIP_PATH_PARTS = {
    "scripts/shared/tools/check_pii.py",
    "tests/test_check_pii.py",
}

FORBIDDEN_LIST_NAME = ".pii_forbidden.txt"

ALLOWED_EMAIL_SUFFIXES = (
    "example.com",
    "example.org",
)

EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b"
)
PRIVATE_KEY_PATTERN = re.compile(
    r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"
)
AWS_KEY_PATTERN = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
KUBE_KEY_DATA_PATTERN = re.compile(
    r"(?i)client-key-data:\s*[A-Za-z0-9+/=]{40,}"
)


def _is_skipped_path(path: Path, repo_root: Path) -> bool:
    try:
        relative = path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        relative = path.as_posix()
    if relative in SKIP_PATH_PARTS:
        return True
    return path.suffix.lower() in SKIP_SUFFIXES


def load_forbidden_substrings(repo_root: Path) -> tuple[str, ...]:
    """Load case-folded substrings from the gitignored local denylist."""
    list_path = repo_root / FORBIDDEN_LIST_NAME
    if not list_path.is_file():
        return ()
    substrings: list[str] = []
    try:
        text = list_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        substrings.append(stripped.casefold())
    return tuple(substrings)


def _email_domain_allowed(domain: str) -> bool:
    folded = domain.casefold()
    for suffix in ALLOWED_EMAIL_SUFFIXES:
        if folded == suffix or folded.endswith("." + suffix):
            return True
    return False


def _email_findings(line: str) -> list[str]:
    findings: list[str] = []
    for match in EMAIL_PATTERN.finditer(line):
        if _email_domain_allowed(match.group(1)):
            continue
        findings.append(f"non-example email {match.group(0)}")
    return findings


def scan_text(
    text: str,
    forbidden_substrings: Sequence[str] = (),
) -> list[tuple[int, str]]:
    """Return (line_number, reason) for each hit."""
    hits: list[tuple[int, str]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        folded = line.casefold()
        for substring in forbidden_substrings:
            if substring and substring in folded:
                hits.append((line_number, "local denylist substring match"))
        if PRIVATE_KEY_PATTERN.search(line):
            hits.append((line_number, "private key block"))
        if AWS_KEY_PATTERN.search(line):
            hits.append((line_number, "AWS access key id"))
        if KUBE_KEY_DATA_PATTERN.search(line):
            hits.append((line_number, "kubeconfig client-key-data"))
        for reason in _email_findings(line):
            hits.append((line_number, reason))
    return hits


def _listed_git_files(repo_root: Path, staged: bool) -> list[Path]:
    command = ["git", "-C", str(repo_root), "diff", "--cached", "--name-only", "--diff-filter=ACMR"]
    if not staged:
        command = ["git", "-C", str(repo_root), "ls-files"]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    paths = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        paths.append(repo_root / line)
    return paths


def scan_paths(
    paths: list[Path],
    repo_root: Path,
    forbidden_substrings: Sequence[str] = (),
) -> list[str]:
    reports: list[str] = []
    for path in paths:
        if not path.is_file() or _is_skipped_path(path, repo_root):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as error:
            reports.append(f"{path}: unreadable ({error})")
            continue
        for line_number, reason in scan_text(text, forbidden_substrings):
            relative = path
            try:
                relative = path.resolve().relative_to(repo_root.resolve())
            except ValueError:
                pass
            reports.append(f"{relative}:{line_number}: {reason}")
    return reports


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Files to scan (default: all git-tracked files)",
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Scan git staged files only",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root (default: cwd)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = (args.repo_root or Path.cwd()).resolve()
    forbidden_substrings = load_forbidden_substrings(repo_root)
    if args.paths:
        paths = [path if path.is_absolute() else repo_root / path for path in args.paths]
    else:
        paths = _listed_git_files(repo_root, staged=args.staged)
    reports = scan_paths(paths, repo_root, forbidden_substrings)
    if reports:
        print("PII or secret material found:", file=sys.stderr)
        for report in reports:
            print(report, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
