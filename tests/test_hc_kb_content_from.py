"""Public-contract tests for KB content_from resolution."""
from __future__ import annotations

from pathlib import Path

import pytest

from hc_report.kb_loader import load_kb


def _write_kb(tmp_path: Path, checks_toml: str) -> Path:
    (tmp_path / "versions.toml").write_text(
        '[active_versions]\nversions = ["4.21"]\n',
        encoding="utf-8",
    )
    (tmp_path / "7_1_base_platform.toml").write_text(checks_toml, encoding="utf-8")
    return tmp_path


def test_content_from_copies_inherited_fields_keeps_local_title(tmp_path: Path) -> None:
    _write_kb(
        tmp_path,
        """
[[checks]]
check_id = "canon.one"
title = "Canonical"
description = "Canon desc"
recommendation = "Canon rec"
impact = "none"

[checks.links]
default = "https://example.invalid/canon"

[[checks]]
check_id = "alias.one"
title = "Alias title"
content_from = "canon.one"
include_in_findings = false
""",
    )
    knowledge_base = load_kb(tmp_path)
    alias_entry = knowledge_base.get_entry("alias.one")
    canonical_entry = knowledge_base.get_entry("canon.one")
    assert alias_entry is not None
    assert canonical_entry is not None
    assert alias_entry.recommendation == canonical_entry.recommendation
    assert alias_entry.description == canonical_entry.description
    assert alias_entry.impact == canonical_entry.impact
    assert alias_entry.links == canonical_entry.links
    assert alias_entry.title == "Alias title"
    assert alias_entry.include_in_findings is False
    assert alias_entry.content_from == "canon.one"


def test_content_from_missing_target_raises(tmp_path: Path) -> None:
    _write_kb(
        tmp_path,
        """
[[checks]]
check_id = "alias.one"
title = "Alias title"
content_from = "missing.id"
""",
    )
    with pytest.raises(ValueError, match="content_from"):
        load_kb(tmp_path)


def test_content_from_self_reference_raises(tmp_path: Path) -> None:
    _write_kb(
        tmp_path,
        """
[[checks]]
check_id = "alias.one"
title = "Alias title"
content_from = "alias.one"
""",
    )
    with pytest.raises(ValueError, match="content_from"):
        load_kb(tmp_path)


def test_content_from_chain_raises(tmp_path: Path) -> None:
    _write_kb(
        tmp_path,
        """
[[checks]]
check_id = "c.one"
title = "C"
recommendation = "C rec"

[[checks]]
check_id = "b.one"
title = "B"
content_from = "c.one"

[[checks]]
check_id = "a.one"
title = "A"
content_from = "b.one"
""",
    )
    with pytest.raises(ValueError, match="content_from"):
        load_kb(tmp_path)


def test_content_from_alias_inherited_fields_raise(tmp_path: Path) -> None:
    _write_kb(
        tmp_path,
        """
[[checks]]
check_id = "canon.one"
title = "Canonical"
recommendation = "Canon rec"

[[checks]]
check_id = "alias.one"
title = "Alias title"
content_from = "canon.one"
recommendation = "overlay"
""",
    )
    with pytest.raises(ValueError, match="content_from"):
        load_kb(tmp_path)


def test_content_from_pattern_entry_raises(tmp_path: Path) -> None:
    _write_kb(
        tmp_path,
        """
[[checks]]
check_id = "canon.one"
title = "Canonical"
recommendation = "Canon rec"

[[checks]]
check_id = "7.x.star.*"
pattern = true
content_from = "canon.one"
""",
    )
    with pytest.raises(ValueError, match="content_from"):
        load_kb(tmp_path)


def test_validating_and_mutating_webhook_stories_differ() -> None:
    knowledge_base = load_kb()
    validating = knowledge_base.get_entry("7.3.webhooks.validatingwebhooks")
    mutating = knowledge_base.get_entry("7.3.webhooks.mutatingwebhooks")
    assert validating is not None
    assert mutating is not None
    assert validating.description != mutating.description
    assert "admit or deny" in validating.description
    assert "rewrite" in mutating.description
