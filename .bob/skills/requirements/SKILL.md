---
name: requirements
description: Use when the user wants to define the requirements of a system — reads docs/idea.md if present, then optionally interviews actors, goals, job stories, acceptance criteria, and constraints, and produces docs/requirements.md. This is the recommended first skill to run; its output feeds /domain-design which in turn feeds all other skills.
metadata:
  disable-model-invocation: false
  argument-hint: "[idea.md or system name]"
---

# Requirements

Capture what the system must do and for whom, before any technical modelling begins.

Produces one living artefact (file or folder — see Document Structure Rules below):
- **`docs/requirements/README.md`** + section files, or **`docs/requirements.md`** for small projects

**Always patch with `apply_diff`** when the file already exists. Never fully rewrite it.

---

## Document Structure Rules

These rules apply to this skill and all downstream skills:

**Lookup order (always check in this order):**
1. `docs/<name>/README.md` — folder structure (used when document is large or explicitly split)
2. `docs/<name>.md` — single file (default for new and small documents)

**When writing for the first time:** always create a single file `docs/<name>.md`.

**Migration to folder structure:** after writing, if the resulting file exceeds ~150 lines,
or if the user explicitly requests splitting, offer:

```
ask_followup_question: "This document is getting large. Would you like to split it into a docs/requirements/ folder for easier navigation?"
suggestion_a: "Yes — split into docs/requirements/README.md + section files"
suggestion_b: "No — keep it as a single file"
```

If the user confirms the split:
- Create `docs/requirements/README.md` — overview, index with links to section files, change log
- Create one file per major section: `actors.md`, `job-stories.md`, `constraints.md`
- Delete the original `docs/requirements.md` using `execute_command: rm docs/requirements.md`

**When updating an existing folder structure:** patch only the relevant section file with
`apply_diff`, then update the `_Last updated:` date in `README.md`.

---

## Step 0 — Check for `idea.md`

Before checking for existing requirements, look for an idea file.

**Lookup order:**
1. The path passed as argument (e.g. `/requirements docs/idea.md`)
2. `docs/idea.md` (default location)

If found, read it with `read_file` and extract as much as possible:
- **System name** — from the document title or first heading
- **Overview / purpose** — from any overview, vision, or summary section
- **Actors** — explicit actor lists, or infer from roles mentioned in the text
- **Goals per actor** — from functional requirements, feature lists, or use-case descriptions
- **Business constraints** — from constraints, rules, or out-of-scope sections
- **Non-functional requirements** — performance, availability, security, compliance hints
- **Out of scope** — explicit exclusions

Use these extracted values to **pre-fill** Phases 1–3. Skip or shorten any interview question
for which a clear answer was already found in `idea.md`.

After reading `idea.md`, tell the user:
> _"I found `<file>` and extracted the following context: system `<name>`, `<N>` actors,
> `<M>` goals. I'll use this to pre-fill the requirements — I'll only ask about anything
> that is missing or ambiguous."_

If `idea.md` is **not found**, proceed normally — all interview questions remain active.

**Re-run behaviour:** if `docs/requirements.md` already exists and `idea.md` has changed
since the last run (the user says so, or the content clearly differs from the existing
requirements), regenerate or patch the affected sections automatically using `apply_diff`,
then report what changed.

---

## Step 1 — Check for Existing Work

```
glob: docs/requirements/README.md
glob: docs/requirements.md
```

**If `docs/requirements/README.md` exists (folder structure):**
- Read `README.md` and all linked section files with `read_file`
- Extract: system name, actors, job stories already captured, open questions, change log
- Tell the user: _"I found existing requirements for `<system>` (folder structure). They cover
  `<N>` actors and `<M>` job stories. Last updated: `<date>`."_
- Ask what to do and jump to the appropriate phase.

**If `docs/requirements.md` exists (single file):**
- Read the file with `read_file`
- Extract: system name, actors, job stories already captured, open questions, change log
- Tell the user: _"I found existing requirements for `<system>`. They cover `<N>` actors and
  `<M>` job stories. Last updated: `<date>`."_
- Ask:

  ```
  ask_followup_question: "What would you like to do?"
  suggestion_a: "Add new job stories or actors"
  suggestion_b: "Refine existing stories or acceptance criteria"
  suggestion_c: "Add or update constraints"
  suggestion_d: "Start a brand-new requirements document"
  ```

  Jump to the appropriate phase. Do NOT repeat phases already confirmed.

**If neither exists:** proceed to Phase 1.

---

## Phase 1 — Interview

Ask **one question at a time**. Do not proceed to the next until the user has answered.
If the answer was already extracted from `idea.md`, state the extracted value and ask only
for confirmation or correction — do not ask the user to re-type it.

### Q1 — System name

```
ask_followup_question: "What is the name of the system you are defining requirements for?"
suggestion_a: "I'll type it manually"
```

### Q2 — System purpose

```
ask_followup_question: "In two or three sentences: what problem does this system solve, and who benefits from it?"
suggestion_a: "I'll type it manually"
```

### Q3 — Actors

```
ask_followup_question: "Who are the people or systems that will interact with this system? List all actors. (e.g. 'End user, Admin, External payment service, Mobile app')"
suggestion_a: "I'll type it manually"
```

### Q4 — Core goals

```
ask_followup_question: "For each actor, what are the most important things they need to accomplish? List the top 3–5 goals per actor."
suggestion_a: "I'll type them"
```

### Q5 — Business constraints

```
ask_followup_question: "Are there any business rules or constraints that the system must respect? (e.g. 'a user cannot place more than 5 orders per day', 'invoices must be kept for 7 years')"
suggestion_a: "Yes — I'll describe them"
suggestion_b: "None that come to mind right now"
```

### Q6 — Non-functional requirements

```
ask_followup_question: "Are there any non-functional requirements? (e.g. response time, availability, data privacy, compliance, supported languages)"
suggestion_a: "Yes — I'll describe them"
suggestion_b: "None at this stage"
```

### Q7 — Out of scope

```
ask_followup_question: "Is there anything that might seem like part of this system but is explicitly NOT in scope?"
suggestion_a: "Yes — I'll describe what is out of scope"
suggestion_b: "Nothing explicitly excluded"
```

After Q7, summarise all answers back to the user in a brief list and ask:

```
ask_followup_question: "Does this summary look correct before I start writing job stories?"
suggestion_a: "Yes, proceed to job stories"
suggestion_b: "Let me correct something first"
```

---

## Phase 2 — Job Stories

**Goal:** express every user goal as a concrete, testable job story.

### Job Story format

> **When** `<situation or trigger>`, **I want to** `<action>`, **so that** `<benefit>`.

This format captures:
- **When** — the context that triggers the need (more precise than "As a user")
- **I want to** — the action the actor takes (the requirement)
- **So that** — the business value or outcome (why it matters)

### Step 2.1 — Write job stories

For each actor × goal pair from Phase 1, write one or more job stories.
Work through one actor at a time. For each goal ask:

```
ask_followup_question: "For the goal '<goal>' of actor '<actor>', describe the situation that triggers it and the outcome they expect. I'll write the job story."
suggestion_a: "I'll describe it"
```

Draft the job story and present it to the user for confirmation before moving to the next.

Group stories by actor. Number them sequentially: `JS-001`, `JS-002`, …

### Step 2.2 — Identify edge cases

For each job story, ask:

```
ask_followup_question: "Are there any important edge cases or failure scenarios for '<story>'? (e.g. what happens if the data is invalid, the service is unavailable, or the user has no permission?)"
suggestion_a: "Yes — I'll describe them"
suggestion_b: "No edge cases for this story"
```

Add edge cases as additional job stories or as notes on the parent story.

### Step 2.3 — Confirm job stories

Present the full list grouped by actor and ask:

```
ask_followup_question: "Does this job story list capture everything the system must do? Any missing stories?"
suggestion_a: "Yes, the list is complete — proceed to acceptance criteria"
suggestion_b: "I need to add or change something"
```

---

## Phase 3 — Acceptance Criteria

**Goal:** for each job story, define the conditions that must be true for it to be considered
done. Acceptance criteria are the bridge between requirements and testing.

### Format

Use **Given / When / Then** (GWT):

> **Given** `<precondition>`,
> **When** `<action>`,
> **Then** `<expected outcome>`.

### Step 3.1 — Write criteria

For each job story, propose 2–4 acceptance criteria. Ask if unclear:

```
ask_followup_question: "For story '<JS-NNN>', what must be true for it to be considered done? Think about the happy path and the most important error cases."
suggestion_a: "I'll describe the criteria"
```

### Step 3.2 — Confirm

Present all acceptance criteria grouped by story and ask:

```
ask_followup_question: "Do these acceptance criteria correctly define when each story is done?"
suggestion_a: "Yes — write the requirements document"
suggestion_b: "I need to adjust some criteria"
```

---

## Phase 4 — Write / Update `docs/requirements.md`

**If the file does not exist:** create with `write_file`.
**If the file exists:** use `apply_diff` to patch only changed sections.
Always append a row to the Change Log. Never rewrite unchanged sections.

Document structure:

```markdown
# Requirements — <System Name>
_Last updated: <date>_

## Overview
<two or three sentences: what the system does and who it serves>

## Actors
| Actor | Description | Type |
|-------|-------------|------|
| `<name>` | <what this actor does in the system> | Human / System |

## Job Stories

### Actor: <ActorName>

#### JS-001 — <short title>
**When** <situation>, **I want to** <action>, **so that** <benefit>.

**Acceptance criteria:**
- **Given** <precondition>, **When** <action>, **Then** <outcome>.
- **Given** <precondition>, **When** <action>, **Then** <outcome>.

**Edge cases / notes:**
- <edge case or constraint>

_(repeat for each story)_

## Business Constraints
1. <constraint>

## Non-Functional Requirements
| Category | Requirement |
|----------|-------------|
| Performance | <e.g. API responses < 200ms at p95> |
| Availability | <e.g. 99.9% uptime> |
| Security | <e.g. all PII must be encrypted at rest> |
| Compliance | <e.g. GDPR, SOC2> |

## Out of Scope
- <item explicitly excluded>

## Open Questions
- <question to resolve in a future session>

## Change Log
| Version | Date | Change |
|---------|------|--------|
| 0.1 | <date> | Initial requirements |
```

---

## Phase 5 — Report

After writing the document, report:
- Number of actors, job stories, acceptance criteria captured
- Any open questions noted
- Any constraints or NFRs recorded

Then prompt for next steps:

```
ask_followup_question: "What would you like to do next?"
suggestion_a: "Model the domain — run /domain-design (reads this document)"
suggestion_b: "Add more job stories or refine acceptance criteria"
suggestion_c: "The requirements are complete for now"
```

---

## Conventions Reference

### Job Story vs User Story

| Format | Structure | Best for |
|--------|-----------|---------|
| **Job Story** | When / I want to / So that | Capturing context and motivation — preferred |
| **User Story** | As a / I want / So that | Acceptable; weaker on context |

Always prefer Job Story format. Convert user stories to job stories if the user provides them.

### Story ID scheme
- Format: `JS-NNN` (three digits, zero-padded)
- Sequential within the document, never reused
- When updating an existing document, continue from the last number used

### Acceptance criteria rules
- Each criterion must be independently verifiable
- At least one criterion for the happy path
- At least one criterion for the most important failure/edge case
- No implementation details — criteria describe **what**, not **how**
