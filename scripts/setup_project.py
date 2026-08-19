#!/usr/bin/env python3
"""
setup_project.py — First-time project setup and status check.

Called by the container entrypoint during `make setup`.
Handles: project.yaml creation, {CLIENT} placeholder replacement,
template file renaming, summary file generation, diagram seeding.

Usage:
    python3 setup_project.py /workspace "{CLIENT}" "OCP-V"
    python3 setup_project.py /workspace --status
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from client_prefix import derive_hld_lld_file_prefix
from config import get_client_identity
from diagram_layout import PHASE_DIAGRAM_PREFIXES, TOP_LEVEL_PREFIXES
from setup_status import (
    _print_optional,
    _print_step_adr,
    _print_step_ai,
    _print_step_hc_collect,
    _print_step_hc_setup,
    _print_step_lld,
    _print_step_publish,
    _print_step_setup,
    _print_step_workitems,
    run_status,
)

# ── Helpers ──────────────────────────────────────────────────────────

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def info(message: str) -> None:
    print(f"  {message}")


def ok(message: str) -> None:
    print(f"  {GREEN}[ok]{RESET}  {message}")


def warn(message: str) -> None:
    print(f"  {YELLOW}[--]{RESET}  {message}")


def fail(message: str) -> None:
    print(f"  {RED}[!!]{RESET}  {message}")


def heading(message: str) -> None:
    print(f"\n{BOLD}{message}{RESET}")


# ── Project type registry ────────────────────────────────────────────
#
# Each engagement type (OCP-V, future types) is a first-class
# entry here. Adding a new type requires: one ProjectType entry below, one
# project.example.<type>.yaml template file, and nothing else — run_setup()
# and run_status() dispatch purely off these fields.


@dataclass(frozen=True)
class ProjectType:
    """Describes everything setup/status need to know about an engagement type."""

    engagement_type: str
    template_file: str
    scaffold_dirs: tuple[str, ...]
    template_dirs: tuple[str, ...]
    has_hld_templates: bool
    has_diagram_seeding: bool
    has_hld_status: bool
    status_steps: tuple
    next_steps: tuple[str, ...]
    next_step_groups: tuple[tuple[str, tuple[str, ...]], ...] = field(default_factory=tuple)
    project_code_placeholder: str | None = None
    aliases: tuple[str, ...] = field(default_factory=tuple)


# ── project.yaml creation ───────────────────────────────────────────


def create_project_yaml(workspace: Path, client_name: str, project_code: str, project_type: ProjectType) -> dict:
    """Create project.yaml from the type's template, substituting client values."""
    example = workspace / project_type.template_file
    target = workspace / "project.yaml"

    if target.exists():
        with open(target, encoding="utf-8") as yaml_file:
            existing = yaml.safe_load(yaml_file) or {}
        existing_client = existing.get("client_name", "")
        existing_engagement_type = str(existing.get("engagement_type", "ocp-v")).strip() or "ocp-v"
        expected_engagement_type = project_type.engagement_type
        recreate_existing = False
        if existing_client == client_name:
            if existing_engagement_type != expected_engagement_type:
                safe_old_type = re.sub(r"[^A-Za-z0-9._-]+", "-", existing_engagement_type) or "unknown"
                backup_path = workspace / f"project.yaml.bak.{safe_old_type}"
                shutil.copy2(target, backup_path)
                warn(
                    "project.yaml engagement type mismatch "
                    f"('{existing_engagement_type}' -> '{expected_engagement_type}'); "
                    f"recreating from {project_type.template_file} (backup: {backup_path.name})."
                )
                recreate_existing = True
            else:
                info("project.yaml already exists with correct client, loading it.")
                return existing
        elif "{CLIENT}" not in existing_client and "{CLIENT_PREFIX}" not in existing_client:
            info(f"project.yaml already exists (client: {existing_client}), loading it.")
            return existing
        else:
            info(f"project.yaml has placeholder client '{existing_client}', recreating...")
            recreate_existing = True

        if recreate_existing and target.exists():
            target.unlink()

    if not example.exists():
        print(f"{RED}Error: {project_type.template_file} not found in {workspace}{RESET}")
        sys.exit(1)

    with open(example, encoding="utf-8") as template_file:
        content = template_file.read()

    file_prefix = derive_hld_lld_file_prefix(client_name)

    content = content.replace("{CLIENT}", client_name)
    content = content.replace("{CLIENT_PREFIX}", file_prefix)
    placeholder = project_type.project_code_placeholder
    if placeholder and project_code != placeholder:
        content = content.replace(placeholder, project_code)

    with open(target, "w", encoding="utf-8") as yaml_file:
        yaml_file.write(content)

    info(f"Created project.yaml (client: {client_name}, code: {project_code})")

    with open(target, encoding="utf-8") as yaml_file:
        return yaml.safe_load(yaml_file)


# ── Template file processing ────────────────────────────────────────

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


def process_templates(workspace: Path, client_name: str, file_prefix: str, template_dirs: tuple[str, ...]) -> None:
    """Replace {CLIENT} placeholders in client working markdown (never mutate templates/)."""
    heading("Replacing placeholders in client working files...")
    _ = file_prefix

    replacements = {
        "{CLIENT}": client_name,
        "{CLIENT_LOWER}": client_name.lower().replace(" ", ""),
    }

    changed = 0
    for directory_relative in template_dirs:
        directory_path = workspace / directory_relative
        if not directory_path.exists():
            continue
        for markdown_file in directory_path.rglob("*"):
            if markdown_file.suffix in TEMPLATE_EXTENSIONS and markdown_file.is_file():
                if replace_placeholders_in_file(markdown_file, replacements):
                    changed += 1

    info(f"Updated {changed} file(s) with client placeholders.")


# ── File renaming (Template_* -> Client_*) ──────────────────────────

HLD_TEMPLATE_PREFIX = "Template_OCP-V_HLD_DecisionJourney"
LLD_TEMPLATE_PREFIX = "Template_OCP-V_LLD"

TEMPLATES_HLD_MD = Path("templates") / "HLD" / "markdown_files"
TEMPLATES_LLD = Path("templates") / "LLD"
TEMPLATES_ADR = Path("templates") / "ADR"
TEMPLATES_DIAGRAMS_EXAMPLES = Path("templates") / "Diagrams" / "examples"
OUTPUT_HLD_MD = Path("output") / "HLD" / "markdown_files"
OUTPUT_LLD = Path("output") / "LLD"
OUTPUT_DIAGRAMS = Path("output") / "Diagrams"


def collect_working_copy_conflicts(workspace: Path, file_prefix: str, project_code: str) -> list[Path]:
    """Return existing HLD/LLD/ADR working copies that setup would overwrite."""
    conflicts: list[Path] = []
    hld_source = workspace / TEMPLATES_HLD_MD
    hld_dest = workspace / OUTPUT_HLD_MD
    if hld_source.exists():
        client_hld_prefix = f"{file_prefix}_{project_code}_HLD_DecisionJourney"
        for source in sorted(hld_source.glob(f"{HLD_TEMPLATE_PREFIX}*.md")):
            suffix_part = source.name[len(HLD_TEMPLATE_PREFIX) :]
            dest = hld_dest / f"{client_hld_prefix}{suffix_part}"
            if dest.exists():
                conflicts.append(dest)
    lld_source = workspace / TEMPLATES_LLD
    lld_dest = workspace / OUTPUT_LLD
    if lld_source.exists():
        for source in sorted(lld_source.glob(f"{LLD_TEMPLATE_PREFIX}*.md")):
            dest = lld_dest / source.name.replace("Template_", f"{file_prefix}_")
            if dest.exists():
                conflicts.append(dest)
    adr_client = workspace / "ADR" / f"ADR_{file_prefix.lower()}.md"
    if adr_client.exists():
        conflicts.append(adr_client)
    return conflicts


def _refuse_existing_working_copies(workspace: Path, conflicts: list[Path]) -> None:
    heading("Working copies already exist")
    warn("Setup will not overwrite existing markdown working copies.")
    for path in conflicts:
        try:
            relative_path = path.relative_to(workspace)
        except ValueError:
            relative_path = path
        warn(str(relative_path))
    print("Re-run with FORCE=1 (or --force) to overwrite working copies from templates.")
    sys.exit(1)


def rename_templates(workspace: Path, config: dict, file_prefix: str, project_code: str) -> None:
    """Create client-named copies of Template_* files under output/ (ADR under ADR/)."""
    heading("Creating client-named copies of templates...")
    _ = config

    count = 0

    # HLD phase + preamble + appendix files: templates → output
    hld_source = workspace / TEMPLATES_HLD_MD
    hld_dest = workspace / OUTPUT_HLD_MD
    if hld_source.exists():
        hld_dest.mkdir(parents=True, exist_ok=True)
        client_hld_prefix = f"{file_prefix}_{project_code}_HLD_DecisionJourney"
        for template_file in sorted(hld_source.glob(f"{HLD_TEMPLATE_PREFIX}*.md")):
            suffix_part = template_file.name[len(HLD_TEMPLATE_PREFIX) :]  # e.g. "_phase1.md"
            new_name = f"{client_hld_prefix}{suffix_part}"
            dest = hld_dest / new_name
            shutil.copy2(template_file, dest)
            info(f"  {template_file.name} -> output/HLD/markdown_files/{new_name}")
            count += 1

    # LLD phase files: templates → output
    lld_source = workspace / TEMPLATES_LLD
    lld_dest = workspace / OUTPUT_LLD
    if lld_source.exists():
        lld_dest.mkdir(parents=True, exist_ok=True)
        for template_file in sorted(lld_source.glob(f"{LLD_TEMPLATE_PREFIX}*.md")):
            new_name = template_file.name.replace("Template_", f"{file_prefix}_")
            dest = lld_dest / new_name
            shutil.copy2(template_file, dest)
            info(f"  {template_file.name} -> output/LLD/{new_name}")
            count += 1

    # ADR template: templates/ADR → ADR/ (filled engagement ADR stays at repo root)
    adr_source = workspace / TEMPLATES_ADR
    adr_dir = workspace / "ADR"
    adr_dir.mkdir(parents=True, exist_ok=True)
    adr_template = adr_source / "ADR_template.md"
    adr_client = adr_dir / f"ADR_{file_prefix.lower()}.md"
    if adr_template.exists():
        shutil.copy2(adr_template, adr_client)
        info(f"  ADR_template.md -> ADR/{adr_client.name}")
        count += 1

    info(f"Created {count} client-named file(s).")


# ── Stitchmd summary file ───────────────────────────────────────────


def create_summary_file(
    workspace: Path, config: dict, file_prefix: str, project_code: str, force: bool = False
) -> None:
    """Generate a client-specific stitchmd summary file for HLD assembly."""
    heading("Creating stitchmd summary file...")

    hld_md = workspace / OUTPUT_HLD_MD
    if not hld_md.exists():
        warn("output/HLD/markdown_files/ not found, skipping summary.")
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
    if summary_path.exists() and not force:
        info(f"{summary_name} already exists, skipping.")
        return

    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    info(f"Created {summary_name} ({len(lines)} entries)")
    # Update project.yaml summary_map
    yaml_path = workspace / "project.yaml"
    with open(yaml_path, encoding="utf-8") as yaml_file:
        raw = yaml.safe_load(yaml_file)

    summary_map = raw.setdefault("hld", {}).setdefault("summary_map", {})
    combined_name = f"{client_hld_prefix}_combined.md"

    existing_summaries = {entry.get("summary") for entry in summary_map.values()}
    existing_outputs = {entry.get("output") for entry in summary_map.values()}

    if summary_name in existing_summaries or combined_name in existing_outputs:
        for key, entry in summary_map.items():
            if entry.get("output") == combined_name and entry.get("summary") != summary_name:
                entry["summary"] = summary_name
                with open(yaml_path, "w", encoding="utf-8") as yaml_file:
                    yaml.dump(raw, yaml_file, default_flow_style=False, sort_keys=False, allow_unicode=True)
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

        combined = raw["hld"].get("combined_files", [])
        if combined_name not in combined:
            combined.append(combined_name)
            raw["hld"]["combined_files"] = combined

        with open(yaml_path, "w", encoding="utf-8") as yaml_file:
            yaml.dump(raw, yaml_file, default_flow_style=False, sort_keys=False, allow_unicode=True)
        info(f"Added '{map_key}' to hld.summary_map in project.yaml")


# ── Diagram seeding ─────────────────────────────────────────────────

def seed_diagrams(workspace: Path, force: bool = False) -> None:
    """Copy example .drawio files into output/Diagrams working directories."""
    heading("Seeding diagram directories from examples...")

    examples_dir = workspace / TEMPLATES_DIAGRAMS_EXAMPLES
    if not examples_dir.exists():
        warn("templates/Diagrams/examples/ not found, skipping diagram seeding.")
        return

    examples = list(examples_dir.glob("*.drawio"))
    if not examples:
        warn("No .drawio examples found.")
        return

    diag_root = workspace / OUTPUT_DIAGRAMS
    diag_root.mkdir(parents=True, exist_ok=True)

    phase_count = 0
    top_count = 0
    for drawio in examples:
        placed = False
        for phase, prefixes in PHASE_DIAGRAM_PREFIXES.items():
            for prefix in prefixes:
                if drawio.name.startswith(prefix):
                    dest_dir = diag_root / phase
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    dest = dest_dir / drawio.name
                    if force or not dest.exists():
                        shutil.copy2(drawio, dest)
                        phase_count += 1
                    placed = True
                    break
            if placed:
                break

        if not placed:
            for prefix in TOP_LEVEL_PREFIXES:
                if drawio.name.startswith(prefix):
                    dest = diag_root / drawio.name
                    if force or not dest.exists():
                        shutil.copy2(drawio, dest)
                        top_count += 1
                    placed = True
                    break

    info(f"Seeded {phase_count} diagram(s) into output/Diagrams phase directories.")
    if top_count:
        info(f"Seeded {top_count} top-level diagram(s) into output/Diagrams/.")


# ── Directory scaffolding ────────────────────────────────────────────


def scaffold_directories(workspace: Path, dirs: tuple[str, ...]) -> None:
    """Create working directories if they don't exist."""
    heading("Scaffolding directories...")

    created = 0
    for directory in dirs:
        path = workspace / directory
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            (path / ".gitkeep").touch()
            created += 1

    info(f"Ensured {len(dirs)} directories exist ({created} created).")


# ── Project type registry (after step printers for status_steps refs) ─


PROJECT_TYPES: dict[str, ProjectType] = {
    "ocp-v": ProjectType(
        engagement_type="ocp-v",
        template_file="project.example.yaml",
        scaffold_dirs=(
            "output/Work_Items",
            "RVTools",
            "output/HLD/PDFs",
            "output/HLD/diagrams",
            "output/HLD/markdown_files",
            "output/LLD/PDFs",
            "output/LLD/diagrams",
            "output/LLD",
            "output/Diagrams/phase1",
            "output/Diagrams/phase2",
            "output/Diagrams/phase3",
            "output/Diagrams/phase4",
            "ADR",
        ),
        # Placeholder replacement targets (immutable sources live under templates/)
        template_dirs=("ADR", "output/HLD/markdown_files", "output/LLD"),
        has_hld_templates=True,
        has_diagram_seeding=True,
        has_hld_status=True,
        status_steps=(
            _print_step_setup,
            _print_step_adr,
            _print_step_ai,
            _print_step_publish,
            _print_step_lld,
            _print_step_workitems,
            _print_optional,
        ),
        next_steps=(
            "make build-hld-from-adr  — AI prepare HLD inputs from ADR",
            "make publish             — publish HLD (stitch + diagrams + PDFs)",
            "make prepare-and-publish — run AI prepare, then publish HLD",
            "make build       — build everything",
        ),
        project_code_placeholder="OCP-V",
    ),
    "hc": ProjectType(
        engagement_type="health-check",
        template_file="project.example.hc.yaml",
        scaffold_dirs=(
            "output/hc_collect",
            "output/Health_Check_Report",
        ),
        template_dirs=(),
        has_hld_templates=False,
        has_diagram_seeding=False,
        has_hld_status=False,
        status_steps=(
            _print_step_hc_setup,
            _print_step_hc_collect,
        ),
        next_steps=(),
        next_step_groups=(
            (
                "Option A — Live cluster",
                (
                    'make hc-collect KUBECONFIG=<path>            — collect from a live cluster',
                ),
            ),
            (
                "Option B — Supportshell / must-gather",
                (
                    "make hc-push-scripts HC_SSH_HOST=user@host   — push scripts to the remote support shell",
                    "on remote host: yank <case-number>           — fetch and extract case artifacts",
                    "make hc-collect-remote HC_SSH_HOST=user@host HC_MG_INPUT=<absolute-path-from-yank>",
                    "make hc-fetch-results HC_SSH_HOST=user@host  — copy results to output/hc_collect/<date>",
                ),
            ),
        ),
        project_code_placeholder=None,
        aliases=("HEALTH-CHECK", "HEALTHCHECK"),
    ),
}


def get_project_type(project_code: str) -> ProjectType:
    """Resolve a PROJECT= code to its ProjectType. Unknown codes default to ocp-v."""
    raw_key = (project_code or "").strip().upper()
    key = re.sub(r"[-_\s]+", "-", raw_key)
    for type_key, registered_type in PROJECT_TYPES.items():
        if key == type_key.upper() or key in registered_type.aliases:
            return registered_type
    if key.startswith("OCP-V"):
        return PROJECT_TYPES["ocp-v"]
    if key and key != "OCP-V":
        warn(f'Unknown PROJECT="{project_code}" — defaulting to OCP-V')
    return PROJECT_TYPES["ocp-v"]


# ── Main setup flow ─────────────────────────────────────────────────


def run_setup(workspace: Path, client_name: str, project_code: str = "OCP-V", force: bool = False) -> None:
    """Execute the full project setup."""
    project_code = project_code or "OCP-V"
    project_type = get_project_type(project_code)
    file_prefix = derive_hld_lld_file_prefix(client_name)

    heading("Configuration")
    config = create_project_yaml(workspace, client_name, project_code, project_type)
    file_prefix = derive_hld_lld_file_prefix(config.get("client_name", client_name))
    project_code = config.get("project_code", project_code)

    scaffold_directories(workspace, project_type.scaffold_dirs)

    # Copy immutable templates → client working files first, then replace placeholders
    # only in those copies (never mutate templates/).
    if project_type.has_hld_templates:
        conflicts = collect_working_copy_conflicts(workspace, file_prefix, project_code)
        if conflicts and not force:
            _refuse_existing_working_copies(workspace, conflicts)
        rename_templates(workspace, config, file_prefix, project_code)
        create_summary_file(workspace, config, file_prefix, project_code, force=force)
    if project_type.template_dirs:
        process_templates(workspace, client_name, file_prefix, project_type.template_dirs)
    if project_type.has_diagram_seeding:
        seed_diagrams(workspace, force=force)

    heading("Done!")
    info(f"Project '{client_name}' is ready.")
    info("Next steps:")
    info("  make status      — see what's set up")
    if project_type.next_step_groups:
        print(f"  {BOLD}Choose one collection path:{RESET}")
        print()
        for title, steps in project_type.next_step_groups:
            print(f"  {BOLD}{title}{RESET}")
            for index, line in enumerate(steps, start=1):
                info(f"    {index}) {line}")
            print()
    else:
        for line in project_type.next_steps:
            info(f"  {line}")
    print()


# ── CLI ──────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Project setup bootstrap and health status command.")
    parser.add_argument("workspace", type=Path, help="Workspace directory")
    parser.add_argument("client_name", nargs="?", help="Client name for setup mode")
    parser.add_argument("project_code", nargs="?", default="OCP-V", help="Project code for setup mode (default: OCP-V)")
    parser.add_argument("--status", action="store_true", help="Show project status only")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing HLD/LLD/ADR working copies from templates",
    )
    args = parser.parse_args()

    if args.status:
        if args.client_name:
            parser.error("Do not pass <client_name> with --status")
        workspace = args.workspace
        run_status(workspace)
    else:
        if not args.client_name:
            parser.error("Missing <client_name> (or use --status)")
        run_setup(args.workspace, args.client_name, args.project_code, force=args.force)


if __name__ == "__main__":
    main()
