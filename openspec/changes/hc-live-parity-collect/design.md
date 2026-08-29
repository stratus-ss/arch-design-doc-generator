# Design: optional product and platform CR JSON on collect

One `hc_capture_json` per API. Many later check IDs reparse the same file; collect does not issue a second `oc get` for the same resource under a different `check_name`.

`_hc_not_found` is success for optional products (RHOSO, IPsec, StorageCluster, SriovNetwork, FileIntegrity, and empty lists). Live lab classification records `list`, `object`, `not_found`, or `error`; it is evidence, not a merge gate.

Skip `dns.json` and `networkattachmentdefinition.json`. Existing captures:

- `05_components/dns_config` — `get dns cluster`
- `05_components/net_attach_def` — `get net-attach-def -A`

Fourteen new `check_name` values:

| Category | check_name | oc args |
|----------|------------|---------|
| `03_base_platform` | `insightsoperator` | `get insightsoperator -A` |
| `05_components` | `dns_pods` | `get pods -n openshift-dns` |
| `05_components` | `featuregate` | `get featuregate cluster` |
| `05_components` | `csidriver` | `get csidriver` |
| `05_components` | `localvolume` | `get localvolume -A` |
| `05_components` | `metallb` | `get metallb -A` |
| `05_components` | `ipsecconfig` | `get ipsecconfig -A` |
| `05_components` | `sriovnetwork` | `get sriovnetwork -A` |
| `05_components` | `performanceprofile` | `get performanceprofile -A` |
| `06_layered` | `odf_storagecluster` | `get storagecluster -A` |
| `06_layered` | `rhoso_controlplane` | `get openstackcontrolplane -A` |
| `06_layered` | `mtv_controller` | `get forkliftcontroller -A` |
| `07_cluster_health` | `pdb` | `get pdb -A` |
| `09_security` | `fileintegrity` | `get fileintegrity -A` |

Every `collect/0N_*.sh` edit is mirrored into `supportshell/0N_*.sh` in the same task (`make check-hc-sync`).
