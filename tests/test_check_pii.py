"""Public-contract tests for the pre-commit PII scanner."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# Bug: Local denylist token in a report line is treated as ordinary prose
# Mutant: Ignore forbidden_substrings in scan_text
# Contract: public

# Bug: example.com SSH host is flagged as a personal email
# Mutant: Flag every EMAIL_PATTERN match including example.com
# Contract: public

# Bug: PEM private key in a staged markdown file is allowed
# Mutant: Remove PRIVATE_KEY_PATTERN check
# Contract: public

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "shared" / "tools" / "check_pii.py"


def _load_check_pii():
    spec = importlib.util.spec_from_file_location("check_pii", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_pii"] = module
    spec.loader.exec_module(module)
    return module


def test_local_denylist_substring_fails() -> None:
    check_pii = _load_check_pii()
    hits = check_pii.scan_text(
        "node client-canary-host.internal Ready",
        forbidden_substrings=("client-canary-host",),
    )
    assert hits
    assert any("denylist" in reason for _line, reason in hits)


def test_example_com_email_is_allowed() -> None:
    check_pii = _load_check_pii()
    hits = check_pii.scan_text(
        "make hc-fetch-results HC_SSH_HOST=user@your-supportshell-server.example.com"
    )
    assert hits == []


def test_personal_email_fails() -> None:
    check_pii = _load_check_pii()
    hits = check_pii.scan_text("contact consultant@redhat.com for login")
    assert any("non-example email" in reason for _line, reason in hits)


def test_private_key_block_fails() -> None:
    check_pii = _load_check_pii()
    hits = check_pii.scan_text("-----BEGIN PRIVATE KEY-----")
    assert any("private key" in reason for _line, reason in hits)


def test_scan_paths_skips_the_scanner_itself() -> None:
    check_pii = _load_check_pii()
    reports = check_pii.scan_paths([SCRIPT_PATH], PROJECT_ROOT)
    assert reports == []


def test_load_forbidden_substrings_skips_comments(tmp_path: Path) -> None:
    check_pii = _load_check_pii()
    list_path = tmp_path / check_pii.FORBIDDEN_LIST_NAME
    list_path.write_text("# comment\nClient-Canary-Host\n\n", encoding="utf-8")
    loaded = check_pii.load_forbidden_substrings(tmp_path)
    assert loaded == ("client-canary-host",)
