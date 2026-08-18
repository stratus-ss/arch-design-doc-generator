"""Slot-map schema validation (extracted from slots.py)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def validate_slots_against_schema(slots: Dict[str, Any], schema: dict) -> List[dict]:
    """Basic schema validation returning list of error dicts."""
    errors: List[dict] = []
    valid_confidences = {"high", "medium", "low"}
    schema_slots = schema.get("slots", {})

    for slot_name, entry in slots.items():
        if slot_name not in schema_slots:
            errors.append({"type": "unknown_key", "slot": slot_name, "message": f"Slot '{slot_name}' not in schema."})
            continue
        if not isinstance(entry, dict):
            errors.append(
                {
                    "type": "missing_evidence_field",
                    "slot": slot_name,
                    "message": "Slot entry must be a dict with value/confidence/evidence_excerpt/evidence_source.",
                }
            )
            continue
        for field in ("value", "confidence", "evidence_excerpt", "evidence_source"):
            if field not in entry:
                errors.append(
                    {
                        "type": "missing_evidence_field",
                        "slot": slot_name,
                        "message": f"Missing required field '{field}'.",
                    }
                )
        if "confidence" in entry and entry["confidence"] not in valid_confidences:
            errors.append(
                {
                    "type": "invalid_confidence",
                    "slot": slot_name,
                    "message": f"Invalid confidence '{entry['confidence']}'. Must be high/medium/low.",
                }
            )
        if "value" in entry and not isinstance(entry["value"], str):
            errors.append({"type": "invalid_value_format", "slot": slot_name, "message": "Value must be a string."})

    return errors


def validate_slot_file(slots_file: Path, phases: List[str], schema_file: Path | None = None) -> int:
    schema_path = schema_file or (Path(__file__).parent / "slot_schema.json")
    payload = json.loads(slots_file.read_text(encoding="utf-8"))
    raw_slots = payload.get("slots", payload)
    schema = json.loads(schema_path.read_text(encoding="utf-8")) if schema_path.exists() else {"slots": {}}
    is_flat = bool(raw_slots) and all(not isinstance(v, dict) for v in raw_slots.values())

    if is_flat:
        slots = {k: str(v).strip() if v is not None else "" for k, v in raw_slots.items()}
        errors: List[dict] = []
        warnings: List[str] = []
    else:
        slots = raw_slots
        errors = validate_slots_against_schema(slots, schema)
        warnings = []

    required_map = schema.get("required_slots_for_phase", {})
    for phase in phases:
        for slot_name in required_map.get(phase, []):
            if slot_name not in slots:
                errors.append(
                    {
                        "type": "missing_required_slot",
                        "slot": slot_name,
                        "message": f"Required slot '{slot_name}' missing for {phase}.",
                    }
                )
            elif is_flat and str(slots.get(slot_name, "")).strip() in ("", "{TBD}"):
                warnings.append(f"Required slot '{slot_name}' unresolved for {phase}.")

    if errors:
        for e in errors:
            print(f"ERROR: {e['message']}", file=sys.stderr)
        return 1
    for w in warnings:
        print(f"WARN: {w}", file=sys.stderr)
    print("Schema validation: PASS", file=sys.stderr)
    return 0
