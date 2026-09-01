Zero-dependency data collection for OpenShift Health Check engagements.

**Requirements:** `oc` CLI. No `jq`. Category scripts `10_metrics.sh` and `11_hardware.sh` use `python3` when those categories run (default full collect).  
**Cluster access:** All commands are read-only. Nothing is created, modified, or deleted.
