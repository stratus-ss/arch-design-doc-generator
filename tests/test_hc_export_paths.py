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
