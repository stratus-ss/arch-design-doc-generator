# Change Proposal: hc-native-system-reserved

> **STATUS: ARCHIVED**
> Merged into `openspec/specs/hc-report-engine/spec.md` on 2026-08-29.
> Plan: `cursor_plans/archive/hc_native_system_reserved_2026-08-29.md`

Baseline: `openspec/specs/hc-report-engine/spec.md`. Do not modify unrelated `openspec/changes/`.

Without TSR HTML, live **core** SHALL emit native check `7.2.kubelet.system_reserved` that scores effective kubelet `systemReserved.memory` from live `node_image_gc` member excerpts (configz memory string + `autoSizingReserved` only). Missing reserved memory (and not auto-size) is WARNING. Default `1Gi`/`1G` on a node with capacity ≥64 GiB is INFO. Parseable reserved on all members with no 1Gi-large hit is PASS. Never FAIL. `_hc_error` with empty members is SKIPPED; zero members is NOT_APPLICABLE. Per-node `7.2.node.*.sysreserved` / `_check_system_reserved` bars SHALL NOT change.

## Why

No `KubeletConfig` CR still leaves kubelet defaults (`memory=1Gi`). Scoring CR absence as the effective-reserved story is wrong. Coverage percent vs ORIG Chapter 6 is out of this change.

Plan: `cursor_plans/archive/hc_native_system_reserved_2026-08-29.md`
