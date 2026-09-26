---
name: cli-design
description: Use when the user wants to design a CLI interface — derives commands, subcommands, options, and usage examples from docs/domain-design.md and produces docs/cli-design.md. Run before /python-cli. Requires /domain-design to have been run first.
metadata:
  disable-model-invocation: false
  argument-hint: "[CLI name]"
---

# CLI Design

Translate the domain model into a concrete, language-agnostic CLI specification.

Produces one living artefact:
- **`docs/cli-design.md`** — resources, command table, usage examples, configuration convention

**Always patch with `apply_diff`** when the file already exists. Never fully rewrite it.

---

## Step 0 — Check Prerequisites

### 0.1 — Domain design

```
glob: docs/domain-design/README.md
glob: docs/domain-design.md
```

Read whichever exists (folder README takes priority).

**If not found:**
- Stop immediately and tell the user:
  _"No domain design found. Please run `/domain-design` first — it produces `docs/domain-design.md`
  which this skill uses as input. Once that document exists, come back and run `/cli-design` again."_
- Do not proceed further.

**If found:**
- Extract: domain name, entities, value objects, aggregates, bounded contexts, domain events,
  last updated date
- Tell the user: _"I found a domain design for `<domain>`. I'll derive the CLI resources from its
  entities and aggregates."_

### 0.2 — Existing CLI design

```
glob: docs/cli-design.md
```

**If `docs/cli-design.md` exists:**
- Read it with `read_file`
- Extract: CLI name, resources already designed, command table, open questions, last updated date,
  change log
- **Propagation check:** if `docs/domain-design` was updated more recently than this document, warn:
  _"⚠️ `docs/domain-design` was updated after this CLI design. New entities or operations may not
  be reflected. Review domain design changes before proceeding."_
- Tell the user: _"I found an existing CLI design for `<name>`. It covers these resources: `<list>`.
  Last updated: `<date>`."_
- Ask:

  ```
  ask_followup_question: "What would you like to do?"
  suggestion_a: "Add new commands or resources"
  suggestion_b: "Refine existing commands, options, or usage examples"
  suggestion_c: "Start a brand-new CLI design (discard the current one)"
  ```

  Jump to the appropriate phase. Do NOT repeat phases already confirmed.

**If not found:**

### 0.3 — CLI code discovery (existing project)

Before running the full design from scratch, scan for existing CLI implementation:

```
glob: src/**/cli.py
glob: src/**/commands/*.py
glob: src/**/main.py
```

Run targeted searches:

```
grep: "@app.command|@.*\.command|typer\.Typer\(\)|click\.group\(\)|click\.command\(\)" in src/
grep: "add_typer|app\.add_typer" in src/
```

**If CLI command definitions are found:**
- Read the matching files
- Extract: CLI binary name (from `pyproject.toml` `[project.scripts]`), command groups,
  subcommands, options and their types
- Tell the user: _"I found an existing CLI implementation: `<list of files>`.
  I'll reverse-engineer the command structure from the code."_
- Propose a draft command table from the discovered commands
- Ask:

  ```
  ask_followup_question: "Does this reverse-engineered command table look correct? Should I use it as the starting point?"
  suggestion_a: "Yes — document it as-is, I'll refine"
  suggestion_b: "Mostly correct — I need to add or change some commands"
  suggestion_c: "No — start the CLI design from the domain model only"
  ```

  If confirmed: skip Phase 1 (CLI Context) if binary name is known, skip Phase 2 (Resource
  Mapping) for already-implemented resources, jump to Phase 3 (Command Table) to complete
  or validate missing commands, then proceed to Phase 4 (Write artefact).

**If no CLI code found:** proceed to Phase 1 in full.

---

## Phase 1 — CLI Context

Ask one question at a time.

### Q1 — CLI name

```
ask_followup_question: "What is the name of the CLI binary? (e.g. 'golem', 'mytool', 'deploy')"
suggestion_a: "I'll type it manually"
```

### Q2 — Configuration file

```
ask_followup_question: "Does the CLI need persistent configuration (e.g. stored connection profiles, active context, API tokens)?"
suggestion_a: "Yes — store config in $HOME/.<cli-name>/cli/config.yaml"
suggestion_b: "Yes — I want a different path or XDG layout"
suggestion_c: "No persistent configuration needed"
```

If yes, confirm the env var and default path:
- Env var: `<CLI_NAME>_PATH` (uppercased, hyphens → underscores)
- Default: `$HOME/.<cli-name>`
- Config file: `$<CLI_NAME>_PATH/cli/config.yaml`

After both answers, proceed to Phase 2.

---

## Phase 2 — Resource Mapping

**Goal:** identify which domain entities become top-level CLI resources (commands).

### Step 2.1 — Propose resource list

From the domain model, propose a mapping:

| Domain Entity / Aggregate | CLI Resource | Notes |
|--------------------------|--------------|-------|

Rules:
- **Entities with their own lifecycle** → top-level resource (e.g. `Customer` → `customer`)
- **Value Objects** → never a resource; they become options on their owning resource's commands
- **Aggregates** → the aggregate root becomes the top-level resource; its members may become
  nested sub-resources if the relationship is strong
- **Domain Events** → consider a `events` or `log` read-only resource if the CLI needs to
  inspect history

Ask for confirmation:

```
ask_followup_question: "Does this resource mapping look right? Any resources to add, remove, or rename?"
suggestion_a: "Yes, proceed to relationships"
suggestion_b: "I need to adjust something"
```

### Step 2.2 — Relationships and nesting depth

For each pair of related resources, confirm navigation depth:

**Rule:**
- **Strong relationship** (child only exists in the context of a parent) → nested subcommand:
  `cli parent child <verb>`
- **Weak relationship** (child can exist independently; parent is a filter) → top-level resource
  with parent ID as an option: `cli child list --parent-id 1`
- **Maximum depth: 2 levels.** Deeper hierarchies become options, not more nesting.

For each candidate pair ask:

```
ask_followup_question: "Is '<Child>' only meaningful inside a '<Parent>' (strong), or can it exist independently (weak)?"
suggestion_a: "Strong — nest it: cli parent child <verb>"
suggestion_b: "Weak — keep it top-level with a --parent-id option"
```

Produce a confirmed **resource table**:

| Resource | Parent | Relationship | Notes |
|----------|--------|--------------|-------|
| `project` | — | root | Independent |
| `task` | `project` | strong (1:N) | Only exists inside a project |
| `stats` | — | logical group | Aggregates task data |

---

## Phase 3 — Command Table

**Goal:** define every command, subcommand, option, and argument.

### Verb mapping

| HTTP analogy | CLI subcommand | Meaning |
|---|---|---|
| `GET /resources` | `list` | List all instances |
| `GET /resources/{id}` | `show` | Show one instance |
| `POST /resources` | `add` / `create` | Create a new instance |
| `PUT /resources/{id}` | `update` | Update an existing instance |
| `DELETE /resources/{id}` | `delete` / `remove` | Delete an instance |

Add domain-specific verbs where needed: `run`, `export`, `import`, `sync`, `publish`, `connect`.

### Naming conventions

- Commands = resource names (singular noun): `project`, `task`, `user`
- Subcommands = action verbs: `list`, `add`, `show`, `update`, `delete`
- Options use `--kebab-case`; short aliases use a single letter `-x`
- Path parameters (`{id}`) become required options: `--id/-i`
- Body fields become required or optional options: `--name/-n`, `--output/-o`
- Positional arguments only for truly unambiguous single values; prefer named options otherwise

### Step 3.1 — Draft the command table

For each resource and operation produce:

| Command | Subcommand | Options / Args | Description |
|---------|------------|----------------|-------------|
| `project` | `list` | — | List all projects |
| `project` | `add` | `--name/-n` (str, required) | Create a project |
| `project` | `show` | `--id/-i` (int, required) | Show project details |
| `project` | `delete` | `--id/-i` (int, required) | Delete a project |
| `project task` | `list` | `--project-id/-p` (int, required) | List tasks in a project |
| `project task` | `add` | `--project-id/-p` (int, req), `--name/-n` (str, req) | Add a task |
| `project task` | `delete` | `--project-id/-p` (int, req), `--id/-i` (int, req) | Delete a task |

### Step 3.2 — Usage examples

Write the full CLI invocation for every command:

```
<cli> project list
<cli> project add --name "Website redesign"
<cli> project show --id 1
<cli> project delete --id 1
<cli> project task list --project-id 1
<cli> project task add --project-id 1 --name "Buy milk"
<cli> project task delete --project-id 1 --id 3
```

### Step 3.3 — Confirm

```
ask_followup_question: "Does the command table and usage examples look right?"
suggestion_a: "Yes — write the design document"
suggestion_b: "I need to adjust something"
```

---

## Phase 4 — Write / Update the Design Document

Write artefacts **only after the user confirms the command table**.

### `docs/cli-design.md`

**If the file does not exist:** create with `write_file`.
**If the file exists:** use `apply_diff` to patch only changed sections. Always append a row to
the Change Log.

Document structure:

```markdown
# CLI Design — <CLI Name>
_Last updated: <date>_

## Overview
<one paragraph: what the CLI does, who uses it>

## Configuration
- **Binary name:** `<cli-name>`
- **Config env var:** `<CLI_NAME>_PATH`
- **Config default path:** `$HOME/.<cli-name>`
- **Config file:** `$<CLI_NAME>_PATH/cli/config.yaml`

_(omit this section if no persistent configuration is needed)_

## Resources
| Resource | Parent | Relationship | Description |
|----------|--------|--------------|-------------|

## Command Table
| Command | Subcommand | Options / Args | Description |
|---------|------------|----------------|-------------|

## Usage Examples
\`\`\`
<full invocation examples>
\`\`\`

## Design Decisions
1. <decision and rationale>

## Open Questions
- <question to resolve in a future session>

## Change Log
| Version | Date | Change |
|---------|------|--------|
| 0.1 | <date> | Initial design |
```

### After writing, report:

- File written/updated and what changed
- Number of top-level resources, total commands
- Any nesting decisions made
- Prompt for next step:

  ```
  ask_followup_question: "What would you like to do next?"
  suggestion_a: "Implement the CLI in Python — run /python-cli (reads this document)"
  suggestion_b: "Add more commands or resources"
  suggestion_c: "The CLI design is complete for now"
  ```

---

## Conventions Reference

### Naming
| Object | Convention | Example |
|--------|------------|---------|
| CLI binary | `kebab-case` | `my-tool` |
| Resource (command) | singular noun, lowercase | `project`, `task` |
| Subcommand | action verb, lowercase | `list`, `add`, `delete` |
| Option | `--kebab-case` | `--project-id` |
| Short alias | single letter | `-p`, `-n`, `-o` |

### Nesting decision guide
| Question | Answer → Decision |
|----------|-------------------|
| Does `<Child>` have any meaning without a `<Parent>`? | No → strong → nest it |
| Can you list/show `<Child>` without specifying a `<Parent>`? | Yes → weak → top-level |
| Is the nesting already 2 levels deep? | Yes → use options, never add a third level |
