---
name: test-strategy
description: "Use when defining or revising a project's test strategy, test levels, coverage goals, test data isolation, or CI test gates. Produces docs/test-strategy.md and optionally docs/test-plan.md. Stays independent of implementation language and framework."
metadata:
  disable-model-invocation: false
  argument-hint: "[scope or constraints]"
---

# Test Strategy Designer

Define how a project will gain confidence through automated tests, from isolated behavior checks to tests of complete user-visible workflows. Keep this skill language- and framework-agnostic; implementation choices belong to the relevant language/framework skill.

Produces up to two living artefacts:
- **`docs/test-strategy.md`** — test objectives, classification, coverage approach, isolation, and CI gates
- **`docs/test-plan.md`** *(optional)* — concrete test cases derived from requirements, organised by category; produced only if the user confirms it is needed

If either document already exists, preserve confirmed decisions and patch only the sections that need to change. Record meaningful changes in its change log.

---

## Step 0 — Discover Context

Read the available project artefacts, prioritising:

1. `docs/requirements.md` or equivalent requirements document
2. `docs/domain-design.md` or equivalent domain model
3. `docs/architecture.md` or equivalent architecture document
4. `docs/tech-stack.md` or equivalent framework/stack decision
5. API, CLI, database, security, deployment, and operations design documents relevant to the requested scope
6. Existing test configuration, test suites, CI workflows, and contribution guidance

Do not require every document to exist. Note missing or conflicting inputs and ask only for information needed to make a consequential decision. Treat source code and configuration as evidence of the current implementation, not as a substitute for product requirements.

If `docs/test-strategy.md` already exists, summarise its current decisions and ask what scope should change before replacing any confirmed policy.

---

## Step 1 — Establish the Strategy

Clarify the following as needed, one question at a time:

- Which user-visible and system behaviors are in scope?
- Which failures would be most costly, likely, or difficult to detect manually?
- Which external boundaries and infrastructure must be exercised for confidence?
- What runtime and infrastructure are available locally and in CI?
- Which checks must block a pull request, and what feedback-time constraints apply?
- Are there regulatory, security, compatibility, or reliability requirements that affect evidence or retention?

Infer answers from project documents when possible and ask for confirmation rather than repeating already-settled decisions.

Map important requirements and risks to observable outcomes and suitable test evidence. Prefer testing behavior and public contracts over implementation details. Do not prescribe a coverage percentage unless the project has a defensible reason and a way to enforce it; identify meaningful behavior gaps instead.

---

## Step 2 — Define Test Categories

Classify tests by their **primary assurance**: the behavior and boundaries they verify. These categories are useful but are not mutually exclusive technical shapes. If a test provides more than one kind of assurance, name it by its primary purpose and avoid counting it as multiple independent checks.

| Category    | Primary assurance                       | Typical boundary                          |
|-------------|-----------------------------------------|-------------------------------------------|
| Unit        | One behavior in isolation.              | A focused function, object, or component. |
| Integration | Components work across a real boundary. | Database, framework, or external adapter. |
| End-to-end  | A complete user workflow succeeds.      | Public entry point to observable result.  |

Use these principles:

- A test is not a unit test merely because it uses mocks, nor an integration test merely because it avoids them. Classify by scope and assurance.
- Use real dependencies when their behavior is part of the assurance being sought; use controlled substitutes when isolation, determinism, or failure simulation is the purpose.
- Avoid mocking the implementation's private call structure. Prefer stable interfaces and observable outcomes.
- An in-process framework client can provide integration assurance without proving deployment or process-level behavior. State that boundary explicitly.
- A complete workflow can be exercised by an integration-style harness; classify it as end-to-end only when it verifies the system through its intended external entry point and configuration.
- Do not duplicate broad scenarios across categories unless each repetition proves a distinct risk or boundary.

Add contract, performance, security, accessibility, migration, or resilience testing only where requirements or risks justify them. These describe additional assurance dimensions and need not become separate mandatory layers.

---

## Step 3 — Set Execution and Isolation Policy

For each category, define:

- What runs locally and in CI
- Required services, environment, and setup/teardown
- How tests isolate data and avoid depending on execution order
- How time, randomness, network access, and asynchronous work are controlled
- How failures are diagnosed and whether retries are permitted
- Ownership and maintenance expectations

Prefer deterministic, independently runnable tests. Retries must not conceal flaky behavior. Give parallel tests isolated state where they share mutable resources. Keep secrets and production data out of test fixtures.

Choose infrastructure based on the behavior that must be verified and what CI can reliably provide. Do not mandate containers, a live server, or a particular database solely because a category name suggests it.

---

## Step 4 — Define CI Gates

Create a concise execution policy that states:

- Required pull-request checks and their intended feedback time
- Broader checks run on merge, schedule, release, or manually
- Which failures block delivery and how flaky tests are handled
- How test commands are discoverable and reproducible

Optimise for fast, trustworthy feedback, not for putting every test in the same job. Do not invent duration limits or CI capabilities without evidence; propose them for user confirmation when unknown.

---

## Step 5 — Review and Confirm

Present the proposed decisions and unresolved assumptions. Ask the user to confirm consequential choices, especially test boundaries, required infrastructure, and pull-request gates.

After confirmation, create or update `docs/test-strategy.md`. Keep it actionable and specific to the project while keeping this skill reusable. Include:

- Scope and goals
- Risk/requirement-to-test mapping
- Category definitions and their boundaries in this project
- Isolation, data, and determinism policy
- Local and CI execution matrix
- Deferred checks and known gaps
- Change log

Once `docs/test-strategy.md` is written, ask the user (using `ask_followup_question`):
> "Vuoi che produca anche un `docs/test-plan.md` con i casi di test concreti ricavati dai requisiti?"

A test plan is worth producing when:
- traceability from requirements to test cases is needed before writing code
- multiple contributors need to agree on coverage upfront
- an audit trail or compliance record is required

If the user confirms, create or update `docs/test-plan.md`. Organise it by test category (unit, integration, e2e). For each category list the concrete test cases derived from requirements (job stories, acceptance criteria, invariants) with: test ID, scenario description, inputs, expected outcome, and the requirement it traces to. Keep it free of implementation detail — no code, no fixture names.

Do not implement test code or alter application architecture in this skill. Hand off concrete implementation tasks to the language/framework-specific testing skill. If the existing architecture prevents a required guarantee, describe the gap and ask before expanding scope.