# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""URL-Konfiguration für die Instructor-App: Praxistutoren, Ausbildungskoordinationen und Änderungsanträge."""
from django.urls import path
from . import views

app_name = 'instructor'

urlpatterns = [
    path('', views.instructor_list, name='instructor_list'),
    path('neu/', views.instructor_create, name='instructor_create'),
    path('<uuid:public_id>/', views.instructor_detail, name='instructor_detail'),
    path('<uuid:public_id>/bearbeiten/', views.instructor_edit, name='instructor_edit'),
    path('<uuid:public_id>/entfernen/', views.instructor_delete, name='instructor_delete'),
    path('<uuid:public_id>/bestaetigen/', views.instructor_confirm, name='instructor_confirm'),

    # Koordination (Gruppenobjekt)
    path('statistik/', views.instructor_statistics, name='instructor_statistics'),

    path('koordination/', views.chief_instructor_list, name='chief_instructor_list'),
    path('koordination/neu/', views.chief_instructor_create, name='chief_instructor_create'),
    path('koordination/<uuid:public_id>/', views.chief_instructor_detail, name='chief_instructor_detail'),
    path('koordination/<uuid:public_id>/bearbeiten/', views.chief_instructor_edit, name='chief_instructor_edit'),
    path('koordination/<uuid:public_id>/entfernen/', views.chief_instructor_delete, name='chief_instructor_delete'),
    path('koordination/<uuid:public_id>/kalender/', views.chief_instructor_calendar, name='chief_instructor_calendar'),

    # Mitglieder (ChiefInstructor-Personen innerhalb einer Koordination)
    path('koordination/<uuid:koordination_public_id>/person/neu/', views.member_create, name='member_create'),
    path('koordination/<uuid:koordination_public_id>/person/<uuid:member_public_id>/bearbeiten/', views.member_edit, name='member_edit'),
    path('koordination/<uuid:koordination_public_id>/person/<uuid:member_public_id>/entfernen/', views.member_delete, name='member_delete'),
    path('koordination/<uuid:koordination_public_id>/person/<uuid:member_public_id>/benutzer-anlegen/', views.member_create_user, name='member_create_user'),

    # Einsatz-Aktionen
    path('koordination/<uuid:chief_public_id>/praktikum/<str:assignment_pk>/bearbeiten/', views.chief_instructor_assignment_edit, name='chief_instructor_assignment_edit'),
    path('koordination/<uuid:chief_public_id>/praktikum/<str:assignment_pk>/annehmen/', views.chief_instructor_approve_assignment, name='chief_instructor_approve_assignment'),
    path('koordination/<uuid:chief_public_id>/praktikum/<str:assignment_pk>/ablehnen/', views.chief_instructor_reject_assignment, name='chief_instructor_reject_assignment'),

    # Änderungsanträge für einen Praktikumseinsatz
    path('koordination/<uuid:chief_public_id>/praktikum/<str:assignment_pk>/aenderung/<str:change_type>/',
         views.change_request_create, name='change_request_create'),

    # Änderungsantrag-Review (Ausbildungsleitung)
    path('aenderungsantraege/', views.change_request_list, name='change_request_list'),
    path('aenderungsantrag/<uuid:change_request_public_id>/', views.change_request_review, name='change_request_review'),
    path('aenderungsantrag/<uuid:change_request_public_id>/annehmen/', views.change_request_approve, name='change_request_approve'),
    path('aenderungsantrag/<uuid:change_request_public_id>/ablehnen/', views.change_request_reject, name='change_request_reject'),

    path('praxistutoren-ajax/', views.instructors_for_unit, name='instructors_for_unit'),
    path('standorte-ajax/', views.locations_for_unit, name='locations_for_unit'),
]
