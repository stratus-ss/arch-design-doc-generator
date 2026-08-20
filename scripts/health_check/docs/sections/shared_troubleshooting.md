**`oc` not found in PATH**  
Download from https://mirror.openshift.com/pub/openshift-v4/clients/ocp/latest/ or install via `dnf install openshift-clients`.

**Cannot reach cluster API**  
Run `oc cluster-info` manually to check connectivity. Verify VPN is connected, the API URL is correct, and the kubeconfig is pointing at the right context (`oc config current-context`).

**Permission denied on a resource**  
A `WARN skipped (exit_code=1)` with an authorization error means the account lacks read access to that resource. Raise this with the customer's cluster administrator.

**All 06_layered results show `not-installed`**  
Normal on a base OCP cluster. These checks are only applicable if the layered product is installed.

**`hc-report` finishes almost instantly, or errors with "no collected JSON files found"**  
`HC_COLLECT_OUT` / `--results-dir` pointed at a directory with no `manifest.json` and no category subfolders directly inside it. The most common cause: supportshell/must-gather fetches (`hc-fetch-results`, `hc-report-from-supportshell`) stage results into a **dated subfolder** (`output/hc_collect/<YYYY-MM-DD>/`), not directly in `output/hc_collect/`. `hc-report` auto-detects and uses the latest dated subdirectory in this case — look for a `Note: no results directly under ...` line in its output confirming which directory it actually loaded. If it picks the wrong date (e.g. multiple engagements collected on different days), set `HC_COLLECT_OUT=output/hc_collect/<date>` explicitly. If no dated subdirectory exists either, `hc-report` now fails with an explicit error instead of silently rendering an empty 0-finding report — re-run `hc-collect` / `hc-fetch-results` first.

**`make hc-report` doesn't pick up a script change I just made**  
The container image rebuild check (`make image`) hashes the *list of file names* under `scripts/`, not file contents, to keep every `make` invocation fast — so editing an existing file's content (without adding/removing files) won't be detected as stale. Run `make force-image` to force a rebuild after editing scripts. The same blind spot applies to `Containerfile` itself — e.g. adding a new `pip install` package — so `make force-image` is needed after editing it too.
