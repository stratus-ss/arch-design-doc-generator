#!/usr/bin/env python3
"""Draft Chapter 3 (Executive Summary) and Chapter 8 (Conclusions) from one HC report.

Optional Make path: --in-place replaces those chapters in the report.
Not part of check evaluation. Live apply in the container supports Cursor only.

Three model passes: P0/P1 (Chapter 3 + 8.1–8.3), P2 remaining work, P3 remaining work.
Engagement bounds (8.5) are appended in code.

Usage:
    python3 scripts/health_check/draft_summary_conclusion.py --dry-run REPORT.md
    python3 scripts/health_check/draft_summary_conclusion.py --in-place REPORT.md
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parents[1]
_SHARED_LIB = _SCRIPT_DIR.parent / "shared" / "lib"
_HC_REPORT = _SCRIPT_DIR / "hc_report"
for extra_path in (_SHARED_LIB, _SCRIPT_DIR, _HC_REPORT):
    extra = str(extra_path)
    if extra not in sys.path:
        sys.path.insert(0, extra)

from ai_invoke import ensure_cursor_key, ensure_cursor_sdk, invoke_ai
from extract_finding_descriptions import (
    FindingDescription,
    extract_finding_descriptions,
    format_count_line,
    format_grouped_title_dump,
    format_high_priority_dump,
)
from kb_loader import KnowledgeBase, load_kb

_DEFAULT_PROMPT = _SCRIPT_DIR / "prompts" / "draft_summary_conclusion.md"
_DEFAULT_PROMPT_P2 = _SCRIPT_DIR / "prompts" / "draft_conclusion_p2.md"
_DEFAULT_PROMPT_P3 = _SCRIPT_DIR / "prompts" / "draft_conclusion_p3.md"
_DUMP_PLACEHOLDER = "{{FINDING_DUMP}}"
_HEADING_LIST_PLACEHOLDER = "{{PRIORITY_WALK_HEADINGS}}"
HIGH_PRIORITY_BANDS = frozenset({"P0", "P1"})
HLD_TOOL_CHOICES = ("cursor", "claude", "codex")
CONTAINER_DRAFT_TOOLS = frozenset({"cursor"})
CHAPTER_THREE_HEADING = "## Chapter 3. Executive Summary"
EXECUTIVE_SUMMARY_HEADING = "### 3.1 Executive Summary"
TECHNICAL_SUMMARY_HEADING = "### 3.2 Technical Summary"
CHAPTER_EIGHT_HEADING = "## Chapter 8. Conclusions"
CLOSE_HEADING = "### 8.1 Close and cost of inaction"
REMEDIATION_HEADING = "### 8.2 Priority remediation"
SEQUENCE_HEADING = "### 8.3 Sequence and disruption"
REMAINING_WORK_HEADING = "### 8.4 Remaining work"
P2_WORK_HEADING = "#### P2 work units"
P3_WORK_HEADING = "#### P3 work units"
BOUNDS_HEADING = "### 8.5 Engagement bounds"
SUMMARY_STATISTICS_HEADING = "### Summary Statistics"
INTERNAL_USE_FOOTER = "*This document is prepared"
HORIZONTAL_RULE = "\n---\n"
ENGAGEMENT_BOUNDS_BODY = (
    "Key points:\n\n"
    "- This assessment reflects configuration and operational state at a "
    "single point in time; cluster state may have changed since data was captured.\n"
    "- Sizing, capacity planning, and performance benchmarking are outside "
    "the scope of this engagement.\n"
    "- Remediation timelines should be prioritized according to the P0–P3 "
    "classification: P0 findings require immediate attention, P1 findings "
    "should be addressed within the current sprint or change window.\n"
    "- Red Hat recommends scheduling a follow-up review after P0 and P1 "
    "remediations are completed to confirm resolution."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Draft Chapter 3 executive summary and Chapter 8 conclusions "
            "from one HC report."
        )
    )
    parser.add_argument(
        "report",
        type=Path,
        help="Path to one rendered HC report markdown file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Sidecar output path when not using --in-place",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write the filled prompts only; do not invoke an AI tool",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Replace Chapter 3 and Chapter 8 in the report file",
    )
    parser.add_argument(
        "--tool",
        default=os.environ.get("AI_TOOL", "cursor"),
        choices=list(HLD_TOOL_CHOICES),
        help="AI tool (default: AI_TOOL or cursor)",
    )
    parser.add_argument(
        "--model",
        default=(
            os.environ.get("AI_MODEL")
            or os.environ.get("CURSOR_MODEL")
            or "claude-sonnet-4-6"
        ),
        help="Model name (default: AI_MODEL / CURSOR_MODEL / claude-sonnet-4-6)",
    )
    parser.add_argument("--timeout", type=int, default=420)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument(
        "--prompt",
        type=Path,
        default=_DEFAULT_PROMPT,
        help="P0/P1 prompt template path",
    )
    parser.add_argument(
        "--prompt-p2",
        type=Path,
        default=_DEFAULT_PROMPT_P2,
        help="P2 remaining-work prompt template path",
    )
    parser.add_argument(
        "--prompt-p3",
        type=Path,
        default=_DEFAULT_PROMPT_P3,
        help="P3 remaining-work prompt template path",
    )
    return parser.parse_args()


def load_prompt_template(path: Path) -> str:
    if not path.is_file():
        print(f"Error: prompt template not found at {path}", file=sys.stderr)
        sys.exit(2)
    return path.read_text(encoding="utf-8")


def fill_prompt(
    template: str,
    finding_dump: str,
    heading_list: str = "",
) -> str:
    if _DUMP_PLACEHOLDER not in template:
        raise ValueError(f"prompt template missing {_DUMP_PLACEHOLDER}")
    filled = template.replace(_DUMP_PLACEHOLDER, finding_dump)
    if _HEADING_LIST_PLACEHOLDER in filled:
        filled = filled.replace(_HEADING_LIST_PLACEHOLDER, heading_list)
    return filled


def default_summary_conclusion_path(report_path: Path) -> Path:
    return report_path.with_name(report_path.stem + "_summary_conclusion.md")


def default_prompt_output_path(report_path: Path) -> Path:
    return report_path.with_name(report_path.stem + "_summary_conclusion.p0p1.prompt.md")


def default_p2_prompt_output_path(report_path: Path) -> Path:
    return report_path.with_name(report_path.stem + "_summary_conclusion.p2.prompt.md")


def default_p3_prompt_output_path(report_path: Path) -> Path:
    return report_path.with_name(report_path.stem + "_summary_conclusion.p3.prompt.md")


def unwrap_markdown_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped + ("\n" if stripped else "")
    lines = stripped.splitlines()
    lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    body = "\n".join(lines).strip()
    return body + ("\n" if body else "")


def resolve_output_path(report_path: Path, output: Path | None, dry_run: bool) -> Path:
    if output is not None:
        return output
    if dry_run:
        return default_prompt_output_path(report_path)
    return default_summary_conclusion_path(report_path)


def findings_in_bands(
    findings: list[FindingDescription],
    bands: frozenset[str],
) -> list[FindingDescription]:
    return [finding for finding in findings if finding.priority in bands]


def format_impact_line(check_ids: list[str], knowledge_base: KnowledgeBase) -> str:
    if not check_ids:
        return "Impact: unavailable"
    triple = knowledge_base.get_impact(check_ids[0])
    if triple is None:
        return "Impact: unavailable"
    kind, scope, detail = triple
    if kind == "none":
        return "Impact: none"
    label = kind.replace("-", " ")
    scope_text = f" ({scope})" if scope else ""
    detail_text = f" — {detail}" if detail else ""
    return f"Impact: {label}{scope_text}{detail_text}"


def impact_by_finding_id(findings: list[FindingDescription]) -> dict[str, str]:
    knowledge_base = load_kb()
    mapping: dict[str, str] = {}
    for finding in findings:
        mapping[finding.finding_id] = format_impact_line(
            finding.check_ids, knowledge_base
        )
    return mapping


def priority_walk_headings(findings: list[FindingDescription]) -> str:
    if not findings:
        return "(none)"
    lines = [
        f"- {finding.priority} — {finding.finding_id}. {finding.title}"
        for finding in findings
    ]
    return "\n".join(lines)


def build_p0p1_dump(all_findings: list[FindingDescription]) -> str:
    high_priority = findings_in_bands(all_findings, HIGH_PRIORITY_BANDS)
    return format_high_priority_dump(
        all_findings,
        high_priority,
        impact_by_finding_id(high_priority),
    )


def band_dump_with_counts(
    all_findings: list[FindingDescription],
    band_findings: list[FindingDescription],
    include_first_sentence: bool,
) -> str:
    grouped = format_grouped_title_dump(
        band_findings,
        include_first_sentence=include_first_sentence,
    )
    return f"{format_count_line(all_findings)}\n\n{grouped}"


def require_container_draft_tool(tool: str) -> None:
    if tool in CONTAINER_DRAFT_TOOLS:
        return
    print(
        f"Error: AI_TOOL={tool} is not in the container yet. "
        f"Supported now: {', '.join(sorted(CONTAINER_DRAFT_TOOLS))}. "
        "Add the tool id to CONTAINER_DRAFT_TOOLS after baking the CLI into the image.",
        file=sys.stderr,
    )
    sys.exit(2)


def resolve_cursor_python() -> str:
    override = os.environ.get("HC_CURSOR_PYTHON", "").strip()
    if override:
        return override
    try:
        import cursor_sdk  # noqa: F401
    except ImportError:
        return ensure_cursor_sdk(_REPO_ROOT)
    return sys.executable


def split_draft_chapters(model_text: str) -> tuple[str, str, str]:
    text = unwrap_markdown_fence(model_text).strip()
    if CHAPTER_THREE_HEADING not in text or CHAPTER_EIGHT_HEADING not in text:
        raise ValueError("model output missing Chapter 3 or Chapter 8 heading")
    if EXECUTIVE_SUMMARY_HEADING not in text:
        raise ValueError("model output missing ### 3.1 Executive Summary heading")
    if TECHNICAL_SUMMARY_HEADING not in text:
        raise ValueError("model output missing ### 3.2 Technical Summary heading")
    _prefix, rest = text.split(EXECUTIVE_SUMMARY_HEADING, 1)
    executive_body, after_exec = rest.split(TECHNICAL_SUMMARY_HEADING, 1)
    technical_body, conclusions_body = after_exec.split(CHAPTER_EIGHT_HEADING, 1)
    conclusions = conclusions_body.strip()
    for heading in (CLOSE_HEADING, REMEDIATION_HEADING, SEQUENCE_HEADING):
        if heading not in conclusions:
            raise ValueError(f"model output missing {heading}")
    if REMAINING_WORK_HEADING in conclusions or BOUNDS_HEADING in conclusions:
        raise ValueError("P0/P1 pass must not include 8.4 or 8.5")
    return executive_body.strip(), technical_body.strip(), conclusions


def split_work_unit_block(model_text: str, heading: str) -> str:
    text = unwrap_markdown_fence(model_text).strip()
    if heading not in text:
        raise ValueError(f"model output missing {heading}")
    _prefix, body = text.split(heading, 1)
    leftover = body.lstrip()
    next_heading_at = leftover.find("\n#### ")
    if next_heading_at != -1:
        leftover = leftover[:next_heading_at]
    next_chapter = leftover.find("\n## ")
    if next_chapter != -1:
        leftover = leftover[:next_chapter]
    return f"{heading}\n\n{leftover.strip()}\n"


def stub_work_unit_block(heading: str, empty_sentence: str) -> str:
    return f"{heading}\n\n{empty_sentence}\n"


def stitch_conclusions(
    close_through_sequence: str,
    p2_block: str,
    p3_block: str,
) -> str:
    return (
        f"{close_through_sequence.strip()}\n\n"
        f"{REMAINING_WORK_HEADING}\n\n"
        f"{p2_block.strip()}\n\n"
        f"{p3_block.strip()}\n\n"
        f"{BOUNDS_HEADING}\n\n"
        f"{ENGAGEMENT_BOUNDS_BODY}\n"
    )


def apply_summary_conclusion(
    report_markdown: str,
    executive_summary: str,
    technical_summary: str,
    conclusions: str,
) -> str:
    if CHAPTER_THREE_HEADING not in report_markdown:
        raise ValueError("report missing Chapter 3 heading")
    if SUMMARY_STATISTICS_HEADING not in report_markdown:
        raise ValueError("report missing Summary Statistics heading")
    if CHAPTER_EIGHT_HEADING not in report_markdown:
        raise ValueError("report missing Chapter 8 heading")
    if INTERNAL_USE_FOOTER not in report_markdown:
        raise ValueError("report missing internal-use footer")

    before_three, after_three_heading = report_markdown.split(CHAPTER_THREE_HEADING, 1)
    _old_three, after_three = after_three_heading.split(SUMMARY_STATISTICS_HEADING, 1)
    before_eight, after_eight_heading = after_three.split(CHAPTER_EIGHT_HEADING, 1)
    rule_at = after_eight_heading.rfind(HORIZONTAL_RULE)
    if rule_at == -1:
        raise ValueError("report missing horizontal rule before Chapter 8 footer")
    after_rule = after_eight_heading[rule_at:]
    chapter_three_body = (
        f"{EXECUTIVE_SUMMARY_HEADING}\n\n{executive_summary.strip()}\n\n"
        f"{TECHNICAL_SUMMARY_HEADING}\n\n{technical_summary.strip()}\n\n"
    )
    return (
        f"{before_three}{CHAPTER_THREE_HEADING}\n\n{chapter_three_body}"
        f"{SUMMARY_STATISTICS_HEADING}{before_eight}{CHAPTER_EIGHT_HEADING}\n\n"
        f"{conclusions.strip()}\n{after_rule}"
    )


def atomic_write(path: Path, text: str) -> None:
    temporary_path = path.with_name(path.name + ".tmp")
    temporary_path.write_text(text, encoding="utf-8")
    temporary_path.replace(path)


def run_model(
    prompt: str,
    tool: str,
    model: str,
    timeout: int,
    retries: int,
) -> str:
    cursor_python = "python3"
    if tool == "cursor":
        cursor_python = resolve_cursor_python()
        ensure_cursor_key()
    raw = invoke_ai(prompt, tool, model, timeout, retries, cursor_python)
    return unwrap_markdown_fence(raw)


def write_dry_run_prompts(
    report_path: Path,
    output: Path | None,
    p0p1_prompt: str,
    p2_prompt: str,
    p3_prompt: str,
) -> Path:
    p0p1_path = resolve_output_path(report_path, output, dry_run=True)
    if output is not None:
        p2_path = output.with_name(output.stem + ".p2.prompt.md")
        p3_path = output.with_name(output.stem + ".p3.prompt.md")
    else:
        p2_path = default_p2_prompt_output_path(report_path)
        p3_path = default_p3_prompt_output_path(report_path)
    p0p1_path.write_text(p0p1_prompt, encoding="utf-8")
    p2_path.write_text(p2_prompt, encoding="utf-8")
    p3_path.write_text(p3_prompt, encoding="utf-8")
    print(f"Filled prompts written to: {p0p1_path}", file=sys.stderr)
    print(f"Filled prompts written to: {p2_path}", file=sys.stderr)
    print(f"Filled prompts written to: {p3_path}", file=sys.stderr)
    return p0p1_path


def main() -> None:
    args = parse_args()
    report_path = args.report
    if not report_path.is_file():
        print(f"Error: report not found at {report_path}", file=sys.stderr)
        sys.exit(2)

    markdown = report_path.read_text(encoding="utf-8")
    all_findings = extract_finding_descriptions(markdown)
    high_priority = findings_in_bands(all_findings, HIGH_PRIORITY_BANDS)
    p2_findings = findings_in_bands(all_findings, frozenset({"P2"}))
    p3_findings = findings_in_bands(all_findings, frozenset({"P3"}))
    heading_list = priority_walk_headings(high_priority)

    p0p1_prompt = fill_prompt(
        load_prompt_template(args.prompt),
        build_p0p1_dump(all_findings),
    )
    p2_prompt = fill_prompt(
        load_prompt_template(args.prompt_p2),
        band_dump_with_counts(all_findings, p2_findings, True),
        heading_list,
    )
    p3_prompt = fill_prompt(
        load_prompt_template(args.prompt_p3),
        band_dump_with_counts(all_findings, p3_findings, False),
        heading_list,
    )

    if args.dry_run:
        write_dry_run_prompts(
            report_path, args.output, p0p1_prompt, p2_prompt, p3_prompt
        )
        return

    if args.in_place:
        require_container_draft_tool(args.tool)

    p0p1_raw = run_model(
        p0p1_prompt, args.tool, args.model, args.timeout, args.retries
    )
    executive_summary, technical_summary, close_through_sequence = split_draft_chapters(
        p0p1_raw
    )

    if p2_findings:
        p2_block = split_work_unit_block(
            run_model(p2_prompt, args.tool, args.model, args.timeout, args.retries),
            P2_WORK_HEADING,
        )
    else:
        p2_block = stub_work_unit_block(
            P2_WORK_HEADING, "No P2 findings were raised."
        )

    if p3_findings:
        p3_block = split_work_unit_block(
            run_model(p3_prompt, args.tool, args.model, args.timeout, args.retries),
            P3_WORK_HEADING,
        )
    else:
        p3_block = stub_work_unit_block(
            P3_WORK_HEADING, "No P3 findings were raised."
        )

    conclusions = stitch_conclusions(close_through_sequence, p2_block, p3_block)
    if args.in_place:
        updated = apply_summary_conclusion(
            markdown, executive_summary, technical_summary, conclusions
        )
        atomic_write(report_path, updated)
        print(f"Updated chapters in place: {report_path}", file=sys.stderr)
        return

    sidecar = (
        f"{CHAPTER_THREE_HEADING}\n\n"
        f"{EXECUTIVE_SUMMARY_HEADING}\n\n{executive_summary.strip()}\n\n"
        f"{TECHNICAL_SUMMARY_HEADING}\n\n{technical_summary.strip()}\n\n"
        f"{CHAPTER_EIGHT_HEADING}\n\n{conclusions.strip()}\n"
    )
    output_path = resolve_output_path(report_path, args.output, dry_run=False)
    output_path.write_text(sidecar, encoding="utf-8")
    print(f"Draft sections written to: {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
