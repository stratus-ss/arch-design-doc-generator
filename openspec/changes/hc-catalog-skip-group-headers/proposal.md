# Proposal: Skip TSR group headers in crosswalk catalog

> **STATUS: ARCHIVED**
> Merged into `openspec/specs/hc-report-engine/spec.md` on 2026-09-03.
> Plan: `cursor_plans/archive/hc_catalog_skip_group_headers_2026-09-03.md`

## Problem

`build_crosswalk_catalog.py` scraped every `pf-v6-c-tree-view__node-text` span from TSR HTML sections 1–7, including tree-view group/dropdown headers (e.g. "1.5. Other Basic Checks", "3.5. ETCD") that are never real checks — they are container nodes whose children are the actual leaf checks. `tsr_parser.py` only extracts `leaf-extra` div checks, so these group headers never matched at runtime, producing ~160 SKIPPED Chapter 7 rows with operator-debug fallback evidence ("was not found in the supplied TSR HTML export...") visible to the client.

## Change

`_collect_tsr_sections` now skips any tree-view node whose `</button>` is immediately followed by a child `<ul class="pf-v6-c-tree-view__list">` — the structural signal that a node is a group header, not a leaf check. Only leaf nodes become catalog entries. The committed `catalogs/tsr_ccx_crosswalk.json` was regenerated from the homelab TSR export.

## Impact

- Unmatched TSR catalog titles dropped from 160 to 26 (the remainder are pre-existing title-format mismatches, out of scope).
- Chapter 7 no longer shows SKIPPED rows for group headers like "Other Basic Checks".
