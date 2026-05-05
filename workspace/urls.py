# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.urls import path

from . import views


app_name = 'workspace'


urlpatterns = [
    path('', views.workspace_list, name='workspace_list'),
    path('kalender/', views.workspace_calendar, name='workspace_calendar'),
    path('uebersicht/', views.booking_list, name='booking_list'),
    path('<uuid:public_id>/', views.workspace_detail, name='workspace_detail'),
    path('buchung/neu/', views.booking_create, name='booking_create'),
    path('buchung/neu/<uuid:workspace_public_id>/', views.booking_create, name='booking_create_for_workspace'),
    path('buchung/<uuid:public_id>/stornieren/', views.booking_cancel, name='booking_cancel'),
    path('sperrung/neu/', views.closure_create, name='closure_create'),
    path('sperrung/neu/<uuid:workspace_public_id>/', views.closure_create, name='closure_create_for_workspace'),
    path('sperrung/<uuid:public_id>/entfernen/', views.closure_delete, name='closure_delete'),

    # Portal (für Nachwuchskräfte)
    path('portal/meine-buchungen/', views.portal_my_bookings, name='portal_my_bookings'),
    path('portal/raeume/', views.portal_workspace_list, name='portal_workspace_list'),
    path('portal/raeume/<uuid:public_id>/', views.portal_workspace_detail, name='portal_workspace_detail'),
    path('portal/buchung/neu/', views.portal_booking_create, name='portal_booking_create'),
    path('portal/buchung/neu/<uuid:workspace_public_id>/', views.portal_booking_create, name='portal_booking_create_for_workspace'),
    path('portal/buchung/<uuid:public_id>/stornieren/', views.portal_booking_cancel, name='portal_booking_cancel'),
]