"""
Checks the outer dotenv location and isolation of the local test runner.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase


class DotenvSettingsTests(TestCase):
    def setUp(self) -> None:
        """
        Copies application files into a temporary outer/project layout.
        Called by: the test runner.
        """
        super().setUp()
        temporary_directory = TemporaryDirectory(prefix='illiad-dotenv-')
        self.addCleanup(temporary_directory.cleanup)
        self.outer = Path(temporary_directory.name)
        self.project = self.outer / 'project'
        self.project.mkdir()
        self.other_directory = self.outer / 'unrelated-directory'
        self.other_directory.mkdir()
        source = Path(__file__).resolve().parents[2]
        for name in ('config', 'illiad_app'):
            shutil.copytree(source / name, self.project / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        for name in ('manage.py', 'run_tests.py', '.env.example'):
            shutil.copyfile(source / name, self.project / name)

    def run_python(self, script: str, *arguments: str) -> subprocess.CompletedProcess[str]:
        """
        Runs copied application code with a separate environment and working directory.
        Called by: the dotenv tests.
        """
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith('ILLIAD_WS__') and key not in ('DJANGO_SETTINGS_MODULE', 'PYTHON_DOTENV_DISABLED')
        }
        environment['PYTHONPATH'] = str(self.project)
        environment['ILLIAD_WS__SECRET_KEY'] = 'inherited-value'
        environment['ILLIAD_WS__ENV_SETTINGS_PATH'] = str(self.other_directory / '.env')
        environment['DOTENV_TEST_EXPANSION'] = 'should-not-expand'
        return subprocess.run(
            [sys.executable, '-c', script, *arguments],
            cwd=self.other_directory,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_settings_load_outer_dotenv_independently_of_working_directory(self) -> None:
        """
        Checks the outer file wins over inherited values, other files, and the obsolete selector.
        """
        dotenv = (self.project / '.env.example').read_text()
        dotenv = dotenv.replace('local-checks-only-not-a-real-secret', 'outer-${DOTENV_TEST_EXPANSION}')
        (self.outer / '.env').write_text(dotenv)
        for directory in (self.project, self.other_directory):
            (directory / '.env').write_text("ILLIAD_WS__SECRET_KEY='wrong-file'\n")

        result = self.run_python(
            'import json, runpy, sys; settings = runpy.run_path(sys.argv[1]); '
            'print(json.dumps([settings["SECRET_KEY"], settings["BASE_DIR"], settings["DEBUG"]]))',
            str(self.project / 'config' / 'settings.py'),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), ['outer-${DOTENV_TEST_EXPANSION}', str(self.project.resolve()), False])

    def test_test_runner_does_not_read_outer_dotenv(self) -> None:
        """
        Checks test startup reads only dummy settings even when an outer file exists.
        """
        (self.outer / '.env').write_text("ILLIAD_WS__DEBUG_JSON='invalid-json-from-outer-file'\n")
        script = """
import runpy
import os
import sys
from pathlib import Path
from unittest.mock import patch

import dotenv

runner = Path(sys.argv[1])
sys.argv = [str(runner), '--check']
os.environ['PYTHON_DOTENV_DISABLED'] = '1'
with patch('dotenv.load_dotenv', wraps=dotenv.load_dotenv) as loader:
    runpy.run_path(str(runner), run_name='__main__')
    loader.assert_called_once_with(runner.parent / '.env.example', override=True, interpolate=False)
from django.conf import settings
assert settings.DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3'
assert settings.DATABASES['default']['NAME'] == ':memory:'
assert settings.SECRET_KEY == 'local-checks-only-not-a-real-secret'
"""

        result = self.run_python(script, str(self.project / 'run_tests.py'))

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_management_and_wsgi_start_with_outer_settings(self) -> None:
        """
        Checks both entry points start with temporary settings and the same dotenv loader.
        """
        dotenv = (self.project / '.env.example').read_text()
        dotenv = dotenv.replace('local.log', str(self.outer / 'startup.log'))
        (self.outer / '.env').write_text(dotenv)
        script = """
import os
import runpy
import sys
from pathlib import Path
from unittest.mock import patch

import dotenv

project = Path(sys.argv[1]).resolve()
entry_point = sys.argv[2]
with patch('dotenv.load_dotenv', wraps=dotenv.load_dotenv) as loader, patch(
    'requests.sessions.Session.request', side_effect=RuntimeError('External HTTP is disabled.')
), patch('requests.sessions.Session.send', side_effect=RuntimeError('External HTTP is disabled.')):
    if entry_point == 'manage':
        sys.argv = [str(project / 'manage.py'), 'check']
        runpy.run_path(str(project / 'manage.py'), run_name='__main__')
    else:
        from config.passenger_wsgi import application
        from django.core.handlers.wsgi import WSGIHandler
        assert isinstance(application, WSGIHandler)
    loader.assert_called_once_with(project.parent / '.env', override=True, interpolate=False)
    from django.conf import settings
    assert settings.SECRET_KEY == 'local-checks-only-not-a-real-secret'
    assert settings.DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3'
"""
        for entry_point in ('manage', 'wsgi'):
            with self.subTest(entry_point=entry_point):
                result = self.run_python(script, str(self.project), entry_point)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_test_runner_blocks_regular_and_prepared_http_requests(self) -> None:
        """
        Checks the runner blocks HTTP before either request path can contact a service.
        """
        script = """
from unittest.mock import patch

import requests
import run_tests

def check_requests(command):
    prepared = requests.Request('GET', 'https://example.invalid/').prepare()
    for call, args in ((requests.get, ('https://example.invalid/',)), (requests.Session().send, (prepared,))):
        try:
            call(*args)
        except RuntimeError as error:
            assert str(error) == 'External HTTP is disabled in run_tests.py.'
        else:
            raise AssertionError('Outgoing HTTP was not blocked')

with patch('run_tests.execute_from_command_line', side_effect=check_requests) as execute:
    run_tests.run_checks([], True, 0)
    execute.assert_called_once()
"""
        result = self.run_python(script)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_mysql_driver_loads_without_changing_its_version(self) -> None:
        """
        Checks the installed driver passes Django's backend import without connecting.
        """
        script = """
import pymysql
upstream_version = pymysql.version_info
import config
from django.db.backends.mysql.base import Database, DatabaseWrapper
assert Database is pymysql
assert pymysql.version_info == upstream_version
wrapper = DatabaseWrapper({'NAME': 'unused'}, alias='driver-check')
assert wrapper.connection is None
"""
        result = self.run_python(script)
        self.assertEqual(result.returncode, 0, result.stderr)
