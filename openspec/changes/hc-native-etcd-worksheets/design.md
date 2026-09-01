# Design: native etcd worksheets on core

Mint `7.8.etcd.compaction`, `7.8.etcd.log_errors`, `7.8.etcd.disk`, `7.8.etcd.heartbeat`. Keep TSR check_ids via sparse aliases only.

`7.8.etcd.disk` FAIL iff any member WAL P99 > 10 ms. Reuse parsed WAL vector; no second PromQL.

Compaction: PromQL p95 histogram plus read-only auto-compaction flags from `etcd_pods`. Missing metric is INFO, not FAIL. Collect SHALL NOT run etcdctl compact.

Logs: last 6 hours, three TSR phrases, integer counts only. Heartbeat: existing `etcd_heartbeat_failures` PromQL; WARNING if 1h increase > 0.

Live `10_metrics` MAY write `etcd_compaction_p95` and `etcd_log_phrase_counts`. Supportshell MAY omit both (no fake PromQL, no `oc logs`).

Scoring matrix and alias targets are in the delta spec. Coverage percent vs ORIG Chapter 6 is out of this change.
