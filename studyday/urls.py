# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.urls import path
from . import views

app_name = 'studyday'

urlpatterns = [
    path('', views.request_list, name='request_list'),
    path('<uuid:public_id>/entscheiden/', views.request_decide, name='request_decide'),
    path('<uuid:public_id>/stornieren/', views.request_cancel, name='request_cancel'),
    path('einstellungen/', views.policy_settings, name='policy_settings'),
]
