# Design: native Quay application pods

Mint `7.4.quay.pods` from QuayRegistry namespaces and a merged pod List (`quay_pods.json`). Collect namespaces from each CR `metadata.namespace` plus `spec.targetNamespace` when set; if the CR list is empty, still collect `quay-enterprise` and `quay-registry`. Prefer label `quay-component` when that list is non-empty, and always merge per-namespace `oc get pods`.

Do not score QuayRegistry Available as a substitute for app pods. Do not alias supported-configuration (lifecycle). Do not retune `_evaluate_layered_product` for Quay Registry.

Scoring matrix is in the delta spec. Coverage percent vs ORIG Chapter 6 is out of this change.
