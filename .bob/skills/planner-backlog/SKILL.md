---
name: planner-backlog
description: Use when generating or updating the GitHub issue backlog from project documents — reads docs/requirements.md, docs/api-design.md, docs/cli-design.md, docs/db-design.md, docs/architecture.md and any other available design docs, proposes a set of issues with labels and epics, asks for confirmation, then creates or updates them on GitHub. Idempotent — safe to re-run when new documents are added. Run after /planner-init.
metadata:
  argument-hint: "[optional: focus area, e.g. 'performance' or 'api']"
---

# Planner Backlog

Generate or update the GitHub product backlog from all available project documents.

**Idempotent:** uses a stable `<!-- planner-id: <id> -->` marker in each issue body to detect
existing issues. Re-running the skill adds new issues and offers to update changed ones —
it never creates duplicates.

---

## Phase 0 — Check Prerequisites

### Step 0.1 — Planner configuration

```
glob: docs/planner.yaml
```

**If not found:**
- Stop and tell the user:
  _"No planner configuration found. Please run `/planner-init` first to set up the project
  planner, then come back and run `/planner-backlog`."_

**If found:** read and extract `repo`, `milestone_duration_weeks`, `versioning.current`.

### Step 0.2 — gh CLI and authentication

```
execute_command: gh auth status
```

**If not authenticated:** stop and tell the user to run `gh auth login`.

### Step 0.3 — Existing issues (idempotency check)

Fetch all existing issues (open and closed) with their body:

```
execute_command: gh issue list --repo <repo> --state all --limit 500 --json number,title,body,labels,milestone
```

Extract all `<!-- planner-id: <id> -->` markers from issue bodies.
Build a map: `planner-id → { number, title, labels, milestone }`.
This map is used throughout Phase 2 to skip already-created issues and detect changes.

---

## Phase 1 — Read Project Documents

Read every document that exists. Do not fail if any is absent.

```
glob: docs/requirements.md
glob: docs/domain-design.md
glob: docs/architecture.md
glob: docs/tech-stack.md
glob: docs/api-design.md
glob: docs/cli-design.md
glob: docs/db-design.md
glob: docs/test-strategy.md
```

For each found document, extract actionable items:

| Document | Extract |
|---|---|
| `requirements.md` | User stories, functional requirements, non-functional requirements |
| `domain-design.md` | Entities to implement, aggregates, bounded contexts |
| `architecture.md` | Infrastructure decisions, patterns to adopt, non-functional constraints |
| `tech-stack.md` | Dependency setup tasks, tooling to configure |
| `api-design.md` | Endpoints to implement (group by resource) |
| `cli-design.md` | Commands to implement (group by resource) |
| `db-design.md` | Schema to implement, migrations, indexes |
| `test-strategy.md` | Test suites to write (unit, integration, e2e, performance) |

---

## Phase 2 — Generate Issue Proposals

Transform extracted items into a structured issue list. Apply these rules:

### Issue structure

Each proposed issue has:
- **`planner-id`**: stable slug derived from the issue content, e.g. `api-links-crud`, `db-schema-init`, `perf-baseline-benchmark`. Used for idempotency. Format: `<epic>-<short-description>` in kebab-case.
- **Title**: concise action-oriented sentence (`Implement POST /api/v1/links endpoint`)
- **Body**: markdown with sections:
  - `## Goal` — one paragraph describing what this issue delivers
  - `## Acceptance Criteria` — checklist of verifiable conditions
  - `## Notes` — technical context, links to design docs, constraints (optional)
  - `<!-- planner-id: <id> -->` — hidden marker at the bottom (required)
- **Labels**: one `type:` label + one `priority:` label + `backlog`
- **Epic**: the parent grouping label (e.g. `epic: api`, `epic: performance`, `epic: infrastructure`)

### Epic grouping rules

Derive epics from the document sources:

| Source | Epic label |
|---|---|
| `api-design.md` endpoints | `epic: api` |
| `cli-design.md` commands | `epic: cli` |
| `db-design.md` / `domain-design.md` | `epic: data` |
| `architecture.md` infrastructure | `epic: infrastructure` |
| `test-strategy.md` performance tests | `epic: performance` |
| `requirements.md` non-functional | `epic: infrastructure` or `epic: performance` |
| Documentation tasks | `epic: docs` |

### Priority assignment rules

| Condition | Priority |
|---|---|
| Blocking other issues (foundational: DB schema, scaffold, auth) | `priority: high` |
| Core functional requirement from `requirements.md` | `priority: high` |
| Derived from `api-design.md` or `cli-design.md` | `priority: medium` |
| Performance improvement, observability, tooling | `priority: medium` |
| Nice-to-have, docs, refactors | `priority: low` |

### Idempotency check per issue

Before adding an issue to the proposal list:
1. Look up its `planner-id` in the existing issues map (from Phase 0.3).
2. **If not found:** mark as `[NEW]` → will be created.
3. **If found with identical title and labels:** mark as `[UNCHANGED]` → skip silently.
4. **If found but title or labels differ:** mark as `[CHANGED]` → will be offered for update.

---

## Phase 3 — Preview and Confirm

Present the full proposal to the user **before touching GitHub**. Group by epic:

```
## Proposed Backlog Changes

### epic: api (5 issues)
| # | Status | planner-id | Title | Type | Priority |
|---|--------|------------|-------|------|----------|
| — | NEW    | api-links-create | Implement POST /api/v1/links | feature | high |
| — | NEW    | api-links-list   | Implement GET /api/v1/links  | feature | medium |
| 7 | UNCHANGED | api-links-delete | ... | — | — |
| 3 | CHANGED | api-links-get  | (title changed) | feature | high |

### epic: data (2 issues)
...

### epic: performance (3 issues)
...

**Summary:** 8 new · 1 updated · 4 unchanged · 0 removed
```

Then ask:

```
ask_followup_question: "Does this backlog look correct?"
suggestion_a: "Yes — create/update all issues on GitHub"
suggestion_b: "I want to remove or change some issues before publishing"
suggestion_c: "Cancel — do not publish anything"
```

If the user selects `suggestion_b`: ask them to describe which issues to remove or change,
apply the changes to the proposal, then re-display the preview and ask again.

---

## Phase 4 — Publish to GitHub

Execute only after the user confirms.

### Step 4.1 — Create missing epic labels

For each epic referenced in the proposal, check if the label exists:

```
execute_command: gh label list --repo <repo> --json name --jq '.[].name'
```

Create missing epic labels:

```
execute_command: gh label create "epic: <name>" --color "#7057ff" --description "<Epic>" --force --repo <repo>
```

### Step 4.2 — Create new issues

For each `[NEW]` issue:

```
execute_command: gh issue create \
  --repo <repo> \
  --title "<title>" \
  --body "<body with planner-id marker>" \
  --label "backlog,<type>,<priority>,<epic>"
```

### Step 4.3 — Update changed issues

For each `[CHANGED]` issue, show the diff to the user and ask:

```
ask_followup_question: "Issue #<n> '<title>' has changed. What would you like to do?"
suggestion_a: "Update title and labels on GitHub"
suggestion_b: "Skip this issue"
```

If updating:

```
execute_command: gh issue edit <number> --repo <repo> --title "<new title>" --add-label "<label>" --remove-label "<old label>"
```

---

## Phase 5 — Report

After all issues are published:

- Total issues created
- Total issues updated
- Total issues skipped (unchanged)
- List of GitHub URLs for new/updated issues
- Next step: _"Run `/planner-milestone` to plan the next milestone and assign issues from this backlog."_
