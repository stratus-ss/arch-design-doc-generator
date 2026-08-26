# Design: named REPORT file for HTML/PDF export

Discover-all (`hc_export_paths.py` three positionals, no `--source`) is unchanged: prune peer wins; two sources mapping to one dest raise `ExportPathCollision` (exit 1).

Named export is `--source PATH` plus optional `--allow-overwrite`. `prepare_named_source_export` validates the file, resolves dest (in-tree relative path vs basename-only), and collects warning titles `PRUNED SIBLING IGNORED` and `SOURCE OUTSIDE REPORT TREE`. Banners are 72 `=` lines around `WARNING: {title}`.

Exit **4** (`EXIT_OVERWRITE_CONSENT_REQUIRED`) means dest exists and the source is not an in-tree regenerate. Stdout still prints `source<TAB>dest`. Entrypoint remaps exit 4: `HC_EXPORT_FORCE=1` reruns with `--allow-overwrite`; TTY prompts `[y/N]`; otherwise fail closed. Make reuses `FORCE` / `_FORCE_ON` as `HC_EXPORT_FORCE=1`. Location outside `output/Health_Check_Report/` does not require `FORCE`.
