# Health Check Report Engine (`hc-catalog-skip-group-headers` delta)

## ADDED Requirements

### Requirement: TSR crosswalk catalog contains only leaf checks
`build_crosswalk_catalog.py` SHALL exclude tree-view group/dropdown headers (parent nodes whose `</button>` is followed by a child `<ul class="pf-v6-c-tree-view__list">`) from the TSR catalog entries it emits. Only leaf check nodes (no child `<ul>` after `</button>`) SHALL become catalog rows.

#### Scenario: Group header is not a catalog entry
- GIVEN TSR tree-view HTML where a node titled "1.5. Other Basic Checks" has a child `<ul>` list containing leaf check nodes
- WHEN `_collect_tsr_sections` runs
- THEN no catalog entry has that title
- AND leaf check titles inside that group's `<ul>` still become catalog entries
