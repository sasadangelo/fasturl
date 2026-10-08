---
name: planner-milestone
description: Use when planning the next development milestone — shows open backlog issues ordered by priority and epic, lets the user interactively select which issues to include, then creates a GitHub milestone with the target version and due date, and assigns the selected issues. Run after /planner-backlog. Safe to re-run to add or remove issues from a milestone.
metadata:
  argument-hint: "[optional: milestone title or focus description]"
---

# Planner Milestone

Plan the next development milestone: select issues from the backlog, set the target version,
and publish the milestone on GitHub.

**Safe to re-run:** if a milestone for the next version already exists, the skill opens it for
editing (add/remove issues, change due date) instead of creating a duplicate.

---

## Phase 0 — Check Prerequisites

### Step 0.1 — Planner configuration

```
glob: docs/planner.yaml
```

**If not found:**
- Stop and tell the user:
  _"No planner configuration found. Please run `/planner-init` first."_

**If found:** read and extract:
- `repo` — GitHub repo slug
- `milestone_duration_weeks` — length of each milestone
- `versioning.current` — current released version

### Step 0.2 — gh CLI and authentication

```
execute_command: gh auth status
```

**If not authenticated:** stop and tell the user to run `gh auth login`.

### Step 0.3 — Compute next version

Apply the versioning rules from `docs/planner.yaml`:

| Current version | Next milestone version | Rule |
|---|---|---|
| `0.0.0` | `0.1.0` | First MVP |
| `0.x.0` | `0.(x+1).0` | Next pre-GA MVP |
| `0.x.y` (y > 0) | `0.(x+1).0` | Next MVP after a patch |
| `1.0.0` or higher | `<major>.(minor+1).0` | Post-GA milestone |

Show the computed next version to the user and ask for confirmation:

```
ask_followup_question: "The next milestone will target version <next-version>. Does this look correct?"
suggestion_a: "Yes — use <next-version>"
suggestion_b: "No — I want to enter a different version"
suggestion_c: "This is a GA release — use 1.0.0"
```

### Step 0.4 — Check for existing milestone

```
execute_command: gh milestone list --repo <repo> --state open --json title,number,dueOn,description
```

**If a milestone for the computed version already exists:**
- Tell the user: _"Milestone `<version>` already exists. Opening it for editing."_
- Skip Phase 2 (issue selection) — go directly to Phase 3 (review and update).

---

## Phase 1 — Load Open Backlog

Fetch all open issues with label `backlog` that are **not yet assigned to any milestone**:

```
execute_command: gh issue list --repo <repo> --state open --label "backlog" --json number,title,labels,milestone --limit 500
```

Filter out issues that already have a milestone assigned.

Group by epic label. Within each epic, sort by priority:
1. `priority: high`
2. `priority: medium`
3. `priority: low`
4. No priority label (treat as low)

---

## Phase 2 — Interactive Issue Selection

### Step 2.1 — Display the backlog

Present the full open backlog grouped by epic, with priority, type, and issue number:

```
## Open Backlog — <N> issues available

### epic: infrastructure
| # | Priority | Type | Title |
|---|----------|------|-------|
| 12 | 🔴 high | infrastructure | Set up PostgreSQL and migrate from SQLite |
| 15 | 🟡 medium | infrastructure | Configure Redis for caching |

### epic: api
| # | Priority | Type | Title |
|---|----------|------|-------|
| 3  | 🔴 high | feature | Implement POST /api/v1/links |
| 4  | 🟡 medium | feature | Implement GET /api/v1/links with pagination |

### epic: performance
| # | Priority | Type | Title |
|---|----------|------|-------|
| 18 | 🟡 medium | performance | Establish baseline benchmark (k6) |
| 19 | 🟠 low    | performance | Add p99 latency tracking to CI |
```

### Step 2.2 — Ask the user to select issues

```
ask_followup_question: "Which issues should be included in milestone <version>? You can list issue numbers (e.g. '3, 4, 12, 18') or describe what you want to focus on."
suggestion_a: "Include all high-priority issues"
suggestion_b: "I'll specify issue numbers manually"
suggestion_c: "Focus on a specific epic (I'll tell you which)"
```

If the user specifies numbers: parse them and confirm the selection.
If the user says "all high priority": filter to `priority: high` issues automatically.
If the user specifies an epic: filter to that epic's issues and confirm.

### Step 2.3 — Confirm selection

Display the selected issues as a final list and ask:

```
## Milestone <version> — Selected Issues (<n> issues)

| # | Epic | Priority | Title |
|---|------|----------|-------|
| 3  | api | high | Implement POST /api/v1/links |
| 12 | infrastructure | high | Set up PostgreSQL |
| 18 | performance | medium | Establish baseline benchmark |

Milestone duration: <n> weeks
Start date: today (<YYYY-MM-DD>)
Due date: <YYYY-MM-DD> (+<n> weeks)
Target version: <version>
```

```
ask_followup_question: "Does this milestone plan look correct?"
suggestion_a: "Yes — create milestone and assign issues on GitHub"
suggestion_b: "I want to add or remove some issues"
suggestion_c: "Change the due date"
```

Iterate until confirmed.

---

## Phase 3 — Publish to GitHub

Execute only after the user confirms.

### Step 3.1 — Create the milestone

```
execute_command: gh api repos/<repo>/milestones \
  --method POST \
  --field title="<version>" \
  --field description="MVP <version> — <focus description>" \
  --field due_on="<YYYY-MM-DDT00:00:00Z>"
```

Extract the milestone number from the response.

### Step 3.2 — Assign issues to the milestone

For each selected issue:

```
execute_command: gh issue edit <number> --repo <repo> --milestone "<version>"
```

Also remove the `backlog` label and add a `milestone: <version>` label if desired
(ask the user once whether to keep or remove the `backlog` label when a milestone is assigned).

### Step 3.3 — Update `docs/planner.yaml`

Patch the current version to the new milestone version:

```yaml
versioning:
  current: "<new-version>"
```

Use `apply_diff` — do not rewrite the whole file.

---

## Phase 4 — Report

After publishing:

- Milestone URL: `https://github.com/<repo>/milestone/<number>`
- Issues assigned: list with numbers and titles
- Due date
- Next step: _"Start working on the milestone. Run `/planner-status` at any time to track progress."_
