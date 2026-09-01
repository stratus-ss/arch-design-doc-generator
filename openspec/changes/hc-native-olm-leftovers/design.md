# Design: native OLM failed CSV

Mint `7.3.olm.failed_csv` from collected `03_base_platform/csv` (`oc get csv -A`). Do not retune `7.3.co.platform`. Do not change `7.3.tsr.3_2_2_additional_operators` `content_from`. Do not alias Insights leftover CRDs.

`_hc_error` is SKIPPED. Missing payload is NOT_APPLICABLE. Zero items is NOT_APPLICABLE. Any `status.phase == Failed` is FAIL. Else any non-empty phase other than Succeeded is WARNING. Else PASS.

Scoring matrix is in the delta spec. Coverage percent vs ORIG Chapter 6 is out of this change.
