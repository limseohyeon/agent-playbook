---
name: agent-playbook-manager
description: Create or update reusable Codex agents, skills, rules, and prompts in the D:\agent-playbook repository using its category, Korean-translation, hash, and README-index conventions. Use for playbook artifacts only; do not route ordinary project files or general documents into this repository.
---

# Agent Playbook Manager

Manage reusable playbook artifacts in `D:\agent-playbook`. Keep this repository as the source of truth. Do not install generated artifacts into Codex unless the user separately requests installation; this manager skill is the only artifact installed globally by default.

## Scope

Apply this skill when creating or updating reusable:

- Custom agents
- Codex skills
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

Treat the English file as canonical. Always create or update the Korean counterpart in the same task.

- Markdown translations declare `translation_of` and `source_sha256` in YAML frontmatter.
- TOML translations declare the same fields in leading comments so the TOML schema remains valid.
- Translate behavior and explanations, but keep identifiers, commands, paths, code, and schema keys unchanged when translation would break them.
- After the English and Korean contents are final, refresh translation metadata with:

```powershell
python D:\agent-playbook\.github\scripts\sync_translation_hash.py <english-repository-relative-path>
```

Never update only the hash. Review and update the Korean content against the final English source first.

## Repository Workflow

1. Inspect `D:\agent-playbook`, its Git status, and any applicable repository guidance.
2. Preserve unrelated user changes. Stop if overlapping changes cannot be handled safely.
3. Classify the artifact and announce the English and Korean target paths.
4. Create or update the English entrypoint in its native runtime format.
5. Create or update the Korean counterpart in the same native format.
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

## Authorization Boundaries

- Writing to `D:\agent-playbook` may require explicit filesystem approval; request it when required.
- Do not commit, push, merge, change branch protection, or install generated artifacts without a separate request.
- Do not bypass missing credentials, unavailable services, sandbox restrictions, or failed validation.
- Complete translation and validation before reporting success.
