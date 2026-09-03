# Proposal: Chapter 6 TSR ref is the TSR HTML section number

> **STATUS: ARCHIVED**
> Merged into `openspec/specs/hc-report-engine/spec.md` on 2026-09-03.
> Plan: `cursor_plans/hc_ch6_tsr_ref_correctness_2026-09-03.md`

## Problem

§6.2 printed `**TSR ref:**` by splitting the finding title for a leading dotted number. KB titles without that prefix (for example `TSR CNV identification and state`) rendered `n/a` even when `CheckResult.tsr_ref` already held the TSR HTML tree number (for example `4.8.1.1.1`).

## Change

`Finding.tsr_ref` is populated at derive time from member `CheckResult.tsr_ref` values that match `^\d+(?:\.\d+)+$`, unique, first-seen order, space-separated. §6.2 prints that field as plain text, or `n/a` when none match. The finding title is not parsed for this line. No hyperlink.

## Impact

Consultants can look up the TSR HTML tree by the printed section number when the heading uses a KB title without a numeric prefix. Deterministic and CCX rows stay `n/a`. Grouped findings may list more than one number.
