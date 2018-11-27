# -*- coding: utf-8 -*-

import datetime, json, logging, os, pprint
from django.conf import settings as project_settings
from django.contrib.auth import logout
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from illiad_app.models import V2_Helper
from illiad_app.lib import info_helper


log = logging.getLogger(__name__)



# def info( request ):
#     """ Returns simple response. """
#     log.debug( 'starting info()' )
#     doc_url = os.environ['ILLIAD_WS__DOCS']
#     now = datetime.datetime.now()
#     referrer = request.META.get( 'REMOTE_ADDR', 'unavailable' )
#     dct = { 'date_time': str(now), 'docs': doc_url, 'ip': referrer }
#     output = json.dumps( dct, sort_keys=True, indent=2 )
#     return HttpResponse( output, content_type='application/json; charset=utf-8' )


def info( request ):
    """ Returns basic data including branch & commit. """
    log.debug( 'user-agent, ```%s```; ip, ```%s```; referrer, ```%s```' %
        (request.META.get('HTTP_USER_AGENT', None), request.META.get('REMOTE_ADDR', None), request.META.get('HTTP_REFERER', None)) )
    rq_now = datetime.datetime.now()
    commit = info_helper.get_commit()
    branch = info_helper.get_branch()
    info_txt = commit.replace( 'commit', branch )
    resp_now = datetime.datetime.now()
    taken = resp_now - rq_now
    context_dct = info_helper.make_context( request, rq_now, info_txt, taken )
    output = json.dumps( context_dct, sort_keys=True, indent=2 )
    return HttpResponse( output, content_type='application/json; charset=utf-8' )


def make_request_v2( request ):
    """ Handles current (October 2015) easyBorrow controller illiad call. """
    log.debug( 'starting' )
    # log.debug( 'request.__dict__, `%s`' % pprint.pformat(request.__dict__) )
    v2_helper = V2_Helper( request.POST.get('request_id', 'no_id') )
    if v2_helper.check_validity( request ) is False:
        return HttpResponseBadRequest( 'Bad Request' )
    v2_response_dct = v2_helper.run_request( request )
    output = json.dumps( v2_response_dct, sort_keys=True, indent=2 )
    return HttpResponse( output, content_type='application/json; charset=utf-8' )
