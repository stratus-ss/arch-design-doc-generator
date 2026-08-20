# OpenShift Health Check — Execution Guide (LLD)

**Customer:** {CLIENT}  
**Cluster:** {CLUSTER_NAME}  
**OCP Version:** {OCP_VERSION}  
**Report Date:** {REPORT_DATE}  
**Case Number:** {CASE_NUMBER}  
**Author:** {AUTHOR}  

---

> **About this document:** This Low-Level Design (LLD) is the procedural runbook for executing an OpenShift Health Check engagement. It describes every step required to collect cluster data, assess each check category, analyze findings, and produce the final deliverable report. Each section provides both an **Automated Path** (using must-gather tooling) and a **Manual Fallback Path** (using `oc`/`kubectl` commands directly) for environments where must-gather data collection is restricted by NDA or access policy.
>
> **Pipeline note:** This guide predates, and describes a lower level of detail than, the fully automated collection/report pipeline now built into this repository. For most engagements, prefer `make hc-collect` (live cluster) or the `scripts/health_check/supportshell/` workflow (must-gather/offline) for HC-02/HC-03 collection, and `make hc-report` for HC-10/HC-11 analysis — see the root [README.md](../../README.md#health-check). The automated pipeline deterministically evaluates every check, resolves recommendations/documentation links/operational-impact ratings from the external knowledge base (`scripts/health_check/hc_report/kb/`), and supports check-profile scoping (`core` / `extended` / `advisory`, the latter adding TSR/CCX parity coverage). The manual steps below remain useful for spot-checking individual checks or when the automated tooling cannot be used in a given environment.

---

## HC-01: Engagement Setup

### Prerequisites

- Red Hat VPN access and valid customer case open in SFDC (Case #: {CASE_NUMBER})
- Access to the OpenShift cluster API endpoint (`oc login` credentials confirmed)
- `oc` CLI installed and matching target cluster version ({OCP_VERSION})
- `kubectl` CLI available as fallback
- `must-gather` tool access (if automated path applies)
- Engagement tooling: arch-design-doc-generator repo cloned, dependencies installed

### Steps

1. Confirm cluster API reachability: `oc cluster-info`
2. Confirm authentication: `oc whoami`
3. Confirm cluster version matches engagement scope: `oc get clusterversion`
4. Create working directory for engagement artifacts: `mkdir -p {CLIENT_PREFIX}_HC_{CLUSTER_NAME}/`
5. Confirm case number and log engagement start in SFDC case notes
6. Set environment variable: `export CLUSTER_NAME={CLUSTER_NAME}`

### Expected Output Format

- Shell confirms cluster API URL and version
- `oc whoami` returns a cluster-admin privileged account
- Working directory created and accessible

### Completion Gate

- [ ] Cluster API reachable and authenticated
- [ ] Correct OCP version confirmed ({OCP_VERSION})
- [ ] Working directory initialized
- [ ] SFDC case updated with engagement start note

---

## HC-02: Data Collection

### Prerequisites

- HC-01 complete
- Decision made: Automated Path or Manual Fallback Path (document in engagement notes)

### Automated Path

Must-gather collects all required data in a single archive:

```bash
# Standard must-gather (required for all engagements)
oc adm must-gather --dest-dir=must-gather-$(date +%Y%m%d)

# CNV / OpenShift Virtualization (if installed)
oc adm must-gather --image=registry.redhat.io/container-native-virtualization/cnv-must-gather-rhel9 \
  --dest-dir=must-gather-cnv-$(date +%Y%m%d)

# Pipelines (if installed)
oc adm must-gather --image=registry.redhat.io/openshift-pipelines/pipelines-must-gather-rhel8 \
  --dest-dir=must-gather-pipelines-$(date +%Y%m%d)
```

Compress and transfer archive to analysis workstation.

### Manual Fallback Path

When must-gather is not available due to NDA or access restrictions, collect data category by category using `oc` commands. Run all commands in HC-03 through HC-09 manual fallback sections. Save output to `{CLIENT_PREFIX}_HC_{CLUSTER_NAME}/raw_data/`.

```bash
# Verify data collection directory
mkdir -p {CLIENT_PREFIX}_HC_{CLUSTER_NAME}/raw_data/
```

### Expected Output Format

- Automated: `must-gather-YYYYMMDD/` directory with cluster data
- Manual: `raw_data/` directory populated by per-category commands in HC-03 through HC-09

### Completion Gate

- [ ] Must-gather archive collected OR manual fallback collection confirmed for all categories
- [ ] Data archived and accessible for analysis

---

## HC-03: Base Platform Assessment

*Maps to Chapter 7.1 — Base Platform Checks (Identification, Infrastructure, Hardware, Other Basic)*

### Prerequisites

- HC-02 complete; data available

### Automated Path

Run Phased Gates / CCX check tooling against must-gather data for category 7.1.

### Manual Fallback Path

Execute the following `oc` commands and save output:

```bash
# 7.1.1 — Cluster identification and release
oc get clusterversion -o yaml > raw_data/clusterversion.yaml
oc get clusteroperator > raw_data/clusteroperator.txt

# 7.1.2 — Subscriptions / installed operators
oc get subscription -A -o wide > raw_data/subscriptions.txt
oc get csv -A > raw_data/csv.txt

# 7.1.3 — Infrastructure and platform
oc get infrastructure cluster -o yaml > raw_data/infrastructure.yaml

# 7.1.4 — Hardware: master and worker node specs
oc get nodes -o wide > raw_data/nodes_wide.txt
oc describe nodes > raw_data/nodes_describe.txt
oc get nodes -o json | jq '.items[] | {name: .metadata.name, cpu: .status.capacity.cpu, memory: .status.capacity.memory, os: .status.nodeInfo.osImage}' > raw_data/node_resources.json

# 7.1.5 — Other basic checks: SCCs, auth
oc get scc > raw_data/scc.txt
oc get oauth cluster -o yaml > raw_data/oauth.yaml
```

### Expected Output Format

- YAML/JSON files for structured resources; `.txt` files for tabular output
- Each file named to match the check category it satisfies

### Completion Gate

- [ ] Cluster version and operator data collected
- [ ] Node hardware and resource data collected
- [ ] SCC and authentication data collected

---

## HC-04: Topology Assessment

*Maps to Chapter 7.2 — Topology Checks (Consistency, HA, Scalability)*

### Prerequisites

- HC-02 complete

### Automated Path

Run Phased Gates / CCX tooling for category 7.2 checks.

### Manual Fallback Path

```bash
# Node roles and topology
oc get nodes --show-labels > raw_data/node_labels.txt
oc get nodes -o json | jq '.items[] | {name: .metadata.name, roles: [.metadata.labels | to_entries[] | select(.key | startswith("node-role")) | .key]}' > raw_data/node_roles.json

# Machine config
oc get machineconfig > raw_data/machineconfig.txt
oc get machineconfigpool > raw_data/machineconfigpool.txt
oc get kubeletconfig -o yaml > raw_data/kubeletconfig.yaml

# Etcd member count (HA check)
oc get etcd cluster -o yaml > raw_data/etcd.yaml
oc -n openshift-etcd get pods > raw_data/etcd_pods.txt
```

### Expected Output Format

- Node role JSON, machine/kubelet config output, etcd pod status

### Completion Gate

- [ ] Node topology (roles, HA layout) documented
- [ ] Machine config pool states captured
- [ ] KubeletConfig and systemReserved settings captured
- [ ] Etcd member count verified

---

## HC-05: Component Assessment

*Maps to Chapter 7.3 — Component Checks (Operators, CRDs, MCO, ETCD, Registry, Monitoring, Ingress, Storage, Network)*

### Prerequisites

- HC-02 complete

### Automated Path

Run Phased Gates / CCX tooling for category 7.3 checks.

### Manual Fallback Path

```bash
# Operators and CRDs
oc get co > raw_data/cluster_operators.txt
oc get co -o json | jq '.items[] | {name: .metadata.name, available: (.status.conditions[] | select(.type=="Available") | .status), degraded: (.status.conditions[] | select(.type=="Degraded") | .status)}' > raw_data/operator_status.json

# MCO / MachineConfig
oc get mc -o yaml > raw_data/machineconfig_full.yaml

# ETCD health and performance
oc -n openshift-etcd exec -c etcd $(oc get pods -n openshift-etcd -l app=etcd -o name | head -1) -- etcdctl endpoint status --cluster -w table 2>/dev/null > raw_data/etcd_status.txt || true
oc -n openshift-etcd get pods -o wide > raw_data/etcd_pods_wide.txt

# Image registry
oc get configs.imageregistry.operator.openshift.io cluster -o yaml > raw_data/imageregistry.yaml

# Monitoring
oc get prometheus -n openshift-monitoring -o yaml > raw_data/prometheus.yaml
oc get prometheusrule -n openshift-monitoring > raw_data/prometheusrule.txt

# Ingress
oc get ingresscontroller -n openshift-ingress-operator -o yaml > raw_data/ingresscontroller.yaml

# Storage
oc get storageclass > raw_data/storageclass.txt
oc get pv > raw_data/pv.txt
oc get pvc -A > raw_data/pvc.txt

# Networking
oc get network cluster -o yaml > raw_data/network.yaml
oc get hostsubnet > raw_data/hostsubnet.txt 2>/dev/null || true
```

### Expected Output Format

- Per-component YAML/JSON/txt files in `raw_data/`

### Completion Gate

- [ ] All cluster operators status captured
- [ ] ETCD health data collected
- [ ] Storage, network, monitoring data collected

---

## HC-06: Layered Products Assessment

*Maps to Chapter 7.4 — Layered Products (Logging, Service Mesh, Serverless, Quay, ACS, ACM, CNV, Pipelines)*

### Prerequisites

- HC-02 complete
- Inventory of installed layered products confirmed (from 7.1.2 subscription check)

### Automated Path

Run Phased Gates / CCX tooling for category 7.4 checks. Use product-specific must-gather images where available.

### Manual Fallback Path

```bash
# CNV / OpenShift Virtualization
oc get hyperconverged -n openshift-cnv -o yaml > raw_data/hyperconverged.yaml 2>/dev/null || echo "CNV not installed"

# ACM
oc get multiclusterhub -n open-cluster-management -o yaml > raw_data/acm.yaml 2>/dev/null || echo "ACM not installed"

# ACS / StackRox
oc get central -n stackrox -o yaml > raw_data/acs.yaml 2>/dev/null || echo "ACS not installed"

# Logging / Loki
oc get clusterlogging instance -n openshift-logging -o yaml > raw_data/logging.yaml 2>/dev/null || echo "Logging not installed"

# Pipelines
oc get tektonconfig cluster -o yaml > raw_data/pipelines.yaml 2>/dev/null || echo "Pipelines not installed"
```

### Expected Output Format

- Per-product YAML files; missing products logged as "not installed"

### Completion Gate

- [ ] All installed layered products assessed
- [ ] Products not installed documented as NOT APPLICABLE

---

## HC-07: Cluster Health Assessment

*Maps to Chapter 7.5 — Cluster Health (Kubelet, Alerts, Pod Restarts)*

### Prerequisites

- HC-02 complete

### Automated Path

Run Phased Gates / CCX tooling for category 7.5 checks.

### Manual Fallback Path

```bash
# Kubelet status and version
oc get nodes -o json | jq '.items[] | {name: .metadata.name, kubeletVersion: .status.nodeInfo.kubeletVersion}' > raw_data/kubelet_versions.json

# Active alerts
oc -n openshift-monitoring exec -c prometheus $(oc get pods -n openshift-monitoring -l prometheus=k8s -o name | head -1) -- \
  curl -s http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | select(.state=="firing")' > raw_data/firing_alerts.json 2>/dev/null || true

# Pod restarts (top restarters)
oc get pods -A -o json | jq '[.items[] | {ns: .metadata.namespace, name: .metadata.name, restarts: ([.status.containerStatuses[]?.restartCount] | add // 0)}] | sort_by(-.restarts) | .[0:20]' > raw_data/pod_restarts.json

# Schedulable masters check
oc get nodes -l node-role.kubernetes.io/master -o json | jq '.items[] | {name: .metadata.name, taints: .spec.taints}' > raw_data/master_taints.json
```

### Expected Output Format

- JSON files for alerts, restarts, kubelet versions; taint output for master schedulability

### Completion Gate

- [ ] Kubelet version consistency verified across all nodes
- [ ] Firing alerts captured and categorized
- [ ] Top pod restart candidates identified
- [ ] Master node schedulability assessed

---

## HC-08: Day-2 Operations Assessment

*Maps to Chapter 7.6 — Day-2 Operations (Quotas, Pruning, Upgrades, Alerts)*

### Prerequisites

- HC-02 complete

### Automated Path

Run Phased Gates / CCX tooling for category 7.6 checks.

### Manual Fallback Path

```bash
# Resource quotas and limit ranges
oc get resourcequota -A > raw_data/resourcequota.txt
oc get limitrange -A > raw_data/limitrange.txt

# Cluster pruning config
oc get image.config.openshift.io cluster -o yaml > raw_data/image_config.yaml

# Upgrade history
oc get clusterversion -o json | jq '.items[].status.history' > raw_data/upgrade_history.json

# Namespace-level resource usage (top)
oc adm top nodes > raw_data/top_nodes.txt 2>/dev/null || true
oc adm top pods -A --sort-by=memory 2>/dev/null | head -30 > raw_data/top_pods.txt || true
```

### Expected Output Format

- Quota and limit range tables, upgrade history JSON, resource usage summary

### Completion Gate

- [ ] All namespace resource quotas and limit ranges captured
- [ ] Upgrade history documented
- [ ] Resource utilization baseline captured

---

## HC-09: Security and Compliance Assessment

*Maps to Chapter 7.7 — Security and Compliance (SCCs, Auth, Compliance)*

### Prerequisites

- HC-02 complete

### Automated Path

Run Phased Gates / CCX tooling for category 7.7 checks.

### Manual Fallback Path

```bash
# SCC modifications
oc get scc -o json | jq '.items[] | {name: .metadata.name, creationTimestamp: .metadata.creationTimestamp, annotations: .metadata.annotations}' > raw_data/scc_detail.json

# Identity providers / OAuth
oc get oauth cluster -o yaml > raw_data/oauth_detail.yaml

# Compliance operator (if installed)
oc get compliancescan -A > raw_data/compliance_scans.txt 2>/dev/null || echo "Compliance operator not installed"

# Cluster role bindings (broad access check)
oc get clusterrolebinding -o json | jq '.items[] | select(.subjects[]?.kind=="User" or .subjects[]?.kind=="ServiceAccount") | {name: .metadata.name, role: .roleRef.name, subjects: .subjects}' > raw_data/crb_summary.json 2>/dev/null | head -50 || true
```

### Expected Output Format

- SCC detail JSON, OAuth config, compliance scan results, role binding summary

### Completion Gate

- [ ] SCC modifications identified and documented
- [ ] Authentication providers confirmed
- [ ] Compliance scan results captured (or NOT APPLICABLE logged)

---

## HC-10: Analysis and Prioritization

### Prerequisites

- HC-03 through HC-09 complete (all data collected)

### Steps

1. **Triage all FAIL and WARNING results** from each category into a master finding list
2. **Apply P0–P3 priority classification:**
   - **P0 — Critical (Immediate Action Required):** Poses imminent threat to cluster consensus, API stability, or data integrity. Examples: etcd disk latency exceeding thresholds, schedulable master nodes, active split-brain risk.
   - **P1 — High (Security, Supportability, OS Configuration):** Unsupported configurations, security boundary violations, OS-level issues that affect supportability. Examples: modified default SCCs, Kubernetes version mismatches, imminent certificate expiration.
   - **P2 — Medium (Performance, Configuration, Operations):** Configuration drift, performance degradation, operational gaps. Examples: undersized system reservations, runaway quotas, missing pruning config, garbage collection gaps.
   - **P3 — Specific Component Findings:** Component-specific issues that don't fit P0–P2. Orphaned PVs, non-critical authentication defaults.

3. **Group findings into risk domains** for the 6.1 Critical Findings Summary:
   - Control Plane & Etcd Instability
   - Unsupported Configurations & Version Drift
   - Compute Resource Violations
   - Storage & Networking Bottlenecks
   - (Add domains as findings warrant)

4. **Write finding summaries:** For each P0–P3 finding, draft:
   - Finding title (concise, specific)
   - Problem description with observed values and thresholds
   - Recommendation with actionable steps and relevant KCS/doc links

### Expected Output Format

- Master finding list with IDs, priorities, and domains
- Draft finding summaries ready for Chapter 6 narrative

### Completion Gate

- [ ] All FAILs and WARNINGs triaged
- [ ] P0–P3 classification applied to each finding
- [ ] Risk domains identified for 6.1 summary
- [ ] Finding summaries drafted with recommendations

---

## HC-11: Report Writing

### Prerequisites

- HC-10 complete; finding list finalized

### Steps

1. **Chapter 3 — Executive Summary:**
   - State overall cluster health rating (Degraded and At Risk / Stable / etc.)
   - Reference total check counts: {TOTAL_CHECKS} checks run, {FAIL_COUNT} FAIL, {WARNING_COUNT} WARNING
   - 2–3 paragraphs summarizing the most critical risk themes

2. **Chapter 6.1 — Critical Findings Summary:**
   - Group P0 and high-impact P1 findings by risk domain
   - Write 3–5 bullet points per domain describing the issue and impact

3. **Chapter 6.2 — Observations and Recommendations:**
   - For each P0–P3 finding, write a structured finding entry:
     ```
     #### 6.2.N.M. Finding Title (check ID references)
     [Problem description with observed metrics]
     **Recommendation:**
     [Actionable steps with oc commands and KCS links]
     ```

4. **Chapter 5 — Health Check Overview:**
   - Fill cluster identification table from collected metadata
   - Must-gather data checks table (PASS/NOT APPLICABLE per image)
   - Summary of checks table by category with counts

5. **Chapter 7 — Raw Check Report:**
   - Paste or reference all check results from data collection
   - Ensure each check entry has: Check (ID + description), Status, Result, Links

6. **Conclusions section:** Standard disclaimer (snapshot in time, sizing not considered)

### Expected Output Format

- Completed `{CLIENT_PREFIX}_OpenShift_Health_Check_{CLUSTER_NAME}.md`
- All 7 chapters populated with actual data and findings

### Completion Gate

- [ ] Chapter 3 executive summary written
- [ ] Chapter 6.1 critical summary written
- [ ] All Chapter 6.2 P0–P3 findings written with recommendations
- [ ] Chapter 5 cluster identification populated
- [ ] Chapter 7 check results populated
- [ ] Report self-review: no placeholder text remaining

---

## HC-12: Deliverable Assembly

### Prerequisites

- HC-11 complete; report markdown finalized

### Steps

1. **Self-review the completed report:**
   - No placeholder text remaining
   - All check IDs reference actual collected data
   - KCS and documentation links are valid and relevant
   - Finding count matches priority breakdown table

2. **Generate PDF:**
   ```bash
   # Using arch-design-doc-generator pipeline
   make hc-pdf

   # Manual fallback: pandoc + weasyprint
   pandoc report.md -o report.html --standalone --metadata title="{CLIENT} OpenShift Health Check"
   weasyprint report.html {CLIENT_PREFIX}_OpenShift_Health_Check_{CLUSTER_NAME}.pdf
   ```

3. **Final checklist:**
   - PDF page count reasonable (typically 50–150 pages depending on cluster size)
   - Tables render correctly in PDF
   - TOC links functional in PDF
   - Header/footer shows correct client and document title

4. **Deliver to customer:**
   - Upload to SFDC case #{CASE_NUMBER}
   - Share via agreed delivery method (email, portal, etc.)
   - Schedule debrief call to walk through findings

5. **Archive engagement artifacts** (without client data in git)

### Expected Output Format

- `{CLIENT_PREFIX}_OpenShift_Health_Check_{CLUSTER_NAME}.pdf` — final deliverable
- Engagement closed in SFDC with delivery note

### Completion Gate

- [ ] PDF generated and visually reviewed
- [ ] Report delivered to customer via agreed channel
- [ ] SFDC case updated with delivery note
- [ ] Engagement artifacts archived (client data not committed to git)
