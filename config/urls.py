# -*- coding: utf-8 -*-

from django.conf.urls import include, url
from django.contrib import admin
from django.views.generic import RedirectView
from illiad_app import views


admin.autodiscover()

urlpatterns = [

    # url( r'^admin/', include(admin.site.urls) ),

    # url( r'^check_user/$', views.check_user, name='check_user' ),  # (remote-auth method) checks status meaning 'registered', 'blocked', etc.
    # url( r'^cloud_check_user/$', views.cloud_check_user, name='cloud_check_user' ),
    url( r'^check_user/$', views.cloud_check_user, name='cloud_check_user' ),

    # url( r'^v2/make_request/$', views.make_request_v2, name='request_v2' ),  # (remote-auth method) simulated web access to submit request
    # url( r'^cloud_book_request/$', views.cloud_book_request, name='cloud_book_request' ),  # (official illiad-api) submits request
    url( r'^v2/make_request/$', views.cloud_book_request, name='cloud_book_request' ),  # easyBorrow April 2019 calling syntax, uses official illiad-api to submit book-request

    # url( r'^check_status_via_shib/$', views.check_status_via_shib, name='check_status_via_shib' ),  # (remote-auth method) status meaning 'Undergrad', 'Staff', etc.
    # url( r'^update_status/$', views.update_status, name='update_status' ),  # (remote-auth method)

    # url( r'^create_user/$', views.create_user, name='create_user' ),
    # url( r'^cloud_create_user/$', views.cloud_create_user, name='cloud_create_user' ),
    url( r'^create_user/$', views.cloud_create_user, name='cloud_create_user' ),

    url( r'^info/$', views.info, name='info_url' ),
    url( r'^error_check/$', views.error_check, name='error_check' ),  # only generates error if DEBUG == True

    url( r'^$',  RedirectView.as_view(pattern_name='info_url') ),

]
