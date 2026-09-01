# Design: native CNV firing alerts

Mint `7.4.cnv.alerts` from `results["07_cluster_health"]["firing_alerts"]`. Parse with `_parse_alerts_list`. Filter virt tokens on alertname or namespace. Ignore states other than firing/pending. Implement `_evaluate_cnv_alerts` in `layered_cnv.py` and call it from `evaluate_cnv_p3`. Do not edit `07_cluster_health.sh`. Do not retune 7.5 natives.

Scoring matrix is in the delta spec. Coverage percent vs ORIG Chapter 6 is out of this change.
