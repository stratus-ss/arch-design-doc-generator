#!/usr/bin/env python3
"""Generate Drawio_* markdown variants for HLD/LLD documents."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from config import load_config  # noqa: E402


HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$")
MD_LINK_RE = re.compile(r"\(([^)]+\.md)\)")


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


def drawio_rel_path(doc_type: str, phase_tag: str, image_name: str) -> str:
    if doc_type == "hld":
        return f"../../Diagrams/{phase_tag}/{image_name}"
    return f"../Diagrams/{phase_tag}/{image_name}"


def mermaid_rel_path(doc_type: str, phase_tag: str, image_name: str) -> str:
    if doc_type == "hld":
        return f"../diagrams/{phase_tag}/{image_name}"
    return f"diagrams/{phase_tag}/{image_name}"


def generate_variant(
    src: Path,
    out: Path,
    *,
    doc_type: str,
    doc_prefix: str,
    diagrams_root: Path,
    mermaid_png_dir: Path,
) -> None:
    base_noext = src.stem
    phase_tag = phase_tag_from_basename(base_noext)
    in_mermaid = False
    skip_block = False
    last_heading = ""
    diagram_idx = 0
    slug_seen: dict[str, int] = {}
    out_lines: list[str] = []

    for line in src.read_text(encoding="utf-8").splitlines():
        heading_match = HEADING_RE.match(line)
        if heading_match:
            last_heading = heading_match.group(1)

        if line == "```mermaid":
            in_mermaid = True
            diagram_idx += 1
            slug = slugify(last_heading) or f"diagram-{diagram_idx}"
            seen = slug_seen.get(slug, 0) + 1
            slug_seen[slug] = seen

            drawio_base = f"{doc_prefix}_{phase_tag}_{slug}"
            if seen > 1:
                drawio_base = f"{drawio_base}_{seen}"

            drawio_name = f"{drawio_base}.drawio.png"
            drawio_abs = diagrams_root / phase_tag / drawio_name
            alt_text = last_heading or f"Diagram {diagram_idx}"

            if drawio_abs.exists():
                out_lines.append(f"![{alt_text}]({drawio_rel_path(doc_type, phase_tag, drawio_name)})")
                skip_block = True
            else:
                mermaid_name = f"{phase_tag}_{diagram_idx}_{slug}.png"
                mermaid_abs = mermaid_png_dir / phase_tag / mermaid_name
                if mermaid_abs.exists():
                    out_lines.append(f"![{alt_text}]({mermaid_rel_path(doc_type, phase_tag, mermaid_name)})")
                    skip_block = True
                else:
                    out_lines.append("```mermaid")
                    skip_block = False
                    print(
                        f"  WARNING: Diagram image not found — the diagram "
                        f"'{alt_text}' in {base_noext} has no exported PNG.\n"
                        f"           The raw mermaid code will be kept inline "
                        f"(it won't render in the PDF).\n"
                        f"           To fix: run the mermaid export step first, "
                        f"or provide a .drawio.png at:\n"
                        f"             {drawio_abs}",
                        file=sys.stderr,
                    )
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


def resolve_stitchmd() -> str:
    stitchmd = os.environ.get("STITCHMD", "stitchmd")
    if shutil_which(stitchmd):
        return stitchmd
    fallback = str(Path.home() / "go" / "bin" / "stitchmd")
    if Path(fallback).is_file():
        return fallback
    raise SystemExit("Error: stitchmd not found. Install with: go install go.abhg.dev/stitchmd@latest")


def shutil_which(cmd: str) -> str | None:
    from shutil import which

    return which(cmd)


def run_stitchmd(stitchmd: str, output: Path, summary: Path) -> None:
    subprocess.run(
        [stitchmd, "-no-toc", "-o", str(output), str(summary)],
        check=True,
    )


def generate_hld(cfg: dict, project_root: Path) -> None:
    md_dir = project_root / "HLD" / "markdown_files"
    diagrams_root = project_root / "Diagrams"
    mermaid_png_dir = project_root / "HLD" / "diagrams"
    summary_map = cfg.get("hld", {}).get("summary_map", {})
    stitchmd = resolve_stitchmd()
    generated: set[str] = set()

    def generate_one_if_needed(rel: str) -> None:
        if not rel or rel in generated:
            return
        src = md_dir / rel
        out = md_dir / f"Drawio_{rel}"
        if src.exists():
            generate_variant(
                src,
                out,
                doc_type="hld",
                doc_prefix="HLD",
                diagrams_root=diagrams_root,
                mermaid_png_dir=mermaid_png_dir,
            )
            generated.add(rel)
            print(f"  {rel} -> Drawio_{rel}")

    print("=== Generating Drawio variants for HLD ===")
    for _, entry in sorted(summary_map.items()):
        summary = entry.get("summary", "")
        output = entry.get("output", "")
        summary_src = md_dir / summary
        if not summary_src.exists():
            continue

        drawio_summary = md_dir / f"Drawio_{summary}"
        out_lines: list[str] = []
        for line in summary_src.read_text(encoding="utf-8").splitlines():
            replaced = line
            for linked in MD_LINK_RE.findall(line):
                generate_one_if_needed(linked)
                replaced = replaced.replace(f"({linked})", f"(Drawio_{linked})")
            out_lines.append(replaced)
        drawio_summary.write_text("\n".join(out_lines) + "\n", encoding="utf-8")

        drawio_output = md_dir / f"Drawio_{output}"
        run_stitchmd(stitchmd, drawio_output, drawio_summary)
        print(f"  {drawio_summary.name} -> {drawio_output.name}")
    print("Done.")


def generate_lld(cfg: dict, project_root: Path) -> None:
    md_dir = project_root / "LLD"
    diagrams_root = project_root / "Diagrams"
    mermaid_png_dir = project_root / "LLD" / "diagrams"
    phase_files = [p["lld_file"] for p in cfg.get("phases", [])]
    combined_file = cfg["lld"]["combined_file"]
    combined_title = cfg["lld"]["combined_title"]

    print("=== Generating Drawio variants for LLD ===")
    for md in phase_files:
        src = md_dir / md
        if not src.exists():
            continue
        out = md_dir / f"Drawio_{md}"
        generate_variant(
            src,
            out,
            doc_type="lld",
            doc_prefix="LLD",
            diagrams_root=diagrams_root,
            mermaid_png_dir=mermaid_png_dir,
        )
        print(f"  {md} -> Drawio_{md}")

    drawio_combined = md_dir / f"Drawio_{combined_file}"
    lines = [
        f"# {combined_title}",
        "",
        "> **Combined document** — all phase LLDs stitched into one file for review.",
        "",
        "---",
        "",
    ]
    first = True
    for md in phase_files:
        src = md_dir / f"Drawio_{md}"
        if not src.exists():
            continue
        if not first:
            lines.extend(["", "---", ""])
        first = False
        lines.append(src.read_text(encoding="utf-8").rstrip("\n"))
    drawio_combined.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
    print(f"  Drawio combined -> {drawio_combined.name}")
    print("Done.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Drawio markdown variants.")
    parser.add_argument("--type", required=True, choices=["hld", "lld"], help="Document type.")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[2]
    cfg = load_config(project_root / "project.yaml")
    if args.type == "hld":
        generate_hld(cfg, project_root)
    else:
        generate_lld(cfg, project_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
