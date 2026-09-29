---
name: write-work-log
description: Write a Korean Markdown work log from the current conversation and verifiable evidence when the user explicitly invokes $write-work-log or asks for a development or work journal. Do not use for ordinary summaries, automatic retrospectives, or file creation.
metadata:
  short-description: Summarize completed development work as a Markdown journal
---

# Write a Work Log

Turn completed development or other work into a readable Korean Markdown journal covering its background, decisions, implementation, verification, and retrospective.

## Trigger Conditions

- Run when the user explicitly invokes `$write-work-log`.
- Run when the user explicitly asks for a development journal or work log, such as "개발일지 작성해줘" or "작업 일지로 정리해줘".
- Do not run for ordinary development requests, simple summaries, or merely because work has completed.

## Writing Procedure

1. Read [assets/work-log-template.md](assets/work-log-template.md) from beginning to end.
2. Collect facts from the current conversation, user-provided information, and already verified work results.
3. Classify the information into problem, goals and constraints, alternatives, solution, implementation, verification, retrospective, and follow-up work.
4. Preserve the template structure while replacing its guidance and examples with the actual content.
5. Remove duplicate or irrelevant subsections and empty table rows. When required information for a major section is not verified, write `확인되지 않음` rather than guessing.
6. Output the completed journal directly in the chat as Markdown.

## Writing Principles

- Use Korean by default. Follow the user's requested language when they specify another language.
- Make the purpose and outcome understandable from the title, one-line summary, and key result alone.
- State only verified facts as certain. Label an unconfirmed cause as a hypothesis.
- Include commits, pull requests, issues, documents, and test results only when their values were actually verified.
- Fill the alternatives table only when alternatives were genuinely considered. Do not invent alternatives after the fact.
- Describe concrete before-and-after differences only when supporting information exists.
- Keep the flow diagram only when execution flow is meaningful, and rewrite it in the actual execution order.
- Avoid boilerplate, repetition, and unnecessary verbosity.

## Output Restrictions

- Do not create, modify, or save a journal file.
- Do not record the result in an external document, issue tracker, or note service.
- Do not wrap the entire result in a code block. Use a code block only when the user asks for raw Markdown to copy.
- Ask one concise, consolidated question only when essential information required for an accurate journal is missing.
