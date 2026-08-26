<div class="cover-page">

# OpenShift Health Check

## {CLIENT}

{AUTHOR}

{REPORT_DATE}

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
4. Purpose and Engagement Approach  
5. Health Check Overview  
6. Observations and Recommendations  
7. Raw Check Report (7.1–7.9)  
8. Conclusions  

---

## Chapter 3. Executive Summary

### 3.1 Executive Summary

{EXEC_SUMMARY}

### 3.2 Technical Summary

{TECH_SUMMARY}

### Summary Statistics

| Metric | Count |
|--------|-------|
| Total Checks Performed | {TOTAL_CHECKS} |
| PASS | {PASS_COUNT} |
| WARNING | {WARNING_COUNT} |
| FAIL | {FAIL_COUNT} |
| INFO | {INFO_COUNT} |
| NOT APPLICABLE / SKIPPED | {SKIP_COUNT} |
| Findings (P0–P3) | {FINDING_COUNT} |

---

## Chapter 4. Purpose and Engagement Approach

Red Hat Consulting was engaged by {CLIENT} to assist with an OpenShift Health Check which seeks to assess the state and health of the OpenShift cluster. This report details the architecture and supportability review performed for the OpenShift cluster `{CLUSTER_ID}`, with data collected in {CAPTURE_MONTH_YEAR}.

The assessment criteria and results are based on the data provided by the customer ({CLIENT}). {CLIENT} may change their configuration at any time, and Red Hat's products, versions, and associated life cycles also evolve over time; therefore this report is a snapshot assessment and is subject to change.

The goal of the assessment is to give the customer feedback on the supportability of their current configuration with respect to Red Hat's current products, certification ecosystem, and support services.

### 4.1 How to Interpret the Health Check Results

The following are the types of key responses when executing a check or rule:

| Result | Meaning |
|--------|---------|
| 🟢 PASS | The check result matches the expected or documented configuration. |
| 🔵 INFO | The rule does not assert a pass/fail outcome; it surfaces data such as cluster ID or version. Some INFO results still need a manual follow-up that cannot be automated yet. |
| 🟡 WARNING | A finding that needs attention so you can draw a conclusion. For example, an Ingress HA check may be unable to prove HA from the collected data, so it warns and further judgement is yours. |
| 🟡 LIMITATION | Same class of attention as WARNING: the check could not fully prove the expected state from available data or known product limits. |
| 🔴 FAIL | Not as expected or documented; this configuration may not be generally supported or recommended. |
| ⚪ SKIPPED | The data required to perform the check is not available. Confirm whether that is expected. |
| ⚪ NOT APPLICABLE | The check was not executed for a reason. For example, if a sub-check shows OpenShift Logging is not installed, further Logging-related checks are N/A. |
| ⚫ NONE | The rule returned no result. Phased_Gates rules should not return ⚫ NONE. |
| ⚪ EXCEPTION | There is an issue or error in the rule with the given data. File a bug that references the error message and the data (for example the SFDC case attachment) this occurred with. |

---

## Chapter 5. Health Check Overview

### 5.1 Cluster Identification

{CLUSTER_ID_TABLE}

### 5.2 Must Gather(s) Data Checks

{DATA_COLLECTION_METHOD}

### 5.3 Check Summary by Category

| Category | PASS | WARNING | FAIL | INFO | N/A / Skipped | Total |
|----------|------|---------|------|------|---------------|-------|
{STATS_TABLE_ROWS}
| **Total** | **{PASS_COUNT}** | **{WARNING_COUNT}** | **{FAIL_COUNT}** | **{INFO_COUNT}** | **{SKIP_COUNT}** | **{TOTAL_CHECKS}** |

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
