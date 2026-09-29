# Issue Tree Payload

Send UTF-8 JSON on standard input to `dry-run` and `create-tree`.

```json
{
  "plan_id": "stable-user-visible-plan-id",
  "parent": {
    "title": "Overall goal",
    "purpose": "Why this work exists",
    "in_scope": ["Included outcome"],
    "out_of_scope": ["Explicit exclusion"],
    "acceptance_criteria": ["Verifiable completion condition"],
    "dependencies": [],
    "labels": ["existing-label"],
    "priority": null
  },
  "children": [
    {
      "key": "short-stable-key",
      "title": "Independent deliverable",
      "purpose": "Why this child exists",
      "in_scope": ["Included work"],
      "out_of_scope": ["Excluded work"],
      "acceptance_criteria": ["Verifiable completion condition"],
      "dependencies": [],
      "labels": [],
      "priority": null
    }
  ]
}
```

## Rules

- `plan_id` must be stable for retries and unique within the target project.
- `children` must contain at least one item.
- Child `key` values must be unique within the plan.
- `dependencies` contains child keys from the same payload, not free-form prose.
- `labels` are matched against existing project labels. Unknown labels are omitted and reported; they are never created.
- `priority` is omitted or `null` unless the user explicitly supplied it. When present, it is rendered as text and does not create a label.
- Assignee, milestone, weight, and due date are intentionally unsupported in the first version.

For `comment`, send:

```json
{
  "completed": ["Completed item"],
  "verification": ["Observed check and result"],
  "blockers": [],
  "next_step": "One concrete next action"
}
```
