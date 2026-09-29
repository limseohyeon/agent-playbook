---
name: gitlab-issue-lifecycle
description: Create and maintain issue trees for approved agent plans on self-managed GitLab. Use only when the user explicitly asks to register a plan as issues, record progress on a linked issue, or close a completed linked issue. Do not use for GitHub, CI configuration, or ordinary planning that was not requested for issue registration.
---

# GitLab Issue Lifecycle

Use the bundled script for deterministic GitLab operations. This skill manages issues; it does not configure CI, create branches, commit code, or infer that work is complete.

## Preconditions

- Work only with a self-managed GitLab remote detected from the current repository.
- If zero or multiple distinct GitLab project remotes are plausible, stop and ask the user to select one.
- Use a project access token stored in Windows Credential Manager under the script-derived project key. Never request or print a token in chat, command arguments, files, or logs.
- A new project requires one-time interactive credential registration with `credential-set`.
- Do not create, update, comment on, or close an issue unless the current request authorizes that exact class of write.

Run commands through:

```powershell
& "<skill-dir>\scripts\run.ps1" <command> [options]
```

## Register an Approved Plan

Run this workflow only when the user explicitly asks to register the plan as issues.

1. Convert the plan into one parent item and independently verifiable child items using [the payload schema](references/payload-schema.md).
2. Keep assignees and due dates unset. Include priority only when the user supplied it.
3. Discover existing project labels and retain exact matches only. Never create a missing label.
4. Run `dry-run` and show the complete proposed parent and child issue set to the user.
5. Ask for one approval covering the displayed batch.
6. After approval, run `create-tree --confirm CREATE`. Do not reinterpret or expand the approved payload.
7. Return only created issue titles, IIDs, and URLs. Also provide one concise start prompt per child containing its issue URL.

The parent description contains a checklist linking every child. Child descriptions link back to the parent. The script uses a plan ID marker and refuses to create a second tree when it finds a matching marker.

## Record Progress

Operate only on the issue explicitly linked by the current task.

- At useful checkpoints or task completion, prepare a concise comment containing completed work, verification, blockers, and the next concrete step.
- A task already started from a generated issue prompt authorizes ordinary progress comments for that issue; show the intended comment before writing when it includes an unexpected scope change.
- Run `comment --issue <iid> --confirm UPDATE` with a JSON body from standard input.
- Update the parent checklist only when the linked child state changes.
- New scope requires a separately previewed and approved issue batch.

## Close an Issue

- Never infer closure from an assistant statement alone.
- Summarize the completion evidence and ask for explicit approval immediately before closing.
- After approval, run `close --issue <iid> --confirm CLOSE`.
- Then update the parent checklist if a parent is recorded.

## Failure Handling

- Treat authentication errors, project mismatches, missing permissions, and partial writes as blockers.
- On a partial batch failure, report the created IIDs and stop. Never retry the whole batch automatically.
- Do not disable TLS verification. If an internal CA is required, use `--ca-file` with an approved certificate path.
- Keep command output compact and never expose headers or response bodies containing sensitive data.

## Validation

For setup and maintenance, use only non-mutating checks unless the user separately authorizes a real issue operation:

```powershell
& "<skill-dir>\scripts\run.ps1" target
& "<skill-dir>\scripts\run.ps1" check
& "<skill-dir>\scripts\run.ps1" labels
```

Do not create a test issue merely to validate the skill.
