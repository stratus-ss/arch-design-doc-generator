# Health Check Command Reference

Generated from `scripts/health_check/collect/[0-9][0-9]_*.sh`.

## 03_base_platform.sh — Chapter 7.1: Base Platform Assessment

| Check Name | Command | Report Section |
|------------|---------|----------------|
| clusterversion | `oc get clusterversion -o json` | 7.1 |
| clusteroperators | `oc get clusteroperator -o json` | 7.1 |
| subscriptions | `oc get subscription -A -o json` | 7.1 |
| csv | `oc get csv -A -o json` | 7.1 |
| infrastructure | `oc get infrastructure cluster -o json` | 7.1 |
| install_config | `oc get configmap cluster-config-v1 -n kube-system -o json` | 7.1 |
| scheduler | `oc get scheduler cluster -o json` | 7.1 |
| proxy | `oc get proxy cluster -o json` | 7.1 |
| nodes | `oc get nodes -o json` | 7.1 |
| nodes_wide | `"$HC_CLI" get nodes -o wide` | 7.1 |
| csr | `oc get csr -o json` | 7.1 |
| scc | `oc get scc -o json` | 7.1 |
| oauth | `oc get oauth cluster -o json` | 7.1 |
| insightsoperator | `oc get insightsoperator -A -o json` | 7.1 |

## 04_topology.sh — Chapter 7.2: Topology Assessment

| Check Name | Command | Report Section |
|------------|---------|----------------|
| nodes | `oc get nodes -o json` | 7.2 |
| node_labels | `$HC_CLI get nodes --show-labels` | 7.2 |
| machineconfig | `oc get machineconfig -o json` | 7.2 |
| machineconfigpool | `oc get machineconfigpool -o json` | 7.2 |
| kubeletconfig | `oc get kubeletconfig -o json` | 7.2 |
| etcd | `oc get etcd cluster -o json` | 7.2 |
| etcd_pods | `oc get pods -n openshift-etcd -o json` | 7.2 |

## 05_components.sh — Chapter 7.3: Component Assessment

| Check Name | Command | Report Section |
|------------|---------|----------------|
| cluster_operators | `oc get co -o json` | 7.3 |
| machineconfig | `oc get mc -o json` | 7.3 |
| etcd_pods | `oc get pods -n openshift-etcd -o json` | 7.3 |
| etcd_status | `"$HC_CLI" -n openshift-etcd get pods -o wide` | 7.3 |
| imageregistry | `oc get configs.imageregistry.operator.openshift.io cluster -o json` | 7.3 |
| prometheus | `oc get prometheus -n openshift-monitoring -o json` | 7.3 |
| prometheusrule | `oc get prometheusrule -n openshift-monitoring -o json` | 7.3 |
| alertmanager | `oc get alertmanager -n openshift-monitoring -o json` | 7.3 |
| ingresscontroller | `oc get ingresscontroller -n openshift-ingress-operator -o json` | 7.3 |
| storageclass | `oc get storageclass -o json` | 7.3 |
| pv | `oc get pv -o json` | 7.3 |
| pvc | `oc get pvc -A -o json` | 7.3 |
| csidriver | `oc get csidriver -o json` | 7.3 |
| localvolume | `oc get localvolume -A -o json` | 7.3 |
| network | `oc get network cluster -o json` | 7.3 |
| clusternetwork | `oc get clusternetwork -o json` | 7.3 |
| network_operator | `oc get network.operator cluster -o json` | 7.3 |
| nncp | `oc get nncp -o json` | 7.3 |
| net_attach_def | `oc get net-attach-def -A -o json` | 7.3 |
| metallb | `oc get metallb -A -o json` | 7.3 |
| ipsecconfig | `oc get ipsecconfig -A -o json` | 7.3 |
| sriovnetwork | `oc get sriovnetwork -A -o json` | 7.3 |
| performanceprofile | `oc get performanceprofile -A -o json` | 7.3 |
| dns_operator | `oc get dns.operator default -o json` | 7.3 |
| dns_config | `oc get dns cluster -o json` | 7.3 |
| dns_pods | `oc get pods -n openshift-dns -o json` | 7.3 |
| featuregate | `oc get featuregate cluster -o json` | 7.3 |
| crds | `oc get crd -o json` | 7.3 |
| apirequestcounts | `oc get apirequestcounts -o json` | 7.3 |
| validatingwebhooks | `oc get validatingwebhookconfigurations -o json` | 7.3 |
| mutatingwebhooks | `oc get mutatingwebhookconfigurations -o json` | 7.3 |
| monitoring_config | `oc get configmap cluster-monitoring-config -n openshift-monitoring -o json` | 7.3 |

## 06_layered.sh — Chapter 7.4: Layered Products Assessment

| Check Name | Command | Report Section |
|------------|---------|----------------|
| cnv_hyperconverged | `oc get hyperconverged -n openshift-cnv -o json` | 7.4 |
| cnv_kubevirt | `oc get kubevirt -n openshift-cnv -o json` | 7.4 |
| cnv_pods | `oc get pods -n openshift-cnv -o json` | 7.4 |
| cnv_vm | `oc get vm -A -o json` | 7.4 |
| cnv_vmi | `oc get vmi -A -o json` | 7.4 |
| acm_multiclusterhub | `oc get multiclusterhub -n open-cluster-management -o json` | 7.4 |
| acm_pods | `oc get pods -n open-cluster-management -o json` | 7.4 |
| acs_central | `oc get central -n stackrox -o json` | 7.4 |
| acs_pods | `oc get pods -n stackrox -o json` | 7.4 |
| logging_clusterlogging | `oc get clusterlogging instance -n openshift-logging -o json` | 7.4 |
| logging_loki | `oc get lokistack -n openshift-logging -o json` | 7.4 |
| logging_pods | `oc get pods -n openshift-logging -o json` | 7.4 |
| pipelines_tektonconfig | `oc get tektonconfig cluster -o json` | 7.4 |
| pipelines_pods | `oc get pods -n openshift-pipelines -o json` | 7.4 |
| servicemesh_smcp | `oc get servicemeshcontrolplane -A -o json` | 7.4 |
| servicemesh_pods | `oc get pods -n istio-system -o json` | 7.4 |
| serverless_knserving | `oc get knativeserving -A -o json` | 7.4 |
| serverless_kneventing | `oc get knativeeventing -A -o json` | 7.4 |
| quay_registry | `oc get quayregistry -A -o json` | 7.4 |
| datasciencecluster | `oc get datasciencecluster -A -o json` | 7.4 |
| odf_storagecluster | `oc get storagecluster -A -o json` | 7.4 |
| rhoso_controlplane | `oc get openstackcontrolplane -A -o json` | 7.4 |
| mtv_controller | `oc get forkliftcontroller -A -o json` | 7.4 |

## 07_cluster_health.sh — Chapter 7.5: Cluster Health Assessment

| Check Name | Command | Report Section |
|------------|---------|----------------|
| nodes | `oc get nodes -o json` | 7.5 |
| node_conditions | `oc get nodes -o json` | 7.5 |
| pods_all | `oc get pods -A -o json` | 7.5 |
| pdb | `oc get pdb -A -o json` | 7.5 |
| master_nodes | `oc get nodes -l node-role.kubernetes.io/master -o json` | 7.5 |
| clusterversion | `oc get clusterversion -o json` | 7.5 |
| clusteroperators | `oc get clusteroperator -o json` | 7.5 |
| firing_alerts | `oc -n openshift-monitoring exec "$(oc get pods -n openshift-monitoring -l prometheus=k8s -o jsonpath='{.items[0].metadata.name}' 2>/dev/null \|\| echo '')" -c prometheus -- curl -s http://localhost:9090/api/v1/alerts 2>/dev/null` | 7.5 |
| events | `oc get events -A -o json` | 7.5 |
| jobs | `oc get jobs -A -o json` | 7.5 |

## 08_day2.sh — Chapter 7.6: Day-2 Operations Assessment

| Check Name | Command | Report Section |
|------------|---------|----------------|
| resourcequota | `oc get resourcequota -A -o json` | 7.6 |
| limitrange | `oc get limitrange -A -o json` | 7.6 |
| image_config | `oc get image.config.openshift.io cluster -o json` | 7.6 |
| clusterversion | `oc get clusterversion -o json` | 7.6 |
| top_nodes | `oc adm top nodes` | 7.6 |
| top_pods | `oc adm top pods -A --sort-by=memory` | 7.6 |
| apiserver | `oc get apiserver cluster -o json` | 7.6 |
| proxy | `oc get proxy cluster -o json` | 7.6 |
| namespaces | `oc get namespaces -o json` | 7.6 |
| subscriptions | `oc get subscriptions -A -o json` | 7.6 |
| deploymentconfig | `oc get dc -A -o json` | 7.6 |
| certificates | `oc get certificates -A -o json` | 7.6 |

## 09_security.sh — Chapter 7.7: Security and Compliance Assessment

| Check Name | Command | Report Section |
|------------|---------|----------------|
| scc | `oc get scc -o json` | 7.7 |
| oauth | `oc get oauth cluster -o json` | 7.7 |
| clusterrolebindings | `oc get clusterrolebinding -o json` | 7.7 |
| rolebindings | `oc get rolebinding -A -o json` | 7.7 |
| compliance_scans | `oc get compliancescan -A -o json` | 7.7 |
| compliance_suites | `oc get compliancesuite -A -o json` | 7.7 |
| fileintegrity | `oc get fileintegrity -A -o json` | 7.7 |
| namespaces | `oc get namespaces -o json` | 7.7 |
| secrets_count | `"$HC_CLI" get secrets -A --no-headers` | 7.7 |
| clusterrolebindings_admin | `oc get clusterrolebinding -o json` | 7.7 |

## 10_metrics.sh — Chapter 7.8: Metrics Collection

| Check Name | Command | Report Section |
|------------|---------|----------------|
| _(none found)_ | _(none found)_ | 7.8 |

## 11_hardware.sh — Chapter 7.9: Node Hardware Inventory

| Check Name | Command | Report Section |
|------------|---------|----------------|
| _(none found)_ | _(none found)_ | 7.9 |

## 12_ccx.sh — Chapter unknown: 12 Ccx

| Check Name | Command | Report Section |
|------------|---------|----------------|
| _(none found)_ | _(none found)_ | unknown |
