"""
Checks complete API requests using synthetic data and simulated HTTP replies.
"""

from __future__ import annotations

import base64
import json
import os
from collections.abc import Mapping
from itertools import product
from unittest.mock import ANY, patch
from urllib.parse import quote, urlencode

from django.core.exceptions import BadRequest
from django.http import HttpResponse
from django.test import Client, SimpleTestCase, override_settings
from requests import Response

from illiad_app import settings_app


def json_reply(data: Mapping[str, object], status_code: int = 200) -> Response:
    """
    Builds a JSON HTTP reply without contacting a service.
    Called by: RequestFlowTests test methods.
    """
    response = Response()
    response.status_code = status_code
    response.url = 'https://example.invalid/reply/'
    response.encoding = 'utf-8'
    response._content = json.dumps(dict(data)).encode('utf-8')
    response.headers['Content-Type'] = 'application/json'
    return response


class RequestFlowTests(SimpleTestCase):
    def setUp(self) -> None:
        """
        Sets dummy application values and replaces outgoing HTTP calls.
        Called by: the Django test runner.
        """
        super().setUp()
        self.client = Client(enforce_csrf_checks=True)
        application_settings = patch.multiple(
            settings_app,
            API_KEY='test-internal-key',
            BASIC_AUTH_USER='test-client',
            BASIC_AUTH_PASSWORD='test-password',
            LEGIT_IPS=['127.0.0.1'],
            ILLIAD_API_URL='https://example.invalid/illiad/',
            ILLIAD_API_KEY='test-upstream-key',
        )
        application_settings.start()
        self.addCleanup(application_settings.stop)
        environment = patch.dict(os.environ, {'ILLIAD_WS__OFFICIAL_ILLIAD_API_KEY': 'test-upstream-key'})
        environment.start()
        self.addCleanup(environment.stop)
        get_patcher = patch('requests.get')
        self.http_get = get_patcher.start()
        self.addCleanup(get_patcher.stop)
        post_patcher = patch('requests.post')
        self.http_post = post_patcher.start()
        self.addCleanup(post_patcher.stop)
        self.http_get.side_effect = AssertionError('Unexpected external GET in test.')
        self.http_post.side_effect = AssertionError('Unexpected external POST in test.')
        self.user_form = {
            'auth_key': 'test-internal-key',
            'auth_id': 'test-reader',
            'first_name': 'Zoë',
            'last_name': 'García',
            'department': 'Art & Design',
            'email': 'reader@example.invalid',
            'phone': 'unavailable',
            'status': 'Graduate',
        }

    def assert_submission(self, endpoint: str, expected_fields: dict[str, object]) -> None:
        """
        Checks the destination, credentials, and submitted application fields.
        Called by: the successful transaction and user-creation tests.
        """
        self.http_post.assert_called_once()
        call = self.http_post.call_args
        if call is None:
            self.fail('No ILLiad submission was recorded.')
        self.assertEqual(call.args, ('https://example.invalid/illiad/' + endpoint,))
        self.assertEqual(call.kwargs['headers']['ApiKey'], 'test-upstream-key')
        data = call.kwargs['data']
        self.assertEqual({key: data[key] for key in expected_fields}, expected_fields)
        self.assertNotIn('auth_key', data)

    def test_book_request_submits_mapped_fields_and_returns_transaction(self) -> None:
        """
        Checks a book form through URL decoding, field mapping, and JSON output.
        """
        openurl = 'genre=book&title=Café+studies&notes=Please+keep+this+edition'
        self.http_get.side_effect = None
        self.http_get.return_value = json_reply(
            {
                'response': {
                    'bib': {
                        '_rfr': 'test-catalog',
                        'identifier': [{'type': 'isbn', 'id': '9780000000002'}, {'type': 'oclc', 'id': '123456'}],
                        'author': [{'name': 'García, Zoë'}],
                        'year': '2020',
                        'place_of_publication': None,
                        'publisher': 'Example Press',
                        'title': 'Café studies',
                    }
                },
            }
        )
        self.http_post.side_effect = None
        self.http_post.return_value = json_reply({'TransactionNumber': 12345})

        with self.assertLogs('illiad_app', level='DEBUG') as captured:
            response = self.client.post(
                '/v2/make_request/',
                {
                    'auth_key': 'test-internal-key',
                    'openurl': quote(openurl, safe=''),
                    'request_id': 'test-book',
                    'username': 'test-reader',
                },
            )

        assert isinstance(response, HttpResponse)
        self.assertNotIn('test-internal-key', '\n'.join(captured.output))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'].split(';')[0], 'application/json')
        self.assertEqual(json.loads(response.content), {'status': 'submission_successful', 'transaction_number': 12345})
        self.http_get.assert_called_once_with(ANY, params={'ourl': openurl}, timeout=30, verify=True)
        self.assert_submission(
            'transaction',
            {
                'DocumentType': 'Book',
                'RequestType': 'Loan',
                'ProcessType': 'Borrowing',
                'Username': 'test-reader',
                'LoanTitle': 'Café studies',
                'LoanAuthor': 'García, Zoë',
                'LoanDate': '2020',
                'LoanPlace': '',
                'LoanPublisher': 'Example Press',
                'ISSN': '9780000000002',
                'ESPNumber': '123456',
                'CitedIn': 'test-catalog',
                'CitedTitle': 'NOTES: Please keep this edition',
            },
        )

    def test_article_request_preserves_notes_and_returns_transaction(self) -> None:
        """
        Checks article-specific fields and semicolon-containing notes through Django.
        """
        openurl = 'genre=article&title=Café+research&Notes=First+note;+second+note'
        self.http_get.side_effect = None
        self.http_get.return_value = json_reply(
            {
                'response': {
                    'bib': {
                        '_rfr': 'test-index',
                        'journal': {'name': 'Example Journal'},
                        'title': 'Café research',
                        'author': [{'name': 'García, Zoë'}],
                        'volume': '12',
                        'issue': None,
                        'year': '2021',
                        'pages': '10-18',
                        'identifier': [{'type': 'issn', 'id': '1234-5678'}, {'type': 'oclc', 'id': '654321'}],
                    }
                },
            }
        )
        self.http_post.side_effect = None
        self.http_post.return_value = json_reply({'TransactionNumber': 67890})

        with self.assertLogs('illiad_app', level='DEBUG') as captured:
            response = self.client.post(
                '/request_article/',
                {
                    'auth_key': 'test-internal-key',
                    'openurl': quote(openurl, safe=''),
                    'request_id': 'test-article',
                    'username': 'test-reader',
                },
            )

        assert isinstance(response, HttpResponse)
        self.assertNotIn('test-internal-key', '\n'.join(captured.output))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'].split(';')[0], 'application/json')
        self.assertEqual(json.loads(response.content), {'status': 'submission_successful', 'transaction_number': 67890})
        self.http_get.assert_called_once_with(ANY, params={'ourl': openurl}, timeout=30, verify=True)
        self.assert_submission(
            'transaction',
            {
                'DocumentType': 'Article',
                'RequestType': 'Article',
                'ProcessType': 'Borrowing',
                'Username': 'test-reader',
                'PhotoJournalTitle': 'Example Journal',
                'PhotoArticleTitle': 'Café research',
                'PhotoArticleAuthor': 'García, Zoë',
                'PhotoJournalVolume': '12',
                'PhotoJournalIssue': '',
                'PhotoJournalYear': '2021',
                'PhotoJournalInclusivePages': '10-18',
                'ISSN': '1234-5678',
                'ESPNumber': '654321',
                'CitedIn': 'test-index',
                'CitedTitle': 'NOTES: First note; second note',
            },
        )

    def test_create_user_preserves_form_values_and_omits_auth_key_from_response(self) -> None:
        """
        Checks user creation, Unicode form values, and the returned registration result.
        """
        self.http_post.side_effect = None
        self.http_post.return_value = json_reply({'UserName': 'test-reader'})

        response = self.client.post('/create_user/', self.user_form, REMOTE_ADDR='127.0.0.1')

        assert isinstance(response, HttpResponse)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'].split(';')[0], 'application/json')
        result = json.loads(response.content)
        self.assertEqual(set(result), {'request', 'response'})
        self.assertEqual(result['response']['status_data'], {'status': 'Registered', 'status_code': 200})
        self.assertEqual(result['response']['raw_data']['UserName'], 'test-reader')
        self.assertEqual(
            result['request']['params'], {key: value for key, value in self.user_form.items() if key != 'auth_key'}
        )
        self.assert_submission(
            'Users',
            {
                'Username': 'test-reader',
                'FirstName': 'Zoë',
                'LastName': 'García',
                'Department': 'Art & Design',
                'EmailAddress': 'reader@example.invalid',
                'Phone': 'unavailable',
                'Status': 'Graduate',
            },
        )
        self.http_get.assert_not_called()

    def test_authenticated_user_lookup_returns_expected_statuses(self) -> None:
        """
        Checks Basic-auth requests and the status flags callers receive for four user states.
        """
        credentials = base64.b64encode(b'test-client:test-password').decode('ascii')
        cases = [
            (
                'registered',
                {'UserName': 'test-reader', 'Cleared': 'Yes'},
                200,
                {
                    'authenticated': True,
                    'registered': True,
                    'blocked': False,
                    'disavowed': False,
                    'interpreted_new_user': False,
                },
            ),
            (
                'blocked',
                {'UserName': 'test-reader', 'Cleared': 'B'},
                200,
                {
                    'authenticated': True,
                    'registered': True,
                    'blocked': True,
                    'disavowed': False,
                    'interpreted_new_user': False,
                },
            ),
            (
                'disavowed',
                {'UserName': 'test-reader', 'Cleared': 'DIS'},
                200,
                {
                    'authenticated': False,
                    'registered': False,
                    'blocked': False,
                    'disavowed': True,
                    'interpreted_new_user': False,
                },
            ),
            (
                'not found',
                {'Message': 'User not found'},
                404,
                {
                    'authenticated': False,
                    'registered': False,
                    'blocked': False,
                    'disavowed': False,
                    'interpreted_new_user': True,
                },
            ),
        ]
        for name, upstream_data, status_code, expected in cases:
            with self.subTest(user_state=name):
                self.http_get.reset_mock()
                self.http_get.side_effect = None
                self.http_get.return_value = json_reply(upstream_data, status_code)

                response = self.client.get(
                    '/check_user/', {'user': 'test-reader'}, HTTP_AUTHORIZATION='Basic ' + credentials
                )

                assert isinstance(response, HttpResponse)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response['Content-Type'].split(';')[0], 'application/json')
                result = json.loads(response.content)
                self.assertEqual(set(result), {'request', 'response'})
                self.assertEqual(result['response']['status_data'], expected)
                self.http_get.assert_called_once_with(
                    'https://example.invalid/illiad/Users/test-reader',
                    headers=ANY,
                    timeout=60,
                    verify=True,
                )
                call = self.http_get.call_args
                if call is None:
                    self.fail('No user lookup was recorded.')
                self.assertEqual(call.kwargs['headers']['ApiKey'], 'test-upstream-key')
                self.http_post.assert_not_called()

    def test_rejected_requests_do_not_contact_illiad(self) -> None:
        """
        Checks that rejected credentials and source addresses stop requests before any HTTP call.
        """
        for key, address in [('wrong-key', '127.0.0.1'), ('test-internal-key', '192.0.2.10')]:
            with self.subTest(auth_key=key, source_address=address):
                form = dict(self.user_form, auth_key=key)

                response = self.client.post('/create_user/', form, REMOTE_ADDR=address)

                assert isinstance(response, HttpResponse)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.content, b'Bad Request')
                self.http_get.assert_not_called()
                self.http_post.assert_not_called()

        with self.subTest(authentication='incorrect Basic-auth password'):
            credentials = base64.b64encode(b'test-client:wrong-password').decode('ascii')
            response = self.client.get('/check_user/', {'user': 'test-reader'}, HTTP_AUTHORIZATION='Basic ' + credentials)

            assert isinstance(response, HttpResponse)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.content, b'Bad Request')
            self.http_get.assert_not_called()
            self.http_post.assert_not_called()

    def test_urlencoded_user_form_preserves_unicode_and_repeated_fields(self) -> None:
        """
        Checks UTF-8 aliases and ordinary HTTPS forms keep Unicode values and the last repeated value.
        """
        self.http_post.side_effect = None
        self.http_post.return_value = json_reply({'UserName': 'test-reader'})
        body = urlencode([*self.user_form.items(), ('first_name', 'Renée')])

        for suffix in ('', '; charset=UTF-8', '; charset=utf-8', '; charset=utf8', '; charset=utf_8', '; charset=cp65001'):
            with self.subTest(charset=suffix):
                self.http_post.reset_mock()
                response = self.client.post(
                    '/create_user/',
                    body,
                    content_type='application/x-www-form-urlencoded' + suffix,
                    secure=True,
                    REMOTE_ADDR='127.0.0.1',
                    HTTP_ORIGIN='https://legacy-client.example.invalid',
                )

                assert isinstance(response, HttpResponse)
                self.assertEqual(response.status_code, 200)
                result = json.loads(response.content)
                self.assertEqual(result['request']['params']['first_name'], 'Renée')
                self.assertEqual(result['request']['params']['last_name'], 'García')
                self.assertEqual(result['response']['status_data'], {'status': 'Registered', 'status_code': 200})
                self.assert_submission('Users', {'Username': 'test-reader', 'FirstName': 'Renée', 'LastName': 'García'})

    def test_rejected_form_charset_returns_fixed_instructions(self) -> None:
        """
        Checks rejected form charsets receive safe instructions in either debug mode without external calls.
        """
        paths = ('/create_user/', '/v2/make_request/', '/request_article/')
        charsets = ('ISO-8859-1', 'UTF-16', 'utf-8-sig')
        body = urlencode(dict(self.user_form, private_note='private-form-value'))
        for path, charset, debug in product(paths, charsets, (False, True)):
            with self.subTest(path=path, charset=charset, debug=debug), override_settings(DEBUG=debug):
                response = self.client.post(
                    path,
                    body.encode(),
                    content_type='application/x-www-form-urlencoded; charset=' + charset,
                    HTTP_AUTHORIZATION='Basic private-header-value',
                )

                assert isinstance(response, HttpResponse)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response['Content-Type'], 'text/plain; charset=utf-8')
                self.assertEqual(
                    response.content,
                    b'Bad Request: Send application/x-www-form-urlencoded data encoded as UTF-8. '
                    b'Omit the charset parameter from Content-Type, or use charset=UTF-8.',
                )
                self.assertEqual(response['X-Frame-Options'], 'SAMEORIGIN')
                self.http_get.assert_not_called()
                self.http_post.assert_not_called()

    @override_settings(DEBUG=False)
    def test_other_bad_requests_do_not_receive_encoding_instructions(self) -> None:
        """
        Checks unrelated exceptions and invalid hosts keep their generic response even with a bad charset.
        """
        with patch('illiad_app.views.CloudCreateUserHandler', side_effect=BadRequest('private-exception-detail')):
            response = self.client.post(
                '/create_user/',
                b'private-form-value',
                content_type='application/x-www-form-urlencoded; charset=ISO-8859-1',
            )

        assert isinstance(response, HttpResponse)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response['Content-Type'], 'text/html; charset=utf-8')
        self.assertNotIn(b'private-exception-detail', response.content)
        self.assertNotIn(b'charset', response.content)

        with override_settings(ALLOWED_HOSTS=['testserver']):
            response = self.client.post(
                '/create_user/',
                b'private-form-value',
                content_type='application/x-www-form-urlencoded; charset=ISO-8859-1',
                HTTP_HOST='unlisted.example.invalid',
            )

        assert isinstance(response, HttpResponse)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response['Content-Type'], 'text/html; charset=utf-8')
        self.assertNotIn(b'charset', response.content)
        self.http_get.assert_not_called()
        self.http_post.assert_not_called()

    def test_basic_auth_accepts_configured_unicode_and_colons(self) -> None:
        """
        Checks configured credentials survive Base64 prefixes, Unicode, and colons.
        """
        cases = [
            ('j-reader', 'password'),
            ('legacy:reader', 'password'),
            ('reader', 'pass:word'),
            ('legacy;reader', 'pass;word'),
            ('Zoë', 'pässword'),
        ]
        for username, password in cases:
            with (
                self.subTest(username=username),
                patch.multiple(settings_app, BASIC_AUTH_USER=username, BASIC_AUTH_PASSWORD=password),
            ):
                self.http_get.reset_mock()
                self.http_get.side_effect = None
                self.http_get.return_value = json_reply({'UserName': 'test-reader', 'Cleared': 'Yes'})
                credentials = base64.b64encode(f'{username}:{password}'.encode()).decode('ascii')

                with self.assertLogs('illiad_app.lib.basic_auth', level='DEBUG') as captured:
                    response = self.client.get(
                        '/check_user/', {'user': 'test-reader'}, HTTP_AUTHORIZATION='Basic ' + credentials
                    )

                assert isinstance(response, HttpResponse)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(json.loads(response.content)['response']['status_data']['authenticated'])
                self.http_get.assert_called_once()
                self.http_post.assert_not_called()
                log_output = '\n'.join(captured.output)
                for private_value in (username, password, credentials):
                    self.assertNotIn(private_value, log_output)

    def test_basic_auth_preserves_legacy_base64_formatting(self) -> None:
        """
        Checks formatting tolerated by the old decoder still allows exactly matching credentials.
        """
        credentials = base64.b64encode(b'test-client:test-password').decode('ascii')
        self.http_get.side_effect = None
        self.http_get.return_value = json_reply({'UserName': 'test-reader', 'Cleared': 'Yes'})
        headers = [
            'Basic  ' + credentials,
            'Basic    ' + credentials,
            'Basic ' + credentials + ' \t',
            'Basic ' + credentials[:8] + ' \t' + credentials[8:],
            'Basic ' + credentials[:8] + '!' + credentials[8:],
        ]
        for header in headers:
            with self.subTest(authorization=header):
                self.http_get.reset_mock()
                response = self.client.get(
                    '/check_user/',
                    {'user': 'test-reader'},
                    HTTP_AUTHORIZATION=header,
                )

                assert isinstance(response, HttpResponse)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(json.loads(response.content)['response']['status_data']['authenticated'])
                self.http_get.assert_called_once()
                self.http_post.assert_not_called()

    def test_malformed_basic_auth_uses_existing_bad_request_response(self) -> None:
        """
        Checks undecodable values and incorrect credentials are rejected before any external request.
        """
        wrong_token = base64.b64encode(b'test-client:wrong-password').decode('ascii')
        headers = [
            '',
            'Bearer unrelated-token',
            'Basic ',
            'Basic !not-base64!',
            'Basic abc',
            'Basic é',
            'Basic ' + wrong_token[:8] + ' \t!' + wrong_token[8:],
            'Basic ' + base64.b64encode(b'no-separator').decode('ascii'),
            'Basic ' + base64.b64encode(b'\xff:password').decode('ascii'),
        ]
        for header in headers:
            with self.subTest(authorization=header):
                response = self.client.get('/check_user/', {'user': 'test-reader'}, HTTP_AUTHORIZATION=header)

                assert isinstance(response, HttpResponse)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.content, b'Bad Request')
                self.http_get.assert_not_called()
                self.http_post.assert_not_called()

    def test_root_and_missing_slash_redirects_keep_existing_targets(self) -> None:
        """
        Checks root and missing-slash GET redirects keep their status codes and query strings.
        """
        for path, status_code, target in [
            ('/', 302, '/info/'),
            ('/check_user?user=test-reader', 301, '/check_user/?user=test-reader'),
        ]:
            with self.subTest(path=path):
                response = self.client.get(path)

                assert isinstance(response, HttpResponse)
                self.assertEqual(response.status_code, status_code)
                self.assertEqual(response['Location'], target)
                self.http_get.assert_not_called()
                self.http_post.assert_not_called()

    @override_settings(ALLOWED_HOSTS=['testserver'])
    def test_unlisted_host_is_rejected_before_the_view(self) -> None:
        """
        Checks the configured host allowlist still rejects unknown hosts.
        """
        response = self.client.post('/create_user/', self.user_form, HTTP_HOST='unlisted.example.invalid')

        assert isinstance(response, HttpResponse)
        self.assertEqual(response.status_code, 400)
        self.http_get.assert_not_called()
        self.http_post.assert_not_called()
