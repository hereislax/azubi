# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""URL-Konfiguration für das Maßnahmen-Modul."""

from django.urls import path
from . import views

app_name = 'intervention'

urlpatterns = [
    path('',               views.intervention_list,   name='list'),
    path('neu/',           views.intervention_create, name='create'),
    path('<uuid:public_id>/',      views.intervention_detail, name='detail'),
    path('<uuid:public_id>/loeschen/', views.intervention_delete, name='delete'),

    # ── Kategorien-Verwaltung (Leitung) ──────────────────────────────────────
    path('kategorien/',              views.category_list,   name='category_list'),
    path('kategorien/neu/',          views.category_create, name='category_create'),
    path('kategorien/<uuid:public_id>/bearbeiten/', views.category_edit, name='category_edit'),
    path('kategorien/<uuid:public_id>/loeschen/',  views.category_delete, name='category_delete'),
]
