# Design: content_from aliases for native-without-TSR

Prefer native `check_id` as `content_from` target. Flatten inventory TSR→TSR through existing aliases (single hop only). Skip and log missing targets.

Family fan-out: RHACM → `7.4.acm.state`; ODF → `7.4.odf.state`; RHOSO → `7.4.rhoso.state`. Virt maps to `7.4.cnv.state` / `kubevirt` / `pods` / `live_migratable` by story. Distinct virt KB rows are not converted into aliases of identification-and-state.

New alias rows omit inherited fields and set `include_in_findings = false`. Existing loader contracts (no chains, no overlay, exact target) stay as specified.
