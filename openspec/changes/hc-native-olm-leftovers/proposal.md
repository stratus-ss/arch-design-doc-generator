# Change Proposal: hc-native-olm-leftovers

> **STATUS: ARCHIVED**
> Merged into `openspec/specs/hc-report-engine/spec.md` on 2026-08-29.
> Plan: `cursor_plans/hc_native_olm_leftovers_2026-08-29.md`

Baseline: `openspec/specs/hc-report-engine/spec.md`. Do not modify unrelated `openspec/changes/`.

Without TSR HTML, live **core** SHALL emit native check `7.3.olm.failed_csv` that FAILs when any ClusterServiceVersion `status.phase` is `Failed`, WARNINGs when a phase is neither `Succeeded` nor `Failed` nor empty, and PASSes when remaining CSVs are Succeeded or empty-phase. Zero CSV items SHALL be NOT_APPLICABLE. Copied Succeeded CSVs SHALL NOT FAIL. `7.3.co.platform` SHALL not be retuned. `7.3.tsr.3_2_2_additional_operators` SHALL keep `content_from` `7.3.co.platform`. Insights leftover CRDs SHALL NOT be aliased.

## Why

Failed CSV is leftover/broken install. Counting copied Succeeded CSVs would drown Chapter 6. Additional-operators TSR stays on the platform-operator rollup (wrong story for failed CSV). Coverage percent vs ORIG Chapter 6 is out of this change.

Plan: `cursor_plans/hc_native_olm_leftovers_2026-08-29.md`
