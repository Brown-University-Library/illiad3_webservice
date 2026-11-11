# ILLiad webservice

## Brief overview

This Django application provides an internal API for checking ILLiad users, creating users, and submitting book and article requests through the hosted ILLiad API.

## More info

The application lets callers such as [easyAccess](https://github.com/Brown-University-Library/easyaccess_project) and [easyBorrow](https://github.com/birkin/easyborrow_controller) keep using a consistent interface when ILLiad's underlying interface changes. In April 2019, it switched from a client that simulated browser requests to ILLiad's official API.

- [Brief overview](#brief-overview)
- [More info](#more-info)
- [Local installation](#local-installation)
- [Usage](#usage)
- [Tests](#tests)
- [Primary dependencies](#primary-dependencies)

Useful references:

- [ILLiad API documentation](https://support.atlas-sys.com/hc/en-us/articles/360011809394-The-ILLiad-Web-Platform-API)
- [ILLiad table documentation](https://support.atlas-sys.com/hc/en-us/articles/360011812074), including request-field length limits

## Local installation

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git. From the parent directory where you want the checkout:

```bash
mkdir illiad3_webservice_stuff
cd illiad3_webservice_stuff
git clone https://github.com/Brown-University-Library/illiad3_webservice.git illiad3_project
cd illiad3_project
uv sync --locked --group local
cp -n .env.example ../.env
```

If you already have a checkout, start in `illiad3_project` and run the last two commands. `../.env` is in the outer directory, outside the Git checkout; the copy preserves an existing file there. uv creates `.venv` with Python 3.12 and the dependencies recorded in `uv.lock`. The Python requirement is `>=3.12,<3.13`; the upgrade was checked with Python 3.12.16.

The example settings use dummy credentials, local SQLite, and example URLs. They are sufficient for local startup and checks. Set values in the outer `.env` only when you need to connect the application to another service. Run commands from the repository root so relative database, static-file, and log paths resolve consistently.

```bash
uv run ./manage.py check
uv run ./manage.py runserver
```

Visit `http://127.0.0.1:8000/info/` to see the checked-out branch and commit. This endpoint does not contact ILLiad. Local commands may create `local.log`; database operations use `local.sqlite3`.

## Usage

The routes in [config/urls.py](config/urls.py) expose these operations:

| Route | Method | Purpose |
| --- | --- | --- |
| `check_user/` | GET | Check a user's ILLiad status using HTTP Basic authentication. |
| `create_user/` | POST | Create an ILLiad user. |
| `v2/make_request/` | POST | Submit a book request. |
| `request_article/` | POST | Submit an article request. |
| `info/` | GET | Show application version information. |

The [client tests](illiad_app/tests/tests_client.py) illustrate request parameters. The [new-user example](sample_scripts/sample_newuser_submission.py) and [transaction example](sample_scripts/sample_transaction_submission.py) show additional usage. These examples use their own environment variables and can create users or requests when pointed at a real service; inspect them before running them.

Django settings load the outer directory's `.env` directly, using a location derived from `settings.py` rather than the working directory. Its values take precedence over inherited application values. The loader treats values literally and does not expand `${VARIABLE}` expressions or execute shell commands. A `.env` inside the Git checkout is not used. If the outer file is absent, required settings must already be in the environment. Leave `PYTHON_DOTENV_DISABLED` unset: python-dotenv recognizes that variable and can skip loading the file when it is enabled.

## Tests

From the repository root:

```bash
uv run ./run_tests.py
uv run ./run_tests.py --check
uv run ./run_tests.py illiad_app.tests.tests_book_mapper --verbosity 2
```

The default run covers field mapping, complete API requests, authentication, invalid requests, redirects, host validation, and dotenv loading. It also checks management-command and WSGI startup with temporary settings and verifies that Django can load the MySQL driver without making a connection. It uses dummy settings from `.env.example`, an in-memory SQLite database, and a temporary log file. It ignores inherited application settings, prevents Django startup from reading the outer `.env`, and blocks HTTP requests made through `requests`, including prepared requests sent through a session. It does not need your `.env` or real credentials.

The tests in [tests_request_flows.py](illiad_app/tests/tests_request_flows.py) exercise book and article submissions, user creation, authenticated user-status lookup, and rejected requests. They run the real Django routes, form parsing, handlers, and JSON responses with simulated external HTTP replies. They check Unicode text, article notes, submitted fields, response formats, and whether rejected requests avoid external calls. They also check Basic authentication parsing, form-encoded submissions, existing redirect destinations, and allowed hosts. These provide regression checks for framework changes without requiring real service access.

`--check` runs Django's system checks with the same temporary settings. A test label selects a smaller set of tests; outgoing HTTP remains blocked. Tests that require external services are excluded from the default set. Running the existing client tests directly through Django can contact the configured services.

## Primary dependencies

`pyproject.toml` declares the application's dependencies and allowed version ranges. Django stays within the 5.2 series, and Python stays within 3.12. `certifi>=2026.10.19` is an explicit requirement even though requests also depends on it. `uv.lock` records exact versions for these packages and their supporting dependencies. The historical `config/requirements.txt` remains for reference; install using uv and the lockfile.

The inventory below combines the historical declarations, current imports and configuration, and dependency relationships recorded in `uv.lock`.

| Package | Locked version | Purpose and location |
| --- | --- | --- |
| Django | 5.2.19 | Web framework, URL routing, settings, and test runner; declared in the historical requirements and used throughout `config/` and `illiad_app/`. Requires `asgiref`, `sqlparse`, and, on Windows, `tzdata`. |
| requests | 2.34.2 | HTTP calls in the user, book, and article handlers under `illiad_app/lib/`, plus sample scripts. Retained for these existing integrations. Requires `certifi`, `charset-normalizer`, `idna`, and `urllib3`. |
| PyMySQL | 1.2.4 | MySQL driver declared in the historical requirements and registered as `MySQLdb` by `config/__init__.py` using PyMySQL's compatibility adapter. Its `rsa` extra supplies `cryptography` for SHA-256 password authentication. |
| python-dotenv | 1.2.4 | Reads the outer `.env` in `config/settings.py` and dummy settings in `run_tests.py`; replaces the historical environment-file reader. |
| certifi | 2026.10.23 | Supplies the certificate-authority bundle used by requests to verify outgoing HTTPS connections. The explicit minimum keeps this requirement visible when dependencies are updated. |

Dependency cleanup:

- `illiad3` and `beautifulsoup4` were present in the original environment but are unused by the current application, tests, and sample scripts. Both were removed, along with the `illiad3` Git-source entry.
- `asgiref`, `sqlparse`, `charset-normalizer`, `idna`, `urllib3`, the Windows-only `tzdata`, and the MySQL authentication dependencies `cryptography`, `cffi`, and `pycparser` are recorded in `uv.lock`; application code does not need separate direct declarations for them. The current dependencies no longer require `chardet` or `pytz`.
- `shellvars-py` is replaced by `python-dotenv`; application code no longer imports it. The historical requirements still record the old declaration.
- `pip`, `setuptools`, and `wheel` are installation tools rather than application dependencies. uv supplies isolated build requirements when needed.

The `local`, `staging`, and `prod` dependency groups are explicit and currently empty: each uses the same application dependencies. Tests use Django and the standard library. There is no additional test framework or interactive-tool dependency.

For later dependency updates, keep exact resolved versions in `uv.lock`, preserve the Python 3.12 and Django 5.2 bounds and the explicit certifi minimum, and validate each relevant environment group. Recheck the imports, configuration, and dependency relationships before removing a direct requirement.
