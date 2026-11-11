
"""
Submits ILLiad request via hitting the ILLiad API instead of simulating browser GETs and POSTs.
Implemented in preparation for ILLiad cloud switch-over.
"""

import logging
import pprint
import unicodedata
import urllib.parse

import requests

from illiad_app import settings_app

log = logging.getLogger(__name__)


class BookRequestHandler:
    """ `Book` hardcoded for now, for easyBorrow requests.
        Will later do the `Article` manager for easyAccess requests, and then refactor for common features. """

    def __init__( self, request_id ):
        # self.request_id = random.randint( 1111, 9999 )  # to follow logic if simultaneous hits
        self.request_id = request_id
        self.API_KEY = settings_app.API_KEY

    def check_validity( self, request ):
        """ Checks post, auth_key, ip, & params.
            Called by views.cloud_book_request() """
        log.debug( '%s - starting check_validity()', self.request_id )
        return_val = False
        if request.method == 'POST' and self.check_params(request) is True:
            if request.POST['auth_key'] == self.API_KEY:
                return_val = True
            else:
                log.debug('%s - ip, `%s`', self.request_id, request.META.get('REMOTE_ADDR', 'unavailable'))
        log.debug( '%s - return_val, `%s`', self.request_id, return_val )
        return return_val

    def check_params( self, request ):
        """ Checks params.
            Called by check_validity() """
        return_val = None
        for param in [ 'auth_key', 'openurl', 'request_id', 'username' ]:
            log.debug( '%s - on param, `%s`', self.request_id, param )
            if param not in request.POST:
                return_val = False
                break
        return_val = return_val is None
        log.debug( '%s - return_val, `%s`', self.request_id, return_val )
        return return_val

    def manage_request( self, request):
        """ - Parses openurl
            - Prepares other params.
            - Submits request to illiad-cloud-api transaction endpoint.
            - Prepares response.
            Called by views.cloud_book_request() """
        param_builder = ILLiadParamBuilder( self.request_id )
        open_url_params = param_builder.parse_openurl( request.POST['openurl'] )
        full_illiad_params = self.add_additional_params( open_url_params, request.POST['username'] )
        cloud_api_response_dct = self.submit_transaction( full_illiad_params )
        # output_dct = self.prepare_V2_output_dct( cloud_api_response_dct )
        return cloud_api_response_dct

    def add_additional_params( self, param_dct, username ):
        """ Adds additional params needed for illiad-api submission.
            Called by manage_request() """
        param_dct['DocumentType'] = 'Book'
        param_dct['RequestType'] = 'Loan'
        param_dct['ProcessType'] = 'Borrowing'
        param_dct['Username'] = username
        log.debug( '%s - updated param_dct, ```%s```', self.request_id, pprint.pformat(param_dct) )
        return param_dct

    def submit_transaction( self, param_dct ):
        """ Submits request to illiad-api.
            Called by manage_request() """
        ( url, headers ) = self.prepare_submit_request()
        try:
            r = requests.post( url, data=param_dct, headers=headers, timeout=30, verify=True )
            response_dct = r.json()
            response_dct['added_status_code'] = r.status_code
            log.debug( '%s - response, ```%s```', self.request_id, pprint.pformat(response_dct) )
            return response_dct
        except Exception as e:
            message = f'exception submitting book transaction, ```{e!r}```'
            log.exception('%s - ```%s```', self.request_id, message)
            return { 'error': message }

    def prepare_submit_request( self ):
        """ Sets url & headers.
            Called by submit_transaction() """
        url = f'{settings_app.ILLIAD_API_URL}transaction'  # root url contains ending-slash
        log.debug( '%s - url, ```%s```', self.request_id, url )
        headers = {
            'Accept-Type': 'application/json; charset=utf-8',
            'ApiKey': settings_app.ILLIAD_API_KEY }
        return ( url, headers )

    def prepare_V2_output_dct( self, cloud_api_response_dct ):
        """ Prepares response expected by the easyBorrow v2 call.
            TODO: at some point, update to the more modern api-response format, and update easyBorrow accordingly to handle it.
            Called by views.cloud_book_request() """
        v2_response_dct = { 'status': 'submission_failed', 'message': 'see illiad-webservice logs for more info' }
        if 'TransactionNumber' in cloud_api_response_dct:
            v2_response_dct = { 'status': 'submission_successful', 'transaction_number': cloud_api_response_dct['TransactionNumber'] }
        log.debug( '%s - v2_response_dct, ```%s```', self.request_id, v2_response_dct )
        return v2_response_dct

    ## end class BookRequestHandler()


class ILLiadParamBuilder:
    """ Handles conversion of openurl and mapping to illiad-cloud-api keys. """

    def __init__( self, request_id ):
        # self.request_id = random.randint( 1111, 9999 )  # to follow logic if simultaneous hits
        self.request_id = request_id
        self.OURL_API_URL = 'https://library.brown.edu/bib_ourl_api/v1/ourl_to_bib/'

    def parse_openurl( self, openurl ):
        """ Prepares ILLiad-compatible params.
            Called by BookRequestHandler.manage_request() """
        log.debug( '%s - initial openurl, ```%s```', self.request_id, openurl )
        decoded_openurl_querystring = self.decode_openurl_querystring( openurl )
        params = { 'ourl': decoded_openurl_querystring }
        r = requests.get( self.OURL_API_URL, params=params, timeout=30, verify=True )
        log.debug( '%s - full url, ```%s```', self.request_id, r.url )
        log.debug( '%s - status_code, `%s`', self.request_id, r.status_code )
        bib_json_dct = r.json()
        log.debug( '%s - bib-dct, ```%s```', self.request_id, pprint.pformat(bib_json_dct) )
        notes = self.extract_notes( decoded_openurl_querystring )
        illiad_params = self.map_to_illiad_keys( bib_json_dct, notes )
        log.debug( '%s - illiad_params from openurl, ```%s`', self.request_id, pprint.pformat(illiad_params) )
        return illiad_params

    def decode_openurl_querystring( self, querystring ):
        """ Runs one decode on the querystring.
            Called by parse_openurl() """
        decoded_querystring = urllib.parse.unquote( querystring )
        log.debug( '%s - decoded_querystring, ```%s```', self.request_id, decoded_querystring )
        return decoded_querystring

    ## KEEP this commented-out function in case we determine we need to further decode the querystring
    # def decode_openurl_querystring( self, querystring ):
    #     """ Fully decodes the querystring.
    #         Called by parse_openurl() """
    #     ( last_try, decoded_querystring, flag ) = ( 'init', 'init', 'continue' )
    #     while flag == 'continue':
    #         decoded_querystring = urllib.parse.unquote( querystring )
    #         if decoded_querystring == last_try:
    #             log.debug( '%s - decoding done' % self.request_id )
    #             flag = 'stop'
    #         else:
    #             last_try = decoded_querystring
    #             log.debug( '%s - will decode once more; decoded_querystring currently, ```%s```' % (self.request_id, decoded_querystring) )
    #     log.debug( '%s - final decoded_querystring, ```%s```' % (self.request_id, decoded_querystring) )
    #     return decoded_querystring

    def extract_notes( self, decoded_openurl_querystring ):
        """ Returns notes-dct.
            Called by parse_openurl() """
        notes = 'no notes'
        parts_dct = urllib.parse.parse_qs( decoded_openurl_querystring )  # <https://pymotw.com/3/urllib.parse/>
        log.debug( '%s - parts_dct, ```%s```', self.request_id, pprint.pformat(parts_dct) )
        if 'notes' in parts_dct:
            notes = parts_dct['notes'][0]  # all values are in list
        log.debug( '%s - notes, ```%s```', self.request_id, notes )
        return notes

    def map_to_illiad_keys( self, bib_json_dct, notes ):
        """ Returns dct using illiad-cloud-api keys.
            Called by parse_openurl() """
        # defaults = {
        #     'RequestType': 'Book',
        #     'ProcessType' : 'Borrowing'
        #     }
        # user = {
        #     "Username" : None,  # fill later
        #     }
        mapper = Mapper( self.request_id )
        item = {
            'CitedIn': mapper.grab_sid( bib_json_dct ),  # often 'source-id/sid' in openurl
            'ESPNumber': mapper.grab_espn( bib_json_dct ),  # OCLC number
            'ISSN': mapper.grab_isbn( bib_json_dct ),  # really ISBN
            'LoanAuthor': mapper.grab_author( bib_json_dct ),
            'LoanDate': mapper.grab_date( bib_json_dct ),
            'LoanPlace': mapper.grab_place( bib_json_dct ),
            'LoanPublisher': mapper.grab_publisher( bib_json_dct ),
            'LoanTitle': mapper.grab_title( bib_json_dct ),
            # 'Notes': notes,
            'CitedTitle': f'NOTES: {notes}'  # work-around due to the fact that I can't submit Notes directly within this transaction
            }
        log.debug( '%s - illiad_dct, ```%s```', self.request_id, pprint.pformat(item) )
        return item

    ## end class ILLiadParamBuilder()


class Mapper:
    """ Extracts necessary values from bib_dct.
        Truncates data if necessary.
        - field lengths from <https://support.atlas-sys.com/hc/en-us/articles/360011812074> (scroll down to 'Transactions' table )
        - no field-length limits are set when above documentation lists `nvarchar(max)` """

    def __init__( self, request_id ):
        # self.request_id = random.randint( 1111, 9999 )  # to follow logic if simultaneous hits
        self.request_id = request_id

    def grab_sid( self, bib_dct ):
        """ Returns sid number.
            (no field-length limit)
            Called by ILLiadParamBuilder.map_to_illiad_keys() """
        sid = ''
        try:
            sid = bib_dct['response']['bib']['_rfr']
            if sid is None:
                sid = self.check_openurl_for_sid( bib_dct )
        except Exception:
            log.exception('Unable to map response field for request, ``%s``', self.request_id)
        log.debug( '%s - sid, `%s`', self.request_id, sid )
        return sid

    def check_openurl_for_sid( self, bib_dct ):
        """ Checks openurl for sid-like key.
            Called by grab_sid() """
        sid = ''
        parts_dct = urllib.parse.parse_qs( bib_dct['response']['decoded_openurl'] )
        for key in parts_dct:
            if 'sid' in key:
                sid = parts_dct[key][0]
        if sid is None:
            sid = ''
        log.debug( '%s - sid from openurl-check, `%s`', self.request_id, sid )
        return sid

    def grab_espn( self, bib_dct ):
        """ Returns oclc number.
            Called by ILLiadParamBuilder.map_to_illiad_keys() """
        oclc = ''
        try:
            identifiers = bib_dct['response']['bib']['identifier']
            for element_dct in identifiers:
                if element_dct['type'] == 'oclc':
                    oclc = element_dct['id']
                    break
        except Exception:
            log.exception('Unable to map response field for request, ``%s``', self.request_id)
        oclc = self.check_limit( string_value=oclc, limit=32 )
        log.debug( '%s - oclc, `%s`', self.request_id, oclc )
        return oclc

    def grab_isbn( self, bib_dct ):
        """ Returns isbn.
            Called by ILLiadParamBuilder.map_to_illiad_keys() """
        isbn = ''
        try:
            identifiers = bib_dct['response']['bib']['identifier']
            for element_dct in identifiers:
                if element_dct['type'] == 'isbn':
                    isbn = element_dct['id']
                    break
        except Exception:
            log.exception('Unable to map response field for request, ``%s``', self.request_id)
        isbn = self.check_limit( string_value=isbn, limit=20 )
        log.debug( '%s - isbn, `%s`', self.request_id, isbn )
        return isbn

    def grab_author( self, bib_dct ):
        """ Returns author.
            Called by ILLiadParamBuilder.map_to_illiad_keys() """
        author = ''
        try:
            authors = bib_dct['response']['bib']['author']
            for element_dct in authors:
                if 'name' in element_dct:
                    author = element_dct['name']
        except Exception:
            log.exception('Unable to map response field for request, ``%s``', self.request_id)
        author = self.check_limit( string_value=author, limit=100 )
        log.debug( '%s - author, `%s`', self.request_id, author )
        return author

    def grab_date( self, bib_dct ):
        """ Returns date number.
            Called by ILLiadParamBuilder.map_to_illiad_keys() """
        date = ''
        try:
            date = bib_dct['response']['bib']['year']
        except Exception:
            log.exception('Unable to map response field for request, ``%s``', self.request_id)
        date = self.check_limit( string_value=date, limit=30 )
        log.debug( '%s - date, `%s`', self.request_id, date )
        return date

    def grab_place( self, bib_dct ):
        """ Returns place number.
            Called by ILLiadParamBuilder.map_to_illiad_keys() """
        place = ''
        try:
            place = bib_dct['response']['bib']['place_of_publication']
            if place is None:
                place = ''
        except Exception:
            log.exception('Unable to map response field for request, ``%s``', self.request_id)
        place = self.check_limit( string_value=place, limit=30 )
        log.debug( '%s - place, `%s`', self.request_id, place )
        return place

    def grab_publisher( self, bib_dct ):
        """ Returns publisher number.
            Called by ILLiadParamBuilder.map_to_illiad_keys() """
        publisher = ''
        try:
            publisher = bib_dct['response']['bib']['publisher']
            if publisher is None:
                publisher = ''
        except Exception:
            log.exception('Unable to map response field for request, ``%s``', self.request_id)
        publisher = self.check_limit( string_value=publisher, limit=50 )
        log.debug( '%s - publisher, `%s`', self.request_id, publisher )
        return publisher

    def grab_title( self, bib_dct ):
        """ Returns title number.
            Called by ILLiadParamBuilder.map_to_illiad_keys() """
        title = ''
        try:
            title = bib_dct['response']['bib']['title']
            if title is None:
                title = ''
        except Exception:
            log.exception('Unable to map response field for request, ``%s``', self.request_id)
        title = self.check_limit( string_value=title, limit=255 )
        log.debug( '%s - title, `%s`', self.request_id, title )
        return title

    def check_limit( self, string_value, limit ):
        """ Returns truncated string with elipsis if necessary.
            Called by many class functions. """
        checked_value = string_value
        elip = unicodedata.normalize( 'NFC', '…' ); assert len(elip) == 1  # to make explicit it's one-character
        if len( checked_value ) > limit:
            checked_value = f'{checked_value[0:limit-1]}{elip}'
            log.debug( '%s - string value updated; was, ```%s```; now, ```%s```', self.request_id, string_value, checked_value )
        log.debug( '%s - returning string-value, ```%s```', self.request_id, checked_value )
        return checked_value

    ## end class Mapper()
