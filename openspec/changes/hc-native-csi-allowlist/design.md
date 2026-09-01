# Design: native CSI CSO allow-list

Mint `7.3.storage.csi_cso`. Keep TSR check_id via a sparse alias only. Do not fold into `7.3.storage.csi`. Do not FAIL third-party drivers.

Parse `clustercsidrivers.operator.openshift.io` from collected `05_components/crds.json` by walking dict/list nodes and taking `enum` lists that contain `ebs.csi.aws.com`. Collect SHALL NOT add files.

Red Hat names outside CSO that still PASS: prefix `openshift-storage.`, plus exact `lvm.csi.topolvm.io`, `topolvm.io`, `kubevirt.io.hostpath-provisioner`. SnapshotClass is evidence only.

Scoring matrix and alias target are in the delta spec. Coverage percent vs ORIG Chapter 6 is out of this change.
