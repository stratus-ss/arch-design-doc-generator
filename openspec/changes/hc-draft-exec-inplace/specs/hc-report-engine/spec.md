# Health Check Report Engine (`hc-draft-exec-inplace` delta)

## MODIFIED Requirements

### Requirement: No AI on the Health Check evaluation path
The Health Check **engine** CLI (`scripts/health_check/hc_report/cli.py`) SHALL NOT import or invoke the HLD/LLD AI stack. An optional **post-render** process MAY draft Chapter 3 and Chapter 8 after `generate_report.py` has written markdown.

#### Scenario: CLI source has no AI tokens
- GIVEN `scripts/health_check/hc_report/cli.py`
- WHEN the file is scanned for `ai_invoke`, `prompt_loader`, `invoke_ai`, `load_prompt_template`, or `CURSOR_API_KEY`
- THEN none of those tokens appear

## ADDED Requirements

### Requirement: Optional post-render Chapter 3/8 draft
When `HC_SUMMARY_CONCLUSION=1`, the container SHALL run `draft_summary_conclusion.py --in-place` on each generated Health Check markdown report **after** `generate_report.py` succeeds. When `HC_SUMMARY_CONCLUSION` is unset, empty, or `0`, no model SHALL be invoked during `make hc-report`.

#### Scenario: Opt-in draft runs after generate
- GIVEN `HC_SUMMARY_CONCLUSION=1` and a written Health Check markdown report
- WHEN `cmd_hc_report` finishes `generate_report.py` successfully
- THEN `draft_summary_conclusion.py --in-place` runs as a separate process
- AND `hc_report/cli.py` is not the process that calls `invoke_ai`

#### Scenario: Default report is deterministic
- GIVEN `HC_SUMMARY_CONCLUSION` unset
- WHEN `make hc-report` runs
- THEN no model is invoked
- AND Chapter 3 remains the engine placeholder unless `--exec-summary` was passed to generate

#### Scenario: Unsupported container tool fails closed
- GIVEN `--in-place` and `AI_TOOL=claude` (or `codex`) while that tool is not in `CONTAINER_DRAFT_TOOLS`
- WHEN `draft_summary_conclusion.py` runs
- THEN it exits 2 without rewriting the report
