# Change Proposal: hc-tsr-inventory-condense

> **STATUS: ARCHIVED**
> Merged into `openspec/specs/hc-report-engine/spec.md` on 2026-08-26.

Baseline: `openspec/specs/hc-report-engine/spec.md`.

After identical PASS-host condensation, TSR Result cells still dump
inventory tables, NFS mount clones, repeated node WARNING lines, mixed
PASS/WARNING host groups, and unhealthy-pod lists. This change condenses
those families before the 32_000-character clip.

`ALL NODES` remains only when every host in a role group is fully ok.
Mixed groups emit `PASS NODES` for ok hosts and keep non-ok hosts named.
Inventory tables, NFS mounts, node clones, and pods use count markers,
never `ALL NODES`. Check status is unchanged. CCX Message cells are not
condensed. Clip limits are not reopened.
