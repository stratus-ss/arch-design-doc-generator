#!/usr/bin/env python3
"""Draft Chapter 3 (Executive Summary) and Chapter 8 (Conclusions) from one HC report.

Optional Make path: --in-place replaces those chapters in the report.
Not part of check evaluation. Live apply in the container supports Cursor only.

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
for extra_path in (_SHARED_LIB, _SCRIPT_DIR):
    extra = str(extra_path)
    if extra not in sys.path:
        sys.path.insert(0, extra)

from ai_invoke import ensure_cursor_key, ensure_cursor_sdk, invoke_ai
from extract_finding_descriptions import (
    extract_finding_descriptions,
    format_finding_descriptions,
)

_DEFAULT_PROMPT = _SCRIPT_DIR / "prompts" / "draft_summary_conclusion.md"
_DUMP_PLACEHOLDER = "{{FINDING_DUMP}}"
HLD_TOOL_CHOICES = ("cursor", "claude", "codex")
CONTAINER_DRAFT_TOOLS = frozenset({"cursor"})
CHAPTER_THREE_HEADING = "## Chapter 3. Executive Summary"
EXECUTIVE_SUMMARY_HEADING = "### 3.1 Executive Summary"
TECHNICAL_SUMMARY_HEADING = "### 3.2 Technical Summary"
CHAPTER_EIGHT_HEADING = "## Chapter 8. Conclusions"
SUMMARY_STATISTICS_HEADING = "### Summary Statistics"
INTERNAL_USE_FOOTER = "*This document is prepared"
HORIZONTAL_RULE = "\n---\n"


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
        help="Write the filled prompt only; do not invoke an AI tool",
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
        help="Prompt template path",
    )
    return parser.parse_args()


def load_prompt_template(path: Path) -> str:
    if not path.is_file():
        print(f"Error: prompt template not found at {path}", file=sys.stderr)
        sys.exit(2)
    return path.read_text(encoding="utf-8")


def fill_prompt(template: str, finding_dump: str) -> str:
    if _DUMP_PLACEHOLDER not in template:
        raise ValueError(f"prompt template missing {_DUMP_PLACEHOLDER}")
    return template.replace(_DUMP_PLACEHOLDER, finding_dump)


def default_summary_conclusion_path(report_path: Path) -> Path:
    return report_path.with_name(report_path.stem + "_summary_conclusion.md")


def default_prompt_output_path(report_path: Path) -> Path:
    return report_path.with_name(report_path.stem + "_summary_conclusion.prompt.md")


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


def build_finding_dump(markdown: str, report_path: Path) -> str:
    findings = extract_finding_descriptions(markdown)
    return format_finding_descriptions(
        findings,
        report_path,
        include_source_path=False,
    )


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
    return executive_body.strip(), technical_body.strip(), conclusions_body.strip()


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


def main() -> None:
    args = parse_args()
    report_path = args.report
    if not report_path.is_file():
        print(f"Error: report not found at {report_path}", file=sys.stderr)
        sys.exit(2)

    markdown = report_path.read_text(encoding="utf-8")
    finding_dump = build_finding_dump(markdown, report_path)
    template = load_prompt_template(args.prompt)
    filled = fill_prompt(template, finding_dump)

    if args.dry_run:
        output_path = resolve_output_path(report_path, args.output, dry_run=True)
        output_path.write_text(filled, encoding="utf-8")
        print(f"Filled prompt written to: {output_path}", file=sys.stderr)
        return

    if args.in_place:
        require_container_draft_tool(args.tool)

    rendered = run_model(
        filled, args.tool, args.model, args.timeout, args.retries
    )
    if args.in_place:
        executive_summary, technical_summary, conclusions = split_draft_chapters(rendered)
        updated = apply_summary_conclusion(
            markdown, executive_summary, technical_summary, conclusions
        )
        atomic_write(report_path, updated)
        print(f"Updated chapters in place: {report_path}", file=sys.stderr)
        return

    output_path = resolve_output_path(report_path, args.output, dry_run=False)
    output_path.write_text(rendered, encoding="utf-8")
    print(f"Draft sections written to: {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
