#!/usr/bin/env python3
"""Generate Drawio_* markdown variants for HLD/LLD documents."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

from config import find_project_yaml, load_config
from diagram_layout import phase_tag_from_basename, slugify

HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$")
MD_LINK_RE = re.compile(r"\(([^)]+\.md)\)")
DRAWIO_ANNOTATION_RE = re.compile(r"<!--\s*drawio:\s*(.+?)\s*-->")


_STOP_WORDS = frozenset({"and", "the", "of", "for", "or", "to"})
# Strip the doc-prefix + phase from file slugs before comparing
_FILE_PREFIX_RE = re.compile(r"^(hld|lld)-phase\d+-?")


def _compact(slug: str) -> str:
    """Normalize a slug for fuzzy matching.

    - Collapse 'phase-N' (heading form) to 'phaseN' (filename form)
    - Drop common stop words
    - Remove remaining hyphens so compound words match regardless of spacing
    """
    slug = re.sub(r"phase-(\d+)", r"phase\1", slug)
    tokens = [t for t in slug.split("-") if t and t not in _STOP_WORDS]
    return "".join(tokens)


def _tokens_subsequence(tokens: list[str], text: str) -> bool:
    """Return True if every token appears in text in order (non-overlapping).

    This allows extra words in the heading (e.g. 'Running' in 'Bare Metal to
    Running Cluster') without preventing a match against a file whose name omits
    those extra words ('BareMetal_to_Cluster').
    """
    pos = 0
    for token in tokens:
        idx = text.find(token, pos)
        if idx == -1:
            return False
        pos = idx + len(token)
    return True


def find_drawio_png(
    diagrams_root: Path,
    phase_tag: str,
    heading_slug: str,
    used: set | None = None,
) -> Path | None:
    """Scan the phase dir (or diagrams root) for the best-matching drawio PNG.

    Tries four increasingly fuzzy match strategies in order:
      1. heading slug is a direct substring of the full file slug
      2. the file stem (prefix/phase stripped) is a substring of the heading slug
      3. compact both sides (hyphens removed, stop-words dropped, phase-N normalised)
         and check if the file compact is a substring of the heading compact
      4. token subsequence — all significant file tokens appear in the heading compact
         in order, even if non-consecutive (handles extra words in headings such as
         'Running' in 'Bare Metal to Running Cluster' vs 'BareMetal_to_Cluster')

    Returns the first match found, skipping already-used files.
    """
    if not heading_slug:
        return None
    phase_dir = diagrams_root / phase_tag
    search_dir = phase_dir if phase_dir.exists() else diagrams_root
    heading_compact = _compact(heading_slug)

    for png in sorted(search_dir.glob("*.drawio.png")):
        if used is not None and png in used:
            continue
        file_slug = slugify(png.name.replace(".drawio.png", ""))
        # Try 1: direct substring (original behaviour)
        if heading_slug in file_slug:
            return png
        # Strip doc-prefix and phase tag from file slug for tries 2-4
        stripped = _FILE_PREFIX_RE.sub("", file_slug)
        if not stripped:
            continue
        # Try 2: stripped file slug is a substring of heading slug
        if stripped in heading_slug:
            return png
        # Try 3: compact both sides and check substring (handles BareMetal vs
        # Bare-Metal, "and" removal, phase-N vs phaseN, etc.)
        file_compact = _compact(stripped)
        if file_compact and file_compact in heading_compact:
            return png
        # Try 4: all significant file tokens appear in heading compact in order
        # (handles extra descriptive words in headings like 'Configuration',
        # 'Running', 'Cluster' that don't appear in the drawio filename)
        tokens = [t for t in stripped.split("-") if t and t not in _STOP_WORDS]
        if tokens and _tokens_subsequence(tokens, heading_compact):
            return png
    return None


def drawio_rel_path(doc_type: str, phase_tag: str, image_name: str) -> str:
    subpath = f"{phase_tag}/{image_name}" if phase_tag else image_name
    if doc_type == "hld":
        return f"../../Diagrams/{subpath}"
    return f"../Diagrams/{subpath}"


def mermaid_rel_path(doc_type: str, phase_tag: str, image_name: str) -> str:
    if doc_type == "hld":
        return f"../diagrams/{phase_tag}/{image_name}"
    return f"diagrams/{phase_tag}/{image_name}"


def _resolve_explicit_drawio(
    explicit_name: str,
    diagrams_root: Path,
    phase_tag: str,
    alt_text: str,
    base_noext: str,
) -> Path | None:
    """Resolve an explicit <!-- drawio: FILENAME --> annotation to an absolute path."""
    root = diagrams_root.resolve()
    for rel in (diagrams_root / phase_tag / explicit_name, diagrams_root / explicit_name):
        resolved = rel.resolve()
        if not resolved.is_relative_to(root):
            return None
        if resolved.exists():
            return resolved
    print(
        f"  WARNING: Annotated drawio '{explicit_name}' not found "
        f"for '{alt_text}' in {base_noext}. Falling back to fuzzy match.",
        file=sys.stderr,
    )
    return None


def _open_mermaid_block(
    line: str,
    prev_nonblank: str,
    last_heading: str,
    diagram_idx: int,
    slug_seen: dict[str, int],
    out_lines: list[str],
    diagrams_root: Path,
    mermaid_png_dir: Path,
    doc_type: str,
    base_noext: str,
    phase_tag: str,
    used_drawio: set[Path],
) -> bool:
    """Handle a ```mermaid opening fence; return skip_block flag."""
    slug = slugify(last_heading) or f"diagram-{diagram_idx}"
    slug_seen[slug] = slug_seen.get(slug, 0) + 1
    alt_text = last_heading or f"Diagram {diagram_idx}"

    explicit_name: str | None = None
    anno_match = DRAWIO_ANNOTATION_RE.match(prev_nonblank)
    if anno_match:
        explicit_name = anno_match.group(1).strip()
        if not explicit_name.endswith(".drawio.png"):
            explicit_name += ".drawio.png"
        for i in range(len(out_lines) - 1, max(len(out_lines) - 6, -1), -1):
            if DRAWIO_ANNOTATION_RE.match(out_lines[i]):
                out_lines.pop(i)
                break

    drawio_abs: Path | None = None
    if explicit_name:
        drawio_abs = _resolve_explicit_drawio(explicit_name, diagrams_root, phase_tag, alt_text, base_noext)

    if drawio_abs is None:
        drawio_abs = find_drawio_png(diagrams_root, phase_tag, slug, used_drawio)
        if drawio_abs is not None:
            used_drawio.add(drawio_abs)

    if drawio_abs is not None:
        drawio_name = drawio_abs.name
        rel_dir = drawio_abs.parent.relative_to(diagrams_root)
        actual_subdir = "" if str(rel_dir) == "." else str(rel_dir)
        out_lines.append(f"![{alt_text}]({drawio_rel_path(doc_type, actual_subdir, drawio_name)})")
        return True

    mermaid_name = f"{phase_tag}_{diagram_idx}_{slug}.png"
    mermaid_abs = mermaid_png_dir / phase_tag / mermaid_name
    if mermaid_abs.exists():
        out_lines.append(f"![{alt_text}]({mermaid_rel_path(doc_type, phase_tag, mermaid_name)})")
        return True

    out_lines.append("```mermaid")
    phase_dir = diagrams_root / phase_tag
    print(
        f"  WARNING: Diagram image not found — the diagram "
        f"'{alt_text}' in {base_noext} has no exported PNG.\n"
        f"           The raw mermaid code will be kept inline "
        f"(it won't render in the PDF).\n"
        f"           To fix: add <!-- drawio: FILENAME --> above "
        f"the mermaid block, or add a .drawio.png whose name "
        f"contains '{slug}' to:\n"
        f"             {phase_dir}",
        file=sys.stderr,
    )
    return False


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
    prev_nonblank = ""
    diagram_idx = 0
    slug_seen: dict[str, int] = {}
    used_drawio: set[Path] = set()
    out_lines: list[str] = []

    for line in src.read_text(encoding="utf-8").splitlines():
        heading_match = HEADING_RE.match(line)
        if heading_match:
            last_heading = heading_match.group(1)

        if line == "```mermaid":
            in_mermaid = True
            diagram_idx += 1
            skip_block = _open_mermaid_block(
                line,
                prev_nonblank,
                last_heading,
                diagram_idx,
                slug_seen,
                out_lines,
                diagrams_root,
                mermaid_png_dir,
                doc_type,
                base_noext,
                phase_tag,
                used_drawio,
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
            if line.strip():
                prev_nonblank = line

    out.write_text("\n".join(out_lines) + "\n", encoding="utf-8")


def resolve_stitchmd() -> str:
    stitchmd = os.environ.get("STITCHMD", "stitchmd")
    if shutil_which(stitchmd):
        return stitchmd
    fallback = str(Path.home() / "go" / "bin" / "stitchmd")
    if Path(fallback).is_file():
        return fallback
    raise SystemExit("Error: stitchmd not found. Install with: go install go.abhg.dev/stitchmd@v0.9.0")


def shutil_which(cmd: str) -> str | None:
    from shutil import which

    return which(cmd)


_STITCHMD_TIMEOUT_SECS = 120


def run_stitchmd(stitchmd: str, output: Path, summary: Path) -> None:
    subprocess.run(
        [stitchmd, "-no-toc", "-o", str(output), str(summary)],
        check=True,
        timeout=_STITCHMD_TIMEOUT_SECS,
    )


def generate_hld(cfg: dict, project_root: Path) -> None:
    md_dir = project_root / "output" / "HLD" / "markdown_files"
    diagrams_root = project_root / "output" / "Diagrams"
    mermaid_png_dir = project_root / "output" / "HLD" / "diagrams"
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
    md_dir = project_root / "output" / "LLD"
    diagrams_root = project_root / "output" / "Diagrams"
    mermaid_png_dir = project_root / "output" / "LLD" / "diagrams"
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

    project_root = find_project_yaml().parent
    cfg = load_config()
    if args.type == "hld":
        generate_hld(cfg, project_root)
    else:
        generate_lld(cfg, project_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
