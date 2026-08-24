#!/usr/bin/env python3
"""Patch docs/HC_RECOMMENDATION_AUDIT_LOG.md from TOML why-rec + recommendation.

Usage:
  python3 scripts/health_check/update_recommendation_audit_log.py CHECK_ID [CHECK_ID ...]
  python3 scripts/health_check/update_recommendation_audit_log.py --all
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[2]
KB_DIR = REPO_ROOT / "scripts" / "health_check" / "hc_report" / "kb"
AUDIT_LOG = REPO_ROOT / "docs" / "HC_RECOMMENDATION_AUDIT_LOG.md"

_STATUS_BADGES = {
    "CORRECTED": "`🔧 CORRECTED`",
    "ENGINEERING-JUDGMENT-CONFIRMED": "`⚠️ ENGINEERING-JUDGMENT-CONFIRMED`",
    "VERIFIED": "`✅ VERIFIED`",
    "ALIAS": "`↪️ ALIAS`",
}

_BULLET_START = re.compile(
    r"^(`✅ VERIFIED`|CORRECTED\.|ENGINEERING JUDGMENT|ENGINEERING-JUDGMENT|"
    r"Check story:|The rec remediates|Impact |Why the check fires|"
    r"This is a section overview|Prometheus exec|etcdctl |`oc debug`)"
)

_WHY_REC_BLOCK = re.compile(
    r'check_id\s*=\s*"(?P<check_id>[^"]+)"(?P<body>.*?)(?=\n\[\[checks\]\]|\n\[checks\.|\Z)',
    re.DOTALL,
)
_WHY_REC_COMMENTS = re.compile(
    r"# why-rec\n(?P<comments>(?:# .*\n)+)",
)


def _decode_toml_entries(path: Path) -> dict[str, dict]:
    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    entries: dict[str, dict] = {}
    for entry in payload.get("checks", []):
        check_id = str(entry.get("check_id", "")).strip()
        if check_id:
            entries[check_id] = entry
    return entries


def _why_rec_lines(toml_text: str, check_id: str) -> list[str]:
    for match in _WHY_REC_BLOCK.finditer(toml_text):
        if match.group("check_id") != check_id:
            continue
        comments = _WHY_REC_COMMENTS.search(match.group("body"))
        if comments is None:
            return []
        lines: list[str] = []
        for raw_line in comments.group("comments").splitlines():
            if raw_line.startswith("# "):
                lines.append(raw_line[2:])
            elif raw_line == "#":
                lines.append("")
        return lines
    return []


def _status_from_why_rec(lines: list[str]) -> str:
    joined = " ".join(lines)
    if "CORRECTED" in joined:
        return "CORRECTED"
    if "ENGINEERING JUDGMENT" in joined or "ENGINEERING-JUDGMENT" in joined:
        return "ENGINEERING-JUDGMENT-CONFIRMED"
    return "VERIFIED"


def _why_rec_bullets(lines: list[str]) -> list[str]:
    bullets: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if not bullets or _BULLET_START.match(stripped):
            bullets.append(stripped)
            continue
        bullets[-1] = f"{bullets[-1]} {stripped}"
    return bullets


def _blockquote(text: str) -> str:
    lines = text.strip().splitlines() or [""]
    return "\n".join(f"> {line}" if line else ">" for line in lines)


def _render_alias_section(
    check_id: str,
    filename: str,
    entry: dict,
    why_rec_lines: list[str],
) -> str:
    title = str(entry.get("title", "")).strip()
    canonical_id = str(entry.get("content_from", "")).strip()
    why_block = "\n".join(f"- {bullet}" for bullet in _why_rec_bullets(why_rec_lines))
    return (
        f'<a id="{check_id}"></a>\n'
        f"### `{check_id}` — {title}\n"
        f"\n"
        f"**File:** `scripts/health_check/hc_report/kb/{filename}`  \n"
        f"**Status:** {_STATUS_BADGES['ALIAS']}  \n"
        f"**content_from:** [`{canonical_id}`](#{canonical_id})\n"
        f"\n"
        f"Recommendation, description, impact, verification, and links inherit from the canonical row. "
        f"Audit [`{canonical_id}`](#{canonical_id}).\n"
        f"\n"
        f"**Why this rec is correct:**\n"
        f"\n"
        f"{why_block}\n"
        f"\n"
        f"---\n"
    )


def _render_section(
    check_id: str,
    filename: str,
    entry: dict,
    why_rec_lines: list[str],
) -> str:
    title = str(entry.get("title", "")).strip()
    description = str(entry.get("description", "")).strip()
    recommendation = str(entry.get("recommendation", "")).strip()
    verification = str(entry.get("verification", "")).strip() or "_(none)_"
    impact = str(entry.get("impact", "")).strip()
    impact_scope = str(entry.get("impact_scope", "")).strip()
    impact_detail = str(entry.get("impact_detail", "")).strip()
    status = _status_from_why_rec(why_rec_lines)
    badge = _STATUS_BADGES[status]
    if impact_scope:
        impact_line = f"**Impact:** `{impact}` ({impact_scope})"
    else:
        impact_line = f"**Impact:** `{impact}`"
    detail_block = ""
    if impact_detail:
        detail_block = f"\n**Impact detail:** {impact_detail}\n"
    why_block = "\n".join(f"- {bullet}" for bullet in _why_rec_bullets(why_rec_lines))
    return (
        f'<a id="{check_id}"></a>\n'
        f"### `{check_id}` — {title}\n"
        f"\n"
        f"**File:** `scripts/health_check/hc_report/kb/{filename}`  \n"
        f"**Status:** {badge}  \n"
        f"{impact_line}\n"
        f"{detail_block}\n"
        f"**What `description` says the check is:**\n"
        f"\n"
        f"{_blockquote(description)}\n"
        f"\n"
        f"**What `recommendation` tells the reader to do:**\n"
        f"\n"
        f"```\n"
        f"{recommendation}\n"
        f"```\n"
        f"\n"
        f"**What `verification` tells the reader to run:**\n"
        f"\n"
        f"```\n"
        f"{verification}\n"
        f"```\n"
        f"\n"
        f"**Why this rec is correct:**\n"
        f"\n"
        f"{why_block}\n"
        f"\n"
        f"---\n"
    )


def _kb_files() -> list[Path]:
    return sorted(KB_DIR.glob("7_*.toml"))


def _locate_check(check_id: str) -> tuple[Path, dict, str]:
    for path in _kb_files():
        entries = _decode_toml_entries(path)
        if check_id in entries:
            return path, entries[check_id], path.read_text(encoding="utf-8")
    raise KeyError(f"check_id not found in KB: {check_id}")


def _replace_section(audit_text: str, check_id: str, section: str) -> str:
    pattern = re.compile(
        rf'<a id="{re.escape(check_id)}"></a>.*?\n---\n',
        re.DOTALL,
    )
    # Function replacement: string repl would interpret `\n` / `\t` in jsonpath.
    updated, count = pattern.subn(lambda _match: section, audit_text, count=1)
    if count != 1:
        raise ValueError(f"expected one audit section for {check_id}, found {count}")
    return updated


def _replace_index_status(audit_text: str, check_id: str, badge: str) -> str:
    pattern = re.compile(
        rf"(\| \[`{re.escape(check_id)}`\]\(#{re.escape(check_id)}\) \| `[^`]+` \| )`[^`]+`"
    )
    updated, count = pattern.subn(rf"\1{badge}", audit_text, count=1)
    if count != 1:
        raise ValueError(f"expected one index row for {check_id}, found {count}")
    return updated


def _count_status_badges(audit_text: str) -> dict[str, int]:
    status_lines = re.findall(r"\*\*Status:\*\* (`[^`]+`)", audit_text)
    index_lines = re.findall(
        r"\| \[`[^`]+`\]\(#[^)]+\) \| `[^`]+` \| (`[^`]+`)",
        audit_text,
    )
    if len(status_lines) != len(index_lines):
        raise ValueError(
            f"index/section status count mismatch: "
            f"index={len(index_lines)} sections={len(status_lines)}"
        )
    counts = {label: 0 for label in _STATUS_BADGES}
    inverse = {badge: label for label, badge in _STATUS_BADGES.items()}
    for badge in status_lines:
        label = inverse.get(badge)
        if label is None:
            raise ValueError(f"unknown status badge: {badge}")
        counts[label] += 1
    return counts


def _recount_status_table(audit_text: str) -> str:
    counts = _count_status_badges(audit_text)
    corrected = counts["CORRECTED"]
    judgment = counts["ENGINEERING-JUDGMENT-CONFIRMED"]
    verified = counts["VERIFIED"]
    alias_count = counts["ALIAS"]
    total = corrected + judgment + verified + alias_count
    table = (
        "| Status | Count |\n"
        "|--------|-------|\n"
        f"| CORRECTED | {corrected} |\n"
        f"| ENGINEERING-JUDGMENT-CONFIRMED | {judgment} |\n"
        f"| VERIFIED | {verified} |\n"
        f"| ALIAS | {alias_count} |\n"
        f"| Total | {total} |\n"
    )
    return re.sub(
        r"\| Status \| Count \|\n\|--------\|-------\|\n(?:\| .*\n)+",
        table,
        audit_text,
        count=1,
    )


def update_checks(check_ids: list[str]) -> None:
    audit_text = AUDIT_LOG.read_text(encoding="utf-8")
    for check_id in check_ids:
        path, entry, toml_text = _locate_check(check_id)
        why_rec_lines = _why_rec_lines(toml_text, check_id)
        if not why_rec_lines:
            raise ValueError(f"missing why-rec comments for {check_id}")
        canonical_id = str(entry.get("content_from", "")).strip()
        if canonical_id:
            section = _render_alias_section(check_id, path.name, entry, why_rec_lines)
            status_label = "ALIAS"
        else:
            section = _render_section(check_id, path.name, entry, why_rec_lines)
            status_label = _status_from_why_rec(why_rec_lines)
        audit_text = _replace_section(audit_text, check_id, section)
        badge = _STATUS_BADGES[status_label]
        audit_text = _replace_index_status(audit_text, check_id, badge)
        print(f"updated={check_id} status={badge} file={path.name}")
    audit_text = _recount_status_table(audit_text)
    AUDIT_LOG.write_text(audit_text, encoding="utf-8")


def _all_check_ids() -> list[str]:
    check_ids: list[str] = []
    for path in _kb_files():
        check_ids.extend(_decode_toml_entries(path).keys())
    return check_ids


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("check_ids", nargs="*")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    if args.all:
        check_ids = _all_check_ids()
    else:
        check_ids = args.check_ids
    if not check_ids:
        parser.error("pass CHECK_ID arguments or --all")
    update_checks(check_ids)
    return 0


if __name__ == "__main__":
    sys.exit(main())
