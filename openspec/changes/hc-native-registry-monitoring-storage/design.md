# Design: native registry and monitoring storage on core

Mint `7.3.registry.storage` and `7.3.monitoring.storage`. Keep TSR check_ids via sparse aliases only. Do not fold into `7.3.registry.state` or `7.3.monitoring.config`.

Registry: FAIL `emptyDir` when `managementState` is Managed or Unmanaged. PASS object (`s3`, `azure`, `gcs`, `ibmcos`, `oss`, `swift`) or PVC. INFO when Removed or registry payload missing. Unknown remaining storage key is WARNING, not FAIL. Do not score registry PVC access mode or file provisioner.

Monitoring: FAIL if any Prometheus or Alertmanager item lacks `spec.storage.volumeClaimTemplate`. WARNING if a template exists and any access mode is `ReadWriteMany` or the resolved StorageClass provisioner contains `nfs` / `efs` / `azurefile` / `cephfs`. PASS RWO on a non-file provisioner, including empty class name resolved via the default-class annotation. INFO when both Prometheus and Alertmanager payloads are missing. FAIL wins over WARNING.

Reuse collected `05_components` `imageregistry`, `prometheus`, `alertmanager`, and `storageclass` JSON. Collect SHALL NOT add files.

Scoring matrix and alias targets are in the delta spec. Coverage percent vs ORIG Chapter 6 is out of this change.
