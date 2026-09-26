---
name: python-init
description: Use when the user types /python-init or asks to initialize/scaffold a new Python project using the python-blueprint structure. Creates the full project layout with uv, ruff, mypy, bandit, detect-secrets, pre-commit, pytest, and VS Code config.
metadata:
  disable-model-invocation: true
  argument-hint: "[project-name]"
---

# Init Python Project

Scaffold a new Python project based on https://github.com/sasadangelo/python-blueprint.

## Step 1 — Determine the project name

If the user passed an argument after `/python-init` (e.g. `/python-init my-agent`),
use that as the project name. Otherwise ask:

```
ask_followup_question: "What is the name of the new Python project?"
```

Derive a **package name** from the project name: lowercase, replace hyphens with underscores
(e.g. `my-agent` → `my_agent`).

## Step 2 — Determine the target directory

Ask the user where the project files should be written:

```
ask_followup_question: "Where should the project be created?"
suggestion_a: "In a new subfolder ./<project-name>/ (default)"
suggestion_b: "Directly in the current workspace root (.)"
```

- If the user chooses the **subfolder** option (or does not specify), set `TARGET_DIR` to `<project-name>`.
- If the user chooses **workspace root**, set `TARGET_DIR` to `.`.

## Step 3 — Run the scaffold script

Execute the bundled script, passing project name, package name, and target directory:

```bash
bash .bob/skills/python-init/scaffold.sh "<project-name>" "<package-name>" "<target-dir>"
```

- When `<target-dir>` is `<project-name>`, the script creates a new subdirectory.
- When `<target-dir>` is `.`, the script writes all files directly into the workspace root.

## Step 4 — Confirm to the user

Report success and list the created structure (adjust the root label based on the chosen target):

```
<target-dir>/          ← either "<project-name>/" or "." (workspace root)
├── .vscode/
│   ├── launch.json
│   └── settings.json
├── src/
│   └── <package_name>/
│       ├── __init__.py
│       └── hello.py
├── tests/
│   └── test_hello.py
├── .gitignore
├── .pre-commit-config.yaml
├── .python-version
├── .secrets.baseline
├── pyproject.toml
└── README.md
```

Then remind the user of the next steps:

**If a subfolder was created:**

1. `cd <project-name>`
2. `uv python install 3.14 && uv python pin 3.14`
3. `uv sync --group dev`
4. `uv run pre-commit install`
5. `uv run pytest tests`
6. `git init`
7. `git add .`
8. `git commit -m "chore: initial project scaffold"`
9. `git remote add origin <remote-url>`
10. `git push -u origin main`

**If scaffolded in the workspace root:**

1.  `uv python install 3.14 && uv python pin 3.14`
2.  `uv sync --group dev`
3.  `uv run pytest tests`
4.  `git init`
5.  `uv run pre-commit install`
6.  `git add .`
7.  `git commit -m "chore: initial project scaffold"`
8.  `git branch -M main`
9.  `git remote add origin <remote-url>`
10. `git push -u origin main`
