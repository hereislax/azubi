# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""
Middleware für Modul- und Rollenzugriffssteuerung.

ModuleAccessMiddleware: Prüft ob ein Modul in der SiteConfiguration aktiviert ist.
RoleAccessMiddleware:   Beschränkt URL-Zugriff basierend auf der Benutzerrolle.
"""
import re
from django.core.exceptions import PermissionDenied

# Gemeinsame statische App-Ressourcen (für alle Rollen freigegeben)
_COMMON_ALLOWED = [
    re.compile(p) for p in [
        r'^/theme\.css$',
        r'^/logo\.svg$',
        r'^/favicon\.svg$',
        r'^/logo-text\.svg$',
        r'^/mein-konto/',
        r'^/benachrichtigungen/',
        r'^/impressum/$',
        r'^/datenschutz/$',
        r'^/acknowledgments/',
        # Authentifizierungs-Pfade müssen für JEDE Rolle erreichbar sein:
        # Logout, OTP-Schritt, Passwort-Reset etc. Ohne diese Freigabe läuft
        # jeder User ohne expliziten Rollen-Whitelist-Eintrag auf 403, kann
        # sich also auch nicht ausloggen.
        r'^/accounts/',
        r'^/sso/',
    ]
]

# Erlaubte Pfade für Ausbildungskoordinationen
_COORDINATION_ALLOWED = [
    re.compile(p) for p in [
        r'^/$',
        r'^/accounts/',
        r'^/student/$',
        r'^/student/azubi-[^/]+/$',
        r'^/student/azubi-[^/]+/kompetenzmatrix/$',
        r'^/organisation/\d+/$',
        r'^/organisation/\d+/bearbeiten/$',
        r'^/praxistutoren/$',
        r'^/praxistutoren/neu/$',
        r'^/praxistutoren/\d+/$',
        r'^/praxistutoren/koordination/\d+/$',
        r'^/praxistutoren/koordination/\d+/praktikum/[\w-]+/bearbeiten/$',
        r'^/praxistutoren/koordination/\d+/praktikum/[\w-]+/annehmen/$',
        r'^/praxistutoren/koordination/\d+/praktikum/[\w-]+/ablehnen/$',
        r'^/praxistutoren/koordination/\d+/praktikum/[\w-]+/aenderung/[\w_]+/$',
        r'^/praxistutoren/koordination/\d+/kalender/$',
        r'^/praxistutoren/praxistutoren-ajax/$',
        r'^/kurs/kapazitaet/$',
        r'^/kurs/kalender/$',
        r'^/kurs/[\w-]+/kompetenzmatrix/$',
        r'^/suche/$',
        r'^/beurteilungen/$',
        r'^/beurteilungen/\d+/$',
        r'^/beurteilungen/\d+/bestaetigen/$',
        r'^/beurteilungen/\d+/token-senden/$',
        r'^/beurteilungen/aus-einsatz/[^/]+/senden/$',
        # Raumbuchung – Koordinationen sehen NUR den anonymisierten Belegungsplan
        r'^/raumbuchung/kalender/$',
    ]
]

# Erlaubte Pfade für Hausverwaltung
_DORMITORY_MGMT_ALLOWED = [
    re.compile(p) for p in [
        r'^/$',
        r'^/accounts/',
        r'^/wohnheim/calendar/$',
        r'^/student/azubi-[^/]+/$',
    ]
]

# Erlaubte Pfade für Reisekostenstelle
_TRAVEL_EXPENSE_ALLOWED = [
    re.compile(p) for p in [
        r'^/$',
        r'^/accounts/',
        r'^/student/$',
        r'^/student/azubi-[^/]+/$',
        r'^/kurs/$',
        r'^/kurs/[^/]+/$',
        r'^/wohnheim/calendar/$',
    ]
]

# Erlaubte Pfade für Ausbildungsverantwortliche
_TRAINING_RESPONSIBLE_ALLOWED = [
    re.compile(p) for p in [
        r'^/$',
        r'^/accounts/',
        r'^/student/$',
        r'^/student/azubi-[^/]+/$',
        r'^/dokumente/documents/\d+/preview/$',
        r'^/dokumente/documents/\d+/download-original/$',
        r'^/services/student/[^/]+/akte/suche/$',
        r'^/ausbildungsnachweise/',
        r'^/suche/$',
        # Abwesenheiten: Lesezugriff (Listen + Detail, kein Erfassen/Entscheiden)
        r'^/abwesenheiten/urlaub/$',
        r'^/abwesenheiten/urlaub/\d+/$',
        r'^/abwesenheiten/krank/$',
        # Pflichtschulungen: Lesezugriff auf Übersicht, Typen-Liste, Detail eigener NK
        r'^/pflichtschulungen/$',
        r'^/pflichtschulungen/typen/$',
        r'^/pflichtschulungen/nachwuchskraft/azubi-[^/]+/$',
    ]
]

# Erlaubte Pfade für Nachwuchskräfte (Portal)
_STUDENT_ALLOWED = [
    re.compile(p) for p in [
        r'^/$',
        r'^/accounts/',
        r'^/portal/',
        r'^/ausbildungsnachweise/',
        r'^/beurteilungen/praxistutor/[0-9a-f-]+/$',
        r'^/media/knowledge/documents/',
        r'^/raumbuchung/portal/',
        r'^/pflichtschulungen/portal/',
    ]
]

# Modul-URL-Zuordnung: URL-Präfix → (Config-Flag, Anzeigename)
_MODULE_URL_MAP = {
    '/wohnheim/':             ('module_dormitory',       'Wohnheimverwaltung'),
    '/inventar/':             ('module_inventory',       'Inventar'),
    '/abwesenheiten/':        ('module_absence',         'Abwesenheiten'),
    '/lerntage/':             ('module_studyday',        'Lerntage'),
    '/beurteilungen/':        ('module_assessment',      'Beurteilungen'),
    '/massnahmen/':           ('module_intervention',    'Maßnahmen'),
    '/ankuendigungen/':       ('module_announcements',   'Ankündigungen'),
    '/wissensdatenbank/':     ('module_knowledge',       'Wissensdatenbank'),
    '/ausbildungsnachweise/': ('module_proofoftraining', 'Ausbildungsnachweise'),
    '/auditlog/':             ('module_auditlog',        'Audit-Log'),
}


class ModuleAccessMiddleware:
    """Blockiert Zugriff auf deaktivierte Module (konfigurierbar in SiteConfiguration)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            for prefix, (flag, label) in _MODULE_URL_MAP.items():
                if request.path.startswith(prefix):
                    from services.models import SiteConfiguration
                    from django.shortcuts import render as _render
                    config = SiteConfiguration.get()
                    if not getattr(config, flag):
                        return _render(
                            request,
                            'module_disabled.html',
                            {'module_name': label},
                            status=404,
                        )
                    break
        return self.get_response(request)


class RoleAccessMiddleware:
    """Erzwingt rollenbasierte URL-Zugriffsbeschränkungen per Whitelist-Muster."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Gemeinsame Ressourcen immer erlauben (Logo, Theme, Mein Konto …)
            if any(p.match(request.path) for p in _COMMON_ALLOWED):
                return self.get_response(request)

            from services.roles import (
                is_training_coordinator, is_dormitory_management,
                is_travel_expense_office, is_training_responsible,
            )

            # Nachwuchskraft: nur Portal-Pfade erlaubt
            if hasattr(request.user, 'student_profile'):
                if not any(p.match(request.path) for p in _STUDENT_ALLOWED):
                    raise PermissionDenied
                return self.get_response(request)

            is_coord = is_training_coordinator(request.user)
            is_responsible = is_training_responsible(request.user)

            # Kombination Koordination + Ausbildungsverantwortliche
            if is_coord and is_responsible:
                combined = _COORDINATION_ALLOWED + _TRAINING_RESPONSIBLE_ALLOWED
                if not any(p.match(request.path) for p in combined):
                    raise PermissionDenied
            elif is_coord:
                if not any(p.match(request.path) for p in _COORDINATION_ALLOWED):
                    raise PermissionDenied
            elif is_dormitory_management(request.user):
                if not any(p.match(request.path) for p in _DORMITORY_MGMT_ALLOWED):
                    raise PermissionDenied
            elif is_travel_expense_office(request.user):
                if not any(p.match(request.path) for p in _TRAVEL_EXPENSE_ALLOWED):
                    raise PermissionDenied
            elif is_responsible:
                if not any(p.match(request.path) for p in _TRAINING_RESPONSIBLE_ALLOWED):
                    raise PermissionDenied
            else:
                # Kein eingeschränktes Rollenprofil → prüfe ob Leitung/Referat
                from services.roles import is_training_director, is_training_office
                if not (request.user.is_staff
                        or is_training_director(request.user)
                        or is_training_office(request.user)):
                    raise PermissionDenied
        return self.get_response(request)
