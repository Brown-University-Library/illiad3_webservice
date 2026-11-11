"""
Checks complete API requests using synthetic data and simulated HTTP replies.
"""

from __future__ import annotations

import base64
import json
import os
from collections.abc import Mapping
from unittest.mock import ANY, patch
from urllib.parse import quote

from django.http import HttpResponse
from django.test import Client, SimpleTestCase
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
