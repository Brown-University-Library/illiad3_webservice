# AGENTS.md — Repository Agent Instructions (Source of Truth)

This file defines the canonical coding directives for this repository.

If other instruction files exist (Copilot, IDE rules, contributor docs) and conflict with this file, follow this file and treat the others as stale.


## Table of contents

- [Project basics](#project-basics)
- [How to run code](#how-to-run-code)
- [Coding directives (Python)](#coding-directives-python)
- [Django architecture conventions](#django-architecture-conventions)
- [Front-end change guidance](#front-end-change-guidance)
- [Tests](#tests)
- [Change workflow expectations](#change-workflow-expectations)
- [If instructions are missing or ambiguous](#if-instructions-are-missing-or-ambiguous)
- [Agent project index](#agent-project-index)


## Project basics

- Primary language: Python
- Target runtime: Python 3.12.16 or a later 3.12 patch, with `requires-python = ">=3.12.16,<3.13"` in `pyproject.toml`
- Django version: stay within the 5.2 series and use the latest compatible patch release when updating dependencies.
- Dependency / execution tool: `uv`
- Project-root is the directory containing this file (and `.git/`, and `.gitignore`).
- NEVER include full server filesystem paths in documentation, examples, or agent notes. Use relative paths or variable names instead.
- Keep all server-deployment documentation outside READMEs, including any mention of deployment caller scripts. Creating the caller outside the Git repository remains part of tomlization.


## How to run code

- Assume user is in the project-root directory.
- Do not use `python` to run scripts.
- Run a script via: `uv run ./path_to_script.py --help`
- Run tests via:
    - `uv run ./run_tests.py`
        - Note that `run_tests.py` has usage instructions about how to run more granular tests.
- Run django management scripts via: `uv run ./manage.py THE-COMMAND`


## Coding directives (Python)

### Type hints and imports

- Use Python 3.12-compatible type hints for new functions and important variables.
- Use builtin generic annotations such as `list[str]` and `X | None` for optional values. Use `from __future__ import annotations` when postponed annotation evaluation is useful.
- Keep annotations simple and check explicitly for `None` where needed.

### Script structure

- Structure runnable modules as:
  - `def main() -> None: ...`
  - `if __name__ == '__main__': main()`
- Keep `main()` simple: parse args / orchestrate calls only.
- Put real logic into top-level helper functions and modules (no nested function definitions).
- Rarely use more than three levels of hierarchy: main() can call helper_A() which can call helper(B) which can, if necessary, can call helper(C) -- but that's it.

### Functions and control flow

- Prefer single-return functions (use local variables and a final return).
- Do not define functions inside other functions.
- Favor clarity and explicitness over cleverness.

### Logging

- When adding a log statement, when possible, format variable values as a label, followed by a comma and a space, with the value enclosed in double backticks.
- Prefer a label that matches the variable name. For example: ```log.debug(f'branch_and_commit, ``{branch_and_commit}``')```

### HTTP and networking

- Use `httpx` for all HTTP calls.
- Do not introduce alternate HTTP libraries (e.g., `requests`, `aiohttp`) unless the repository already depends on them and there is a documented reason.
- Existing ILLiad and bibliographic-service integrations retain `requests` to preserve their request handling. Keep the isolated test runner's network blocking in step with any HTTP-library change.

### Docstrings

- Use triple-quoted docstrings.
- Write docstrings in present tense, with triple-quotes on their own lines.
  - Good:
    ```
    """
    Parses ...
    """
    ```
  - Avoid: `"""Parse ..."""`
- The last line of non-test function-docstrings should be: `Called by: the_caller_function()` (or, if in another class/module, `Called by: module.Class.the_caller_function()`)
- Start test-function docstring-text with "Checks..."
- For header-comments, in functions, start the comment with two hashes (e.g., `## does this`).

### Additional coding directives

- inspect `ruff.toml` for additional coding directives, such as `max-line-length` and `quote-style`.

### Markdown formatting

- Do not use hard line-breaks in markdown files; let paragraphs wrap naturally.
- When creating a Markdown file with more than three top-level `##` headings, add a table of contents near the top with links to those `##` headings.


## Django architecture conventions

### View-layer responsibilities

- `project/app/views.py` should contain **only** view functions that directly handle URL endpoints.
- Every view function in `project/app/views.py` should correspond to an entry in `project/config/urls.py`.
- Views should act as **manager/orchestrator** functions:
  - Parse request input (query params, POST body, files)
  - Perform minimal validation and shaping of inputs
  - Delegate substantive work to modules under `project/app/lib/`
  - Convert returned results into the appropriate `HttpResponse` (HTML, JSON, redirects)

### Business logic placement

- Put domain logic, integrations, and reusable operations in `project/app/lib/` (not in `views.py`).
- If multiple endpoints share logic, move that shared logic into `project/app/lib/` and keep each view thin.
- Prefer pure, testable functions in `project/app/lib/` that accept plain Python values (not Django request objects)
  unless passing the request is necessary for a narrow, well-justified reason.

### Imports and dependencies

- `views.py` should primarily import:
  - Django primitives (`HttpRequest`, `HttpResponse`, `render`, `redirect`, etc.)
  - The minimal set of functions/classes from `project/app/lib/` needed for each endpoint
- Avoid creating a secondary abstraction layer inside `views.py` (no view-helper utilities); place helpers in `project/app/lib/`.


## Front-end change guidance

- When front-end changes are required, use JavaScript only where it is truly required.
- Prefer updates in CSS, Python code, or Django template code when those can satisfy the behavior or presentation need.


## Tests

- Use the standard library `unittest` framework (not pytest) for non-Django projects.
- Use Django's test framework for Django projects.
- New behavior should usually come with a focused test covering:
  - the happy path
  - at least one failure / edge case


## Change workflow expectations

When implementing a change (especially from an issue/task):

1. Read relevant surrounding code and match existing conventions.
2. Make the smallest correct change that satisfies the request.
3. Update tests and run: `uv run ./run_tests.py`
4. If you cannot run tests in your environment, still write/adjust tests and state what you would run.

### Commit messages

- Group related files into logical, focused commits; do not require a separate commit for every file.
- Keep each commit message brief, with no more than ten words.
- Write messages in the present tense so they complete the phrase "This commit..." Begin with a fitting verb such as "Adds," "Implements," or "Updates."


## If instructions are missing or ambiguous

- Do not ask questions unless absolutely necessary to proceed.
- Make reasonable assumptions, state them explicitly, then implement.
- If blocked, provide:
  - what you tried
  - what you found in the repo
  - a concrete next step (command, file to edit, or minimal decision needed)


## Agent project index

- `manage.py` and `config/settings.py`: Django commands and settings. Settings load `.env` in the outer directory using a path derived from `__file__`, independent of the working directory. No environment-file selector is needed.
- `config/passenger_wsgi.py`: WSGI entry point; uses the same settings loader.
- `config/__init__.py`: registers PyMySQL as Django's MySQL driver.
- `config/urls.py` and `illiad_app/views.py`: endpoint routing and request handling.
- `illiad_app/lib/`: user checks, user creation, book/article request mapping, authentication, and information responses.
- `illiad_app/settings_app.py`: application environment variables, including legacy and test settings still read at import time.
- `run_tests.py`: temporary local configuration and selected tests with outgoing HTTP requests blocked. It prevents Django startup from loading the outer `.env`. Run `uv run ./run_tests.py --help` for options.
- `illiad_app/tests/`: mapping tests and client tests; some client tests contact external services when run directly through Django.
- `.env.example`: dummy local settings; never put real operational values in tracked files.
- `config/requirements.txt`: retained historical declarations. Use `pyproject.toml` and `uv.lock` for installation.
- `pyproject.toml` declares Django, requests, PyMySQL, python-dotenv, and the explicit `certifi>=2026.10.19` requirement. Supporting dependencies and exact resolved versions are recorded in `uv.lock`. Preserve the Python `>=3.12.16,<3.13` and Django 5.2 bounds and do not lower the certifi minimum without an explicit request.
- Before finishing Python changes, run Ruff and Pylance or Pyright with `.venv` and the settings in `pyproject.toml`. Fix diagnostics in changed files without suppressing rules.
