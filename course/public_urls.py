# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Tokenlose öffentliche Routen für externe Vortragende (Bestätigung/Ablehnung).

Eingebunden in Azubi/urls.py unter dem Prefix `/vortrag/`. Authentifizierung
erfolgt über das ``confirmation_token`` (UUID) auf dem Vortragsobjekt – das
Pattern ist identisch zu den tokenlosen Beurteilungs-Routen für Praxistutoren.
"""
from django.urls import path

from . import public_views

app_name = 'lecture_public'

urlpatterns = [
    path('<uuid:token>/bestaetigen/', public_views.lecture_confirm, name='lecture_confirm'),
    path('<uuid:token>/ablehnen/', public_views.lecture_decline, name='lecture_decline'),
]