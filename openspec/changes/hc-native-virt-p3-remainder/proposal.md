# Change Proposal: hc-native-virt-p3-remainder

> **STATUS: ARCHIVED**
> Merged into `openspec/specs/hc-report-engine/spec.md` on 2026-08-29.
> Plan: `cursor_plans/hc_native_virt_p3_remainder_2026-08-29.md`

Baseline: `openspec/specs/hc-report-engine/spec.md`. Do not modify unrelated `openspec/changes/`.

Without TSR HTML, live **core** SHALL emit `7.4.cnv.storageprofile` and `7.4.cnv.vm_quota`. ORIG IDs `7.4.tsr.4_8_3_1_1_storage_profiles` and `7.4.tsr.4_8_5_1_1_quota_and_resources` SHALL be sparse `content_from` aliases with `include_in_findings = false`. The quota native SHALL NOT alias to `7.6.rq` or `7.6.cluster_quota`. StorageProfile SHALL NOT alias to `7.4.cnv.virt_storageclass`. Missing ResourceQuota in a VM namespace SHALL NOT FAIL.

## Why

Parent change `hc-native-virt-p3` parked those two ORIG P3 leaves as full TSR rows so StorageProfile clone strategy and VM-namespace quota would not be lost. This change mints the two natives and one-hop aliases.

Plan: `cursor_plans/hc_native_virt_p3_remainder_2026-08-29.md`
