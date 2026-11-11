"""
Runs selected Django tests with dummy settings and blocked HTTP requests.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import execute_from_command_line
from dotenv import load_dotenv

DEFAULT_TESTS = [
    'illiad_app.tests.tests_article_mapper',
    'illiad_app.tests.tests_book_mapper',
    'illiad_app.tests.tests_request_flows',
    'illiad_app.tests.tests_environment',
    'illiad_app.tests.tests_client.ClientCloudBookRequest_Test.test__check_bad_method',
    'illiad_app.tests.tests_client.ClientCloudBookRequest_Test.test__check_bad_post_params',
    'illiad_app.tests.tests_client.ClientCloudArticleRequest_Test.test__check_bad_method',
    'illiad_app.tests.tests_client.ClientCloudArticleRequest_Test.test__check_bad_post_params',
]


def run_checks(labels: list[str], check_only: bool, verbosity: int) -> None:
    """
    Runs Django against temporary local data with outgoing HTTP blocked.
    Called by: main()
    """
    with TemporaryDirectory(prefix='illiad-tests-') as temporary_directory, patch.dict(os.environ):
        ## Ignore inherited application settings.
        for key in list(os.environ):
            if key.startswith('ILLIAD_WS__') or key == 'DJANGO_SETTINGS_MODULE':
                del os.environ[key]
        load_dotenv(Path(__file__).parent / '.env.example', override=True, interpolate=False)
        os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
        os.environ['ILLIAD_WS__DATABASES_NAME'] = ':memory:'
        os.environ['ILLIAD_WS__LOG_PATH'] = str(Path(temporary_directory) / 'tests.log')
        command = ['manage.py', 'check' if check_only else 'test', '--verbosity', str(verbosity)]
        if not check_only:
            command.extend(labels or DEFAULT_TESTS)
        ## Keep Django startup from reading the outer directory's real .env.
        with patch('dotenv.load_dotenv', return_value=False), patch(
            'requests.sessions.Session.request', side_effect=RuntimeError('External HTTP is disabled in run_tests.py.')
        ):
            execute_from_command_line(command)


def main() -> None:
    """
    Parses options for local checks and selected tests.
    Called by: the command-line entry point.
    """
    parser = argparse.ArgumentParser(
        description='Run mapper and API request tests using dummy settings and an in-memory database. '
        'Ignores application environment settings and blocks outgoing requests made with requests.'
    )
    parser.add_argument('labels', nargs='*', help='Optional Django test labels; HTTP remains blocked.')
    parser.add_argument('--check', action='store_true', help='Run Django system checks instead of tests.')
    parser.add_argument('--verbosity', type=int, choices=(0, 1, 2, 3), default=1)
    args = parser.parse_args()
    if args.check and args.labels:
        parser.error('--check cannot be combined with test labels.')
    run_checks(args.labels, args.check, args.verbosity)


if __name__ == '__main__':
    main()
