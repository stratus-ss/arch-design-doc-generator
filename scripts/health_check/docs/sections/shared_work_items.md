```bash
make workitems
```

This parses the execution guide LLD (from `output/Health_Check_LLD/`) and extracts all action items as Kanban stories and sub-tasks into `output/Work_Items/`. Two files are produced:

- Individual markdown files per HC phase (HC-01 through HC-12) — one Story per phase
- `health_check_workitems.csv` — a Jira bulk-import CSV that can be uploaded directly to a Jira project

To import into Jira: **Issues → Import Issues from CSV**, select the CSV, map the columns, and import.

