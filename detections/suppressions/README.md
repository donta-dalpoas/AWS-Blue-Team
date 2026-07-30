# Suppression Rules

Place suppression YAML files in this directory to prevent known false positives
from generating alerts.

See `docs/runbooks/false-positive-suppression.md` for the full workflow.

## File Format

```yaml
id: SUP-XXX
name: Short description
description: Why this is a false positive
suppresses:
  - rule_id: DET-XXX
    conditions:
      field.name: "match-value"
created_by: your-name
created_date: "YYYY-MM-DD"
expires: null  # or "YYYY-MM-DD"
approved_by: approver-name
reason: Detailed justification
```
