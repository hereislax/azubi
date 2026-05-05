# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.urls import path
from . import views

app_name = 'announcements'

urlpatterns = [
    path('',                      views.announcement_list,    name='list'),
    path('neu/',                  views.announcement_create,  name='create'),
    path('<uuid:public_id>/',             views.announcement_detail,  name='detail'),
    path('<uuid:public_id>/bearbeiten/',  views.announcement_edit,    name='edit'),
    path('<uuid:public_id>/veroeffentlichen/', views.announcement_publish, name='publish'),
    path('<uuid:public_id>/loeschen/',    views.announcement_delete,  name='delete'),
]
