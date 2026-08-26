# Change Proposal: hc-tsr-pass-host-condense

> **STATUS: ARCHIVED**
> Merged into `openspec/specs/hc-report-engine/spec.md` on 2026-08-26.
> Plan: `cursor_plans/hc_tsr_pass_host_condense_2026-08-26.md`

Baseline: `openspec/specs/hc-report-engine/spec.md`.

TSR Result text SHALL collapse identical PASS/INFO-only per-host blocks under
role node groups into `GROUP::>ALL NODES:` before the 32_000-character clip.
Non-PASS hosts and unique PASS bodies stay named. Check status is unchanged.
CCX Message cells are not condensed. This does not reopen clip limits, omit
flags, or Chapter 7 table layout.
