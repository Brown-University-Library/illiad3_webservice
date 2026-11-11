import base64
import binascii
import logging
from hmac import compare_digest

from django.http import HttpRequest, HttpResponse

from illiad_app import settings_app

log = logging.getLogger(__name__)


def check_basic_auth(request: HttpRequest) -> bool:
    """
    Checks the configured Basic credentials and safely handles decoding failures.
    Called by: CloudCheckUserHandler.data_check()
    """
    basic_auth_ok = False
    auth_info = request.META.get('HTTP_AUTHORIZATION')
    if isinstance(auth_info, str) and auth_info.startswith('Basic '):
        try:
            ## Preserve the old decoder's formatting tolerance; compare decoded credentials exactly below.
            decoded_credentials = base64.b64decode(auth_info[6:])
        except (binascii.Error, ValueError):
            log.debug('Rejecting malformed Basic authorization.')
        else:
            expected_credentials = f'{settings_app.BASIC_AUTH_USER}:{settings_app.BASIC_AUTH_PASSWORD}'.encode()
            basic_auth_ok = compare_digest(decoded_credentials, expected_credentials)
    log.debug(f'basic_auth_ok, ``{basic_auth_ok}``')
    return basic_auth_ok


def display_prompt() -> HttpResponse:
    """
    Builds a Basic-auth response that displays a username and password dialog.
    Called by: no current application endpoint; retained for existing imports.
    """
    response = HttpResponse(status=401)
    response['WWW-Authenticate'] = 'Basic realm="brown-illiad-api"'
    return response
