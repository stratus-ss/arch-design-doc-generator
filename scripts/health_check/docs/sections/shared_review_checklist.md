Open `output/Health_Check_Report/<ClientPrefix>_OpenShift_Health_Check_<cluster>.md` in your editor or a markdown viewer. 

Key things to review before delivering to the customer:

- **Executive summary** — replace the placeholder if you used `--dry-run`, or refine the generated text
- **P0 / P1 findings** — verify the remediation recommendations are accurate for this customer's environment, and sanity-check the priority itself (see "How finding priority is determined" above — it's a keyword heuristic, not a guaranteed-correct severity rating)
- **NOT_APPLICABLE checks** — confirm these correctly reflect what is / isn't installed on the cluster
- **Cluster metadata at the top** — if any fields show `TBD`, populate them in `project.yaml` and re-run `make hc-report`

