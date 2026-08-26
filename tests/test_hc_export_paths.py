from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RENDERING_ROOT = PROJECT_ROOT / "scripts" / "shared" / "rendering"


def _load_export_paths():
    rendering_root = str(RENDERING_ROOT)
    if rendering_root not in sys.path:
        sys.path.insert(0, rendering_root)
    import hc_export_paths

    return hc_export_paths


def test_draft_targets_from_generate_log_uses_only_written_reports() -> None:
    # Bug: hc-report drafted every markdown under output/Health_Check_Report
    # Mutant: treat any path mentioned in generate stdout as a draft target
    hc_export_paths = _load_export_paths()
    log_text = (
        "Loading results from: output/hc_collect/2026-08-10/04502902\n"
        "Report written to: /workspace/output/Health_Check_Report/new_cluster.md\n"
        "Also see leftover: /workspace/output/Health_Check_Report/old_cluster.md\n"
    )

    targets = hc_export_paths.draft_targets_from_generate_log(log_text)

    assert targets == [
        Path("/workspace/output/Health_Check_Report/new_cluster.md")
    ]


def test_draft_targets_from_generate_log_prefers_pruned_peer() -> None:
    # Bug: this-run full and pruned reports were both drafted
    # Mutant: skip _prefer_pruned_markdown on generate-log paths
    hc_export_paths = _load_export_paths()
    log_text = (
        "Report written to: /workspace/output/Health_Check_Report/Example.md\n"
        "Pruned report written to: "
        "/workspace/output/Health_Check_Report/Example_pruned.md\n"
    )

    targets = hc_export_paths.draft_targets_from_generate_log(log_text)

    assert targets == [
        Path("/workspace/output/Health_Check_Report/Example_pruned.md")
    ]


def test_draft_targets_from_generate_log_empty_when_no_written_lines() -> None:
    # Bug: empty parse fell back to globbing every report markdown
    # Mutant: return a default report path when no written-to lines exist
    hc_export_paths = _load_export_paths()

    targets = hc_export_paths.draft_targets_from_generate_log(
        "Deriving cluster metadata...\n"
    )

    assert targets == []


def test_discover_report_markdown_prefers_pruned_peer(tmp_path: Path) -> None:
    hc_export_paths = _load_export_paths()
    report_directory = tmp_path / "Health_Check_Report"
    report_directory.mkdir()
    original = report_directory / "Example_OpenShift_Health_Check_x.md"
    pruned = report_directory / "Example_OpenShift_Health_Check_x_pruned.md"
    original.write_text("full", encoding="utf-8")
    pruned.write_text("pruned", encoding="utf-8")

    discovered = hc_export_paths.discover_report_markdown(report_directory)

    assert discovered == [pruned.resolve()]


def test_nested_same_basename_maps_to_cluster_subdirectories(tmp_path: Path) -> None:
    hc_export_paths = _load_export_paths()
    report_directory = tmp_path / "Health_Check_Report"
    first_cluster = report_directory / "dr-ocp-01"
    second_cluster = report_directory / "prod-ocp-01"
    first_cluster.mkdir(parents=True)
    second_cluster.mkdir(parents=True)
    filename = "Example_OpenShift_Health_Check_version.md"
    (first_cluster / filename).write_text("rar", encoding="utf-8")
    (second_cluster / filename).write_text("arl", encoding="utf-8")
    export_root = tmp_path / "PDFs"

    mapping = hc_export_paths.build_export_mapping(report_directory, export_root, "pdf")
    destinations = {destination for _source, destination in mapping}

    expected_first = (export_root / "dr-ocp-01" / "Example_OpenShift_Health_Check_version.pdf").resolve()
    expected_second = (export_root / "prod-ocp-01" / "Example_OpenShift_Health_Check_version.pdf").resolve()
    assert expected_first in destinations
    assert expected_second in destinations
    assert len(destinations) == 2


def test_top_level_markdown_maps_flat_under_export_root(tmp_path: Path) -> None:
    hc_export_paths = _load_export_paths()
    report_directory = tmp_path / "Health_Check_Report"
    report_directory.mkdir()
    (report_directory / "Example_OpenShift_Health_Check_one-6x489.md").write_text(
        "top", encoding="utf-8"
    )
    export_root = tmp_path / "PDFs"

    mapping = hc_export_paths.build_export_mapping(report_directory, export_root, "pdf")
    destinations = [destination for _source, destination in mapping]

    assert destinations == [
        (export_root / "Example_OpenShift_Health_Check_one-6x489.pdf").resolve()
    ]


def test_markdown_under_html_or_pdfs_is_not_discovered(tmp_path: Path) -> None:
    hc_export_paths = _load_export_paths()
    report_directory = tmp_path / "Health_Check_Report"
    html_directory = report_directory / "HTML"
    pdf_directory = report_directory / "PDFs"
    html_directory.mkdir(parents=True)
    pdf_directory.mkdir(parents=True)
    (html_directory / "leftover.md").write_text("html", encoding="utf-8")
    (pdf_directory / "leftover.md").write_text("pdf", encoding="utf-8")

    discovered = hc_export_paths.discover_report_markdown(report_directory)

    assert discovered == []


def test_depth_three_markdown_is_not_discovered(tmp_path: Path) -> None:
    hc_export_paths = _load_export_paths()
    report_directory = tmp_path / "Health_Check_Report"
    nested = report_directory / "cluster" / "sub"
    nested.mkdir(parents=True)
    (nested / "deep.md").write_text("deep", encoding="utf-8")

    discovered = hc_export_paths.discover_report_markdown(report_directory)

    assert discovered == []


def test_duplicate_output_path_raises_collision(tmp_path: Path) -> None:
    hc_export_paths = _load_export_paths()
    cluster_directory = tmp_path / "Health_Check_Report" / "dr-ocp-01"
    cluster_directory.mkdir(parents=True)
    (cluster_directory / "report.md").write_text("one", encoding="utf-8")
    (cluster_directory / "report.pdf.md").write_text("two", encoding="utf-8")
    export_root = tmp_path / "PDFs"

    with pytest.raises(hc_export_paths.ExportPathCollision):
        hc_export_paths.build_export_mapping(
            tmp_path / "Health_Check_Report", export_root, "pdf"
        )


def test_cli_prints_tab_separated_source_and_destination(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    hc_export_paths = _load_export_paths()
    report_directory = tmp_path / "Health_Check_Report"
    report_directory.mkdir()
    (report_directory / "cluster.md").write_text("cli", encoding="utf-8")
    export_root = tmp_path / "PDFs"

    status = hc_export_paths.main([str(report_directory), str(export_root), "pdf"])
    captured = capsys.readouterr()
    lines = [line for line in captured.out.splitlines() if line]

    assert status == 0
    assert len(lines) == 1
    assert lines[0].count("\t") == 1
    source_text, destination_text = lines[0].split("\t")
    assert destination_text.endswith(".pdf")
    assert Path(source_text).name == "cluster.md"


def test_cli_exits_nonzero_when_no_exportable_markdown(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    hc_export_paths = _load_export_paths()
    report_directory = tmp_path / "Health_Check_Report"
    html_directory = report_directory / "HTML"
    html_directory.mkdir(parents=True)
    (html_directory / "foo.md").write_text("skip", encoding="utf-8")
    export_root = tmp_path / "PDFs"

    status = hc_export_paths.main([str(report_directory), str(export_root), "pdf"])
    captured = capsys.readouterr()

    assert status == 1
    assert "no report markdown found" in captured.err


def test_named_source_exports_exact_file_and_warns_if_pruned_sibling(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Bug: in-tree REPORT=Foo.md silently exports Foo_pruned.md or omits banner
    # Mutant: _prefer_pruned_markdown on named export, skip banner, or warn only out-of-tree
    hc_export_paths = _load_export_paths()
    report_directory = tmp_path / "Health_Check_Report"
    report_directory.mkdir()
    named = report_directory / "Foo.md"
    pruned = report_directory / "Foo_pruned.md"
    named.write_text("full", encoding="utf-8")
    pruned.write_text("pruned", encoding="utf-8")
    export_root = tmp_path / "PDFs"

    status = hc_export_paths.main(
        [str(report_directory), str(export_root), "pdf", "--source", str(named)]
    )
    captured = capsys.readouterr()
    lines = [line for line in captured.out.splitlines() if line]
    source_text, destination_text = lines[0].split("\t")

    assert status == 0
    assert Path(source_text).resolve() == named.resolve()
    assert Path(destination_text).name == "Foo.pdf"
    assert "WARNING: PRUNED SIBLING IGNORED" in captured.err


def test_out_of_tree_source_maps_basename_and_warns(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Bug: out-of-tree source raises, is refused, or keeps a cluster prefix
    # Mutant: relative_to(report_directory) without is_relative_to; skip location banner
    hc_export_paths = _load_export_paths()
    report_directory = tmp_path / "Health_Check_Report"
    report_directory.mkdir()
    outside = tmp_path / "scratch" / "Outside.md"
    outside.parent.mkdir()
    outside.write_text("outside", encoding="utf-8")
    export_root = tmp_path / "PDFs"

    status = hc_export_paths.main(
        [
            str(report_directory),
            str(export_root),
            "pdf",
            "--source",
            str(outside),
        ]
    )
    captured = capsys.readouterr()
    lines = [line for line in captured.out.splitlines() if line]
    _source_text, destination_text = lines[0].split("\t")

    assert status == 0
    assert Path(destination_text).resolve() == (export_root / "Outside.pdf").resolve()
    assert "WARNING: SOURCE OUTSIDE REPORT TREE" in captured.err


def test_in_tree_regenerate_does_not_require_overwrite_consent(
    tmp_path: Path,
) -> None:
    # Bug: in-tree re-export exits 4 whenever dest exists
    # Mutant: destination.exists() always requires consent
    hc_export_paths = _load_export_paths()
    report_directory = tmp_path / "Health_Check_Report"
    report_directory.mkdir()
    named = report_directory / "Regen.md"
    named.write_text("report", encoding="utf-8")
    export_root = tmp_path / "PDFs"
    export_root.mkdir()
    existing = export_root / "Regen.pdf"
    existing.write_bytes(b"old-pdf")

    status = hc_export_paths.main(
        [str(report_directory), str(export_root), "pdf", "--source", str(named)]
    )

    assert status == 0
    assert existing.read_bytes() == b"old-pdf"


def test_out_of_tree_existing_destination_requires_allow_overwrite(
    tmp_path: Path,
) -> None:
    # Bug: basename dest silently overwrites; or --allow-overwrite ignored
    # Mutant: skip dest-exists for out-of-tree; ignore --allow-overwrite
    hc_export_paths = _load_export_paths()
    report_directory = tmp_path / "Health_Check_Report"
    report_directory.mkdir()
    outside = tmp_path / "scratch" / "Clash.md"
    outside.parent.mkdir()
    outside.write_text("outside", encoding="utf-8")
    export_root = tmp_path / "PDFs"
    export_root.mkdir()
    existing = export_root / "Clash.pdf"
    existing.write_bytes(b"keep-me")

    refused = hc_export_paths.main(
        [
            str(report_directory),
            str(export_root),
            "pdf",
            "--source",
            str(outside),
        ]
    )
    allowed = hc_export_paths.main(
        [
            str(report_directory),
            str(export_root),
            "pdf",
            "--source",
            str(outside),
            "--allow-overwrite",
        ]
    )

    assert refused == 4
    assert existing.read_bytes() == b"keep-me"
    assert allowed == 0


def test_cli_named_source_missing_exits_nonzero_without_discovering(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Bug: missing --source falls through to discover-all
    # Mutant: empty/missing source ignored; run build_export_mapping
    hc_export_paths = _load_export_paths()
    report_directory = tmp_path / "Health_Check_Report"
    report_directory.mkdir()
    other = report_directory / "Other.md"
    other.write_text("other", encoding="utf-8")
    missing = report_directory / "Missing.md"
    export_root = tmp_path / "PDFs"

    status = hc_export_paths.main(
        [
            str(report_directory),
            str(export_root),
            "pdf",
            "--source",
            str(missing),
        ]
    )
    captured = capsys.readouterr()

    assert status == 1
    assert "Other.md" not in captured.out
    assert "report not found" in captured.err


def test_named_source_sidecar_exits_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Bug: --source exports _summary_conclusion.md
    # Mutant: skip _is_sidecar_markdown for --source
    hc_export_paths = _load_export_paths()
    report_directory = tmp_path / "Health_Check_Report"
    report_directory.mkdir()
    sidecar = report_directory / "Foo_summary_conclusion.md"
    sidecar.write_text("sidecar", encoding="utf-8")
    export_root = tmp_path / "PDFs"

    status = hc_export_paths.main(
        [
            str(report_directory),
            str(export_root),
            "pdf",
            "--source",
            str(sidecar),
        ]
    )
    captured = capsys.readouterr()

    assert status == 1
    assert "sidecar" in captured.err.lower()
