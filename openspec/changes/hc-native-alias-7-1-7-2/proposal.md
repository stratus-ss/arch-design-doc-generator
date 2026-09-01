# Change Proposal: hc-native-alias-7-1-7-2

> **STATUS: ARCHIVED**
> Merged into `openspec/specs/hc-report-engine/spec.md` on 2026-08-29.
> Plan: `cursor_plans/hc_native_alias_7_1_7_2_2026-08-29.md`

Baseline: `openspec/specs/hc-report-engine/spec.md`. Do not modify unrelated `openspec/changes/`.

Without TSR HTML, live **core** SHALL sparse-alias ORIG master-memory, authentication, AZ-label, and HAProxy-replica TSR ids onto existing natives; mint `7.1.dns.coredns_alerts` from existing Prometheus firing alerts; retarget hops so there is no `content_from` chain through `7.1.tsr.1_5_2_3_dns_alerts`. Firewalls TSR (`7.1.tsr.1_5_5_firewalls`) SHALL stay a full TSR row. Existing FAIL/WARNING/PASS bars on memory, auth, AZ, HAProxy, and firewall natives SHALL not be retuned.

## Why

ORIG Chapter 6 still lists those TSR ids. Native scorers already exist except CoreDNS-named firing alerts. Sparse aliases keep TSR `check_id` strings without overlay. Coverage percent vs ORIG Chapter 6 is out of this change.

Plan: `cursor_plans/hc_native_alias_7_1_7_2_2026-08-29.md`
