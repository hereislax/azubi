# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.urls import path
from . import views

app_name = 'proofoftraining'

urlpatterns = [
    # Student-facing
    path('', views.record_list, name='record_list'),
    path('neu/', views.record_create, name='record_create'),
    path('<uuid:public_id>/bearbeiten/', views.record_edit, name='record_edit'),
    path('<uuid:public_id>/einreichen/', views.record_submit, name='record_submit'),
    path('<uuid:public_id>/', views.record_view, name='record_view'),

    # Export für die Nachwuchskraft
    path('export/', views.record_export, name='record_export'),

    # Verwaltungsseiten (aufgerufen aus der Detailansicht der Nachwuchskraft)
    path('nachwuchskraft/<str:student_pk>/<uuid:public_id>/', views.admin_record_detail, name='admin_record_detail'),
    path('nachwuchskraft/<str:student_pk>/<uuid:public_id>/annehmen/', views.admin_record_approve, name='admin_record_approve'),
    path('nachwuchskraft/<str:student_pk>/<uuid:public_id>/ablehnen/', views.admin_record_reject, name='admin_record_reject'),
    path('nachwuchskraft/<str:student_pk>/export/', views.admin_record_export, name='admin_record_export'),
]
