"""Public-contract tests for KB documentation link review."""
from __future__ import annotations

from pathlib import Path

from hc_report.link_review.cli import run_link_review
from hc_report.link_review.finalize import (
    apply_main,
    apply_replace_rows_from_csv,
    suppress_unchanged_suggestions,
)
from hc_report.link_review.match import suggest_documentation_link
from hc_report.link_review.models import LinkSuggestion
from hc_report.link_review.parse_url import parse_documentation_url

_OPERATORS_URL_4_18 = (
    "https://docs.redhat.com/en/documentation/openshift_container_platform"
    "/4.18/html-single/operators/index"
)
_OPENSHIFT_CRDS_URL_4_18 = (
    "https://docs.openshift.com/container-platform/4.18/scalability_and_performance/"
    "planning-your-environment-according-to-object-maximums.html"
)
_REDHAT_STORAGE_URL = (
    "https://docs.redhat.com/en/documentation/openshift_container_platform/4.18/"
    "html-single/storage/index#change-default-storage-class_dynamic-provisioning"
)


def test_parse_redhat_html_single_url() -> None:
    parsed = parse_documentation_url(_REDHAT_STORAGE_URL)
    assert parsed.product == "openshift_container_platform"
    assert parsed.version == "4.18"
    assert parsed.book_slug == "storage"
    assert parsed.fragment == "change-default-storage-class_dynamic-provisioning"


def test_docs_openshift_maps_to_ocp_book() -> None:
    parsed = parse_documentation_url(_OPENSHIFT_CRDS_URL_4_18)
    assert parsed.product == "openshift_container_platform"
    assert parsed.book_slug == "scalability_and_performance"


_HAPROXY_URL_4_18 = (
    "https://docs.redhat.com/en/documentation/openshift_container_platform/4.18/"
    "html-single/networking_overview/index"
    "#configuring-ingress-cluster-traffic-ingress-controller"
)


def test_targeted_current_link_is_kept_not_replaced(tmp_path: Path) -> None:
    book_path = tmp_path / "ingress.txt"
    book_path.write_text("3.1. Configuring ingress cluster traffic\n", encoding="utf-8")
    docs_index = {
        ("openshift_container_platform", "4.18", "ingress_and_load_balancing"): book_path,
    }
    suggestion = suggest_documentation_link(
        entry_title="HAProxy HA",
        check_id="7.2.tsr.2_2_3_haproxy_ha",
        description="Confirm HAProxy high availability for ingress.",
        version_key="4.18",
        current_url=_HAPROXY_URL_4_18,
        docs_index=docs_index,
    )
    assert suggestion.verdict == "BOOK-HINT"
    assert suggestion.suggested_url == _HAPROXY_URL_4_18


def test_logging_storage_check_suggests_logging_book(tmp_path: Path) -> None:
    book_path = _write_logging_book(tmp_path)
    docs_index = {
        ("red_hat_openshift_logging", "6.5", "configuring_logging"): book_path,
    }
    suggestion = suggest_documentation_link(
        entry_title="Logging storage type",
        check_id="7.4.tsr.4_1_2_logging_storage_type",
        description="The Loki operator storage is emptyDir.",
        version_key="4.18",
        current_url=_OPERATORS_URL_4_18,
        docs_index=docs_index,
    )
    assert "red_hat_openshift_logging" in suggestion.suggested_url
    assert "configuring_logging" in suggestion.suggested_url
    assert "#" not in suggestion.suggested_url
    assert suggestion.verdict == "REPLACE"


def test_same_book_keeps_existing_fragment(tmp_path: Path) -> None:
    book_path = tmp_path / "storage.txt"
    book_path.write_text("1.3. Understanding update channels and releases\n", encoding="utf-8")
    docs_index = {
        ("openshift_container_platform", "4.18", "storage"): book_path,
    }
    suggestion = suggest_documentation_link(
        entry_title="Default storage class",
        check_id="7.3.tsr.storage_class",
        description="Confirm the default StorageClass is set.",
        version_key="4.18",
        current_url=_REDHAT_STORAGE_URL,
        docs_index=docs_index,
    )
    assert suggestion.suggested_url == _REDHAT_STORAGE_URL
    assert "1-3-understanding" not in suggestion.suggested_url


def test_http_404_clears_suggested_url(tmp_path: Path) -> None:
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()
    (kb_dir / "versions.toml").write_text(
        '[active_versions]\nversions = ["4.18"]\n',
        encoding="utf-8",
    )
    (kb_dir / "7_4_layered.toml").write_text(
        "[[checks]]\n"
        'check_id = "7.4.tsr.4_1_2_logging_storage_type"\n'
        'title = "Logging storage type"\n'
        'description = "The Loki operator storage is emptyDir."\n'
        "\n"
        "[checks.links]\n"
        f'"4.18" = "{_OPERATORS_URL_4_18}"\n',
        encoding="utf-8",
    )
    docs_root = tmp_path / "docs"
    _write_logging_book(docs_root)
    output_directory = tmp_path / "out"

    def fake_status(_url: str) -> int | str:
        return 404

    exit_code = run_link_review(
        kb_dir,
        docs_root,
        output_directory,
        validate_http=True,
        check_page_status=fake_status,
    )
    csv_text = (output_directory / "kb_link_review.csv").read_text(encoding="utf-8")
    assert exit_code == 0
    assert "HTTP-404" in csv_text


def test_cli_writes_replace_row(tmp_path: Path) -> None:
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()
    (kb_dir / "versions.toml").write_text(
        '[active_versions]\nversions = ["4.18", "4.19", "4.20", "4.21", "4.22"]\n',
        encoding="utf-8",
    )
    (kb_dir / "7_4_layered.toml").write_text(
        "[[checks]]\n"
        'check_id = "7.4.tsr.4_1_2_logging_storage_type"\n'
        'title = "Logging storage type"\n'
        'description = "The Loki operator storage is emptyDir."\n'
        "\n"
        "[checks.links]\n"
        f'"4.18" = "{_OPERATORS_URL_4_18}"\n',
        encoding="utf-8",
    )
    docs_root = tmp_path / "docs"
    _write_logging_book(docs_root)
    output_directory = tmp_path / "out"
    exit_code = run_link_review(kb_dir, docs_root, output_directory)
    csv_text = (output_directory / "kb_link_review.csv").read_text(encoding="utf-8")
    assert exit_code == 0
    assert "REPLACE" in csv_text
    assert "red_hat_openshift_logging" in csv_text


def test_proxy_with_same_url_becomes_keep() -> None:
    suggestion = LinkSuggestion(
        check_id="7.1.identity.channel",
        toml_file="7_1_base_platform.toml",
        title="Identity update channel",
        version_key="4.20",
        current_url=(
            "https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/"
            "html-single/updating_clusters/index"
            "#fast-stable-channel-strategies_understanding-update-channels-releases"
        ),
        suggested_url=(
            "https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/"
            "html-single/updating_clusters/index"
            "#fast-stable-channel-strategies_understanding-update-channels-releases"
        ),
        verdict="PROXY-4.19/4.21",
        confidence="HIGH",
        evidence="proxy match",
    )
    finalized = suppress_unchanged_suggestions([suggestion])
    assert finalized[0].verdict == "KEEP"


def test_cli_missing_docs_root_exits_nonzero(tmp_path: Path) -> None:
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()
    output_directory = tmp_path / "out"
    docs_root = tmp_path / "missing"
    exit_code = run_link_review(kb_dir, docs_root, output_directory)
    assert exit_code == 1


def test_apply_replace_row_updates_matching_link(tmp_path: Path) -> None:
    kb_directory, csv_path = _write_apply_fixture(tmp_path)
    exit_code = apply_replace_rows_from_csv(csv_path, kb_directory)
    toml_text = (kb_directory / "7_3_components.toml").read_text(encoding="utf-8")
    assert exit_code == 0
    assert 'default = "https://example.com/new-default"' in toml_text
    assert '"4.18" = "https://example.com/old-418"' in toml_text


def test_apply_refuses_stale_current_url(tmp_path: Path) -> None:
    kb_directory, csv_path = _write_apply_fixture(tmp_path)
    stale_csv = tmp_path / "stale.csv"
    stale_csv.write_text(
        csv_path.read_text(encoding="utf-8").replace(
            "https://example.com/old-default",
            "https://example.com/not-in-toml",
        ),
        encoding="utf-8",
    )
    original = (kb_directory / "7_3_components.toml").read_text(encoding="utf-8")
    exit_code = apply_replace_rows_from_csv(stale_csv, kb_directory)
    assert exit_code == 1
    assert (kb_directory / "7_3_components.toml").read_text(encoding="utf-8") == original


def test_hc_link_apply_missing_csv_exits_nonzero(tmp_path: Path) -> None:
    missing = tmp_path / "missing.csv"
    kb_directory = tmp_path / "kb"
    kb_directory.mkdir()
    assert apply_main(["--csv", str(missing), "--kb-dir", str(kb_directory)]) == 1


def _write_logging_book(docs_root: Path) -> Path:
    book_directory = docs_root / "Red_Hat_Openshift_Logging-6.5-docs" / "txt"
    book_directory.mkdir(parents=True, exist_ok=True)
    book_path = book_directory / "Red_Hat_Openshift_Logging-6.5-configuring_logging-en-US.txt"
    book_path.write_text("2.5. Configuring LokiStack storage\n", encoding="utf-8")
    return book_path


def _write_apply_fixture(tmp_path: Path) -> tuple[Path, Path]:
    kb_directory = tmp_path / "kb"
    kb_directory.mkdir()
    (kb_directory / "7_3_components.toml").write_text(
        "[[checks]]\n"
        'check_id = "7.3.demo"\n'
        'title = "Demo"\n'
        "\n"
        "[checks.links]\n"
        'default = "https://example.com/old-default"\n'
        '"4.18" = "https://example.com/old-418"\n',
        encoding="utf-8",
    )
    csv_path = tmp_path / "kb_link_review.csv"
    csv_path.write_text(
        "check_id,toml_file,title,version_key,verdict,confidence,"
        "current_url,suggested_url,evidence\n"
        "7.3.demo,7_3_components.toml,Demo,4.18,KEEP,HIGH,"
        "https://example.com/old-418,https://example.com/old-418,same book\n"
        "7.3.demo,7_3_components.toml,Demo,default,REPLACE,MEDIUM,"
        "https://example.com/old-default,https://example.com/new-default,"
        "HTTP 200 for https://example.com/new-default\n",
        encoding="utf-8",
    )
    return kb_directory, csv_path
