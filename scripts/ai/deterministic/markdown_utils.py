#!/usr/bin/env python3
"""Shared markdown utility helpers for deterministic pipeline."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
CITATION_RE = re.compile(r"\(ADR[^)\n]*\)")
PLACEHOLDER_RE = re.compile(r"\{[A-Z0-9_]+\}")
PLACEHOLDER_TOKEN_RE = re.compile(r"\{([A-Z0-9_]+)\}")


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


def render_contract_text(value: str, slot_map: dict) -> str:
    def repl(match: re.Match[str]) -> str:
        token = match.group(1)
        raw = slot_map.get(token, "")
        if isinstance(raw, dict):
            raw = raw.get("value", "")
        v = str(raw).strip()
        return v if v else "{TBD}"

    return PLACEHOLDER_TOKEN_RE.sub(repl, value)
