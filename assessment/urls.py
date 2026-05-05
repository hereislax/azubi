# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.urls import path
from . import views

app_name = 'assessment'

urlpatterns = [
    # ── Öffentlich (kein Login) ────────────────────────────────────────────────
    path('praxistutor/<uuid:token>/', views.assessment_token_form, name='token_form'),

    # ── Staff ──────────────────────────────────────────────────────────────────
    path('aus-einsatz/<str:assignment_pk>/senden/', views.assessment_send_for_assignment, name='send_for_assignment'),
    path('stationsfeedback/', views.station_feedback_overview, name='station_feedback_overview'),
    path('', views.assessment_list, name='list'),
    path('<uuid:public_id>/', views.assessment_detail, name='detail'),
    path('<uuid:public_id>/bestaetigen/', views.assessment_confirm, name='confirm'),
    path('<uuid:public_id>/signiert/', views.assessment_signed_pdf, name='signed_pdf'),
    path('<uuid:public_id>/token-senden/', views.assessment_resend_token, name='resend_token'),
    path('<uuid:public_id>/token-erneuern/', views.assessment_renew_token, name='renew_token'),
    path('<uuid:public_id>/praxistutor-wechseln/', views.assessment_change_assessor, name='change_assessor'),
]
