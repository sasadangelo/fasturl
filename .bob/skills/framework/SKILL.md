---
name: framework
description: Use when the user wants to choose the technology stack for a system — interviews about system type, language, team skills, and constraints, then recommends the best stack and produces docs/tech-stack.md. Language-agnostic. Requires /architecture to have been run first. Run before any language-specific skill (e.g. /python-framework).
metadata:
  disable-model-invocation: false
  argument-hint: "[language]"
---

# Framework — Technology Stack Designer

Choose the right technology stack based on the domain model and architecture decisions, document
the choice with explicit rationale, and hand off to a language-specific skill for implementation.

Produces one living artefact:
- **`docs/tech-stack.md`** — stack decision, component choices, rationale, change log

**Always patch with `apply_diff`** when the file already exists. Never fully rewrite it.
The stack decision drives every downstream language-specific skill — it is the source of truth.

---

## Step 0 — Check Prerequisites

### 0.1 — Architecture document

```
glob: docs/architecture/README.md
glob: docs/architecture.md
```

Read whichever exists (folder README takes priority).

**If not found:**
- Stop immediately and tell the user:
  _"No architecture document found. Please run `/architecture` first — it produces
  `docs/architecture.md` which this skill uses to align the stack with the chosen pattern.
  Once that document exists, come back and run `/framework` again."_
- Do not proceed further.

**If found:**
- Extract: domain name, architectural pattern, organisation style, deployment model,
  testability requirement, scale expectation, last updated date
- Keep these facts — they feed the recommendation in Phase 2.

### 0.2 — Domain design

```
glob: docs/domain-design/README.md
glob: docs/domain-design.md
```

Read whichever exists (folder README takes priority).

**If found:**
- Extract: bounded contexts count, domain events presence, external system integrations
- These supplement the architecture signals for the recommendation.

### 0.3 — Existing tech stack document

```
glob: docs/tech-stack.md
```

**If `docs/tech-stack.md` exists:**
- Read it with `read_file`
- Extract: language, framework choices, component decisions, last updated date, change log
- **Propagation check:** if `docs/architecture` was updated more recently than this document, warn:
  _"⚠️ `docs/architecture` was updated after this tech stack document. Some decisions may no
  longer align with the current architecture. Review before proceeding."_
- Tell the user: _"I found an existing tech stack for `<domain>` using `<language>` /
  `<framework>`. Last updated: `<date>`."_
- Ask:

  ```
  ask_followup_question: "What would you like to do?"
  suggestion_a: "Re-evaluate the stack based on new requirements or constraints"
  suggestion_b: "Add a component decision (e.g. choose a message broker or ORM)"
  suggestion_c: "Update the document only — no changes to existing decisions"
  suggestion_d: "Start a brand-new stack design"
  ```

  Jump to the appropriate phase. Do NOT repeat phases already confirmed.

**If not found:**

### 0.4 — Dependency discovery (existing project)

Before running the full interview, read `pyproject.toml` (or `requirements.txt` / `package.json`
/ `pom.xml` / `go.mod`) to infer the stack already in use:

```
glob: pyproject.toml
glob: requirements.txt
glob: package.json
glob: pom.xml
glob: go.mod
```

**Read whichever exists and extract dependencies:**

| Dependency found | Inferred component |
|-----------------|-------------------|
| `fastapi` | App framework: FastAPI |
| `django` | App framework: Django |
| `flask` | App framework: Flask |
| `celery` | App framework: Celery (worker) |
| `typer` | App framework: Typer (CLI) |
| `sqlalchemy` | ORM: SQLAlchemy |
| `tortoise-orm` | ORM: Tortoise |
| `pydantic` | Validation: Pydantic v2 |
| `pytest` | Testing: pytest |
| `ruff` | Code quality: ruff |
| `mypy` | Code quality: mypy |
| `redis`, `celery[redis]` | Message broker: Redis |
| `kafka-python`, `confluent-kafka` | Message broker: Kafka |

**If dependencies are found:**
- Tell the user: _"I found an existing `pyproject.toml` / dependency file. I can infer most of
  the tech stack from it: `<inferred component list>`."_
- Propose a draft stack table from the inferred dependencies
- Ask:

  ```
  ask_followup_question: "Does this inferred stack look correct? Should I document it as-is?"
  suggestion_a: "Yes — document it, I'll fill in any gaps"
  suggestion_b: "Mostly correct — I need to change a few things"
  suggestion_c: "No — run the full interview"
  ```

  If confirmed: skip Phase 1, jump to Phase 3 (write `docs/tech-stack.md`) using the inferred
  stack. Only ask about components not inferrable from dependencies (e.g. containerisation,
  deployment target).

**If no dependency file found:** proceed to Phase 1 in full.

---

## Phase 1 — Interview

Ask **one question at a time**. Do not proceed to the next until the user has answered.

### Q1 — System type

```
ask_followup_question: "What type of system are you building?"
suggestion_a: "REST API / web service"
suggestion_b: "Full-stack web application (server-rendered UI)"
suggestion_c: "CLI tool"
suggestion_d: "Background worker / event consumer / ETL pipeline"
```

If the answer can be inferred from `docs/domain-design.md` or `docs/architecture.md`, present
the inference and ask for confirmation instead.

### Q2 — Programming language

```
ask_followup_question: "Which programming language will you use?"
suggestion_a: "Python"
suggestion_b: "Node.js / TypeScript"
suggestion_c: "Java / Kotlin"
suggestion_d: "Go"
```

> **Note:** only Python is fully supported today. For other languages the skill will produce
> `docs/tech-stack.md` with recommendations, but no language-specific folder adaptation skill
> exists yet.

### Q3 — Team skills

```
ask_followup_question: "Does the team have strong experience with any specific framework or stack?"
suggestion_a: "No strong preference — recommend the best fit"
suggestion_b: "Yes — I'll describe what the team knows"
```

### Q4 — Constraints

```
ask_followup_question: "Are there any hard constraints on the technology choices?"
suggestion_a: "No constraints — greenfield, free to choose"
suggestion_b: "Cloud provider or infrastructure constraints (e.g. must run on AWS Lambda)"
suggestion_c: "Company-mandated stack or licensing restrictions"
suggestion_d: "I'll describe the constraints"
```

### Q5 — External integrations

```
ask_followup_question: "Does the system need to integrate with any specific external services that constrain the stack? (e.g. a specific database engine, message broker, or auth provider already in use)"
suggestion_a: "No — free to choose"
suggestion_b: "Yes — I'll list them"
```

After Q5, summarise the answers and proceed to Phase 2.

---

## Phase 2 — Stack Recommendation

**Goal:** recommend the full technology stack based on system type + language + architecture +
constraints. Every choice must have an explicit rationale.

### Step 2.1 — Application framework

Apply this decision logic for the **application framework** (the core runtime/web framework):

#### Python

| System type | Architecture pattern | Recommended framework |
|-------------|---------------------|-----------------------|
| REST API | any | **FastAPI** — async, OpenAPI out of the box, Pydantic validation |
| REST API | layered (simple) | **Flask** — lightweight, fewer abstractions, good for small APIs |
| Full-stack web | any | **Django** — batteries included, admin, ORM, auth |
| Background worker | event-driven | **Celery** — mature, supports Redis/RabbitMQ, beat scheduler |
| CLI tool | any | **Typer** — type-annotated, built on Click, integrates with mypy |
| ETL / pipeline | pipeline | **Prefect** or plain Python with **Click** for orchestration |

Override rules:
- If team knows Django well → prefer Django even for APIs (Django REST Framework)
- If company mandates a framework → use it regardless of fit, note the trade-off

#### Node.js / TypeScript

| System type | Recommended framework |
|-------------|-----------------------|
| REST API | **Fastify** or **Express** + TypeScript |
| Full-stack web | **Next.js** |
| Background worker | **BullMQ** + **Fastify** |
| CLI tool | **Commander.js** or **oclif** |

#### Java / Kotlin

| System type | Recommended framework |
|-------------|-----------------------|
| REST API | **Spring Boot** |
| Background worker | **Spring Batch** or **Quartz** |

#### Go

| System type | Recommended framework |
|-------------|-----------------------|
| REST API | **Gin** or **Echo** |
| CLI tool | **Cobra** |

---

### Step 2.2 — Supporting components

For each relevant component category, recommend based on language + constraints:

#### Data access / ORM

| Language | Options | When to choose |
|----------|---------|----------------|
| Python | **SQLAlchemy** (2.x async) | Any SQL database, hexagonal/ddd pattern |
| Python | **Django ORM** | Only when using Django |
| Python | **Tortoise ORM** | FastAPI + async-first |
| Python | **raw SQL** (psycopg3) | Performance-critical, simple schemas |
| Node.js | **Prisma** | Type-safe, excellent DX |
| Node.js | **Drizzle** | Lightweight, SQL-first |
| Java | **Spring Data JPA** / Hibernate | Standard Spring stack |
| Go | **sqlx** or **GORM** | sqlx for control, GORM for DX |

#### Validation / serialisation

| Language | Recommended |
|----------|-------------|
| Python | **Pydantic v2** (already included in FastAPI) |
| Node.js / TypeScript | **Zod** |
| Java | **Bean Validation** (Jakarta) |
| Go | **go-playground/validator** |

#### Testing

| Language | Unit | Integration | E2E |
|----------|------|-------------|-----|
| Python | **pytest** + **pytest-asyncio** | **pytest** + **testcontainers** | **httpx** |
| Node.js | **Vitest** or **Jest** | **Supertest** | **Playwright** |
| Java | **JUnit 5** + **Mockito** | **Spring Boot Test** | **RestAssured** |
| Go | **testing** stdlib | **testcontainers-go** | **httptest** |

#### Message broker (if event-driven)

| Option | When |
|--------|------|
| **Redis Streams** | Simple, already using Redis, low volume |
| **RabbitMQ** | Complex routing, mature ecosystem |
| **Apache Kafka** | High throughput, event log, replay needed |
| **AWS SQS/SNS** | Cloud-native, serverless, AWS environment |

#### Containerisation

Always recommend **Docker** + **Docker Compose** for local development unless a constraint
prevents it. For production orchestration, recommend **Kubernetes** if scale is large,
**Docker Compose** or **ECS** for medium scale.

#### Code quality (Python-specific)

| Tool | Purpose |
|------|---------|
| **ruff** | Linting + formatting (replaces flake8 + black + isort) |
| **mypy** | Static type checking |
| **pre-commit** | Enforce checks before commit |

---

### Step 2.3 — Present recommendation

Present the full stack as a table:

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | `<language>` | `<why>` |
| App framework | `<framework>` | `<why>` |
| ORM / data access | `<choice>` | `<why>` |
| Validation | `<choice>` | `<why>` |
| Testing | `<choice>` | `<why>` |
| Message broker | `<choice>` or N/A | `<why>` |
| Containerisation | `<choice>` | `<why>` |
| Code quality | `<choice>` | `<why>` |

Then state any trade-offs explicitly.

Ask for confirmation:

```
ask_followup_question: "Does this technology stack fit your needs?"
suggestion_a: "Yes — write the tech stack document"
suggestion_b: "Change one or more components"
suggestion_c: "Add a component category not listed"
```

---

## Phase 3 — Write / Update `docs/tech-stack.md`

**If the file does not exist:** create with `write_file`.
**If the file exists:** use `apply_diff` to patch only changed sections. Always append to Change Log.

Document structure:

```markdown
# Technology Stack — <Domain Name>
_Last updated: <date>_

## Overview
<two sentences: what the system is and what stack was chosen>

## System Profile
| Attribute | Value |
|-----------|-------|
| System type | <REST API / full-stack / CLI / worker / pipeline> |
| Language | <language + version> |
| Architecture pattern | <from docs/architecture.md> |
| Deployment target | <from docs/architecture.md> |

## Stack Decisions
| Component | Choice | Version | Rationale |
|-----------|--------|---------|-----------|
| App framework | | | |
| ORM / data access | | | |
| Validation | | | |
| Testing | | | |
| Message broker | | | |
| Containerisation | | | |
| Code quality | | | |

## Trade-offs
- <trade-off 1>
- <trade-off 2>

## Constraints Applied
- <constraint and how it influenced the decision>

## Open Questions
- <question to resolve in a future session>

## Change Log
| Version | Date | Change |
|---------|------|--------|
| 0.1 | <date> | Initial stack decision |
```

---

## Phase 4 — Report

After writing the document, report:
- Language and primary framework chosen
- Key component decisions
- Any trade-offs or constraints noted

Then prompt for next steps:

```
ask_followup_question: "What would you like to do next?"
suggestion_a: "Adapt the Python project structure to the chosen framework — run /python-framework"
suggestion_b: "Design the database schema — run /db-designer"
suggestion_c: "Design the CLI interface — run /cli-design"
suggestion_d: "The technology stack is complete for now"
```

> **Note:** `/python-framework` requires the project scaffold to exist first.
> Run `/python-init <project-name>` before `/python-framework` if not done yet.
