# Design: native Alertmanager receivers

Mint `7.6.alert_receivers` from redacted `08_day2/alertmanager_receivers.json`. Collect reads secret `alertmanager-main` in `openshift-monitoring`, base64-decodes `alertmanager.yaml` in memory with stdlib only (no PyYAML), and writes receiver names matched under a `receivers:` heading. Do not persist decoded YAML or URLs. Do not score AlertmanagerConfig CRDs. Do not dump the secret in KB verification.

Scoring matrix is in the delta spec. Coverage percent vs ORIG Chapter 6 is out of this change.
