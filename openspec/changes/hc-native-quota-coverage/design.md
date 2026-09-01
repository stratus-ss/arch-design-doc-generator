# Design: native user-project quota coverage

Mint `7.6.quota.coverage`. Keep TSR check_id via a sparse alias only. Do not fold into `7.6.rq` or ClusterResourceQuota inventory.

User namespaces are names that do not start with `openshift-` or `kube-` and are not `default` or `openshift`. A user namespace is covered when it has at least one ResourceQuota or at least one LimitRange. Missing payloads SKIP. Zero user namespaces is NOT_APPLICABLE. The project-request template is evidence only and is not scored.

Scoring matrix and alias targets are in the delta spec. Coverage percent vs ORIG Chapter 6 is out of this change.
