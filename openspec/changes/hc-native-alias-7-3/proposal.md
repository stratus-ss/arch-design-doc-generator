# Change Proposal: hc-native-alias-7-3

> **STATUS: ARCHIVED**
> Merged into `openspec/specs/hc-report-engine/spec.md` on 2026-08-29.
> Plan: `cursor_plans/hc_native_alias_7_3_2026-08-29.md`

Baseline: `openspec/specs/hc-report-engine/spec.md`. Do not modify unrelated `openspec/changes/`.

Without TSR HTML, live **core** SHALL mint cluster rollup `7.3.co.platform` from frozen per-operator `7.3.co.{name}` statuses; sparse-alias matching ORIG TSR IDs onto natives (`7.3.co.platform`, `7.3.crds`, `7.3.ingress.sharding`, `7.3.misc.mcp`); retarget hops so there are no `content_from` chains through `7.3.tsr.3_2_1_platform_operators` or `7.3.tsr.3_15_machine_config_pool`. CSI third-party classification (`7.3.tsr.3_9_5_csi_drivers`) SHALL stay a full TSR row. Exact KB `7.3.co.kube-apiserver` SHALL remain. Per-operator FAIL/WARNING/PASS bars SHALL not be retuned.

## Why

ORIG Chapter 6 still lists platform operators, CRDs, ingress sharding, and MCP as distinct stories. Per-operator `7.3.co.{name}` already exists but `content_from` cannot target `7.3.co.*`. CRD currently hops onto operators (wrong story). Sparse aliases keep TSR `check_id` strings without overlay. Coverage percent vs ORIG Chapter 6 is out of this change.

Plan: `cursor_plans/hc_native_alias_7_3_2026-08-29.md`
