### `03_base_platform.sh` — Chapter 7.1

Captures the foundational cluster version and platform configuration.

| File | Command | Purpose |
|------|---------|---------|
| `clusterversion.json` | `oc get clusterversion` | OCP version, update history, available updates |
| `clusteroperators.json` | `oc get clusteroperator` | All 34+ operator states (Available, Degraded, Progressing) |
| `subscriptions.json` | `oc get subscription -A` | Installed operators and their channels |
| `csv.json` | `oc get csv -A` | ClusterServiceVersions — installed operator versions |
| `infrastructure.json` | `oc get infrastructure cluster` | Platform type (AWS, vSphere, bare metal, etc.) |
| `nodes.json` | `oc get nodes` | Node inventory with status and roles |
| `nodes_wide.json` | `oc get nodes -o wide` | Node IPs, OS images, kernel versions |
| `scc.json` | `oc get scc` | Security Context Constraints — default vs custom |
| `oauth.json` | `oc get oauth cluster` | Identity providers configured |
| `insightsoperator.json` | `oc get insightsoperator -A` | Insights Operator CR — remote health reporting |

### `04_topology.sh` — Chapter 7.2

Assesses cluster topology, HA configuration, and machine/kubelet configuration.

| File | Command | Purpose |
|------|---------|---------|
| `nodes.json` | `oc get nodes` | Node count and role distribution |
| `node_labels.json` | `oc get nodes --show-labels` | Full label set for topology mapping |
| `machineconfig.json` | `oc get machineconfig` | All machine configs (system-level configuration) |
| `machineconfigpool.json` | `oc get machineconfigpool` | MCP states — degraded pools indicate drift |
| `kubeletconfig.json` | `oc get kubeletconfig` | KubeletConfig resources (systemReserved and per-pool tuning) |
| `etcd.json` | `oc get etcd cluster` | Etcd operator state and member health |
| `etcd_pods.json` | `oc get pods -n openshift-etcd` | Etcd pod count and status (should be 3 on HA clusters) |

### `05_components.sh` — Chapter 7.3

Core component health — monitoring, storage, networking, ingress.

| File | Command | Purpose |
|------|---------|---------|
| `cluster_operators.json` | `oc get co` | Full operator health with conditions |
| `machineconfig.json` | `oc get mc` | Machine config inventory |
| `etcd_pods.json` | `oc get pods -n openshift-etcd` | Etcd pod health |
| `etcd_status.json` | `oc -n openshift-etcd get pods -o wide` | Etcd pod distribution across nodes |
| `imageregistry.json` | `oc get configs.imageregistry.operator.openshift.io cluster` | Internal registry state and storage config |
| `prometheus.json` | `oc get prometheus -n openshift-monitoring` | Prometheus instance configuration |
| `prometheusrule.json` | `oc get prometheusrule -n openshift-monitoring` | Custom alerting rules |
| `alertmanager.json` | `oc get alertmanager -n openshift-monitoring` | Alertmanager configuration |
| `ingresscontroller.json` | `oc get ingresscontroller -n openshift-ingress-operator` | Ingress controller replicas and config |
| `storageclass.json` | `oc get storageclass` | Available storage classes and defaults |
| `pv.json` | `oc get pv` | Persistent volume inventory and states |
| `pvc.json` | `oc get pvc -A` | PVC states across all namespaces |
| `csidriver.json` | `oc get csidriver` | CSI driver inventory |
| `localvolume.json` | `oc get localvolume -A` | Local Storage Operator volumes |
| `network.json` | `oc get network cluster` | Cluster network config (CNI, CIDR ranges) |
| `clusternetwork.json` | `oc get clusternetwork` | OCP 3.x SDN object — marks `not-installed` on OCP 4.x |
| `network_operator.json` | `oc get network.operator cluster` | Network operator configuration |
| `metallb.json` | `oc get metallb -A` | MetalLB load balancer instances |
| `ipsecconfig.json` | `oc get ipsecconfig -A` | IPsec configuration (if installed) |
| `sriovnetwork.json` | `oc get sriovnetwork -A` | SR-IOV network definitions |
| `performanceprofile.json` | `oc get performanceprofile -A` | Node performance profiles (low-latency tuning) |
| `dns_pods.json` | `oc get pods -n openshift-dns` | DNS pods status across cluster |
| `featuregate.json` | `oc get featuregate cluster` | Enabled feature gates and tech preview features |

### `06_layered.sh` — Chapter 7.4

Optional Red Hat products. Every command here may produce `_hc_not_found` if the product isn't installed — this is expected and normal.

| Product | Files collected |
|---------|----------------|
| **OpenShift Virtualization (CNV)** | `cnv_hyperconverged.json`, `cnv_kubevirt.json`, `cnv_pods.json` |
| **Advanced Cluster Management (ACM)** | `acm_multiclusterhub.json`, `acm_pods.json` |
| **Advanced Cluster Security (ACS)** | `acs_central.json`, `acs_pods.json` |
| **Logging (ClusterLogging / Loki)** | `logging_clusterlogging.json`, `logging_loki.json`, `logging_pods.json` |
| **OpenShift Pipelines (Tekton)** | `pipelines_tektonconfig.json`, `pipelines_pods.json` |
| **Service Mesh (Istio)** | `servicemesh_smcp.json`, `servicemesh_pods.json` |
| **OpenShift Data Foundation (ODF)** | `odf_storagecluster.json` |
| **Red Hat OpenStack Services (RHOSO)** | `rhoso_controlplane.json` |
| **Migration Toolkit for Virtualization (MTV)** | `mtv_controller.json` |

### `07_cluster_health.sh` — Chapter 7.5

Runtime health — alerts, pod restarts, node conditions.

| File | Command | Purpose |
|------|---------|---------|
| `nodes.json` | `oc get nodes` | Kubelet version consistency check |
| `node_conditions.json` | `oc get nodes` | NotReady, MemoryPressure, DiskPressure conditions |
| `pods_all.json` | `oc get pods -A` | All pods — used to detect high restart counts |
| `pdb.json` | `oc get pdb -A` | PodDisruptionBudgets across all namespaces |
| `master_nodes.json` | `oc get nodes -l node-role.kubernetes.io/master` | Master schedulability check |
| `clusterversion.json` | `oc get clusterversion` | Current version and update state |
| `clusteroperators.json` | `oc get clusteroperator` | Degraded operator check |
| `firing_alerts.json` | `oc exec prometheus-k8s-0 -- curl localhost:9090/api/v1/alerts` | Live firing Prometheus alerts (best-effort) |

### `08_day2.sh` — Chapter 7.6

Day-2 operational hygiene — quotas, upgrade history, resource utilization.

| File | Command | Purpose |
|------|---------|---------|
| `resourcequota.json` | `oc get resourcequota -A` | Namespace quota configuration |
| `limitrange.json` | `oc get limitrange -A` | Limit range configuration |
| `image_config.json` | `oc get image.config.openshift.io cluster` | Image pruning policy |
| `clusterversion.json` | `oc get clusterversion` | Full upgrade history |
| `top_nodes.json` | `oc adm top nodes` | Current CPU/memory utilization per node |
| `top_pods.json` | `oc adm top pods -A --sort-by=memory` | Top memory consumers across cluster |
| `apiserver.json` | `oc get apiserver cluster` | API server TLS and audit config |
| `proxy.json` | `oc get proxy cluster` | Cluster-wide proxy configuration |
| `namespaces.json` | `oc get namespaces` | Total namespace count (sprawl check) |

### `09_security.sh` — Chapter 7.7

Security posture — SCCs, OAuth, RBAC, compliance operator (if installed).

| File | Command | Purpose |
|------|---------|---------|
| `scc.json` | `oc get scc` | SCC inventory — non-default SCCs flagged |
| `oauth.json` | `oc get oauth cluster` | Identity providers — `htpasswd` only is a finding |
| `clusterrolebindings.json` | `oc get clusterrolebinding` | Full RBAC cluster-level bindings |
| `rolebindings.json` | `oc get rolebinding -A` | Namespace-level role bindings |
| `compliance_scans.json` | `oc get compliancescan -A` | Compliance Operator scan results (if installed) |
| `compliance_suites.json` | `oc get compliancesuite -A` | Compliance suite configurations (if installed) |
| `fileintegrity.json` | `oc get fileintegrity -A` | File Integrity Operator instances (if installed) |
| `namespaces.json` | `oc get namespaces` | Pod Security Admission labels per namespace |
| `secrets_count.json` | `oc get secrets -A --no-headers` | Secret inventory by namespace (count only — no content) |
| `clusterrolebindings_admin.json` | `oc get clusterrolebinding` | Used to audit cluster-admin grants |

### `12_ccx.sh` — Advisory Rule Payload (optional)

Optional ingestion of CCX advisory rule output from a local JSON payload.

| File | Source | Purpose |
|------|--------|---------|
| `ccx_rules.json` | `HC_CCX_RULES_FILE` | Runtime advisory/failure import for CCX rule parity |
