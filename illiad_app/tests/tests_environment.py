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
        for name in ('run_tests.py', '.env.example'):
            shutil.copyfile(source / name, self.project / name)

    def run_python(self, script: str, *arguments: str) -> subprocess.CompletedProcess[str]:
        """
        Runs copied application code with a separate environment and working directory.
        Called by: the dotenv tests.
        """
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith('ILLIAD_WS__') and key != 'DJANGO_SETTINGS_MODULE'
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
import sys
from pathlib import Path
from unittest.mock import patch

import dotenv

runner = Path(sys.argv[1])
sys.argv = [str(runner), '--check']
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
