---
name: notion-record-tech-concept
description: Record technical concepts and technical learning schedules from the current conversation into Notion when the user explicitly asks to save them. Keep reusable concept documentation and schedules as separate pages; never merge a learning plan, project schedule, phased checklist, or roadmap into an existing concept page.
---

# Record Technical Concepts in Notion

Turn the requested portion of the conversation into reusable technical documentation, route it through the correct top-level category page, and create or enrich an entry in that page's nested database.

Read [references/notion-target.md](references/notion-target.md) before accessing Notion.

## Enforce the trigger

- Write to Notion only when the user explicitly requests recording or saving.
- Treat ordinary requests such as "설명해줘", "정리해줘", and technical questions as non-recording requests.
- Use the latest technical topic by default. Follow an explicit scope such as "방금 두 개념을 기록해줘" when provided.
- Do not ask for confirmation when the recording request and scope are clear.

## Prepare the entry

1. Extract the concept, accurate explanation, examples, caveats, and related concepts from the conversation.
2. Prefer one page per independently reusable concept. Keep tightly coupled details together.
3. Rewrite the conversation as durable documentation; do not paste the transcript verbatim.
4. Exclude incidental personal information, credentials, secrets, and irrelevant conversation.
5. Use a concise canonical concept name as the page title.

Use this content structure, omitting empty sections:

```markdown
## 한 줄 정의

## 핵심 개념

## 동작 방식

## 예시

## 자주 헷갈리는 점

## 관련 개념

```

## Separate schedule records

- Treat learning plans, study roadmaps, project schedules, phased task lists, and completion checklists as schedule records rather than reusable concept documentation.
- Create each schedule record as a new standalone page even when an existing concept page covers the same technologies or architecture.
- Never append or merge schedule content into an existing concept page.
- When the user names a destination database, verify that database and create the schedule page there instead of applying the default technical-concept category routing.
- Give schedule pages a purpose-specific title such as `[topic] 학습 일정` or `[project] 진행 일정`.
- Structure schedule pages around `목표`, `바로 해야 할 일`, ordered phases, phase completion criteria, `추후 해야 할 일`, and explicitly deferred work.
- Apply duplicate prevention only against equivalent schedule pages, not against concept pages that merely share topic keywords.

## Route to a category

1. Fetch the root technical-concept database from the configured URL and verify its data-source ID.
2. Infer the broad category from the concept. Prefer an existing framework, platform, language, database, infrastructure, or tooling category over a vague category.
3. Search the root data source for likely category names using one literal query per search.
4. Fetch each plausible page and accept it only when its immediate `parent-data-source` equals the configured root data-source ID. Search results may include nested concept pages; never treat those as category pages.
5. If no appropriate existing category is found, select the direct-child category named `기타`.
6. Never create a new top-level category unless the user explicitly requests it.
7. For a concept spanning categories, choose the category representing its primary runtime or ownership. For example, a Tomcat JVM system property belongs under an existing Tomcat category when present, otherwise Java, otherwise 기타.

## Locate the nested database

1. Fetch the selected category page.
2. Find the inline child database in the page content.
3. When exactly one child database exists, use it.
4. When several exist, choose only if one clearly matches the category name or purpose; otherwise ask the user which database to use and do not write yet.
5. If no child database exists, stop and report the structural mismatch. Never write directly to the root database or category page as a fallback.
6. Fetch the child database before writing and use its `collection://...` data-source ID and actual title-property name.

## Prevent duplicates

1. Search within the selected child data source using the canonical title.
2. Search common Korean/English aliases separately when they may produce an existing entry.
3. Fetch plausible matches and accept only pages whose immediate `parent-data-source` equals the selected child data-source ID.
4. If no equivalent entry exists, create a new page with an explicit `data_source_id`, the real title property, and the prepared content.
5. If one equivalent entry exists, fetch it and merge the new knowledge without deleting useful existing material. Preserve the established style when practical.
6. If several plausible duplicates remain ambiguous, ask the user which entry to update instead of guessing.

## Use Notion tools safely

- Prefer Notion search and fetch for discovery. Include `filters: {}` when no narrower search filter is needed.
- Use one literal search query per search call; do not combine variants with `or` or `+`.
- Pass only Notion page, database, data-source URLs, or IDs to fetch.
- Create pages with an explicit parent and pages array.
- Fetch an existing page immediately before updating its content.
- If a Notion tool reports `Tool <name> not found`, do not retry that tool during the request. Continue with search and fetch when sufficient.
- Do not depend on data-source query APIs; they may be unavailable for this workspace.
- Do not modify database schemas, views, category pages, or unrelated entries.

## Report the result

After a successful write, tell the user:

- selected category;
- created or updated status;
- final page title;
- Notion page link.

If recording fails, state the exact structural or access problem and confirm that no fallback location was modified.
