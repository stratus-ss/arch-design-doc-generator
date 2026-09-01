# Design: native virt P3 remainder (StorageProfile + VM quota)

Mint `7.4.cnv.storageprofile` and `7.4.cnv.vm_quota`. Collect `storageprofile` in `05_components` (`oc get storageprofile || true`). Quota reads existing `08_day2/resourcequota` plus `06_layered` `cnv_vm`. Do not retune `_evaluate_cnv_virt_storageclass` or `_evaluate_resource_quotas` / `7.6.rq`. Do not FAIL missing VM-namespace ResourceQuota. Exhausted quota is string equality of `status.used[key]` and `spec.hard[key]` for a shared key — no quantity math.

Evaluators live in `evaluators/layered_cnv.py` and dispatch from `evaluate_cnv_p3`.

Scoring matrix and alias targets are in the delta spec. Coverage percent vs ORIG Chapter 6 is out of this change.
