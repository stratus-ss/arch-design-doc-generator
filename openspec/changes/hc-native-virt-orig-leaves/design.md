# Design: native virt NNCP, virt-default StorageClass, and OADP

Mint `7.4.cnv.nncp`, `7.4.cnv.virt_storageclass`, and `7.4.oadp.state`. Do not name a native `node_disk`. Keep TSR check_ids via sparse aliases only. Do not retarget `7.4.tsr.4_8_1_4_node_disk` away from `7.4.cnv.state`.

NNCP: both payloads missing is NOT_APPLICABLE. Else zero NNCP and zero NNCE items is INFO. Any item not healthy (`Available=True` or `SuccessfullyConfigured=True`) is FAIL. Else PASS. Do not score NAD count. Do not change `7.3.net.hwnet`.

Virt-default StorageClass: HyperConverged missing is NOT_APPLICABLE. Else exactly one StorageClass with annotation `storageclass.kubevirt.io/is-default-virt-class` equal to `"true"` is PASS; otherwise FAIL. VolumeSnapshotClass is evidence only. Do not use cluster `is-default-class`. Do not change `7.3.storage.default_sc`.

OADP: no DPA items, no CSV items, and no BackupStorageLocation items is NOT_APPLICABLE. Any CSV in `openshift-adp` with phase not Succeeded, or any DPA not Available, or any BSL phase not Available, is FAIL. Else PASS. Do not FAIL on absence. Do not retune inventory `7.4.OADP`.

Live `05_components` MAY write `nnce` and `volumesnapshotclass`. Live `06_layered` MAY write `oadp_dpa`, `oadp_csv`, and `backupstoragelocation`. Supportshell MAY write the same names.

Scoring matrix and alias targets are in the delta spec. Coverage percent vs ORIG Chapter 6 is out of this change.
