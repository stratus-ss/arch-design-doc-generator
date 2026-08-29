# Health Check Report Engine (`hc-live-parity-collect` delta)

## ADDED Requirements

### Requirement: Optional product and platform CR JSON on collect
Live `hc-collect` SHALL write the following check_name files (plus `.meta.json`) via `hc_capture_json`. Missing CRD or empty items SHALL be `_hc_not_found`, not a failed collect.

#### Scenario: New capture names exist after collect
- GIVEN a successful `hc-collect` run
- WHEN the results directory is listed
- THEN these files exist under their category dirs:
  `03_base_platform/insightsoperator.json`,
  `05_components/dns_pods.json`, `featuregate.json`, `metallb.json`, `ipsecconfig.json`,
  `sriovnetwork.json`, `performanceprofile.json`, `localvolume.json`, `csidriver.json`,
  `06_layered/odf_storagecluster.json`, `rhoso_controlplane.json`, `mtv_controller.json`,
  `07_cluster_health/pdb.json`,
  `09_security/fileintegrity.json`
- AND collect does not add a second DNS cluster capture besides existing `dns_config.json`
