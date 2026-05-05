# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.urls import path
from . import views

app_name = 'auditlog'

urlpatterns = [
    path('', views.auditlog_list, name='list'),
    path('student/<str:student_id>/', views.auditlog_student, name='student'),
]
