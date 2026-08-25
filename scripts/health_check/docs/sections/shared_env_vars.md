KUBECONFIG          Path to kubeconfig (live cluster collection)
HC_COLLECT_OUT      output/hc_collect        — collection results directory
HC_REPORT_OUT       output/Health_Check_Report — final report output
HC_SSH_HOST         user@host                — remote support shell server
HC_SSH_RESULTS      results path on remote (default is ~/hc_results, but ~ does not
                    resolve reliably here — set explicitly, e.g. /home/remote/<username>/hc_results)
HC_SSH_SCRIPTS      scripts path on remote (default is ~/hc_supportshell — same ~
                    caveat, set explicitly, e.g. /home/remote/<username>/hc_supportshell)
HC_MG_INPUT         must-gather/case path on remote (for hc-collect-remote) — always set
                    explicitly, e.g. /home/remote/<username>/<case-number>, not ~/<case-number>
HC_FETCH_STAGE      output/hc_collect/<date> — dated staging dir for supportshell fetches (auto-computed)
MERGE_INPUTS        "dir1 dir2 ..."          — inputs for hc-merge
HC_TSR_HTML         /path/to/file.html       — explicit TSR HTML path (overrides auto-discovery)
HC_TSR_HTML_DIR     output/tsr_html          — directory for TSR HTML auto-discovery (default)
HC_CHECK_PROFILE    advisory                 — check expansion profile: core | extended | advisory
HC_OMIT_CHECK_IDS   repo-relative path to a check-ID omit list (writes {stem}_pruned.md)
HC_OMIT_STRICT      1                        — fail if an omit ID is not on a Chapter 6 finding
HC_CCX_RULES_FILE   /path/to/ccx_rules.json — optional CCX runtime payload for collection
HC_DOCS_ROOT        local OpenShift docs tree for make hc-link-review
HC_LINK_REVIEW_OUT  output dir for kb_link_review.md / .csv
