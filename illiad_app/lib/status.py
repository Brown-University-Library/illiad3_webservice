# -*- coding: utf-8 -*-

import datetime, logging, pprint, random, time
from illiad_app import settings_app
from illiad_app.lib.illiad3.account import Status as LibStatusModule


log = logging.getLogger(__name__)
# status_module = LibStatusModule( settings_app.ILLIAD_REMOTE_AUTH_URL, settings_app.ILLIAD_REMOTE_AUTH_KEY )


class CheckStatusHandler( object ):

    def __init__( self ):
        self.request_id = random.randint( 1111, 9999 )  # to follow logic if simultaneous hits
        self.status_module = LibStatusModule( settings_app.ILLIAD_REMOTE_AUTH_URL, settings_app.ILLIAD_REMOTE_AUTH_KEY )

    def data_check( self, request ):
        """ Checks data.
            Called by views.check_status_via_shib() """
        log.debug( '%s - request.GET, `%s`' % (self.request_id, request.GET) )
        return_val = 'invalid'
        if 'users' in request.GET.keys():
            return_val = 'valid'
        log.debug( '%s - return_val, `%s`' % (self.request_id, return_val) )
        return return_val

    def check_statuses( self, request ):
        """ Handles status check(s).
            Called by views.check_status_via_shib() """
        users = request.GET['users']
        log.debug( '%s - users, ```%s```' % (self.request_id, users) )
        user_list = users.split( ',' )
        log.debug( '%s - user_list, ```%s```' % (self.request_id, user_list) )
        result_dct = {}
        for user in user_list:
            result_dct[user] = self.status_module.check_user_status( user )
            time.sleep( .5 )
        log.debug( '%s - result_dct, ```%s```' % (self.request_id, pprint.pformat(result_dct)) )
        return result_dct

    def prep_output_dct( self, start_time, request, data_dct ):
        """ Preps output-dct.
            Called by views.check_status_via_shib() """
        output_dct = {
            'request': {
                'url': '%s://%s%s?%s' % (
                    request.scheme,
                    request.META.get( 'HTTP_HOST', '127.0.0.1' ),  # HTTP_HOST doesn't exist for client-tests
                    request.META.get('REQUEST_URI', request.META['PATH_INFO']),
                    request.META['QUERY_STRING'] ),
                'timestamp': str( start_time )
                },
            'response': self.prep_response_segment( start_time, data_dct ) }
        log.debug( 'output_dct, ```%s```' % pprint.pformat(output_dct) )
        return output_dct

    def prep_response_segment( self, start_time, data_dct ):
        """ Returns response part of context dct.
            Called by update_response_dct() """
        response_dct = {
            'elapsed_time': str( datetime.datetime.now() - start_time ),
            'status_data': data_dct
            }
        return response_dct

    ## end class CheckStatusHandler()


class UpdateStatusHandler( object ):

    def __init__( self ):
        self.request_id = random.randint( 1111, 9999 )  # to follow logic if simultaneous hits
        self.status_module = LibStatusModule( settings_app.ILLIAD_REMOTE_AUTH_URL, settings_app.ILLIAD_REMOTE_AUTH_KEY )
        self.legit_statuses = [ 'Distance Ed Grad', 'Faculty', 'Graduate', 'Staff', 'Undergraduate' ]
        self.current_status = None
        self.output_dct = None

    def data_check( self, request ):
        """ Checks data.
            Called by views.update_status() """
        # log.debug( '%s - request.POST, `%s`' % (self.request_id, request.POST) )
        return_val = 'invalid'
        ( return_val, post_keys, source_ip ) = ( 'invalid', request.POST.keys(), request.META.get('REMOTE_ADDR', 'unavailable') )
        if 'user' in post_keys and 'requested_status' in post_keys and 'auth_key' in post_keys:
            if request.POST['auth_key'] == settings_app.API_KEY:
                if source_ip in settings_app.LEGIT_IPS:
                    if request.POST['requested_status'] in self.legit_statuses:
                        return_val = 'valid'
        if return_val == 'invalid':
            log.debug( 'validation failed; post-keys, ```%s```; ip, `%s`; requested_status, ```%s```' % (list(post_keys), source_ip, request.POST['requested_status']) )
        log.debug( '%s - return_val, `%s`' % (self.request_id, return_val) )
        return return_val

    def manage_status_update( self, request, start_time ):
        """ Manager for updating status.
            Called by views.update_status() """
        self.initialize_output_dct( request, start_time )
        ( user, requested_status ) = ( request.POST['user'], request.POST['requested_status'] )
        self.current_status = self.status_module.check_user_status( user )  # illiad3.account.Status()
        self.output_dct['response']['initial_status'] = self.current_status
        self.check_current_status( self.current_status, requested_status, start_time )
        if self.output_dct['response']['error']:
            return self.output_dct
        self.update_status( user, requested_status )
        self.output_dct['response']['elapsed_time'] = str( datetime.datetime.now() - start_time )
        log.debug( 'final output_dct, ```%s```' % pprint.pformat(self.output_dct) )
        return self.output_dct

    def initialize_output_dct( self, request, start_time ):
        """ Sets up initial output_dct.
            Called by manage_status_update() """
        self.output_dct = {
            'request': {
                'url': '%s://%s%s' % ( request.scheme, request.META.get('HTTP_HOST', '127.0.0.1'), request.META.get('REQUEST_URI', request.META['PATH_INFO']) ),  # HTTP_HOST doesn't exist for client-tests
                'payload': { 'user': request.POST['user'], 'requested_status': request.POST['requested_status'], 'auth_key': 'xxxxxxxxxx' },
                'timestamp': str( start_time )
                },
            'response': { 'initial_status': None, 'updated_status': None, 'error': None, 'elapsed_time': None
                }
            }
        log.debug( 'initial output_dct, ```%s```' % pprint.pformat(self.output_dct) )
        return

    def check_current_status( self, current_status, requested_status, start_time ):
        """ Checks current status and updates output_dct if needed.
            Called by manage_status_update() """
        if current_status.strip().lower() == requested_status.strip().lower():
            self.output_dct['response']['error'] = 'Status not updated; existing status is already `%s`.' % current_status
        elif current_status in [ 'DISAVOWED', 'UNREGISTERED' ]:
            self.output_dct['response']['error'] = 'Status not updated; existing status is `%s`.' % current_status
        if self.output_dct['response']['error']:
            self.output_dct['response']['elapsed_time'] = str( datetime.datetime.now() - start_time )
        log.debug( 'check_current_status output_dct, ```%s```' % pprint.pformat(self.output_dct) )
        return

    def update_status( self, user, requested_status ):
        """ Calls module's update-status, and prepares output-dct.
            Called by manage_status_update() """
        ( result, err ) = self.status_module.update_user_status( user, requested_status )
        if err:
            self.output_dct['response']['error'] = err
            # self.prep_status_not_updated_response( err )
        else:
            self.output_dct['response']['updated_status'] = requested_status.strip()
            # self.prep_status_updated_response()
        log.debug( 'output_dct, ```%s```' % pprint.pformat(self.output_dct) )
        return

    ## end clas UpdateStatusHandler()
