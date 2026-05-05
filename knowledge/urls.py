# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.urls import path
from . import views

app_name = 'knowledge'

urlpatterns = [
    path('',                                views.kb_manage,           name='manage'),
    path('<uuid:public_id>/toggle/',                views.kb_toggle_document,  name='toggle_document'),
    path('<uuid:public_id>/loeschen/',              views.kb_delete_document,  name='delete_document'),
    path('kategorie/<uuid:public_id>/loeschen/',   views.kb_delete_category,  name='delete_category'),
    path('portal/',                         views.portal_kb_list,      name='portal_list'),
    path('portal/<uuid:public_id>/',               views.portal_kb_detail,    name='portal_detail'),
]
