# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Rollenprüfungen und Zugriffs-Dekoratoren für das Azubi-Portal."""
from functools import wraps
from django.shortcuts import redirect
from django.core.exceptions import PermissionDenied


# ── Rollenprüfungen ──────────────────────────────────────────────────────────

def is_training_director(user):
    """Prüft ob der Benutzer Ausbildungsleitung ist (Staff oder Gruppenmitglied)."""
    if not user.is_authenticated:
        return False
    return user.is_staff or user.groups.filter(name='ausbildungsleitung').exists()


def is_training_office(user):
    """Prüft ob der Benutzer zum Ausbildungsreferat gehört."""
    if not user.is_authenticated:
        return False
    return user.groups.filter(name='ausbildungsreferat').exists()


def is_training_coordinator(user):
    """Prüft ob der Benutzer eine Ausbildungskoordination ist."""
    if not user.is_authenticated:
        return False
    return user.groups.filter(name='ausbildungskoordination').exists()


def is_dormitory_management(user):
    """Prüft ob der Benutzer zur Hausverwaltung gehört (eingeschränkter Zugriff auf Belegungskalender)."""
    if not user.is_authenticated:
        return False
    return user.groups.filter(name='hausverwaltung').exists()


def is_travel_expense_office(user):
    """Prüft ob der Benutzer zur Reisekostenstelle gehört (Lesezugriff auf NK-Listen und Kurse)."""
    if not user.is_authenticated:
        return False
    return user.groups.filter(name='reisekostenstelle').exists()


def is_training_responsible(user):
    """Prüft ob der Benutzer ein Ausbildungsverantwortlicher ist (Lesezugriff auf zugewiesene NK)."""
    if not user.is_authenticated:
        return False
    return user.groups.filter(name='ausbildungsverantwortliche').exists()


def get_chief_instructor(user):
    """Gibt das ChiefInstructor-Objekt des Benutzers zurück, oder None."""
    from instructor.models import ChiefInstructor
    return ChiefInstructor.objects.filter(user=user).first()


def get_dormitory_management_profile(user):
    """Gibt das Hausverwaltungs-Profil des Benutzers zurück, oder None."""
    from dormitory.models import DormitoryManagementProfile
    return DormitoryManagementProfile.objects.filter(user=user).select_related('dormitory').first()


def get_training_office_profile(user):
    """Gibt das Ausbildungsreferat-Profil des Benutzers zurück, oder None."""
    if not user.is_authenticated:
        return None
    try:
        return user.ausbildungsreferat_profile
    except Exception:
        return None


def has_any_role(user):
    """Prüft ob der Benutzer irgendeine Portalrolle hat (inkl. Nachwuchskraft-Profil)."""
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    if user.groups.filter(name__in=[
        'ausbildungsleitung', 'ausbildungsreferat', 'ausbildungskoordination',
        'hausverwaltung', 'reisekostenstelle', 'ausbildungsverantwortliche',
    ]).exists():
        return True
    # Nachwuchskraft-Portal
    return hasattr(user, 'student_profile')


def any_role_required(view_func):
    """Dekorator: Benutzer ohne jegliche Rolle erhalten einen 403-Fehler."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f'/accounts/login/?next={request.path}')
        if not has_any_role(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper


def training_director_required(view_func):
    """Dekorator: Nur Ausbildungsleitung darf auf diese View zugreifen."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f'/accounts/login/?next={request.path}')
        if not is_training_director(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper


# ── Abwärtskompatibilität: Alte Namen als Aliase ─────────────────────────────
# Werden in einer zukünftigen Version entfernt.
is_ausbildungsleitung = is_training_director
is_ausbildungsreferat = is_training_office
is_ausbildungskoordination = is_training_coordinator
is_hausverwaltung = is_dormitory_management
is_reisekostenstelle = is_travel_expense_office
is_ausbildungsverantwortliche = is_training_responsible
ausbildungsleitung_required = training_director_required
get_hausverwaltung_profile = get_dormitory_management_profile
get_ausbildungsreferat_profile = get_training_office_profile
