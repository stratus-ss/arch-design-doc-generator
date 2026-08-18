"""Decide whether expensive slot-map AI extraction should run.

The slot map is cached. Regeneration calls the model (minutes). Skip when
extraction inputs are unchanged; extract when the map is missing or stale.
FORCE=1 extracts even when inputs are unchanged.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

FINGERPRINT_VERSION = 1


@dataclass(frozen=True)
class SlotCacheDecision:
    action: str
    status: str
    changed: tuple[str, ...]
    message: str


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_file(path: Path) -> str:
    if not path.is_file():
        return "MISSING"
    return hash_bytes(path.read_bytes())


def hash_text(text: str) -> str:
    return hash_bytes(text.encode("utf-8"))


def build_fingerprint(parts: dict[str, str]) -> dict:
    ordered = dict(sorted(parts.items()))
    combined = hash_text("\n".join(f"{key}={value}" for key, value in ordered.items()))
    return {"version": FINGERPRINT_VERSION, "combined": combined, "inputs": ordered}


def load_fingerprint(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or not payload.get("combined"):
        return None
    return payload


def save_fingerprint(path: Path, fingerprint: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fingerprint, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def changed_inputs(stored: dict, current: dict) -> tuple[str, ...]:
    old_inputs = stored.get("inputs") if isinstance(stored.get("inputs"), dict) else {}
    new_inputs = current.get("inputs") if isinstance(current.get("inputs"), dict) else {}
    keys = sorted(set(old_inputs) | set(new_inputs))
    return tuple(key for key in keys if old_inputs.get(key) != new_inputs.get(key))


def decide_extraction(
    *,
    slot_exists: bool,
    force: bool,
    stored: dict | None,
    current: dict,
) -> SlotCacheDecision:
    if force:
        changed = changed_inputs(stored, current) if stored else ()
        return SlotCacheDecision(
            "extract",
            "forced",
            changed,
            "FORCE=1 requested a fresh extract",
        )
    if not slot_exists:
        return SlotCacheDecision("extract", "missing", (), "no slot map on disk")
    if stored is None:
        return SlotCacheDecision(
            "skip",
            "untracked",
            (),
            "slot map exists with no input fingerprint; skip to avoid surprise model cost",
        )
    changed = changed_inputs(stored, current)
    if not changed:
        return SlotCacheDecision("skip", "fresh", (), "extraction inputs unchanged")
    return SlotCacheDecision(
        "extract",
        "stale",
        changed,
        "extraction inputs changed",
    )


_STATUS_LABELS = {
    "fresh": "UP TO DATE",
    "stale": "STALE",
    "missing": "MISSING",
    "forced": "FORCED",
    "untracked": "UNTRACKED",
}


def format_decision(decision: SlotCacheDecision, slot_path: Path, force_hint: str) -> str:
    status_label = _STATUS_LABELS.get(decision.status, decision.status.upper())
    lines = [
        "=== Slot map ===",
        f"  file:    {slot_path}",
        f"  status:  {status_label}",
    ]
    if decision.changed:
        lines.append(f"  changed: {', '.join(decision.changed)}")
    if decision.action == "extract":
        lines.append("  action:  EXTRACT — calls the model (typically several minutes)")
        lines.append(f"           {decision.message}")
    else:
        lines.append("  action:  SKIP extraction")
        lines.append(f"           {decision.message}")
        if decision.status == "fresh":
            lines.append(f"           Re-extract anyway: {force_hint}")
        elif decision.status == "untracked":
            lines.append(f"           Re-extract and start tracking: {force_hint}")
    return "\n".join(lines)
