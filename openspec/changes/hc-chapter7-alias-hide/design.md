# Design: hide Chapter 7 sparse-alias rows

One renderer predicate `_include_in_chapter7(check) -> bool`: True when `load_kb().get_entry(check_id)` is missing or `content_from` is empty; False when `content_from` is set. Apply only in `_build_stats_rows` and `_build_check_results_table`.

Do not edit `findings.py`. Do not omit natives. Do not implement Insights HTTP or host UNREACHABLE. Coverage percent vs ORIG Chapter 6 is out of this change.
