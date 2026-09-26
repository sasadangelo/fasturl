#!/usr/bin/env bash
# scaffold.sh <project-name> <package-name> [target-dir]
# Creates a new Python project based on github.com/sasadangelo/python-blueprint
#
# target-dir (optional): directory where files are written.
#   - Defaults to ./<project-name>  (creates a new subdirectory)
#   - Pass "." to scaffold directly into the current working directory
set -euo pipefail

PROJECT_NAME="${1:?Usage: scaffold.sh <project-name> <package-name> [target-dir]}"
PACKAGE_NAME="${2:?Usage: scaffold.sh <project-name> <package-name> [target-dir]}"
TARGET_DIR="${3:-$PROJECT_NAME}"

if [ "$TARGET_DIR" != "." ] && [ -d "$TARGET_DIR" ]; then
  echo "Error: directory '$TARGET_DIR' already exists." >&2
  exit 1
fi

mkdir -p "$TARGET_DIR/.vscode"
mkdir -p "$TARGET_DIR/src/$PACKAGE_NAME"
mkdir -p "$TARGET_DIR/tests"

# ── .python-version ──────────────────────────────────────────────────────────
cat > "$TARGET_DIR/.python-version" << 'EOF'
3.14
EOF

# ── .gitignore ────────────────────────────────────────────────────────────────
cat > "$TARGET_DIR/.gitignore" << 'EOF'
# Byte-compiled / optimized / DLL files
__pycache__/
*.py[codz]
*$py.class

# C extensions
*.so

# Distribution / packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# PyInstaller
*.manifest
*.spec

# Installer logs
pip-log.txt
pip-delete-this-directory.txt

# Unit test / coverage reports
htmlcov/
.tox/
.nox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.py.cover
.hypothesis/
.pytest_cache/
cover/

# Translations
*.mo
*.pot

# Environments
.env
.envrc
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# mypy
.mypy_cache/
.dmypy.json
dmypy.json

# Ruff
.ruff_cache/

# pytype
.pytype/

# Cython debug symbols
cython_debug/

# PyPI configuration file
.pypirc

# UV
#uv.lock

# pdm
.pdm-python
.pdm-build/

# pixi
.pixi

# PEP 582
__pypackages__/

# Celery
celerybeat-schedule
celerybeat.pid

# SageMath
*.sage.py

# Spyder
.spyderproject
.spyproject

# Rope
.ropeproject

# mkdocs
/site

# Pyre
.pyre/

# Cursor
.cursorignore
.cursorindexingignore

# Marimo
marimo/_static/
marimo/_lsp/
__marimo__/
EOF

# ── .pre-commit-config.yaml ───────────────────────────────────────────────────
cat > "$TARGET_DIR/.pre-commit-config.yaml" << 'EOF'
repos:
  # --- Base code hygiene ---
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: check-yaml
      - id: check-toml
      - id: check-json
      - id: check-added-large-files
      - id: check-case-conflict
      - id: check-merge-conflict

  # --- Ruff (replaces black, flake8, isort, pyupgrade, and more) ---
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.4
    hooks:
      # Run the linter
      - id: ruff
        args: [ "--fix" ]
      # Run the formatter
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.18.2
    hooks:
      - id: mypy

  - repo: https://github.com/PyCQA/bandit
    rev: 1.8.6
    hooks:
      - id: bandit
        args: [ "--skip", "B101" ]

  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks:
      - id: detect-secrets
        args: [ "--baseline", ".secrets.baseline" ]

  - repo: https://github.com/Lucas-C/pre-commit-hooks
    rev: v1.5.5
    hooks:
      - id: remove-tabs
      - id: forbid-crlf
EOF

# ── .secrets.baseline ─────────────────────────────────────────────────────────
cat > "$TARGET_DIR/.secrets.baseline" << 'EOF'
{
  "version": "1.5.0",
  "plugins_used": [
    {"name": "ArtifactoryDetector"},
    {"name": "AWSKeyDetector"},
    {"name": "AzureStorageKeyDetector"},
    {"name": "Base64HighEntropyString", "limit": 4.5},
    {"name": "BasicAuthDetector"},
    {"name": "CloudantDetector"},
    {"name": "DiscordBotTokenDetector"},
    {"name": "GitHubTokenDetector"},
    {"name": "GitLabTokenDetector"},
    {"name": "HexHighEntropyString", "limit": 3.0},
    {"name": "IbmCloudIamDetector"},
    {"name": "IbmCosHmacDetector"},
    {"name": "IPPublicDetector"},
    {"name": "JwtTokenDetector"},
    {"name": "KeywordDetector", "keyword_exclude": ""},
    {"name": "MailchimpDetector"},
    {"name": "NpmDetector"},
    {"name": "OpenAIDetector"},
    {"name": "PrivateKeyDetector"},
    {"name": "PypiTokenDetector"},
    {"name": "SendGridDetector"},
    {"name": "SlackDetector"},
    {"name": "SoftlayerDetector"},
    {"name": "SquareOAuthDetector"},
    {"name": "StripeDetector"},
    {"name": "TelegramBotTokenDetector"},
    {"name": "TwilioKeyDetector"}
  ],
  "filters_used": [
    {"path": "detect_secrets.filters.allowlist.is_line_allowlisted"},
    {"path": "detect_secrets.filters.common.is_ignored_due_to_verification_policies", "min_level": 2},
    {"path": "detect_secrets.filters.heuristic.is_indirect_reference"},
    {"path": "detect_secrets.filters.heuristic.is_likely_id_string"},
    {"path": "detect_secrets.filters.heuristic.is_lock_file"},
    {"path": "detect_secrets.filters.heuristic.is_not_alphanumeric_string"},
    {"path": "detect_secrets.filters.heuristic.is_potential_uuid"},
    {"path": "detect_secrets.filters.heuristic.is_prefixed_with_dollar_sign"},
    {"path": "detect_secrets.filters.heuristic.is_sequential_string"},
    {"path": "detect_secrets.filters.heuristic.is_swagger_file"},
    {"path": "detect_secrets.filters.heuristic.is_templated_secret"}
  ],
  "results": {},
  "generated_at": "2025-11-07T18:44:23Z"
}
EOF

# ── pyproject.toml ────────────────────────────────────────────────────────────
cat > "$TARGET_DIR/pyproject.toml" << EOF
[project]
name = "$PROJECT_NAME"
version = "0.1.0"
description = "A Python project based on python-blueprint"
readme = "README.md"
requires-python = ">=3.10,<3.15"
dependencies = [
  "pydantic>=2.3,<3",
  "requests>=2.31.0,<3",
]

[dependency-groups]
dev = [
  "bandit>=1.8.6",
  "coverage>=7.11.0",
  "detect-secrets>=1.5.0",
  "mypy>=1.18.2",
  "poethepoet>=0.37.0",
  "pre-commit>=3.8.0",
  "pytest>=8.4.2",
  "radon>=6.0.1",
  "ruff>=0.8.0",
]

[tool.ruff]
exclude = [".venv", "__pycache__", "build", "dist", "*.egg-info"]
line-length = 120
target-version = "py310"

[tool.ruff.lint]
ignore = []
select = ["E", "W", "F", "I", "N", "UP", "B", "C4", "SIM"]

[tool.ruff.lint.isort]
lines-between-types = 0
section-order = ["future", "standard-library", "third-party", "first-party", "local-folder"]

[tool.ruff.format]
indent-style = "space"
line-ending = "auto"
quote-style = "double"
skip-magic-trailing-comma = false

[tool.pytest.ini_options]
pythonpath = ["src"]
EOF

# ── .vscode/settings.json ─────────────────────────────────────────────────────
cat > "$TARGET_DIR/.vscode/settings.json" << 'EOF'
{
  "[python]": {
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.fixAll": "explicit",
      "source.organizeImports": "explicit"
    },
    "editor.defaultFormatter": "charliermarsh.ruff"
  },
  "python.analysis.extraPaths": ["./src"],
  "flake8.enabled": false,
  "python.linting.flake8Enabled": false,
  "python.linting.enabled": true
}
EOF

# ── .vscode/launch.json ───────────────────────────────────────────────────────
cat > "$TARGET_DIR/.vscode/launch.json" << 'EOF'
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python Debugger: Current File",
      "type": "debugpy",
      "request": "launch",
      "program": "${workspaceFolder}/app.py",
      "cwd": "${workspaceFolder}",
      "console": "integratedTerminal",
      "env": {
        "PYTHONPATH": "${workspaceFolder}",
        "LOGLEVEL": "TRACE"
      }
    }
  ]
}
EOF

# ── src/<package>/__init__.py ─────────────────────────────────────────────────
touch "$TARGET_DIR/src/$PACKAGE_NAME/__init__.py"

# ── src/<package>/hello.py ────────────────────────────────────────────────────
cat > "$TARGET_DIR/src/$PACKAGE_NAME/hello.py" << EOF
def say_hello(name: str) -> str:
    """Return a greeting for the given name."""
    return f"Hello, {name}!"


if __name__ == "__main__":
    print(say_hello(name="World"))
EOF

# ── tests/test_hello.py ───────────────────────────────────────────────────────
cat > "$TARGET_DIR/tests/test_hello.py" << EOF
from ${PACKAGE_NAME}.hello import say_hello


def test_say_hello() -> None:
    assert say_hello(name="World") == "Hello, World!"
    assert say_hello(name="Alice") == "Hello, Alice!"
    assert say_hello(name="Bob") != "Hello, Alice!"
EOF

# ── README.md ─────────────────────────────────────────────────────────────────
cat > "$TARGET_DIR/README.md" << EOF
# $PROJECT_NAME

A Python project scaffolded from [python-blueprint](https://github.com/sasadangelo/python-blueprint).

## Setup

\`\`\`bash
uv python install 3.14 && uv python pin 3.14
uv sync --group dev
\`\`\`

## Run

\`\`\`bash
uv run python -m ${PACKAGE_NAME}.hello
\`\`\`

## Test

\`\`\`bash
uv run pytest tests
\`\`\`

## Tools

\`\`\`bash
uv run ruff check src tests/
uv run ruff format src tests/
uv run mypy src
uv run bandit -r src
pre-commit run --all-files
\`\`\`
EOF

echo "✅  Project '$PROJECT_NAME' created successfully in '$TARGET_DIR'."
