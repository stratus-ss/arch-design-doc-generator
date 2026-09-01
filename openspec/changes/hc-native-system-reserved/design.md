# Design: native effective kubelet systemReserved

Mint `7.2.kubelet.system_reserved` from `08_day2/node_image_gc.json` member fields `system_reserved_memory` and `auto_sizing_reserved`, plus node capacity from `04_topology` `nodes`. Do not dump raw configz. Do not retune `_check_system_reserved`.

Scoring matrix is in the delta spec. Coverage percent vs ORIG Chapter 6 is out of this change.
