---
name: deep-interview
description: |
  Interview ambiguous requests using Socratic questions and turn them into actionable requirements.
  Use when the user requests deep-interview, an in-depth interview, requirements clarification, or help organizing their thoughts, or when the goal, scope, constraints, or completion criteria are unclear.
  Do not use when the request is already specific or when clarification would add little value, such as fixing a typo, changing a small setting, or adding tests.
argument-hint: "<rough request>"
---

# Deep Interview

Do not immediately execute an ambiguous request. First, clarify it into concrete, actionable requirements.

The goal is not to ask many questions. Identify the single most important uncertainty and resolve one uncertainty at a time.

Use Socratic questioning. Instead of deciding on the user's behalf, ask questions that reveal their implicit assumptions, available choices, and decision criteria.

## Question Areas

Choose the most unclear area, using this order as guidance:

- Goal
- Scope and exclusions
- Constraints
- Completion criteria
- Existing context and affected areas

If a question can be answered by inspecting the codebase, investigate it directly instead of asking the user.

## Interview Process

Ask only one question at a time. Select the most important uncertainty and ask a question that reveals the user's decision criteria.

Use this format:

```md
Current understanding: {Briefly summarize the request and decisions made so far}
Decision needed: {The most important uncertainty that must be resolved now}
Question: {One question}
Options: {Only when helpful; provide 2–3 options in total, with `- (Free-form response)` as the final option}
```

Incorporate each answer into the `Current understanding` section of the next question. Adjust the summary length to the depth of the conversation without adding unnecessary detail. Ask another question only when an important uncertainty remains.

Provide options when the user may struggle to answer from a blank slate, or when contrasting examples would help reveal implicit decision criteria, goals, or problem framing. Do not provide options when they would constrain the user's thinking or turn the discussion into a multiple-choice exercise. If more than three options seem necessary, split the issue into a smaller decision instead. Whenever options are provided, the final option must be `- (Free-form response)`.

Only when a low-risk assumption would allow progress without the user's answer, one option may include `(Recommended: brief reason)`. A recommendation is a temporary working assumption, not a final decision. If included, the recommended option must always be option A. Do not recommend an option for decisions involving strategy, budget, security, external publication, operational impact, or actions that are difficult to reverse.

Add a one-sentence `Why this matters` explanation only when necessary. Do not add explanations merely to fill the format or provide excessive detail.

## Completion Criteria

Stop the interview once the following are clear:

- The intended goal
- Included and excluded scope
- Constraints that must be respected
- Criteria for determining completion
- Any remaining open questions

At the end, summarize only the decisions and remaining open questions, not the entire conversation.