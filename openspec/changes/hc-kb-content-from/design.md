# Design: hc-kb-content-from

`load_kb()` parses `content_from` as an exact canonical `check_id` in `entries` (not a glob, not `pattern_entries`).

**Single hop.** If the target also has `content_from`, raise `ValueError` (chains and cycles).

**Inherit (DR-1):** recommendation, description, impact, impact_scope, impact_detail, links, `recommendation_supported_versions`, `priority_hint`, `summary_patterns`.

**Keep local:** `check_id`, `title`, `finding_group`, `finding_group_title`, `include_in_findings`, `finding_on_info`, `pattern`, `content_from`.

**No overlay (DR-2).** Alias TOML omits inherited keys. Non-empty inherited fields on an alias → `ValueError`.

**Copy:** `dataclasses.replace` on the frozen `KBEntry` (do not assign in place).

**Pattern rows** must not set `content_from`.
