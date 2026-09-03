# Design: Skip TSR group headers in crosswalk catalog

`_node_text_is_group_header(section, node_text_end_index)` looks ahead from a tree-view node's `</span>` end index to its `</button>`, then checks the next 100 chars for a `<ul`. Real TSR HTML measured gap is 63 chars; 100 leaves margin without reaching a sibling node's own `<ul>` (siblings are separated by the sibling's full button markup, hundreds of chars away).

`_collect_tsr_sections` calls this helper before appending an entry; group headers are skipped, leaf checks are kept unchanged. `_collect_summary` and `_collect_ccx` are untouched — they don't scrape the group/leaf tree structure.
