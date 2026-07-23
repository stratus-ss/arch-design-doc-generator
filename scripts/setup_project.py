#!/usr/bin/env python3
"""
setup_project.py — First-time project setup and health check.

Called by the container entrypoint during `make setup`.
Handles: project.yaml creation, {CLIENT} placeholder replacement,
template file renaming, summary file generation, diagram seeding.

Usage:
    python3 setup_project.py /workspace "{CLIENT}" "OCP-V"
    python3 setup_project.py /workspace --status
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import yaml


# ── Helpers ──────────────────────────────────────────────────────────

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def info(msg: str) -> None:
    print(f"  {msg}")


def ok(msg: str) -> None:
    print(f"  {GREEN}[ok]{RESET}  {msg}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}[--]{RESET}  {msg}")


def fail(msg: str) -> None:
    print(f"  {RED}[!!]{RESET}  {msg}")


def heading(msg: str) -> None:
    print(f"\n{BOLD}{msg}{RESET}")


def derive_file_prefix(client_name: str) -> str:
    """Derive the filename prefix from a client name.

    'Example Client' -> 'Example'     (first word)
    'Globex'    -> 'Globex'            (single word)
    'Contoso North America' -> 'ContosoNorth'  (first two words joined)
    """
    words = client_name.split()
    if len(words) == 1:
        return words[0]
    if len(words) == 2:
        return words[0]
    return "".join(words[:2])


# ── project.yaml creation ───────────────────────────────────────────

def create_project_yaml(workspace: Path, client_name: str, project_code: str) -> dict:
    """Create project.yaml from the example, substituting client values."""
    example = workspace / "project.example.yaml"
    target = workspace / "project.yaml"

    if target.exists():
        with open(target, encoding="utf-8") as f:
            existing = yaml.safe_load(f)
        existing_client = existing.get("client_name", "")
        if existing_client == client_name:
            info("project.yaml already exists with correct client, loading it.")
            return existing
        if "{CLIENT}" not in existing_client and "{CLIENT_PREFIX}" not in existing_client:
            info(f"project.yaml already exists (client: {existing_client}), loading it.")
            return existing
        info(f"project.yaml has placeholder client '{existing_client}', recreating...")
        target.unlink()

    if not example.exists():
        print(f"{RED}Error: project.example.yaml not found in {workspace}{RESET}")
        sys.exit(1)

    with open(example, encoding="utf-8") as f:
        content = f.read()

    file_prefix = derive_file_prefix(client_name)

    content = content.replace("{CLIENT}", client_name)
    content = content.replace("{CLIENT_PREFIX}", file_prefix)
    # Backward compatibility for older project.example.yaml variants.
    content = content.replace("Acme_", f"{file_prefix}_")
    content = content.replace('"Acme_', f'"{file_prefix}_')
    content = content.replace("OCP-V", project_code) if project_code != "OCP-V" else content

    with open(target, "w", encoding="utf-8") as f:
        f.write(content)

    info(f"Created project.yaml (client: {client_name}, code: {project_code})")

    with open(target, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── Template file processing ────────────────────────────────────────

TEMPLATE_DIRS = [
    "ADR",
    "HLD/markdown_files",
    "LLD",
]

TEMPLATE_EXTENSIONS = {".md"}


def replace_placeholders_in_file(path: Path, replacements: dict[str, str]) -> bool:
    """Replace {CLIENT} and {CLIENT_LOWER} in a file. Returns True if changed."""
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return False

    original = text
    for placeholder, value in replacements.items():
        text = text.replace(placeholder, value)

    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def process_templates(workspace: Path, client_name: str, file_prefix: str) -> None:
    """Replace {CLIENT} placeholders in all template markdown files."""
    heading("Replacing placeholders in template files...")

    replacements = {
        "{CLIENT}": client_name,
        "{CLIENT_LOWER}": client_name.lower().replace(" ", ""),
    }

    changed = 0
    for dir_rel in TEMPLATE_DIRS:
        dir_path = workspace / dir_rel
        if not dir_path.exists():
            continue
        for md in dir_path.rglob("*"):
            if md.suffix in TEMPLATE_EXTENSIONS and md.is_file():
                if replace_placeholders_in_file(md, replacements):
                    changed += 1

    info(f"Updated {changed} file(s) with client placeholders.")


# ── File renaming (Template_* -> Client_*) ──────────────────────────

HLD_TEMPLATE_PREFIX = "Template_OCP-V_HLD_DecisionJourney"
LLD_TEMPLATE_PREFIX = "Template_OCP-V_LLD"


def rename_templates(workspace: Path, cfg: dict, file_prefix: str, project_code: str) -> None:
    """Create client-named copies of Template_* files."""
    heading("Creating client-named copies of templates...")

    count = 0

    # HLD phase + preamble + appendix files
    hld_md = workspace / "HLD" / "markdown_files"
    if hld_md.exists():
        client_hld_prefix = f"{file_prefix}_{project_code}_HLD_DecisionJourney"
        for f in sorted(hld_md.glob(f"{HLD_TEMPLATE_PREFIX}*.md")):
            suffix_part = f.name[len(HLD_TEMPLATE_PREFIX):]  # e.g. "_phase1.md"
            new_name = f"{client_hld_prefix}{suffix_part}"
            dest = hld_md / new_name
            if not dest.exists():
                shutil.copy2(f, dest)
                info(f"  {f.name} -> {new_name}")
                count += 1

    # LLD phase files
    lld_dir = workspace / "LLD"
    if lld_dir.exists():
        for f in sorted(lld_dir.glob(f"{LLD_TEMPLATE_PREFIX}*.md")):
            new_name = f.name.replace("Template_", f"{file_prefix}_")
            dest = lld_dir / new_name
            if not dest.exists():
                shutil.copy2(f, dest)
                info(f"  {f.name} -> {new_name}")
                count += 1

    # ADR template
    adr_dir = workspace / "ADR"
    if adr_dir.exists():
        adr_template = adr_dir / "ADR_template.md"
        adr_client = adr_dir / f"ADR_{file_prefix.lower()}.md"
        if adr_template.exists() and not adr_client.exists():
            shutil.copy2(adr_template, adr_client)
            info(f"  ADR_template.md -> {adr_client.name}")
            count += 1

    info(f"Created {count} client-named file(s).")


# ── Stitchmd summary file ───────────────────────────────────────────

def create_summary_file(workspace: Path, cfg: dict, file_prefix: str, project_code: str) -> None:
    """Generate a client-specific stitchmd summary file for HLD assembly."""
    heading("Creating stitchmd summary file...")

    hld_md = workspace / "HLD" / "markdown_files"
    if not hld_md.exists():
        warn("HLD/markdown_files/ not found, skipping summary.")
        return

    client_hld_prefix = f"{file_prefix}_{project_code}_HLD_DecisionJourney"

    parts = ["preamble", "phase1", "phase2", "phase3", "phase4", "appendix"]
    labels = ["Preamble", "Phase 1", "Phase 2", "Phase 3", "Phase 4", "Appendix"]

    lines = []
    for part, label in zip(parts, labels):
        md_name = f"{client_hld_prefix}_{part}.md"
        if (hld_md / md_name).exists():
            lines.append(f"- [{label}]({md_name})")

    if not lines:
        warn("No client HLD phase files found. Summary not created.")
        return

    summary_name = f"{file_prefix}_summary.md"
    summary_path = hld_md / summary_name
    if summary_path.exists():
        info(f"{summary_name} already exists, skipping.")
        return

    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    info(f"Created {summary_name} ({len(lines)} entries)")

    # Update project.yaml summary_map
    yaml_path = workspace / "project.yaml"
    with open(yaml_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    summary_map = raw.get("hld", {}).get("summary_map", {})
    combined_name = f"{client_hld_prefix}_combined.md"

    existing_summaries = {v.get("summary") for v in summary_map.values()}
    existing_outputs = {v.get("output") for v in summary_map.values()}

    if summary_name in existing_summaries or combined_name in existing_outputs:
        for key, entry in summary_map.items():
            if entry.get("output") == combined_name and entry.get("summary") != summary_name:
                entry["summary"] = summary_name
                with open(yaml_path, "w", encoding="utf-8") as f:
                    yaml.dump(raw, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
                info(f"Updated '{key}' summary_map entry to use {summary_name}")
                break
        else:
            info("summary_map already has an entry for this output file.")
    else:
        map_key = file_prefix
        summary_map[map_key] = {
            "summary": summary_name,
            "output": combined_name,
        }
        raw["hld"]["summary_map"] = summary_map

        combined = raw["hld"].get("combined_files", [])
        if combined_name not in combined:
            combined.append(combined_name)
            raw["hld"]["combined_files"] = combined

        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(raw, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        info(f"Added '{map_key}' to hld.summary_map in project.yaml")


# ── Diagram seeding ─────────────────────────────────────────────────

PHASE_DIAGRAM_PREFIXES = {
    "phase1": ["HLD_Phase1_", "LLD_Phase1_", "HLD_phase1_", "LLD_phase1_"],
    "phase2": ["HLD_Phase2_", "LLD_Phase2_", "HLD_phase2_", "LLD_phase2_"],
    "phase3": ["HLD_Phase3_", "LLD_Phase3_", "HLD_phase3_", "LLD_phase3_"],
    "phase4": ["HLD_Phase4_", "LLD_Phase4_", "HLD_phase4_", "LLD_phase4_"],
}

TOP_LEVEL_PREFIXES = [
    "HLD_Network_", "HLD_Storage_", "HLD_Physical_", "HLD_Observability_",
    "HLD_Provisioning_", "HLD_GitOps_", "HLD_ACM_", "HLD_RBAC_",
    "HLD_Platform_", "HLD_External_", "HLD_Backup_", "HLD_Fleet_",
    "HLD_Migration_", "HLD_Decision_", "HLD_Master_",
]


def seed_diagrams(workspace: Path) -> None:
    """Copy example .drawio files into working phase and top-level directories."""
    heading("Seeding diagram directories from examples...")

    examples_dir = workspace / "Diagrams" / "examples"
    if not examples_dir.exists():
        warn("Diagrams/examples/ not found, skipping diagram seeding.")
        return

    examples = list(examples_dir.glob("*.drawio"))
    if not examples:
        warn("No .drawio examples found.")
        return

    phase_count = 0
    top_count = 0
    for drawio in examples:
        placed = False
        for phase, prefixes in PHASE_DIAGRAM_PREFIXES.items():
            for prefix in prefixes:
                if drawio.name.startswith(prefix):
                    dest_dir = workspace / "Diagrams" / phase
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    dest = dest_dir / drawio.name
                    if not dest.exists():
                        shutil.copy2(drawio, dest)
                        phase_count += 1
                    placed = True
                    break
            if placed:
                break

        if not placed:
            for prefix in TOP_LEVEL_PREFIXES:
                if drawio.name.startswith(prefix):
                    dest = workspace / "Diagrams" / drawio.name
                    if not dest.exists():
                        shutil.copy2(drawio, dest)
                        top_count += 1
                    placed = True
                    break

    info(f"Seeded {phase_count} diagram(s) into phase directories.")
    if top_count:
        info(f"Seeded {top_count} top-level diagram(s) into Diagrams/.")


# ── Directory scaffolding ────────────────────────────────────────────

SCAFFOLD_DIRS = [
    "Work_Items",
    "RVTools",
    "HLD/PDFs",
    "HLD/diagrams",
    "LLD/PDFs",
    "LLD/diagrams",
    "Diagrams/phase1",
    "Diagrams/phase2",
    "Diagrams/phase3",
    "Diagrams/phase4",
]


def scaffold_directories(workspace: Path) -> None:
    """Create working directories if they don't exist."""
    heading("Scaffolding directories...")

    created = 0
    for d in SCAFFOLD_DIRS:
        path = workspace / d
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            (path / ".gitkeep").touch()
            created += 1

    info(f"Ensured {len(SCAFFOLD_DIRS)} directories exist ({created} created).")


# ── Status / health check ───────────────────────────────────────────

def _count_drawio(workspace: Path, cfg: dict) -> tuple:
    """Return (phase_count, top_level_count) of .drawio files."""
    diag_root = workspace / "Diagrams"
    phase_count = 0
    for phase in cfg.get("diagrams", {}).get("phase_dirs", []):
        phase_dir = diag_root / phase
        if phase_dir.exists():
            phase_count += len(list(phase_dir.glob("*.drawio")))
    top_count = len(list(diag_root.glob("*.drawio"))) if diag_root.exists() else 0
    return phase_count, top_count


def run_status(workspace: Path) -> None:
    """Print a plain-language project health report."""
    yaml_path = workspace / "project.yaml"

    heading("Project Status")

    if not yaml_path.exists():
        fail('project.yaml not found — run: make setup CLIENT="Your Client" PROJECT="OCP-V"')
        return

    with open(yaml_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    client = cfg.get("client_name", "Unknown")
    code = cfg.get("project_code", "OCP-V")
    print(f"\n  Project: {BOLD}{client}{RESET} ({code})")
    print(f"  {'─' * 50}\n")

    # ── Gather all state up front ─────────────────────────────────
    hld_md = workspace / "HLD" / "markdown_files"
    lld_dir = workspace / "LLD"

    # Setup state
    hld_phases = cfg.get("hld", {}).get("phase_files", [])
    hld_found = sum(1 for f in hld_phases if (hld_md / f).exists()) if hld_md.exists() else 0
    lld_phases_cfg = [p.get("lld_file", "") for p in cfg.get("phases", [])]
    lld_found = sum(1 for f in lld_phases_cfg if (lld_dir / f).exists()) if lld_dir.exists() else 0
    phase_drawio, top_drawio = _count_drawio(workspace, cfg)
    adr_dir = workspace / "ADR"
    _adr_excluded = {"ADR_template.md", "ADR_EXAMPLE.md"}
    adr_files = [f for f in adr_dir.glob("ADR_*.md") if f.name not in _adr_excluded] if adr_dir.exists() else []

    setup_ok = (
        hld_found == len(hld_phases) and hld_found > 0
        and lld_found == len(lld_phases_cfg) and lld_found > 0
        and (phase_drawio + top_drawio) > 0
        and len(adr_files) > 0
    )

    # AI state
    det_dir = workspace / ".deterministic"
    out_det_dir = workspace / "output" / ".deterministic"
    slots_file = det_dir / "slots" / "slot_map.json"
    if not slots_file.exists():
        slots_file = out_det_dir / "slots" / "slot_map.json"
    drafts_det = workspace / "drafts_deterministic"
    if not drafts_det.exists():
        drafts_det = workspace / "output" / "drafts_deterministic"
    drafts_prose = workspace / "drafts"
    det_hld_files = list(drafts_det.rglob("*.md")) if drafts_det.exists() else []
    has_slots = slots_file.exists()
    prose_files = list(drafts_prose.rglob("*.md")) if drafts_prose.exists() else []
    ai_done = has_slots and len(det_hld_files) > 0

    # Build state — check both in-tree and output/ (container writes to output/)
    def _count_glob(base: Path, pattern: str) -> int:
        return len(list(base.rglob(pattern))) if base.exists() else 0

    out = workspace / "output"
    hld_combined = cfg.get("hld", {}).get("combined_files", [])
    hld_stitched = False
    if hld_md.exists():
        hld_stitched = any((hld_md / f).exists() for f in hld_combined)
    if not hld_stitched and (out / "HLD" / "markdown_files").exists():
        hld_stitched = any((out / "HLD" / "markdown_files" / f).exists() for f in hld_combined)
    hld_pdfs = _count_glob(workspace / "HLD" / "PDFs", "*.pdf") + _count_glob(out / "HLD" / "PDFs", "*.pdf")
    hld_pngs = _count_glob(workspace / "HLD" / "diagrams", "*.png") + _count_glob(out / "HLD" / "diagrams", "*.png")
    hld_drawio_md = _count_glob(workspace / "HLD" / "markdown_files", "Drawio_*.md") + _count_glob(out / "HLD" / "markdown_files", "Drawio_*.md")

    lld_combined_file = cfg.get("lld", {}).get("combined_file", "")
    lld_stitched = bool(lld_combined_file and (lld_dir / lld_combined_file).exists())
    if not lld_stitched and lld_combined_file:
        lld_stitched = (out / "LLD" / lld_combined_file).exists()
    lld_pdfs = _count_glob(workspace / "LLD" / "PDFs", "*.pdf") + _count_glob(out / "LLD" / "PDFs", "*.pdf")
    lld_pngs = _count_glob(workspace / "LLD" / "diagrams", "*.png") + _count_glob(out / "LLD" / "diagrams", "*.png")
    lld_drawio_md = _count_glob(workspace / "LLD", "Drawio_*.md") + _count_glob(out / "LLD", "Drawio_*.md")

    hld_built = hld_stitched or hld_pdfs > 0 or hld_pngs > 0
    lld_built = lld_stitched or lld_pdfs > 0 or lld_pngs > 0

    # Extras state
    wi_dir = workspace / "Work_Items"
    wi_out = out / "Work_Items"
    wi_files = list(wi_dir.rglob("*.md")) if wi_dir.exists() else []
    wi_files += list(wi_out.rglob("*.md")) if wi_out.exists() else []

    # ── Determine next action ─────────────────────────────────────
    ARROW = "\033[1;36m>>>\033[0m"

    # ── Step 1: make setup ────────────────────────────────────────
    step_label = f"{ARROW} " if not setup_ok else "   "
    print(f'  {step_label}{BOLD}Step 1:{RESET}  make setup CLIENT="..." PROJECT="..."')
    if setup_ok:
        parts = [f"HLD {hld_found}/{len(hld_phases)}", f"LLD {lld_found}/{len(lld_phases_cfg)}",
                 f"{phase_drawio + top_drawio} diagrams", f"ADR: {adr_files[0].name}"]
        ok(f"Done — {', '.join(parts)}")
    else:
        if hld_found < len(hld_phases):
            warn(f"HLD templates: {hld_found}/{len(hld_phases)}")
        if lld_found < len(lld_phases_cfg):
            warn(f"LLD templates: {lld_found}/{len(lld_phases_cfg)}")
        if phase_drawio + top_drawio == 0:
            warn("No diagrams seeded")
        if not adr_files:
            warn("No client ADR file — fill in ADR/<client>.md after setup")
    print()

    # ── Step 2: Fill in ADR ───────────────────────────────────────
    adr_has_content = False
    adr_filled_decisions = 0
    adr_total_decisions = 0
    adr_heading_count = 0
    if adr_files:
        adr_text = adr_files[0].read_text(encoding="utf-8")
        for raw_line in adr_text.splitlines():
            line = raw_line.strip()
            if line.startswith("### ADR "):
                adr_heading_count += 1
            if line.startswith("- **Decision**:"):
                adr_total_decisions += 1
                if line != "- **Decision**:":
                    adr_filled_decisions += 1
        adr_has_content = adr_filled_decisions > 0
    step_label = f"{ARROW} " if setup_ok and not adr_has_content else "   "
    print(f"  {step_label}{BOLD}Step 2:{RESET}  Edit ADR/<client>.md with architecture decisions")
    if adr_has_content:
        if adr_heading_count:
            ok(f"Done — {adr_files[0].name} ({adr_heading_count} ADRs, {adr_filled_decisions}/{adr_total_decisions} decisions filled)")
        else:
            ok(f"Done — {adr_files[0].name}")
    elif adr_files:
        if adr_total_decisions:
            warn(f"{adr_files[0].name} has no decisions filled in yet ({adr_filled_decisions}/{adr_total_decisions}) — fill in your architecture decisions")
        else:
            warn(f"{adr_files[0].name} exists but no Decision fields were found — verify ADR template format")
    else:
        warn("No ADR file yet (created by Step 1)")
    print()

    # ── Step 3: make build-hld-from-adr ───────────────────────────
    step_label = f"{ARROW} " if setup_ok and adr_has_content and not ai_done else "   "
    print(f"  {step_label}{BOLD}Step 3:{RESET}  make build-hld-from-adr")
    if has_slots and det_hld_files:
        ok(f"Done — slots extracted, {len(det_hld_files)} draft(s) rendered")
    elif has_slots:
        warn("Slots extracted but drafts not rendered — re-run to complete")
    else:
        warn("Not run yet — AI extracts data from ADR and renders HLD drafts")
    print()

    # ── Step 4: make publish ──────────────────────────────────────
    step_label = f"{ARROW} " if ai_done and not hld_built else "   "
    print(f"  {step_label}{BOLD}Step 4:{RESET}  make publish  (runs in container)")
    if hld_built:
        parts = []
        if hld_stitched: parts.append("stitched")
        if hld_drawio_md: parts.append(f"{hld_drawio_md} Drawio md")
        if hld_pngs: parts.append(f"{hld_pngs} PNG(s)")
        if hld_pdfs: parts.append(f"{hld_pdfs} PDF(s)")
        ok(f"Done — {', '.join(parts)}")
    else:
        warn("Not built yet — stitches phases, exports diagrams, generates PDFs")
    print()

    # ── Step 5: make build-lld ────────────────────────────────────
    step_label = f"{ARROW} " if hld_built and not lld_built else "   "
    print(f"  {step_label}{BOLD}Step 5:{RESET}  make build-lld  (runs in container)")
    if lld_built:
        parts = []
        if lld_stitched: parts.append("stitched")
        if lld_drawio_md: parts.append(f"{lld_drawio_md} Drawio md")
        if lld_pngs: parts.append(f"{lld_pngs} PNG(s)")
        if lld_pdfs: parts.append(f"{lld_pdfs} PDF(s)")
        ok(f"Done — {', '.join(parts)}")
    else:
        warn("Not built yet — stitches phases, exports diagrams, generates PDFs")
    print()

    # ── Step 6: make workitems ────────────────────────────────────
    step_label = f"{ARROW} " if lld_built and not wi_files else "   "
    print(f"  {step_label}{BOLD}Step 6:{RESET}  make workitems")
    if wi_files:
        ok(f"Done — {len(wi_files)} work item(s)")
    else:
        warn("Not run yet — extracts sprint work items from LLD")
    print()

    # ── Optional targets ──────────────────────────────────────────
    print(f"  {BOLD}Optional:{RESET}")
    if prose_files:
        info(f"  Legacy prose drafts detected: {len(prose_files)} file(s)")
    info("  make rvtools FILES=\"...\"    — process RVTools XLSX into migration schedule")

    print()


# ── Main setup flow ─────────────────────────────────────────────────

def run_setup(workspace: Path, client_name: str, project_code: str = "OCP-V") -> None:
    """Execute the full project setup."""
    project_code = project_code or "OCP-V"
    file_prefix = derive_file_prefix(client_name)

    heading("Configuration")
    cfg = create_project_yaml(workspace, client_name, project_code)
    file_prefix = derive_file_prefix(cfg.get("client_name", client_name))
    project_code = cfg.get("project_code", project_code)

    scaffold_directories(workspace)
    process_templates(workspace, client_name, file_prefix)
    rename_templates(workspace, cfg, file_prefix, project_code)
    create_summary_file(workspace, cfg, file_prefix, project_code)
    seed_diagrams(workspace)

    heading("Done!")
    info(f"Project '{client_name}' is ready.")
    info("Next steps:")
    info("  make status      — see what's set up")
    info("  make build-hld-from-adr  — AI prepare HLD inputs from ADR")
    info("  make publish             — publish HLD (stitch + diagrams + PDFs)")
    info("  make prepare-and-publish — run AI prepare, then publish HLD")
    info("  make build       — build everything")
    print()


# ── CLI ──────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Project setup bootstrap and health status command."
    )
    parser.add_argument("workspace", type=Path, help="Workspace directory")
    parser.add_argument("client_name", nargs="?", help="Client name for setup mode")
    parser.add_argument("project_code", nargs="?", default="OCP-V", help="Project code for setup mode (default: OCP-V)")
    parser.add_argument("--status", action="store_true", help="Show project status only")
    args = parser.parse_args()

    if args.status:
        if args.client_name:
            parser.error("Do not pass <client_name> with --status")
        workspace = args.workspace
        run_status(workspace)
    else:
        if not args.client_name:
            parser.error("Missing <client_name> (or use --status)")
        run_setup(args.workspace, args.client_name, args.project_code)


if __name__ == "__main__":
    main()
