<div class="cover-page">

# OpenShift Health Check

## {CLIENT}

{AUTHOR}

{REPORT_DATE}

</div>

<div class="cover-meta">

| | |
|---|---|
| **Customer** | {CLIENT} |
| **Cluster** | {CLUSTER_NAME} |
| **OCP Version** | {OCP_VERSION} |
| **Data Capture Date** | {CAPTURE_DATE} |
| **Report Date** | {REPORT_DATE} |
| **Case Number** | {CASE_NUMBER} |
| **Author** | {AUTHOR} |
| **Install Type** | {INSTALL_TYPE} |
| **Update Channel** | {CHANNEL} |

</div>

---

## Chapter 1. Introduction

This document is an OpenShift Health Check report prepared by Red Hat for {CLIENT}. It provides a point-in-time assessment of the OpenShift Container Platform cluster **{CLUSTER_NAME}** against Red Hat's recommended configuration baseline.

The assessment covers base platform configuration, cluster topology, core component health, layered product status, cluster runtime health, Day-2 operations, and security and compliance. Findings are classified P0–P3 by severity and accompanied by actionable remediation guidance.

> **Scope:** This report reflects the state of the cluster as of {CAPTURE_DATE}. It is a configuration and operational assessment, not a performance or capacity sizing exercise.

---

## Chapter 2. Table of Contents

1. Introduction  
2. Table of Contents  
3. Executive Summary  
4. Critical Findings  
5. Health Check Overview  
6. Observations and Recommendations  
7. Raw Check Report (7.1–7.9)  
8. Conclusions  

---

## Chapter 3. Executive Summary

{EXEC_SUMMARY}

### Summary Statistics

| Metric | Count |
|--------|-------|
| Total Checks Performed | {TOTAL_CHECKS} |
| PASS | {PASS_COUNT} |
| WARNING | {WARNING_COUNT} |
| FAIL | {FAIL_COUNT} |
| NOT APPLICABLE / SKIPPED | {SKIP_COUNT} |
| Findings (P0–P3) | {FINDING_COUNT} |

---

## Chapter 4. Critical Findings

The following critical and high-priority findings require immediate or near-term attention.

{CRITICAL_FINDINGS_SUMMARY}

---

## Chapter 5. Health Check Overview

### 5.1 Cluster Identification

{CLUSTER_ID_TABLE}

### 5.2 Must Gather(s) Data Checks

{DATA_COLLECTION_METHOD}

### 5.3 Check Summary by Category

| Category | Total | PASS | WARNING | FAIL | N/A / Skipped |
|----------|-------|------|---------|------|---------------|
{STATS_TABLE_ROWS}
| **Total** | **{TOTAL_CHECKS}** | **{PASS_COUNT}** | **{WARNING_COUNT}** | **{FAIL_COUNT}** | **{SKIP_COUNT}** |

---

## Chapter 6. Observations and Recommendations

{FINDINGS_NARRATIVE}

### 6.1 Critical Findings Summary

{CRITICAL_FINDINGS}

### 6.2 Observations and Recommendations by Priority

{FINDINGS_SECTIONS}

---

## Chapter 7. Raw Check Report

### 7.1 Base Platform Checks

{CHECK_RESULTS_7_1}

---

### 7.2 Topology Checks

{CHECK_RESULTS_7_2}

---

### 7.3 Component Checks

{CHECK_RESULTS_7_3}

---

### 7.4 Layered Products

{CHECK_RESULTS_7_4}

---

### 7.5 Cluster Health

{CHECK_RESULTS_7_5}

---

### 7.6 Day-2 Operations

{CHECK_RESULTS_7_6}

---

### 7.7 Security and Compliance

{CHECK_RESULTS_7_7}

---

### 7.8 Performance Metrics

{CHECK_RESULTS_7_8}

---

### 7.9 Hardware Inventory

{CHECK_RESULTS_7_9}

---

## Chapter 8. Conclusions

This health check provides a snapshot of {CLIENT}'s OpenShift cluster **{CLUSTER_NAME}** as of {CAPTURE_DATE}. The findings above represent the current deviation from Red Hat's recommended configuration baseline.

Key points:

- This assessment reflects configuration and operational state at a single point in time; cluster state may have changed since data was captured.
- Sizing, capacity planning, and performance benchmarking are outside the scope of this engagement.
- Remediation timelines should be prioritized according to the P0–P3 classification: P0 findings require immediate attention, P1 findings should be addressed within the current sprint or change window.

Red Hat recommends scheduling a follow-up review after P0 and P1 remediations are completed to confirm resolution.

---

*This document is prepared for {CLIENT} and is intended for internal use only. Do not distribute externally without authorization.*
