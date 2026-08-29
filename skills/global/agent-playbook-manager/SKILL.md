---
name: agent-playbook-manager
description: Create or update reusable agents, skills, rules, and prompts in the D:\agent-playbook repository using its category, bidirectional English-Korean synchronization, hash, and README-index conventions. Use for playbook artifacts only; do not route ordinary project files or general documents into this repository. Do not copy artifacts into ~/.codex or ~/.cursor unless the user asks to install them.
---

# Agent Playbook Manager

Manage reusable playbook artifacts in `D:\agent-playbook`. Keep this repository as the source of truth. Do not install generated artifacts into Codex or Cursor unless the user separately requests installation; this manager skill is the only artifact installed globally by default.

## Scope

Apply this skill when creating or updating reusable:

- Custom agents
- Skills
- Rules or durable guidance
- Reusable prompts

Do not apply it to ordinary project code, repository documentation, reports, or one-off Markdown files.

## Classification

Use exactly one of these paths:

```text
agents/global/<name>/
skills/global/<name>/
rules/global/<name>/
prompts/global/<name>/
```

Mirror the English entrypoint under:

```text
translations/ko/<same-relative-path>
```

Entrypoints:

- Agent: exactly one TOML file directly in the artifact directory.
- Skill: `SKILL.md`.
- Rule: exactly one Markdown file directly in the artifact directory.
- Prompt: exactly one Markdown file directly in the artifact directory.

Use lowercase letters, digits, and hyphens for artifact directory names. Do not create a `misc` category or per-artifact README files. The repository root `README.md` is the only README.

If classification is ambiguous, present the proposed category and full path, then wait for confirmation. Otherwise, tell the user the exact target paths before writing.

## Source and Translation

Keep the English entrypoint and Korean counterpart semantically synchronized in both directions. The side the user asks to change, or the side containing the relevant existing edit, is the working source for that change; update the other side in the same task.

- Markdown translations declare `translation_of` and `source_sha256` in YAML frontmatter.
- TOML translations declare the same fields in leading comments so the TOML schema remains valid.
- Translate behavior and explanations, but keep identifiers, commands, paths, code, and schema keys unchanged when translation would break them.
- Before editing, inspect both files and their Git changes to determine whether English, Korean, or both changed.
- If only one side changed, preserve its intent and translate that change into the other side.
- If both sides changed, merge compatible changes into both files. If their intent conflicts or the correct result is unclear, explain the conflict and ask the user instead of choosing one side or overwriting either edit.
- After the English and Korean contents are final, refresh translation metadata with:

```powershell
python D:\agent-playbook\.github\scripts\sync_translation_hash.py <english-repository-relative-path>
```

`source_sha256` records the final English file for stale-translation validation; it does not make English the only allowed direction of change. Never update only the hash. Review both files for semantic equivalence first.

## Repository Workflow

1. Inspect `D:\agent-playbook`, its Git status, and any applicable repository guidance.
2. Preserve unrelated user changes. Stop if overlapping changes cannot be handled safely.
3. Classify the artifact and announce the English and Korean target paths.
4. Inspect both language files and identify the working source for each requested or existing change.
5. Apply each change bidirectionally so the English and Korean files have equivalent behavior in their native runtime format.
6. Refresh translation metadata.
7. Regenerate the root index:

```powershell
python D:\agent-playbook\.github\scripts\generate_readme_index.py
```

8. Validate before completion:

```powershell
python D:\agent-playbook\.github\scripts\generate_readme_index.py --check
```

Also run format-appropriate validation, such as `quick_validate.py` for skills, TOML parsing for agents, Python compilation for changed Python scripts, and `git diff --check`.

If the category structure changes, inspect and update both the README generator and `.github/workflows/update-readme-index.yml` in the same task.

## Installation

Publish English artifacts with a copy, not a link. Do not run these commands unless the user asks to install.

```powershell
python D:\agent-playbook\scripts\install_playbook.py --runtime cursor --scope all
```

```powershell
D:\agent-playbook\scripts\install-playbook.ps1 -Runtime Cursor -Scope All
```

Defaults are `--runtime codex` and `--scope manager`. `scripts/install-agent-playbook-manager.ps1` remains a wrapper for that default.

Runtime mapping:

- Codex skills: `%USERPROFILE%\.codex\skills\<name>\`
- Cursor skills: `%USERPROFILE%\.cursor\skills\<name>\`
- Cursor agents: `%USERPROFILE%\.cursor\agents\<name>.md`
- Cursor rules: stage under `%USERPROFILE%\.cursor\playbook-install\rules\`, then register as Cursor user rules with always-apply. Do not write project rules under `D:\.cursor\`.

Install English sources only. Skip `agents/openai.yaml` when copying skills to Cursor. After a Cursor rule install, register or update the matching user rule by title if it is not already present.

Reinstall overwrites copies that still match their install stamp. If a runtime copy was edited, stop unless the user passes `-Force`.

## Authorization Boundaries

- Writing to `D:\agent-playbook` may require explicit filesystem approval; request it when required.
- Do not commit, push, merge, change branch protection, or install generated artifacts without a separate request.
- Do not bypass missing credentials, unavailable services, sandbox restrictions, or failed validation.
- Complete translation and validation before reporting success.
