Offline data collection for OpenShift Health Check engagements using `omc` against a must-gather bundle. No live cluster access required.

---

## Prerequisites

- **`omc`** installed and in `PATH` — [github.com/gmeghnag/omc](https://github.com/gmeghnag/omc)
- A must-gather already loaded: `omc use /path/to/must-gather/`
- `project.yaml` created via `make setup CLIENT="Your Client" PROJECT="HC"` (from the repo root, on your workstation) — required before `hc-report`, `hc-pdf`, or `hc-html` will run; see [Set Up `project.yaml`](#set-up-projectyaml) below

No `oc`, cluster access, kubeconfig, or network connectivity needed.
