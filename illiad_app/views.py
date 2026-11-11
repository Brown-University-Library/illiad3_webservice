import datetime
import json
import logging

from django.conf import settings as project_settings
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest, HttpResponseNotFound

from illiad_app.lib import info_helper
from illiad_app.lib.cloud_api_check_user import CloudCheckUserHandler
from illiad_app.lib.cloud_api_create_user import CloudCreateUserHandler
from illiad_app.lib.cloud_article_request import ArticleRequestHandler
from illiad_app.lib.cloud_book_request import BookRequestHandler

log = logging.getLogger(__name__)


def cloud_check_user(request: HttpRequest) -> HttpResponse:
    """Handles checking a user's status -- meaing `registered`, `new-user`, `blocked`, `revoked`."""
    rq_now = datetime.datetime.now()
    check_user_handler = CloudCheckUserHandler()
    log.debug('%s - starting', check_user_handler.request_id)
    if check_user_handler.data_check(request) == 'invalid':
        return HttpResponseBadRequest(b'Bad Request')
    result_data = check_user_handler.manage_check(request, rq_now)
    output_dct = json.dumps(result_data, sort_keys=True, indent=2)
    return HttpResponse(output_dct.encode(), content_type='application/json; charset=utf-8')


def cloud_create_user(request: HttpRequest) -> HttpResponse:
    """Handles new-user creation via official illiad-cloud-api."""
    # log.debug( 'request_dct, ```%s```' % pprint.pformat(request.__dict__) )
    rq_now = datetime.datetime.now()
    handler = CloudCreateUserHandler()
    log.debug('%s - starting', handler.request_id)
    if handler.data_check(request) == 'invalid':
        log.debug('returning `BadRequest` response')
        return HttpResponseBadRequest(b'Bad Request')
    result_data = handler.create_user(request)
    output_dct = handler.prep_output_dct(rq_now, request, result_data)
    output = json.dumps(output_dct, sort_keys=True, indent=2)
    return HttpResponse(output.encode(), content_type='application/json; charset=utf-8')


def cloud_book_request(request: HttpRequest) -> HttpResponse:
    """Handles current (April 2019) easyBorrow controller illiad call -- via hitting ILLiad API."""
    log.debug('starting book-request')
    book_handler = BookRequestHandler(request.POST.get('request_id', 'no_id'))
    if book_handler.check_validity(request) is False:
        return HttpResponseBadRequest(b'Bad Request')
    cloud_api_response_dct = book_handler.manage_request(request)
    # output_dct = book_handler.prep_output_dct( rq_now, request, cloud_api_response_dct )  # future TODO
    output_dct = book_handler.prepare_V2_output_dct(
        cloud_api_response_dct
    )  # this is compatible with the April 2019 format of the easyBorrow internal-illiad-api call
    output = json.dumps(output_dct, sort_keys=True, indent=2)
    return HttpResponse(output.encode(), content_type='application/json; charset=utf-8')


def cloud_article_request(request: HttpRequest) -> HttpResponse:
    """Handles current (April 2019) easyAccess article illiad call -- via hitting ILLiad API.
    TO DO: get this working, then look for commonalities with book-requesting"""
    log.debug('starting article-request')
    article_handler = ArticleRequestHandler(request.POST.get('request_id', 'no_id'))
    if article_handler.check_validity(request) is False:
        return HttpResponseBadRequest(b'Bad Request')
    cloud_api_response_dct = article_handler.manage_request(request)
    output_dct = article_handler.prep_output_dct(cloud_api_response_dct)
    output = json.dumps(output_dct, sort_keys=True, indent=2)
    return HttpResponse(output.encode(), content_type='application/json; charset=utf-8')


# ===========================
# for development convenience
# ===========================


def info(request: HttpRequest) -> HttpResponse:
    """Returns basic data including branch & commit."""
    log.debug(
        'user-agent, ```%s```; ip, ```%s```; referrer, ```%s```',
        request.META.get('HTTP_USER_AGENT', None),
        request.META.get('REMOTE_ADDR', None),
        request.META.get('HTTP_REFERER', None),
    )
    rq_now = datetime.datetime.now()
    commit = info_helper.get_commit()
    branch = info_helper.get_branch()
    info_txt = commit.replace('commit', branch)
    resp_now = datetime.datetime.now()
    taken = resp_now - rq_now
    context_dct = info_helper.make_context(request, rq_now, info_txt, taken)
    output = json.dumps(context_dct, sort_keys=True, indent=2)
    return HttpResponse(output.encode(), content_type='application/json; charset=utf-8')


def error_check(request: HttpRequest) -> HttpResponse:
    """For checking that admins receive error-emails."""
    if project_settings.DEBUG:
        raise ZeroDivisionError('division by zero')
    else:
        return HttpResponseNotFound(b'<div>404 / Not Found</div>')


# =========================
# for reference for a while
# =========================


# def check_user( request ):
#     """ Handles logging a user in, evaluating response, and returning basic status info.
#         Status meaning `registered`, `new-user`, `blocked`, `revoked`.
#         This was created in the shift to have the article part of easyAccess hit this illiad api instead of its pip-install module.
#         TODO... Eventually don't hit this url, and then a separte 'create-new-user' url...
#                 instead, perhaps hit a check_user_and_create_new_user_if_necessary() url. """
#     # log.debug( 'request_dct, ```%s```' % pprint.pformat(request.__dict__) )
#     rq_now = datetime.datetime.now()
#     check_user_handler = CheckUserHelper()
#     log.debug( '%s - starting' % check_user_handler.request_id )
#     if check_user_handler.data_check( request ) == 'invalid':
#         return HttpResponseBadRequest( 'Bad Request' )
#     result_data = check_user_handler.manage_check( request, rq_now )
#     output_dct = json.dumps( result_data, sort_keys=True, indent=2 )
#     return HttpResponse( output_dct, content_type='application/json; charset=utf-8' )


# def check_status_via_shib( request ):
#     """ Handles shib-protected check-user-status.
#         Status meaning "type", eg, `Staff`, `Undergraduate`.
#         TODO: change this 'status' reference to 'type'.
#         TODO: update code to return data like `cloud_check_user()` does. """
#     # log.debug( 'request_dct, ```%s```' % pprint.pformat(request.__dict__) )
#     rq_now = datetime.datetime.now()
#     status_checker_handler = CheckStatusHandler()
#     log.debug( '%s - starting' % status_checker_handler.request_id )
#     if status_checker_handler.data_check( request ) == 'invalid':
#         return HttpResponseBadRequest( 'Bad Request' )
#     result_data = status_checker_handler.check_statuses( request )
#     output_dct = status_checker_handler.prep_output_dct( rq_now, request, result_data )
#     output = json.dumps( output_dct, sort_keys=True, indent=2 )
#     return HttpResponse( output, content_type='application/json; charset=utf-8' )


# def update_status( request ):
#     """ No longer possible.
#         Status meant "type", eg, `Staff`, `Undergraduate`.
#         This endpoint will be removed; tracking it for now to see what's calling it so I disable those calls. """
#     log.debug( 'request_dct, ```%s```' % pprint.pformat(request.__dict__) )
#     return HttpResponseNotFound( '404 / Not Found' )


# def create_user( request ):
#     """ Handles new-user creation. """
#     # log.debug( 'request_dct, ```%s```' % pprint.pformat(request.__dict__) )
#     rq_now = datetime.datetime.now()
#     handler = CreateUserHandler()
#     log.debug( '%s - starting' % handler.request_id )
#     if handler.data_check( request ) == 'invalid':
#         log.debug( 'returning `BadRequest` response' )
#         return HttpResponseBadRequest( 'Bad Request' )
#     # return HttpResponse( 'coming' )
#     result_data = handler.create_user( request )
#     output_dct = handler.prep_output_dct( rq_now, request, result_data )
#     output = json.dumps( output_dct, sort_keys=True, indent=2 )
#     return HttpResponse( output, content_type='application/json; charset=utf-8' )


# def make_request_v2( request ):
#     """ Handles current (October 2015) easyBorrow controller illiad call. """
#     log.debug( 'starting' )
#     # log.debug( 'request.__dict__, `%s`' % pprint.pformat(request.__dict__) )
#     v2_helper = V2_Helper( request.POST.get('request_id', 'no_id') )
#     if v2_helper.check_validity( request ) is False:
#         return HttpResponseBadRequest( 'Bad Request' )
#     v2_response_dct = v2_helper.run_request( request )
#     output = json.dumps( v2_response_dct, sort_keys=True, indent=2 )
#     return HttpResponse( output, content_type='application/json; charset=utf-8' )
