# Change Proposal: hc-native-quay-pods

> **STATUS: ARCHIVED**
> Merged into `openspec/specs/hc-report-engine/spec.md` on 2026-08-29.
> Plan: `cursor_plans/archive/hc_native_quay_pods_2026-08-29.md`

Baseline: `openspec/specs/hc-report-engine/spec.md`. Do not modify the living spec in this change until archive. Do not modify unrelated `openspec/changes/`.

Live **core** SHALL emit `7.4.quay.pods` from `06_layered/quay_registry` plus merged `06_layered/quay_pods`. Missing or `_hc_error` `quay_pods` SHALL be SKIPPED. Zero QuayRegistry items SHALL be NOT_APPLICABLE. Any registry namespace with zero Running pods whose name contains `quay-app` or `registry-quay-app` SHALL be FAIL. Else PASS. The engine SHALL NOT retune `7.4.Quay Registry` product inventory. The engine SHALL NOT alias `7.4.tsr.4_5_1_1_quay_supported_configuration`. Sparse aliases `7.4.tsr.4_5_2_quay_pods` and `7.4.tsr.4_5_4_1_quay_pods` SHALL use `content_from` `7.4.quay.pods` with `include_in_findings = false`.

## Why

TSR FAIL for internal Quay is missing application pods while the operator or QuayRegistry Available condition may still look healthy. Inventory scoring is not a substitute.

Plan: `cursor_plans/hc_native_quay_pods_2026-08-29.md`
