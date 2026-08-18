#!/usr/bin/env python3
"""Shared markdown utility helpers for deterministic pipeline."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

from diagram_layout import PHASE_DIAGRAM_PREFIXES, TOP_LEVEL_PREFIXES

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
CITATION_RE = re.compile(r"\(ADR[^)\n]*\)")
PLACEHOLDER_RE = re.compile(r"(?<!\$)\{[A-Z0-9_]+\}")
PLACEHOLDER_TOKEN_RE = re.compile(r"(?<!\$)\{([A-Z0-9_]+)\}")
DERIVED_SLOTS = (
    ("CLIENT_LOWER", "CLIENT"),
    ("SIEM_LOWER", "SIEM_PLATFORM"),
    ("EVENT_MGMT_LOWER", "NOC_PLATFORM"),
    ("BLOCK_STORAGE_LOWER", "BLOCK_STORAGE_VENDOR"),
    ("TIER_PRIMARY_LOWER", "TIER_PRIMARY"),
    ("TIER_MIDDLE_LOWER", "TIER_MIDDLE"),
    ("TIER_EDGE_LOWER", "TIER_EDGE"),
)
TIER_COUNT_DEFAULT = 3
UNUSED_TIER_LABEL = "—"
UNUSED_TIER_LOWER = "na"
SAME_AS_PREFIX = "same as "
BLANK_SLOT_VALUES = {"", "{TBD}", "TBD"}
OVERLAY_SLOT_KEYS = (
    "CLIENT_DOMAIN",
    "GITOPS_HOST",
    "REGISTRY_MIRROR",
    "REGISTRY_MIRROR_FQDN",
    "HUB_CLUSTER_NAME",
    "NTP_DOMAIN",
)
MIRROR_POLICY_COPY = "same_as_image_registry"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_section_citations(text: str) -> Dict[str, List[str]]:
    lines = text.splitlines()
    section_citations: Dict[str, List[str]] = {}
    heading_stack: List[Tuple[int, str]] = []

    for line in lines:
        heading_match = HEADING_RE.match(line)
        if heading_match:
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, title))
        path = " > ".join(h[1] for h in heading_stack) if heading_stack else "__root__"
        citations = CITATION_RE.findall(line)
        if citations:
            section_citations.setdefault(path, []).extend(citations)
    return section_citations


def parse_headings_and_tables(text: str) -> Tuple[List[Tuple[int, str]], List[Tuple[str, str, int]]]:
    lines = text.splitlines()
    headings: List[Tuple[int, str]] = []
    tables: List[Tuple[str, str, int]] = []
    heading_stack: List[Tuple[int, str]] = []

    i = 0
    while i < len(lines):
        line = lines[i]
        heading_match = HEADING_RE.match(line)
        if heading_match:
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, title))
            headings.append((level, title))

        if line.strip().startswith("|"):
            block = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                block.append(lines[i].rstrip())
                i += 1
            if len(block) >= 2:
                sep = block[1].replace("|", "").strip().replace(" ", "")
                if sep and set(sep) <= set("-:"):
                    path = " > ".join(h[1] for h in heading_stack)
                    tables.append((path, block[0].strip(), max(0, len(block) - 2)))
            continue
        i += 1
    return headings, tables


def _canonical_slot_value(raw: object) -> str:
    if isinstance(raw, dict):
        return str(raw.get("value", "")).strip()
    if raw is None:
        return ""
    return str(raw).strip()


def _set_slot_value(slot_map: dict, key: str, value: str, source: str = "derived_default") -> None:
    existing = slot_map.get(key)
    if isinstance(existing, dict):
        slot_map[key] = {
            "value": value,
            "confidence": existing.get("confidence", "high"),
            "evidence_excerpt": "",
            "evidence_source": source,
        }
        return
    slot_map[key] = value


def _parse_tier_count(slot_map: dict) -> int:
    raw = _canonical_slot_value(slot_map.get("TIER_COUNT", ""))
    if raw in {"1", "2", "3"}:
        return int(raw)
    return TIER_COUNT_DEFAULT


def _needs_tier_name(value: str) -> bool:
    if value in BLANK_SLOT_VALUES or value == UNUSED_TIER_LABEL:
        return True
    return value.startswith(SAME_AS_PREFIX)


def _fill_named_tier(slot_map: dict, key: str, default: str) -> None:
    value = _canonical_slot_value(slot_map.get(key, ""))
    if _needs_tier_name(value):
        _set_slot_value(slot_map, key, default)


def _apply_middle_tier(slot_map: dict, count: int, primary: str) -> None:
    if count >= 2:
        _fill_named_tier(slot_map, "TIER_MIDDLE", "DC2")
        return
    _set_slot_value(slot_map, "TIER_MIDDLE", f"{SAME_AS_PREFIX}{primary}")


def _apply_edge_tier(slot_map: dict, count: int, primary: str) -> None:
    if count >= 3:
        _fill_named_tier(slot_map, "TIER_EDGE", "DC3")
        return
    if count == 1:
        _set_slot_value(slot_map, "TIER_EDGE", f"{SAME_AS_PREFIX}{primary}")
        return
    _set_slot_value(slot_map, "TIER_EDGE", UNUSED_TIER_LABEL)


def _apply_tier_defaults(slot_map: dict) -> int:
    count = _parse_tier_count(slot_map)
    stored = _canonical_slot_value(slot_map.get("TIER_COUNT", ""))
    if stored != str(count):
        _set_slot_value(slot_map, "TIER_COUNT", str(count))
    primary = _canonical_slot_value(slot_map.get("TIER_PRIMARY", ""))
    if _needs_tier_name(primary):
        primary = "DC1"
        _set_slot_value(slot_map, "TIER_PRIMARY", primary)
    _apply_middle_tier(slot_map, count, primary)
    _apply_edge_tier(slot_map, count, primary)
    return count


def _apply_derived_lowers(slot_map: dict) -> None:
    for derived, canonical in DERIVED_SLOTS:
        raw = slot_map.get(canonical, "")
        value = _canonical_slot_value(raw)
        if not value:
            continue
        derived_value = value.lower().replace(" ", "")
        if isinstance(raw, dict):
            slot_map[derived] = {
                "value": derived_value,
                "confidence": raw.get("confidence", "high"),
                "evidence_excerpt": "",
                "evidence_source": "derived_default",
            }
        else:
            slot_map[derived] = derived_value


def _fix_unused_tier_lowers(slot_map: dict, count: int) -> None:
    primary_lower = _canonical_slot_value(slot_map.get("TIER_PRIMARY_LOWER", ""))
    if count == 1:
        _set_slot_value(slot_map, "TIER_MIDDLE_LOWER", primary_lower)
        _set_slot_value(slot_map, "TIER_EDGE_LOWER", primary_lower)
        return
    if count == 2:
        _set_slot_value(slot_map, "TIER_EDGE_LOWER", UNUSED_TIER_LOWER)


def _is_blank_slot_value(value: object) -> bool:
    return _canonical_slot_value(value) in BLANK_SLOT_VALUES


def _write_slot_envelope(slot_map: dict, key: str, value: str, source: str) -> None:
    existing = slot_map.get(key)
    confidence = "high"
    if isinstance(existing, dict):
        confidence = str(existing.get("confidence") or "high")
    slot_map[key] = {
        "value": value,
        "confidence": confidence,
        "evidence_excerpt": "",
        "evidence_source": source,
    }


def apply_registry_mirror_policy(slots: dict, project_cfg: dict) -> dict:
    """Copy IMAGE_REGISTRY into empty REGISTRY_MIRROR when policy requests it."""
    policy = str(project_cfg.get("registry_mirror_policy") or "unset").strip()
    if policy != MIRROR_POLICY_COPY:
        return slots
    if not _is_blank_slot_value(slots.get("REGISTRY_MIRROR", "")):
        return slots
    image = _canonical_slot_value(slots.get("IMAGE_REGISTRY", ""))
    if image in BLANK_SLOT_VALUES:
        return slots
    _write_slot_envelope(slots, "REGISTRY_MIRROR", image, "registry_mirror_policy")
    return slots


def apply_yaml_overlay(slots: dict, project_cfg: dict) -> dict:
    """Apply nonempty project.yaml slots: keys. Empty overlay does not wipe extract."""
    overlay = project_cfg.get("slots")
    if not isinstance(overlay, dict):
        overlay = {}
    for key in OVERLAY_SLOT_KEYS:
        if key not in overlay:
            continue
        raw = overlay.get(key)
        if raw is None:
            continue
        value = str(raw).strip()
        if value in BLANK_SLOT_VALUES:
            continue
        _write_slot_envelope(slots, key, value, "project.yaml")
    apply_registry_mirror_policy(slots, project_cfg)
    return slots


def empty_required_slots(slots: dict, schema: dict) -> list[str]:
    """Return schema-required keys whose values are blank."""
    phase_map = schema.get("required_slots_for_phase")
    if not isinstance(phase_map, dict):
        return []
    required: set[str] = set()
    for names in phase_map.values():
        if isinstance(names, list):
            required.update(str(name) for name in names)
    empty_keys: list[str] = []
    for key in sorted(required):
        if _is_blank_slot_value(slots.get(key, "")):
            empty_keys.append(key)
    return empty_keys


def apply_derived_slots(slot_map: dict) -> dict:
    """Set tier defaults and lowercase derived slots. Mutates slot_map."""
    count = _apply_tier_defaults(slot_map)
    _apply_derived_lowers(slot_map)
    _fix_unused_tier_lowers(slot_map, count)
    return slot_map


def render_contract_text(value: str, slot_map: dict) -> str:
    def repl(match: re.Match[str]) -> str:
        token = match.group(1)
        raw = slot_map.get(token, "")
        if isinstance(raw, dict):
            raw = raw.get("value", "")
        v = str(raw).strip()
        return v if v else "{TBD}"

    return PLACEHOLDER_TOKEN_RE.sub(repl, value)


# PHASE_DIAGRAM_PREFIXES / TOP_LEVEL_PREFIXES live in diagram_layout.py


def diagram_dest_for(filename: str) -> str:
    """Return phase dir name, or "" for top-level output/Diagrams placement."""
    for phase, prefixes in PHASE_DIAGRAM_PREFIXES.items():
        for prefix in prefixes:
            if filename.startswith(prefix):
                return phase
    for prefix in TOP_LEVEL_PREFIXES:
        if filename.startswith(prefix):
            return ""
    return ""


def render_drawio_tree(examples_dir: Path, dest_root: Path, slot_map: dict) -> int:
    """Stamp {TOKEN} in example drawio files into dest_root. Overwrites."""
    if not examples_dir.is_dir():
        return 0
    dest_root.mkdir(parents=True, exist_ok=True)
    written = 0
    for src in sorted(examples_dir.glob("*.drawio")):
        phase = diagram_dest_for(src.name)
        dest_dir = dest_root / phase if phase else dest_root
        dest_dir.mkdir(parents=True, exist_ok=True)
        text = src.read_text(encoding="utf-8")
        dest_dir.joinpath(src.name).write_text(render_contract_text(text, slot_map), encoding="utf-8")
        written += 1
    return written
