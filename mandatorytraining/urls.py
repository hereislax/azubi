# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.urls import path

from . import views


app_name = 'mandatorytraining'


urlpatterns = [
    # Verwaltung (lesen für Office/Director/Verantwortliche; schreiben nur Office/Director)
    path('', views.overview, name='overview'),
    path('typen/', views.training_type_list, name='type_list'),
    path('typen/neu/', views.training_type_create, name='type_create'),
    path('typen/<uuid:public_id>/bearbeiten/', views.training_type_edit, name='type_edit'),
    path('typen/<uuid:public_id>/entfernen/', views.training_type_delete, name='type_delete'),

    path('bulk/', views.bulk_create, name='bulk_create'),

    # Pro-Azubi
    path('nachwuchskraft/<str:student_pk>/', views.student_detail, name='student_detail'),
    path('nachwuchskraft/<str:student_pk>/teilnahme/neu/', views.completion_create, name='completion_create'),
    path('teilnahme/<uuid:public_id>/bearbeiten/', views.completion_edit, name='completion_edit'),
    path('teilnahme/<uuid:public_id>/entfernen/', views.completion_delete, name='completion_delete'),

    # Portal
    path('portal/', views.portal_my_trainings, name='portal_my_trainings'),
]
