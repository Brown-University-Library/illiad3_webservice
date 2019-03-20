# -*- coding: utf-8 -*-

import logging
from illiad_app import settings_app


log = logging.getLogger(__name__)


def check_basic_auth( self, request ):
    """ Checks for any, and correct, http-basic-auth info, returns boolean.
        Called by views.try_again() """
    basic_auth_ok = False
    auth_info = request.META.get( 'HTTP_AUTHORIZATION', None )
    if ( auth_info and auth_info.startswith('Basic ') ):
        basic_info = auth_info.lstrip( 'Basic ' )
        decoded_basic_info = basic_info.decode( 'base64' )
        ( received_username, received_password ) = decoded_basic_info.rsplit( ':', 1 )   # cool; 'rsplit-1' solves problem if 'username' contains one or more colons
        if received_username == settings_app.BASIC_AUTH_USER and received_password == settings_app.BASIC_AUTH_PASSWORD:
            basic_auth_ok = True
    log.debug( 'basic_auth_ok, `%s`' % basic_auth_ok )
    return basic_auth_ok

def display_prompt( self ):
    """ Builds http-basic-auth response which brings up username/password dialog box.
        Not used -- for example usage, see easyscan_app.views.try_again() """
    response = HttpResponse()
    response.status_code = 401
    response['WWW-Authenticate'] = 'Basic realm="brown-illiad-api"'
    return response
