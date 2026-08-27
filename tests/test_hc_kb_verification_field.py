"""Public-contract tests for KB recommendation/verification split and join."""
from __future__ import annotations

from pathlib import Path

import pytest

from hc_report.kb_loader import (
    VERIFICATION_SPLIT_LABELS,
    extra_reference_links,
    join_recommendation_parts,
    load_kb,
    split_recommendation_blob,
)


def _write_kb(tmp_path: Path, checks_toml: str) -> Path:
    (tmp_path / "versions.toml").write_text(
        '[active_versions]\nversions = ["4.21"]\n',
        encoding="utf-8",
    )
    (tmp_path / "7_1_base_platform.toml").write_text(checks_toml, encoding="utf-8")
    return tmp_path


def test_join_inserts_bold_verification_label() -> None:
    joined = join_recommendation_parts("Move etcd onto NVMe.", "1. first step")
    assert joined == "Move etcd onto NVMe.\n\n**Verification:**\n1. first step"


def test_join_omits_label_when_verification_empty() -> None:
    joined = join_recommendation_parts("Move etcd onto NVMe.", "")
    assert joined == "Move etcd onto NVMe."
    assert "Verification:" not in joined


def test_split_accepts_single_or_double_newline_before_label() -> None:
    single = split_recommendation_blob("Rec.\nVerification:\n1. x")
    double = split_recommendation_blob("Rec.\n\nVerification:\n1. x")
    assert single == ("Rec.", "1. x")
    assert double == ("Rec.", "1. x")


def test_split_rejects_second_marker() -> None:
    blob = "Rec.\nVerification:\n1. x\nVerification:\n2. y"
    with pytest.raises(ValueError, match="multiple Verification labels"):
        split_recommendation_blob(blob)


def test_content_from_inherits_verification_and_rejects_overlay(tmp_path: Path) -> None:
    _write_kb(
        tmp_path,
        """
[[checks]]
check_id = "canon.one"
title = "Canonical"
recommendation = "Canon rec"
verification = "1. confirm"

[[checks]]
check_id = "alias.one"
title = "Alias title"
content_from = "canon.one"
""",
    )
    knowledge_base = load_kb(tmp_path)
    alias_entry = knowledge_base.get_entry("alias.one")
    canonical_entry = knowledge_base.get_entry("canon.one")
    assert alias_entry is not None
    assert canonical_entry is not None
    assert alias_entry.verification == canonical_entry.verification
    assert alias_entry.verification == "1. confirm"
    assert alias_entry.recommendation == canonical_entry.recommendation

    overlay_dir = tmp_path / "overlay"
    overlay_dir.mkdir()
    _write_kb(
        overlay_dir,
        """
[[checks]]
check_id = "canon.one"
title = "Canonical"
recommendation = "Canon rec"
verification = "1. confirm"

[[checks]]
check_id = "alias.one"
title = "Alias title"
content_from = "canon.one"
verification = "overlay"
""",
    )
    with pytest.raises(ValueError, match="content_from"):
        load_kb(overlay_dir)


def test_loaded_kb_canonical_recommendation_field_has_no_verification_label() -> None:
    knowledge_base = load_kb()
    saw_verification = False
    for entry in knowledge_base.entries.values():
        if entry.content_from:
            continue
        for line in entry.recommendation.splitlines():
            assert line.strip() not in VERIFICATION_SPLIT_LABELS
        if entry.verification.strip():
            saw_verification = True
    assert saw_verification


def test_extra_reference_links_skips_default_and_version_keys() -> None:
    extras = extra_reference_links(
        {
            "default": "https://docs.example/latest",
            "4.18": "https://docs.example/4.18",
            "kcs": "https://access.redhat.com/solutions/778603",
        },
        "https://docs.example/4.18",
    )
    assert extras == ["https://access.redhat.com/solutions/778603"]


def test_chrony_recommendation_includes_kcs_and_versioned_docs() -> None:
    knowledge_base = load_kb()
    recommendation = knowledge_base.get_recommendation(
        "7.1.tsr.1_5_7_2_chrony", "4.18.0"
    )
    assert "at least three" in recommendation
    assert "**Reference:**" in recommendation
    assert "https://access.redhat.com/solutions/778603" in recommendation
    assert (
        "https://docs.redhat.com/en/documentation/openshift_container_platform/"
        "4.18/html-single/installing_on_any_platform/index"
        "#installation-special-config-chrony_installing-platform-agnostic"
        in recommendation
    )
