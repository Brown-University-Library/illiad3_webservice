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

If you already have a checkout, start in `illiad3_project` and run the last two commands. `../.env` is in the outer directory, outside the Git checkout; the copy preserves an existing file there. uv creates `.venv` using the interpreter and dependencies specified in `pyproject.toml` and `uv.lock`.

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

Django settings load the outer directory's `.env` directly, using a location derived from `settings.py` rather than the working directory. Its values take precedence over inherited application values. The loader treats values literally and does not expand `${VARIABLE}` expressions or execute shell commands. A `.env` inside the Git checkout is not used. If the outer file is absent, required settings must already be in the environment.

## Tests

From the repository root:

```bash
uv run ./run_tests.py
uv run ./run_tests.py --check
uv run ./run_tests.py illiad_app.tests.tests_book_mapper --verbosity 2
```

The default run executes 43 tests covering field mapping, complete API requests, invalid requests, and dotenv loading. It uses dummy settings from `.env.example`, an in-memory SQLite database, and a temporary log file. It ignores inherited application settings, prevents Django startup from reading the outer `.env`, and blocks HTTP requests made through `requests`. It does not need your `.env` or real credentials.

The five tests in [tests_request_flows.py](illiad_app/tests/tests_request_flows.py) exercise book and article submissions, user creation, authenticated user-status lookup, and rejected requests. They run the real Django routes, form parsing, handlers, and JSON responses with simulated external HTTP replies. They check Unicode text, article notes, submitted fields, response formats, and whether rejected requests avoid external calls. These provide regression checks for future framework changes without requiring real service access.

`--check` runs Django's system checks with the same temporary settings. A test label selects a smaller set of tests; outgoing HTTP remains blocked. Tests that require external services are excluded from the default set. Running the existing client tests directly through Django can contact the configured services.

## Primary dependencies

`pyproject.toml` lists the four packages used directly by the application and its test runner, with exact `==` pins. Python is pinned to `3.8.20`. Supporting packages required by Django and requests are recorded in `uv.lock` at their original versions. `python-dotenv` replaces the previous environment-file reader. The historical `config/requirements.txt` remains for reference; install using uv and the lockfile.

The inventory below combines the historical declarations, current imports and configuration, and dependency relationships recorded in `uv.lock`.

| Package | Purpose and location |
| --- | --- |
| Django | Web framework, URL routing, settings, and test runner; declared in `config/requirements.txt` and used throughout `config/` and `illiad_app/`. Requires `pytz`. |
| requests | HTTP calls in the user, book, and article handlers under `illiad_app/lib/`, plus sample scripts. Declared in the historical requirements. Requires `certifi`, `chardet`, `idna`, and `urllib3`. |
| PyMySQL | MySQL driver declared in the historical requirements and registered as `MySQLdb` by `config/__init__.py`. SQLite local checks do not exercise a MySQL connection. |
| python-dotenv | Reads the outer `.env` in `config/settings.py` and dummy settings in `run_tests.py`. Pinned to the Python 3.8-compatible `1.0.1` release. |

Dependency cleanup:

- `illiad3` and `beautifulsoup4` were present in the original environment but are unused by the current application, tests, and sample scripts. Both were removed, along with the `illiad3` Git-source entry.
- `certifi`, `chardet`, `idna`, `urllib3`, and `pytz` are required by requests or Django. They remain installed through `uv.lock` and do not need separate entries in the application's direct dependency list.
- `shellvars-py` is replaced by `python-dotenv`; application code no longer imports it. The historical requirements still record the old declaration.
- `pip`, `setuptools`, and `wheel` are installation tools rather than application dependencies. uv supplies isolated build requirements when needed.

The `local`, `staging`, and `prod` dependency groups are explicit and currently empty: each uses the same application dependencies. Tests use Django and the standard library. There is no additional test framework or interactive-tool dependency.

After sustained confirmation that the converted application works normally, consider the preferred `package~=1.2.0` notation with patch zero for a later version update. Keep exact resolved versions in `uv.lock`, retain appropriate environment groups, and validate each group independently when making that change.
