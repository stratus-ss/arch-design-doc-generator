"""Status reporting extracted from setup_project.py."""

from __future__ import annotations

from pathlib import Path

import yaml
from config import get_client_identity

OUTPUT_HLD_MD = Path("output") / "HLD" / "markdown_files"
OUTPUT_LLD = Path("output") / "LLD"
OUTPUT_DIAGRAMS = Path("output") / "Diagrams"

ok = warn = info = fail = heading = None
BOLD = RESET = ""


def _ui():
    import setup_project as sp
    return sp


def _bootstrap_ui() -> None:
    global ok, warn, info, fail, heading, BOLD, RESET
    sp = _ui()
    ok, warn, info, fail, heading = sp.ok, sp.warn, sp.info, sp.fail, sp.heading
    BOLD, RESET = sp.BOLD, sp.RESET


def _count_drawio(workspace: Path, cfg: dict) -> tuple:
    """Return (phase_count, top_level_count) of .drawio files under output/Diagrams."""
    diag_root = workspace / OUTPUT_DIAGRAMS
    phase_count = 0
    for phase in cfg.get("diagrams", {}).get("phase_dirs", []):
        phase_dir = diag_root / phase
        if phase_dir.exists():
            phase_count += len(list(phase_dir.glob("*.drawio")))
    top_count = len(list(diag_root.glob("*.drawio"))) if diag_root.exists() else 0
    return phase_count, top_count


_STATUS_ARROW = "\033[1;36m>>>\033[0m"


def _parse_adr_content(adr_files: list[Path]) -> tuple[bool, int, int, int]:
    """Parse the primary ADR file for filled-in decision counts.

    Returns (has_content, filled_decisions, total_decisions, heading_count).
    """
    if not adr_files:
        return False, 0, 0, 0
    adr_text = adr_files[0].read_text(encoding="utf-8")
    filled = total = headings = 0
    for raw_line in adr_text.splitlines():
        line = raw_line.strip()
        if line.startswith("### ADR "):
            headings += 1
        if line.startswith("- **Decision**:"):
            total += 1
            if line != "- **Decision**:":
                filled += 1
    return filled > 0, filled, total, headings


def _count_glob(base: Path, pattern: str) -> int:
    return len(list(base.rglob(pattern))) if base.exists() else 0


def _setup_state(workspace: Path, cfg: dict) -> dict:
    """Compute HLD/LLD/diagram/ADR presence state (the 'is setup complete' checks)."""
    hld_md = workspace / OUTPUT_HLD_MD
    lld_dir = workspace / OUTPUT_LLD
    hld_phases = cfg.get("hld", {}).get("phase_files", [])
    hld_found = sum(1 for f in hld_phases if (hld_md / f).exists()) if hld_md.exists() else 0
    lld_phases_cfg = [p.get("lld_file", "") for p in cfg.get("phases", [])]
    lld_found = sum(1 for f in lld_phases_cfg if (lld_dir / f).exists()) if lld_dir.exists() else 0
    phase_drawio, top_drawio = _count_drawio(workspace, cfg)
    adr_dir = workspace / "ADR"
    _adr_excluded = {"ADR_template.md", "ADR_EXAMPLE.md"}
    adr_files = [f for f in adr_dir.glob("ADR_*.md") if f.name not in _adr_excluded] if adr_dir.exists() else []
    setup_ok = (
        hld_found == len(hld_phases)
        and hld_found > 0
        and lld_found == len(lld_phases_cfg)
        and lld_found > 0
        and (phase_drawio + top_drawio) > 0
        and len(adr_files) > 0
    )
    adr_has_content, adr_filled_decisions, adr_total_decisions, adr_heading_count = _parse_adr_content(adr_files)

    return {
        "hld_phases": hld_phases,
        "hld_found": hld_found,
        "lld_phases_cfg": lld_phases_cfg,
        "lld_found": lld_found,
        "phase_drawio": phase_drawio,
        "top_drawio": top_drawio,
        "adr_files": adr_files,
        "setup_ok": setup_ok,
        "adr_has_content": adr_has_content,
        "adr_filled_decisions": adr_filled_decisions,
        "adr_total_decisions": adr_total_decisions,
        "adr_heading_count": adr_heading_count,
    }


def _ai_state(workspace: Path, out: Path) -> dict:
    """Compute AI-draft/deterministic-slot presence state."""
    det_dir = workspace / ".deterministic"
    out_det_dir = out / ".deterministic"
    slots_file = det_dir / "slots" / "slot_map.json"
    if not slots_file.exists():
        slots_file = out_det_dir / "slots" / "slot_map.json"
    drafts_det = workspace / "drafts_deterministic"
    if not drafts_det.exists():
        drafts_det = out / "drafts_deterministic"
    drafts_prose = workspace / "drafts"
    det_hld_files = list(drafts_det.rglob("*.md")) if drafts_det.exists() else []
    has_slots = slots_file.exists()
    prose_files = list(drafts_prose.rglob("*.md")) if drafts_prose.exists() else []
    ai_done = has_slots and len(det_hld_files) > 0

    return {
        "has_slots": has_slots,
        "det_hld_files": det_hld_files,
        "ai_done": ai_done,
        "prose_files": prose_files,
    }


def _build_state(workspace: Path, cfg: dict, out: Path) -> dict:
    """Compute HLD/LLD stitched/PDF/PNG build-output state under output/."""
    _ = workspace
    hld_md = out / "HLD" / "markdown_files"
    lld_dir = out / "LLD"
    hld_combined = cfg.get("hld", {}).get("combined_files", [])
    hld_stitched = False
    if hld_md.exists():
        hld_stitched = any((hld_md / f).exists() for f in hld_combined)
    hld_pdfs = _count_glob(out / "HLD" / "PDFs", "*.pdf")
    hld_pngs = _count_glob(out / "HLD" / "diagrams", "*.png")
    hld_drawio_md = _count_glob(out / "HLD" / "markdown_files", "Drawio_*.md")

    lld_combined_file = cfg.get("lld", {}).get("combined_file", "")
    lld_stitched = bool(lld_combined_file and (lld_dir / lld_combined_file).exists())
    lld_pdfs = _count_glob(out / "LLD" / "PDFs", "*.pdf")
    lld_pngs = _count_glob(out / "LLD" / "diagrams", "*.png")
    lld_drawio_md = _count_glob(out / "LLD", "Drawio_*.md")

    hld_built = hld_stitched or hld_pdfs > 0 or hld_pngs > 0
    lld_built = lld_stitched or lld_pdfs > 0 or lld_pngs > 0

    return {
        "hld_stitched": hld_stitched,
        "hld_pdfs": hld_pdfs,
        "hld_pngs": hld_pngs,
        "hld_drawio_md": hld_drawio_md,
        "hld_built": hld_built,
        "lld_stitched": lld_stitched,
        "lld_pdfs": lld_pdfs,
        "lld_pngs": lld_pngs,
        "lld_drawio_md": lld_drawio_md,
        "lld_built": lld_built,
    }


def _extras_state(workspace: Path, out: Path) -> dict:
    """Compute work-items presence state."""
    _ = workspace
    wi_out = out / "Work_Items"
    wi_files = list(wi_out.rglob("*.md")) if wi_out.exists() else []
    return {"wi_files": wi_files}


def _gather_state(workspace: Path, cfg: dict, project_type: ProjectType | None = None) -> dict:
    """Compute all filesystem/config state needed to render the status report."""
    _ = project_type
    state: dict = {}
    out = workspace / "output"
    state.update(_setup_state(workspace, cfg))
    state.update(_ai_state(workspace, out))
    state.update(_build_state(workspace, cfg, out))
    state.update(_extras_state(workspace, out))
    return state


# ── Status step printers ─────────────────────────────────────────────


def _print_step_setup(state: dict) -> None:
    """Step 1: make setup."""
    setup_ok, hld_found, hld_phases = state["setup_ok"], state["hld_found"], state["hld_phases"]
    lld_found, lld_phases_cfg = state["lld_found"], state["lld_phases_cfg"]
    diagrams = state["phase_drawio"] + state["top_drawio"]
    adr_files = state["adr_files"]

    step_label = f"{_STATUS_ARROW} " if not setup_ok else "   "
    print(f'  {step_label}{BOLD}Step 1:{RESET}  make setup CLIENT="..." PROJECT="..."')
    if setup_ok:
        parts = [
            f"HLD {hld_found}/{len(hld_phases)}",
            f"LLD {lld_found}/{len(lld_phases_cfg)}",
            f"{diagrams} diagrams",
            f"ADR: {adr_files[0].name}",
        ]
        ok(f"Done — {', '.join(parts)}")
    else:
        if hld_found < len(hld_phases):
            warn(f"HLD templates: {hld_found}/{len(hld_phases)}")
        if lld_found < len(lld_phases_cfg):
            warn(f"LLD templates: {lld_found}/{len(lld_phases_cfg)}")
        if diagrams == 0:
            warn("No diagrams seeded")
        if not adr_files:
            warn("No client ADR file — fill in ADR/<client>.md after setup")
    print()


def _print_step_adr(state: dict) -> None:
    """Step 2: fill in ADR."""
    adr_files = state["adr_files"]
    adr_has_content = state["adr_has_content"]
    adr_filled_decisions = state["adr_filled_decisions"]
    adr_total_decisions = state["adr_total_decisions"]
    adr_heading_count = state["adr_heading_count"]

    step_label = f"{_STATUS_ARROW} " if state["setup_ok"] and not adr_has_content else "   "
    print(f"  {step_label}{BOLD}Step 2:{RESET}  Edit ADR/<client>.md with architecture decisions")
    if adr_has_content:
        if adr_heading_count:
            ok(
                f"Done — {adr_files[0].name} ({adr_heading_count} ADRs, "
                f"{adr_filled_decisions}/{adr_total_decisions} decisions filled)"
            )
        else:
            ok(f"Done — {adr_files[0].name}")
    elif adr_files:
        if adr_total_decisions:
            warn(
                f"{adr_files[0].name} has no decisions filled in yet "
                f"({adr_filled_decisions}/{adr_total_decisions}) — fill in your architecture decisions"
            )
        else:
            warn(f"{adr_files[0].name} exists but no Decision fields were found — verify ADR template format")
    else:
        warn("No ADR file yet (created by Step 1)")
    print()


def _print_step_ai(state: dict) -> None:
    """Step 3: make build-hld-from-adr."""
    has_slots, det_hld_files = state["has_slots"], state["det_hld_files"]
    step_label = (
        f"{_STATUS_ARROW} " if state["setup_ok"] and state["adr_has_content"] and not state["ai_done"] else "   "
    )
    print(f"  {step_label}{BOLD}Step 3:{RESET}  make build-hld-from-adr")
    if has_slots and det_hld_files:
        ok(f"Done — slots extracted, {len(det_hld_files)} draft(s) rendered")
    elif has_slots:
        warn("Slots extracted but drafts not rendered — re-run to complete")
    else:
        warn("Not run yet — AI extracts data from ADR and renders HLD drafts")
    print()


def _print_step_publish(state: dict) -> None:
    """Step 4: make publish (HLD)."""
    hld_built = state["hld_built"]
    step_label = f"{_STATUS_ARROW} " if state["ai_done"] and not hld_built else "   "
    print(f"  {step_label}{BOLD}Step 4:{RESET}  make publish  (runs in container)")
    if hld_built:
        parts = []
        if state["hld_stitched"]:
            parts.append("stitched")
        if state["hld_drawio_md"]:
            parts.append(f"{state['hld_drawio_md']} Drawio md")
        if state["hld_pngs"]:
            parts.append(f"{state['hld_pngs']} PNG(s)")
        if state["hld_pdfs"]:
            parts.append(f"{state['hld_pdfs']} PDF(s)")
        ok(f"Done — {', '.join(parts)}")
    else:
        warn("Not built yet — stitches phases, exports diagrams, generates PDFs")
    print()


def _print_step_lld(state: dict) -> None:
    """Step 5: make build-lld."""
    lld_built = state["lld_built"]
    step_label = f"{_STATUS_ARROW} " if state["hld_built"] and not lld_built else "   "
    print(f"  {step_label}{BOLD}Step 5:{RESET}  make build-lld  (runs in container)")
    if lld_built:
        parts = []
        if state["lld_stitched"]:
            parts.append("stitched")
        if state["lld_drawio_md"]:
            parts.append(f"{state['lld_drawio_md']} Drawio md")
        if state["lld_pngs"]:
            parts.append(f"{state['lld_pngs']} PNG(s)")
        if state["lld_pdfs"]:
            parts.append(f"{state['lld_pdfs']} PDF(s)")
        ok(f"Done — {', '.join(parts)}")
    else:
        warn("Not built yet — stitches phases, exports diagrams, generates PDFs")
    print()


def _print_step_workitems(state: dict) -> None:
    """Step 6: make workitems."""
    wi_files = state["wi_files"]
    step_label = f"{_STATUS_ARROW} " if state["lld_built"] and not wi_files else "   "
    print(f"  {step_label}{BOLD}Step 6:{RESET}  make workitems")
    if wi_files:
        ok(f"Done — {len(wi_files)} work item(s)")
    else:
        warn("Not run yet — extracts sprint work items from LLD")
    print()


def _print_optional(state: dict) -> None:
    """Optional targets footer."""
    print(f"  {BOLD}Optional:{RESET}")
    if state["prose_files"]:
        info(f"  Legacy prose drafts detected: {len(state['prose_files'])} file(s)")
    info('  make rvtools FILES="..."    — process RVTools XLSX into migration schedule')
    print()

def run_status(workspace: Path, project_type=None) -> None:
    """Print a plain-language project health report."""
    _bootstrap_ui()
    yaml_path = workspace / "project.yaml"

    heading("Project Status")

    if not yaml_path.exists():
        fail('project.yaml not found — run: make setup CLIENT="Your Client" PROJECT="OCP-V"')
        return

    with open(yaml_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    client, code = get_client_identity(cfg)
    client = client or "Unknown"
    engagement = cfg.get("engagement_type", "ocp-v")
    if project_type is None:
        project_type = _ui().get_project_type(engagement)
    print(f"\n  Project: {BOLD}{client}{RESET} ({code})")
    print(f"  {'─' * 50}\n")

    state = _gather_state(workspace, cfg, project_type)
    for step_fn in project_type.status_steps:
        step_fn(state)
