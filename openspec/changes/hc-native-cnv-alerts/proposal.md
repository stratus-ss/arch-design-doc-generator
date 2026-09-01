# Change Proposal: hc-native-cnv-alerts

Baseline: `openspec/specs/hc-report-engine/spec.md`. Do not modify unrelated `openspec/changes/`. Do not modify the living spec until the Doc Update task.

Live **core** SHALL emit `7.4.cnv.alerts` from existing `07_cluster_health/firing_alerts`. Missing payload SHALL be SKIPPED. A virt-matching alert is one whose `alertname` or `namespace` (casefold) contains any of `kubevirt`, `cdi`, `ssp`, `hco`, `hyperconverged`, `openshift-cnv`, `nmstate`. Alerts whose state is not `firing` or `pending` SHALL be ignored. Any remaining match SHALL be FAIL. Else PASS. The check SHALL NEVER be WARNING. `7.5.alerts.critical` SHALL NOT be retuned. `7.4.tsr.4_8_5_2_1_active_alerts` SHALL be a sparse alias of `7.4.cnv.alerts`. Collect SHALL NOT add a new firing-alerts command. Prometheus SHALL NOT be queried again for this change. Coverage percent vs ORIG Chapter 6 is out of this change.

## Why

TSR 4.8.5.2.1 is a virt alert worksheet. Live already collects `firing_alerts`. Native FAIL on any firing or pending virt-matching alert is the live bar; 7.5 critical alerts stay unchanged.

Plan: `cursor_plans/hc_native_cnv_alerts_2026-08-29.md`
