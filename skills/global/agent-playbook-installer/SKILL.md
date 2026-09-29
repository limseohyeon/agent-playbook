---
name: agent-playbook-installer
description: List, install, update, inspect, or remove Codex skills and rules from the local D:\agent-playbook repository. Use when the user wants to apply a playbook artifact to Codex; do not use for authoring artifacts or installing from unrelated repositories.
---

# Agent Playbook Installer

Use `D:\agent-playbook` as the source of truth and operate only on its current local checkout. Never pull, commit, or push as part of installation.

## Workflow

1. Inspect the repository status and resolve the requested artifact to an exact name under `skills/global/` or `rules/global/`.
2. For discovery or inspection, run the installer with `-List` or `-Status`. These operations are read-only.
3. Install, update, or remove artifacts only when the user explicitly requests that mutation. A request such as "install X" or "remove X" is sufficient authorization for that named artifact.
4. Use `-WhatIf` when the requested target, overwrite behavior, or affected global file is unclear. Do not use `-Force` unless the user approves replacing a locally modified managed installation.
5. Report the source artifact, destination, resulting status, and whether Codex may need a new chat or restart to discover a newly installed skill.

Run the deterministic wrapper instead of copying or editing runtime files manually:

```powershell
D:\agent-playbook\scripts\install-playbook.ps1 -List
D:\agent-playbook\scripts\install-playbook.ps1 -Status
D:\agent-playbook\scripts\install-playbook.ps1 -Name <artifact-name>
D:\agent-playbook\scripts\install-playbook.ps1 -Name <artifact-name> -Uninstall
```

## Installation Behavior

- Skills are copied to `%USERPROFILE%\.codex\skills\<name>`. The repository remains canonical; there is no automatic synchronization.
- Rules are rendered into the installer-managed block in `%USERPROFILE%\.codex\AGENTS.md`. Content outside that block belongs to the user and must remain unchanged.
- Installation stamps record source and destination hashes. If an installed copy or managed rule block changed outside the installer, stop instead of overwriting it.
- The installer publishes English runtime artifacts. Korean files under `translations/ko/` are documentation counterparts, not runtime inputs.
- Do not treat `%USERPROFILE%\.codex\rules\` as a destination for playbook guidance; that directory is for command-execution policies.

Use `$agent-playbook-manager` instead when the user wants to create or modify an artifact in the repository.
