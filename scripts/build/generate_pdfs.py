#!/usr/bin/env python3
"""Unified PDF generation for HLD and LLD markdown documents."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from config import load_config, render_css  # noqa: E402


HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:60]


def phase_tag_from_basename(base: str) -> str:
    lower = base.lower()
    if "phase1" in lower:
        return "phase1"
    if "phase2" in lower:
        return "phase2"
    if "phase3" in lower:
        return "phase3"
    if "phase4" in lower:
        return "phase4"
    if "combined" in lower:
        return "combined"
    return "misc"


NOTDEF_RE = re.compile(
    r'WARNING:\s*\.notdef glyph rendered for Unicode string unsupported by fonts:\s*"(.+?)"\s*\(U\+([0-9A-Fa-f]+)\)'
)
CSS_IGNORED_RE = re.compile(r"WARNING:\s*Ignored\s*`.+?`\s*at\s*\d+:\d+,\s*unknown property")


def run(cmd: list[str], *, cwd: Path | None = None, filter_pdf_warnings: bool = False) -> None:
    if not filter_pdf_warnings:
        subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)
        return

    result = subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True,
    )
    bad_chars: set[str] = set()
    other_warnings: list[str] = []
    for line in result.stderr.splitlines():
        m = NOTDEF_RE.search(line)
        if m:
            bad_chars.add(f"{m.group(1)} (U+{m.group(2)})")
            continue
        if CSS_IGNORED_RE.search(line):
            continue
        if line.strip():
            other_warnings.append(line)

    for w in other_warnings:
        print(w, file=sys.stderr)

    if bad_chars:
        chars = ", ".join(sorted(bad_chars))
        print(
            f"  WARNING: {len(bad_chars)} character(s) not supported by the "
            f"bundled PDF fonts: {chars}\n"
            f"           These render as blank boxes in the PDF. Replace them "
            f"with ASCII equivalents in the markdown source to fix.",
            file=sys.stderr,
        )

    if result.returncode:
        raise subprocess.CalledProcessError(result.returncode, cmd)


def resolve_weasyprint(project_root: Path, cfg: dict) -> tuple[str, str | None]:
    venv_rel = cfg["paths"]["venv"]
    venv_root = project_root / venv_rel
    venv_weasy = venv_root / "bin" / "weasyprint"
    venv_pip = venv_root / "bin" / "pip"
    if venv_root.exists():
        if not venv_weasy.exists():
            print("Installing weasyprint into configured venv...")
            run([str(venv_pip), "install", "weasyprint"])
        return str(venv_weasy), str(venv_pip)

    system_weasy = shutil.which("weasyprint")
    if system_weasy:
        return system_weasy, None
    raise SystemExit(f"Error: weasyprint not found and venv missing at {venv_root}/bin/activate")


def substitute_mermaid(src: Path, out: Path, diagrams_dir: Path) -> None:
    basename_noext = src.stem
    phase_tag = phase_tag_from_basename(basename_noext)
    img_dir = diagrams_dir / phase_tag
    if not img_dir.exists() or not any(img_dir.iterdir()):
        shutil.copy2(src, out)
        return

    diagram_idx = 0
    in_mermaid = False
    skip_block = False
    last_heading = ""
    out_lines: list[str] = []

    for line in src.read_text(encoding="utf-8").splitlines():
        heading_match = HEADING_RE.match(line)
        if heading_match:
            last_heading = heading_match.group(1)

        if line == "```mermaid":
            in_mermaid = True
            diagram_idx += 1
            slug = slugify(last_heading)
            png = img_dir / f"{phase_tag}_{diagram_idx}_{slug}.png"
            if png.exists():
                out_lines.append(f"![{last_heading}]({png})")
                skip_block = True
            else:
                out_lines.append("```mermaid")
                skip_block = False
            continue

        if in_mermaid:
            if line == "```":
                in_mermaid = False
                if not skip_block:
                    out_lines.append("```")
                skip_block = False
            elif not skip_block:
                out_lines.append(line)
        else:
            out_lines.append(line)

    out.write_text("\n".join(out_lines) + "\n", encoding="utf-8")


def md_to_pdf(
    src: Path, pdf_dir: Path, diagrams_dir: Path, css_file: Path, weasyprint_cmd: str, *, resource_path: Path | None = None
) -> None:
    pdf = pdf_dir / f"{src.stem}.pdf"
    with tempfile.TemporaryDirectory(prefix="pdfgen-") as tmpdir:
        tmp = Path(tmpdir)
        sub_md = tmp / "sub.md"
        html = tmp / "doc.html"

        if src.name.startswith("Drawio_"):
            print("  Using Drawio variant (no mermaid substitution)")
            shutil.copy2(src, sub_md)
        else:
            print("  Substituting mermaid -> images")
            substitute_mermaid(src, sub_md, diagrams_dir)

        res_path = str(resource_path or src.parent)
        print(f"  {src.name} -> HTML")
        run(
            [
                "pandoc",
                str(sub_md),
                "-o",
                str(html),
                "--standalone",
                "--embed-resources",
                f"--resource-path={res_path}",
                f"--css={css_file}",
                "--metadata",
                "title= ",
            ]
        )

        print(f"  HTML -> {pdf.name}")
        run([weasyprint_cmd, str(html), str(pdf)], filter_pdf_warnings=True)
        size = pdf.stat().st_size / 1024
        print(f"  ✓ {pdf.name} ({size:.1f} KiB)")


def generate_phase_pdfs(
    phase_files: list[str], md_dir: Path, pdf_dir: Path, diagrams_dir: Path, css_file: Path, weasyprint_cmd: str
) -> None:
    pdf_dir.mkdir(parents=True, exist_ok=True)
    for md in phase_files:
        src = md_dir / md
        drawio_src = md_dir / f"Drawio_{md}"
        if drawio_src.exists():
            src = drawio_src
        if not src.exists():
            print(f"  Skipping {md} (not found)")
            continue
        md_to_pdf(src, pdf_dir, diagrams_dir, css_file, weasyprint_cmd, resource_path=md_dir)


def generate_combined_pdfs_hld(
    combined_files: list[str],
    md_dir: Path,
    out_md_dir: Path,
    pdf_dir: Path,
    diagrams_dir: Path,
    css_file: Path,
    weasyprint_cmd: str,
) -> None:
    if not any((md_dir / md).exists() or (out_md_dir / md).exists() for md in combined_files):
        return
    print("\n=== Generating combined PDFs ===")
    for md in combined_files:
        candidates = [
            md_dir / f"Drawio_{md}",
            out_md_dir / f"Drawio_{md}",
            md_dir / md,
            out_md_dir / md,
        ]
        src = next((p for p in candidates if p.exists()), None)
        if src is None:
            continue
        md_to_pdf(src, pdf_dir, diagrams_dir, css_file, weasyprint_cmd, resource_path=src.parent)


def generate_combined_pdfs_lld(
    combined_file: str,
    md_dir: Path,
    out_md_dir: Path,
    pdf_dir: Path,
    diagrams_dir: Path,
    css_file: Path,
    weasyprint_cmd: str,
) -> None:
    candidates = [
        md_dir / f"Drawio_{combined_file}",
        out_md_dir / f"Drawio_{combined_file}",
        md_dir / combined_file,
        out_md_dir / combined_file,
    ]
    src = next((p for p in candidates if p.exists()), None)
    if src is None:
        return
    print("\n=== Generating combined LLD PDF ===")
    md_to_pdf(src, pdf_dir, diagrams_dir, css_file, weasyprint_cmd, resource_path=src.parent)


def export_diagrams_if_needed(doc_type: str, script_dir: Path, project_root: Path) -> None:
    if doc_type == "hld":
        run(["bash", str(script_dir / "export_drawio.sh")], cwd=project_root)
        run(["bash", str(script_dir / "export_mermaid.sh"), "--type", "hld"], cwd=project_root)
    else:
        run(["bash", str(script_dir / "export_mermaid.sh"), "--type", "lld"], cwd=project_root)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate HLD/LLD PDFs.")
    parser.add_argument("--type", required=True, choices=["hld", "lld"])
    parser.add_argument("--pdf-only", action="store_true")
    parser.add_argument("--combined-only", action="store_true")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[2]
    script_dir = Path(__file__).resolve().parent
    cfg = load_config(project_root / "project.yaml")
    css = render_css(cfg, args.type)

    with tempfile.NamedTemporaryFile("w", suffix=".css", delete=False, encoding="utf-8") as f:
        f.write(css)
        css_file = Path(f.name)

    try:
        weasyprint_cmd, _ = resolve_weasyprint(project_root, cfg)
        if args.type == "hld":
            md_dir = project_root / "HLD" / "markdown_files"
            out_md_dir = Path("/output/HLD/markdown_files")
            pdf_dir = project_root / "HLD" / "PDFs"
            diagrams_dir = project_root / "HLD" / "diagrams"
            phase_files = cfg["hld"]["phase_files"]
            combined_files = cfg["hld"]["combined_files"]
        else:
            md_dir = project_root / "LLD"
            out_md_dir = Path("/output/LLD")
            pdf_dir = project_root / "LLD" / "PDFs"
            diagrams_dir = project_root / "LLD" / "diagrams"
            phase_files = [p["lld_file"] for p in cfg["phases"]]
            combined_file = cfg["lld"]["combined_file"]

        if not args.pdf_only and not args.combined_only:
            export_diagrams_if_needed(args.type, script_dir, project_root)
            print()

        if not args.combined_only:
            print(f"=== Generating phase {args.type.upper()} PDFs ===")
            generate_phase_pdfs(phase_files, md_dir, pdf_dir, diagrams_dir, css_file, weasyprint_cmd)

        if args.type == "hld":
            generate_combined_pdfs_hld(
                combined_files, md_dir, out_md_dir, pdf_dir, diagrams_dir, css_file, weasyprint_cmd
            )
        else:
            generate_combined_pdfs_lld(
                combined_file, md_dir, out_md_dir, pdf_dir, diagrams_dir, css_file, weasyprint_cmd
            )
    finally:
        css_file.unlink(missing_ok=True)

    print("\n=== Complete ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
