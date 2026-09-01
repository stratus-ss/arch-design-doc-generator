# Design: native CSI volume mount p99

Mint `7.5.volume.mount_p99` from one Thanos PromQL collect (`volume_mount_p99`). Dual-edit collect and supportshell `10_metrics.sh`. Score in `health.py` (category 7.5). Sparse-alias TSR 5.10. Do not scrape `/proc/mounts` or host mount tables. Do not retune PVC used% bars. Do not call `generate_report.py`.

Scoring matrix is in the delta spec. Coverage percent vs ORIG Chapter 6 is out of this change. Empty result vector on lab is INFO success (DR-I).
