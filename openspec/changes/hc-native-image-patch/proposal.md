# Change Proposal: hc-native-image-patch

> **STATUS: ARCHIVED**
> Merged into `openspec/specs/hc-report-engine/spec.md` on 2026-08-29.
> Plan: `cursor_plans/hc_native_image_patch_2026-08-29.md`

Baseline: `openspec/specs/hc-report-engine/spec.md`. Do not modify unrelated `openspec/changes/`.

Without TSR HTML, live **core** SHALL emit native check `7.6.image.registry_sources` that scores `image.config` `spec.registrySources`: allowed and blocked together FAIL; non-empty `insecureRegistries` WARNING; empty allow and block INFO; allow-only or block-only without insecure PASS. ORIG `7.6.tsr.6_2_3_images_patch_management` SHALL be a sparse `content_from` alias onto that native (`include_in_findings = false`). Inventory `7.6.image_mgmt` SHALL remain independently scored and SHALL NOT be the alias target.

## Why

ORIG Chapter 6 image patch management scores allow/block/insecure registrySources, not allow/block counts only. `7.6.image_mgmt` ignores insecure. Sparse alias keeps the TSR `check_id` without overlay. Coverage percent vs ORIG Chapter 6 is out of this change.

Plan: `cursor_plans/hc_native_image_patch_2026-08-29.md`
