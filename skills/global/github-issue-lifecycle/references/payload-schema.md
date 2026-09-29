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
    "priority": null,
    "template": ".github/ISSUE_TEMPLATE/feature.md",
    "body": "Completed Markdown that follows the selected template"
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
      "priority": null,
      "template": ".github/ISSUE_TEMPLATE/feature.md",
      "body": "Completed Markdown that follows the selected template"
    }
  ]
}
```

## Rules

- `plan_id` must be stable for retries and unique within the target repository.
- `children` must contain at least one item.
- Child `key` values must be unique within the plan.
- `dependencies` contains child keys from the same payload. Each entry becomes a native GitHub `blocked by` relationship.
- `labels` are matched against existing repository labels. Unknown labels are omitted and reported; they are never created.
- `priority` is omitted or `null` unless the user explicitly supplied it. When present, it is rendered as text and does not create a label.
- Run `templates` before constructing the payload. It returns Markdown templates and YAML issue forms under `.github/ISSUE_TEMPLATE`, excluding `config.yml`.
- When templates exist, every parent and child must use one. `template` is its repository-relative path and `body` is completed Markdown following that template. If exactly one template exists, an omitted `template` is filled automatically; `body` remains required.
- When multiple templates exist, `template` is required for every item and must exactly match a discovered path.
- When no templates exist, omit both `template` and `body`; the script renders its standard issue body.
- Assignees, milestones, projects, issue types, and due dates are intentionally unsupported in the first version.

For `comment`, send:

```json
{
  "completed": ["Completed item"],
  "verification": ["Observed check and result"],
  "blockers": [],
  "next_step": "One concrete next action"
}
```
