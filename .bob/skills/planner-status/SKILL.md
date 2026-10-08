---
name: planner-status
description: Use when checking the status of the active milestone — shows open and closed issues, completion percentage, days remaining, and lets the user add or remove issues from the current milestone. Run at any time during a milestone to track progress.
metadata:
  argument-hint: "[optional: milestone version, e.g. '0.2.0']"
---

# Planner Status

Display the progress of the active (or specified) milestone and optionally manage its issues.

---

## Phase 0 — Check Prerequisites

### Step 0.1 — Planner configuration

```
glob: docs/planner.yaml
```

**If not found:**
- Stop and tell the user:
  _"No planner configuration found. Please run `/planner-init` first."_

**If found:** read and extract `repo`, `versioning.current`.

### Step 0.2 — gh CLI and authentication

```
execute_command: gh auth status
```

**If not authenticated:** stop and tell the user to run `gh auth login`.

---

## Phase 1 — Identify Target Milestone

### Step 1.1 — List open milestones

```
execute_command: gh milestone list --repo <repo> --state open --json number,title,dueOn,closedIssues,openIssues
```

**If no open milestones exist:**
- Tell the user: _"No active milestone found. Run `/planner-milestone` to plan the next one."_
- Stop here.

**If exactly one open milestone exists:** use it automatically.

**If multiple open milestones exist:** ask the user which one to inspect:

```
ask_followup_question: "Multiple milestones are open. Which one would you like to check?"
suggestion_a: "<title of first milestone>"
suggestion_b: "<title of second milestone>"
```

**If an argument was passed** to the skill (e.g. `/planner-status 0.2.0`): find the milestone
with that title and use it. If not found, tell the user and list available milestones.

---

## Phase 2 — Load Milestone Issues

Fetch all issues assigned to the milestone:

```
execute_command: gh issue list --repo <repo> --milestone "<title>" --state all --json number,title,state,labels,assignees,closedAt --limit 500
```

Separate into:
- **Open issues** (state: open)
- **Closed issues** (state: closed)

---

## Phase 3 — Display Status

Render the full milestone status report:

```
## Milestone <version> — Status Report

**Due date:** <YYYY-MM-DD> (<n> days remaining / <n> days overdue)
**Progress:** <closed>/<total> issues closed (<pct>%)
[████████░░░░░░░░] <pct>%

---

### ✅ Closed (<n>)
| # | Epic | Title | Closed |
|---|------|-------|--------|
| 3 | api | Implement POST /api/v1/links | 2025-06-01 |

### 🔵 Open (<n>)
| # | Priority | Epic | Title |
|---|----------|------|-------|
| 12 | 🔴 high | infrastructure | Set up PostgreSQL |
| 18 | 🟡 medium | performance | Establish baseline benchmark |

---
**Backlog (not in this milestone):** <m> issues open
```

### Days remaining calculation

- If due date is in the future: show `<n> days remaining`
- If due date is today: show `⚠️ Due today`
- If due date has passed: show `🔴 <n> days overdue`

---

## Phase 4 — Actions

After displaying the report, ask:

```
ask_followup_question: "What would you like to do?"
suggestion_a: "Add an issue from the backlog to this milestone"
suggestion_b: "Remove an issue from this milestone (return to backlog)"
suggestion_c: "Close this milestone and plan the next one"
suggestion_d: "Nothing — just checking progress"
```

### Action A — Add issue to milestone

Fetch open backlog issues not yet in any milestone:

```
execute_command: gh issue list --repo <repo> --state open --label "backlog" --json number,title,labels --limit 200
```

Display them grouped by epic and ask which to add. Then:

```
execute_command: gh issue edit <number> --repo <repo> --milestone "<title>"
```

### Action B — Remove issue from milestone

Ask the user for the issue number to remove. Then:

```
execute_command: gh issue edit <number> --repo <repo> --milestone ""
execute_command: gh issue edit <number> --repo <repo> --add-label "backlog"
```

### Action C — Close milestone

First verify: warn if there are still open issues.

```
ask_followup_question: "There are <n> open issues in this milestone. How would you like to handle them?"
suggestion_a: "Return all open issues to the backlog"
suggestion_b: "Keep them assigned to this milestone and close it anyway"
```

If returning to backlog, for each open issue:
```
execute_command: gh issue edit <number> --repo <repo> --milestone "" --add-label "backlog"
```

Then close the milestone:

```
execute_command: gh api repos/<repo>/milestones/<number> --method PATCH --field state=closed
```

Tell the user: _"Milestone `<version>` closed. Run `/planner-milestone` to plan the next one."_

### Action D — Exit

No further action. Display the GitHub milestone URL:
`https://github.com/<repo>/milestone/<number>`
