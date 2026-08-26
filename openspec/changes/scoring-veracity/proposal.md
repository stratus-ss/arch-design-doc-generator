# Change Proposal: scoring-veracity

> **STATUS: ARCHIVED** (2026-08-25) into `openspec/specs/hc-report-engine/spec.md`
> Plan: `cursor_plans/scoring_veracity_2026-08-25.md`

Baseline: `openspec/specs/hc-report-engine/spec.md`.

Native evaluators stop claiming OCP 4.22-backed FAIL/WARNING (or PASS) where the engine contradicts docs or invents coverage. Chapter 7 and audit JSON expose `scoring_basis` (`doc_backed` | `engine_policy`) on FAIL and WARNING. Hybrid cutoff TOML is not in this change.
