# Change Proposal: hc-native-virt-cpu-flags

> **STATUS: ARCHIVED**
> Merged into `openspec/specs/hc-report-engine/spec.md` on 2026-08-29.
> Plan: `cursor_plans/hc_native_virt_cpu_flags_2026-08-29.md`

Baseline: `openspec/specs/hc-report-engine/spec.md`. Do not modify unrelated `openspec/changes/`.

Live **core** SHALL emit `7.4.cnv.cpu_virt_flag` from node labels `cpu-feature.node.kubevirt.io/vmx` and `cpu-feature.node.kubevirt.io/svm`. HyperConverged missing SHALL be NOT_APPLICABLE. Nodes `_hc_error` SHALL be SKIPPED. Zero matching `true` labels SHALL be WARNING. At least one matching node SHALL PASS. The check SHALL NEVER FAIL. `7.4.tsr.4_8_1_3_2_node_cpu` SHALL remain a sparse alias of `7.4.cnv.state`. The check SHALL NOT read `/proc/cpuinfo` or require both vmx and svm.

## Why

ORIG node-CPU TSR stays parked on CNV state. Compact labs expose AMD SVM (or Intel VMX) on kubevirt cpu-feature labels; that hardware flag is a separate native from virt-handler placement.

Plan: `cursor_plans/hc_native_virt_cpu_flags_2026-08-29.md`
