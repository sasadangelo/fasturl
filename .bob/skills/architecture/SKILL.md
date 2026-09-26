---
name: architecture
description: Use when the user wants to define the software architecture of a Python project — interviews the user about non-functional requirements, recommends the best pattern, writes docs/architecture.md, then scaffolds the folder structure. Requires /domain-design to have been run first.
metadata:
  disable-model-invocation: false
  argument-hint: "[pattern]"
---

# Architecture

Define the software architecture from requirements and domain, document the decision, then
scaffold the folder structure.

Produces one living artefact (file or folder):
- **`docs/architecture/README.md`** + section files, or **`docs/architecture.md`** for small projects

**Always patch with `apply_diff`** when the file already exists. Never fully rewrite it.
The folder scaffolding follows from the document — never the other way around.

**Document lookup order:** always check `docs/architecture/README.md` first, then
`docs/architecture.md`. **Migration offer:** after writing, if the file exceeds ~150 lines,
offer to split into `docs/architecture/` folder (README.md + decisions.md + layer-map.md).

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
  which this skill needs to recommend the right architecture. Once that document exists, come back
  and run `/architecture` again."_
- Do not proceed further.

**If found:**
- Extract: domain name, bounded contexts (count and names), aggregates, domain events (presence),
  external system integrations, last updated date
- Keep these facts — they feed the recommendation in Phase 2.

### 0.2 — Existing architecture document

```
glob: docs/architecture/README.md
glob: docs/architecture.md
```

Read whichever exists (folder README takes priority).

**If found:**
- Extract: pattern chosen, organisation style, layers defined, last updated date, change log
- **Propagation check:** if `docs/domain-design` was updated more recently than this document, warn:
  _"⚠️ `docs/domain-design` was updated after this architecture document. Some changes may not be
  reflected. Review domain design changes before proceeding."_
- Tell the user: _"I found an existing architecture document for `<domain>` using `<pattern>` /
  `<organisation>`. Last updated: `<date>`."_
- Ask:

  ```
  ask_followup_question: "What would you like to do?"
  suggestion_a: "Re-evaluate the architecture based on new requirements"
  suggestion_b: "Extend the folder structure with new layers or components"
  suggestion_c: "Update the document only — no scaffolding changes"
  suggestion_d: "Start a brand-new architecture design"
  ```

  Jump to the appropriate phase. Do NOT repeat phases already confirmed.

**If not found:**

### 0.3 — Source code discovery (existing project)

Before running the full interview, scan the workspace for an existing folder structure that
reveals the architecture pattern already in use:

```
glob: src/**/__init__.py
list_files: src/
```

**If `src/<package>/` exists, inspect its top-level folders:**

| Folders found | Inferred pattern |
|---------------|-----------------|
| `domain/`, `application/`, `infrastructure/`, `interfaces/` | `hexagonal` or `hexagonal ddd` |
| `domain/entities/`, `domain/events/`, `domain/repositories/` | `ddd` |
| `consumers/`, `producers/`, `processors/` | `event-driven` |
| `steps/`, `pipelines/`, `io/` | `pipeline` |
| `api/`, `services/`, `repositories/`, `models/` | `layered` (by layer) |
| `<context_a>/router.py`, `<context_b>/service.py` | `layered` (by component) |

Also check `pyproject.toml` for framework dependencies that confirm the pattern.

**If a recognisable pattern is found:**
- Tell the user: _"I detected an existing `<pattern>` architecture under `src/<package>/`.
  I'll document it rather than redesigning from scratch."_
- Ask:

  ```
  ask_followup_question: "I detected an existing architecture. What would you like to do?"
  suggestion_a: "Document it as-is — create docs/architecture.md from what exists"
  suggestion_b: "Document it, then extend or refine it"
  suggestion_c: "Ignore the existing code — design from scratch"
  ```

  If "document as-is" or "extend": skip Phase 1 interview, jump to Phase 3 (write document)
  using the inferred pattern. Still ask team size, scale, and deployment questions as
  confirmation/supplement (present as "Does this match your setup?" rather than open questions).

**If no recognisable pattern:** proceed to Phase 1 in full.

---

## Phase 1 — Requirements Interview

Ask **one question at a time**. Do not proceed to the next until the user has answered.
Every answer feeds the recommendation in Phase 2.

### Q1 — Team size and structure

```
ask_followup_question: "How large is the development team, and how is it organised?"
suggestion_a: "Solo or very small team (1–3 people)"
suggestion_b: "Small team (4–8 people), everyone works on everything"
suggestion_c: "Medium team (8–20 people), divided by feature or component"
suggestion_d: "Large team or multiple teams, each owning a bounded context"
```

### Q2 — Expected scale

```
ask_followup_question: "What is the expected scale of this system over its lifetime?"
suggestion_a: "Small — internal tool, limited users, no growth pressure"
suggestion_b: "Medium — production system, moderate load, some scalability needed"
suggestion_c: "Large — high traffic, horizontal scaling, availability requirements"
suggestion_d: "Unknown — start simple, must be easy to evolve"
```

### Q3 — Deployment model

```
ask_followup_question: "How will this system be deployed?"
suggestion_a: "Single process / monolith"
suggestion_b: "Monolith today, microservices possible later"
suggestion_c: "Microservices from day one"
suggestion_d: "Serverless / functions"
```

### Q4 — Testability requirements

```
ask_followup_question: "How important is testability and the ability to swap infrastructure (DB, message broker, HTTP client)?"
suggestion_a: "Basic — unit tests on business logic are enough"
suggestion_b: "Important — I want to test business logic without touching the DB or external services"
suggestion_c: "Critical — full isolation of domain from infrastructure is a hard requirement"
```

### Q5 — Domain complexity

```
ask_followup_question: "How complex are the business rules in this domain?"
suggestion_a: "Simple — mostly CRUD, few rules"
suggestion_b: "Moderate — some domain logic, a few invariants to enforce"
suggestion_c: "Complex — rich business rules, multiple aggregates, domain events"
```

### Q6 — Existing constraints

```
ask_followup_question: "Are there any existing constraints I should be aware of?"
suggestion_a: "No constraints — greenfield"
suggestion_b: "Must integrate with an existing system or database"
suggestion_c: "Framework already chosen (FastAPI, Django, Flask, …)"
suggestion_d: "I'll describe the constraints"
```

After Q6, summarise the answers and proceed to Phase 2.

---

## Phase 2 — Architecture Recommendation

**Goal:** recommend the best pattern and organisation based on domain + requirements.

### Step 2.1 — Select the pattern

Apply this decision logic (use all signals, not just one):

| Signal | Recommended pattern |
|--------|-------------------|
| Simple domain + small team + CRUD | `layered` |
| Moderate domain + testability important | `layered` or `hexagonal` |
| Complex domain + multiple bounded contexts | `hexagonal` + `ddd` |
| Domain events present + async processing | `event-driven` (+ `ddd` if domain is complex) |
| ETL / batch / ML pipeline | `pipeline` |
| CQRS needed (explicit read/write split) | add `cqrs` to `ddd` or `hexagonal ddd` |

**Patterns available:**

| Pattern | Core idea |
|---------|-----------|
| `layered` | Code organised in horizontal layers: api → service → repository → model |
| `hexagonal` | Domain at the centre, ports define boundaries, adapters implement them |
| `ddd` | Code mirrors the domain: entities, aggregates, value objects, repositories |
| `event-driven` | Communication via events; consumers, producers, processors |
| `pipeline` | Sequential data transformation steps |
| `cqrs` | Additive — separates command (write) and query (read) models |

### Step 2.2 — Select the organisation style (for `layered` and `ddd`)

When the pattern is `layered` or includes a layered component, ask:

```
ask_followup_question: "How should the code be organised within layers?"
suggestion_a: "By layer — one folder per layer (api/, services/, repositories/, models/). Best for small projects."
suggestion_b: "By component — one folder per bounded context/feature, each containing its own layers. Best for medium/large projects."
suggestion_c: "By feature — like component, but each feature is self-contained with no shared layers. Best for large teams."
```

**Organisation styles explained:**

- **By layer** — classic horizontal slicing. One `services/` folder contains all service classes.
  Simple, familiar, works well up to ~10 entities.
- **By component** — vertical slicing by bounded context. Each component folder contains its own
  `router.py`, `service.py`, `repository.py`, `models.py`. Layers are shared infrastructure.
  Good when each component evolves independently.
- **By feature** — strictest vertical slicing. Each feature is fully self-contained, no shared
  layers at all. Scales to large teams; harder to share code across features.

### Step 2.3 — Present recommendation

Present the chosen pattern + organisation with **explicit rationale**:

_"Based on your domain (`<N>` bounded contexts, `<complexity>`) and requirements (team: `<size>`,
scale: `<scale>`, testability: `<level>`), I recommend **`<pattern>`** organised **`<style>`**
because: `<2–3 sentence rationale>`."_

Ask for confirmation:

```
ask_followup_question: "Does this recommendation fit your needs?"
suggestion_a: "Yes — document and scaffold it"
suggestion_b: "Change the pattern"
suggestion_c: "Change the organisation style only"
```

---

## Phase 3 — Write / Update `docs/architecture.md`

Write the document **before** scaffolding. It is the source of truth.

**If the file does not exist:** create with `write_file`.
**If the file exists:** use `apply_diff` to patch only changed sections. Always append to Change Log.

Document structure:

```markdown
# Architecture — <Domain Name>
_Last updated: <date>_

## Overview
<two sentences: what the system does and what architectural problem this document solves>

## Requirements Summary
| Requirement | Value |
|-------------|-------|
| Team size | <value> |
| Expected scale | <value> |
| Deployment model | <value> |
| Testability | <value> |
| Domain complexity | <value> |

## Decision
**Pattern:** `<pattern(s)>`
**Organisation:** `<by layer / by component / by feature>`

## Rationale
<3–5 sentences explaining why this pattern fits the requirements and domain.
Reference specific signals: number of bounded contexts, domain complexity, testability need, team size.>

## Consequences
**Positive:**
- <benefit 1>
- <benefit 2>

**Trade-offs:**
- <trade-off 1>
- <trade-off 2>

## Layer Map

<ASCII folder tree of the chosen structure — same as what will be scaffolded>

### Layer responsibilities
| Layer / Folder | Responsibility |
|----------------|---------------|

## Change Log
| Version | Date | Change |
|---------|------|--------|
| 0.1 | <date> | Initial architecture decision |
```

---

## Phase 4 — Scaffold the Folder Structure

Scaffold **only after `docs/architecture.md` has been written**. The folder map is derived
directly from the Layer Map section of the document.

### Folder maps by pattern and organisation

---

#### `layered` — by layer

```
<root>/
├── api/
│   ├── __init__.py
│   ├── routers/
│   │   └── __init__.py        ← one router file per resource
│   └── schemas/
│       └── __init__.py        ← request/response DTOs
├── services/
│   └── __init__.py            ← business logic
├── repositories/
│   └── __init__.py            ← data access
├── models/
│   └── __init__.py            ← domain/ORM models
└── core/
    ├── __init__.py
    ├── config.py
    └── log.py
```

---

#### `layered` — by component

One folder per bounded context from `docs/domain-design.md`. Inside each, the same layer files.
Shared infrastructure lives in `core/`.

```
<root>/
├── <context_a>/
│   ├── __init__.py
│   ├── router.py              ← HTTP handlers for this component
│   ├── service.py             ← business logic for this component
│   ├── repository.py          ← data access for this component
│   └── models.py              ← models for this component
├── <context_b>/
│   ├── __init__.py
│   ├── router.py
│   ├── service.py
│   ├── repository.py
│   └── models.py
└── core/
    ├── __init__.py
    ├── config.py
    └── log.py
```

Scaffold one folder per bounded context listed in `docs/domain-design.md`.

---

#### `layered` — by feature

Like by component, but each feature also owns its own `schemas/` and has no shared layers
beyond `core/`. Features must not import from each other.

```
<root>/
├── <feature_a>/
│   ├── __init__.py
│   ├── router.py
│   ├── service.py
│   ├── repository.py
│   ├── models.py
│   └── schemas.py             ← DTOs specific to this feature
├── <feature_b>/
│   └── ...
└── core/
    ├── __init__.py
    ├── config.py
    └── log.py
```

---

#### `hexagonal`

```
<root>/
├── domain/
│   ├── __init__.py
│   └── ports/
│       └── __init__.py        ← abstract interfaces (input + output ports)
├── application/
│   └── __init__.py            ← use cases / application services
├── infrastructure/
│   ├── __init__.py
│   ├── adapters/
│   │   └── __init__.py        ← concrete implementations of output ports
│   └── driven/
│       └── __init__.py        ← DB, HTTP clients, message broker adapters
├── interfaces/
│   ├── __init__.py
│   └── api/
│       └── __init__.py        ← driving adapters (HTTP, CLI, consumer)
└── core/
    ├── __init__.py
    ├── config.py
    └── log.py
```

---

#### `ddd`

```
<root>/
├── domain/
│   ├── __init__.py
│   ├── entities/
│   │   └── __init__.py        ← domain entities and aggregates
│   ├── value_objects/
│   │   └── __init__.py
│   ├── events/
│   │   └── __init__.py        ← domain events
│   └── repositories/
│       └── __init__.py        ← repository interfaces (abstract)
├── application/
│   ├── __init__.py
│   ├── commands/
│   │   └── __init__.py
│   └── handlers/
│       └── __init__.py
├── infrastructure/
│   ├── __init__.py
│   └── persistence/
│       └── __init__.py        ← concrete repository implementations
├── interfaces/
│   ├── __init__.py
│   └── api/
│       └── __init__.py
└── core/
    ├── __init__.py
    ├── config.py
    └── log.py
```

If **by component** was chosen for `ddd`, replicate the `domain/`, `application/`,
`infrastructure/` subtree once per bounded context:

```
<root>/
├── <context_a>/
│   ├── domain/
│   │   ├── entities/
│   │   ├── value_objects/
│   │   ├── events/
│   │   └── repositories/
│   ├── application/
│   │   ├── commands/
│   │   └── handlers/
│   └── infrastructure/
│       └── persistence/
├── <context_b>/
│   └── ...
├── interfaces/
│   └── api/
└── core/
```

---

#### `event-driven`

```
<root>/
├── consumers/
│   └── __init__.py            ← event listeners / message handlers
├── producers/
│   └── __init__.py            ← event publishers
├── processors/
│   └── __init__.py            ← business logic per event type
├── models/
│   └── __init__.py            ← event schemas / data models
└── core/
    ├── __init__.py
    ├── config.py
    └── log.py
```

---

#### `pipeline`

```
<root>/
├── steps/
│   └── __init__.py            ← individual pipeline steps / transforms
├── pipelines/
│   └── __init__.py            ← pipeline definitions (ordered step sequences)
├── models/
│   └── __init__.py            ← input/output data models per step
├── io/
│   └── __init__.py            ← sources (readers) and sinks (writers)
└── core/
    ├── __init__.py
    ├── config.py
    └── log.py
```

---

#### `cqrs` (additive — combine with `ddd` or `hexagonal ddd`)

Replaces `application/commands/` and `application/handlers/` with:

```
<root>/application/
├── commands/
│   └── __init__.py            ← command definitions (write side)
├── queries/
│   └── __init__.py            ← query definitions (read side)
├── command_handlers/
│   └── __init__.py
└── query_handlers/
    └── __init__.py
```

---

### Writing the files

For every folder in the map, create the corresponding `__init__.py` using `write_file`.

Each `__init__.py` must contain:
1. Standard copyright header (from `python-style-guide`)
2. One-line module docstring describing the layer's responsibility
3. `__all__: list[str] = []`

Example:
```python
# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Domain entities and aggregates."""

__all__: list[str] = []
```

`core/config.py` placeholder:
```python
# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Application configuration — run /python-config to populate this module."""
```

`core/log.py` placeholder:
```python
# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Logging setup — add your setup_logger() factory here."""
```

---

## Phase 5 — Report

Show:
1. Pattern and organisation style chosen
2. ASCII tree of the full folder structure created
3. Summary of decisions recorded in `docs/architecture.md`

Then prompt for next steps:

```
ask_followup_question: "What would you like to do next?"
suggestion_a: "Choose the technology stack — run /framework"
suggestion_b: "Design the database schema — run /db-designer"
suggestion_c: "Design the CLI interface — run /cli-design"
suggestion_d: "The architecture is complete for now"
```

> **Recommended sequence after /architecture:**
> `/framework` → `/python-init` → `/python-framework` → `/db-designer` / `/cli-design`
