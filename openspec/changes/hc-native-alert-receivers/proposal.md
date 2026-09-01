# Change Proposal: hc-native-alert-receivers

> **STATUS: ARCHIVED**
> Merged into `openspec/specs/hc-report-engine/spec.md` on 2026-08-29.
> Plan: `cursor_plans/archive/hc_native_alert_receivers_2026-08-29.md`

Baseline: `openspec/specs/hc-report-engine/spec.md`. Do not modify unrelated `openspec/changes/`. Do not modify the living spec until the Doc Update task.

Live **core** SHALL emit `7.6.alert_receivers` from redacted collect `08_day2/alertmanager_receivers.json` (`receiver_names` only). Missing or `_hc_error` SHALL be SKIPPED. Zero names after ignoring `null`, `Default`, `default`, `Watchdog`, and `watchdog` SHALL be FAIL. Else PASS. Collect SHALL NOT persist decoded Alertmanager YAML or webhook URLs. `7.6.tsr.6_3_2_alert_receivers` SHALL be a sparse alias of `7.6.alert_receivers`. The engine SHALL NOT score AlertmanagerConfig CRDs.

## Why

TSR FAIL is receivers not configured. Native is SKIPPED today because collect is missing. The secret body is credential-bearing. Coverage percent vs ORIG Chapter 6 is out of this change.

Plan: `cursor_plans/hc_native_alert_receivers_2026-08-29.md`
