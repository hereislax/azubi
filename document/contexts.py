# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Context-Builder für Word-Dokumente (docxtpl).

Jede Funktion liefert ein Dict mit den Platzhaltern aus
:mod:`document.conventions`. Mehrere Dicts werden im View
zusammengeführt::

    ctx = {
        **student_context(student),
        **course_context(student.course),
        **creator_context(request.user),
        **meta_context(),
        'freitext': freitext,
    }

So bleiben die Tag-Namen über alle Dokumenten konsistent, und neue
Dokumenttypen müssen nur die Bausteine kombinieren.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any


# ── Hilfsfunktionen ─────────────────────────────────────────────────────────


def _fmt_date(value) -> str:
    """Datum als TT. MMMM JJJJ; ``None``/Falsy → leerer String."""
    if not value:
        return ''
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.strftime('%d. %B %Y')
    return str(value)


def _safe(obj, *attrs, default: str = '') -> Any:
    """Greift sicher auf eine Attribut-Kette zu (``obj.a.b.c``)."""
    cur = obj
    for a in attrs:
        if cur is None:
            return default
        cur = getattr(cur, a, None)
    return cur if cur not in (None, '') else default


# ── Domänen-Helper ──────────────────────────────────────────────────────────x
def student_context(student) -> dict:
    """Platzhalter für eine Nachwuchskraft (``None`` → leere Strings)."""
    if student is None:
        return {key: '' for key in (
            'student_vorname', 'student_nachname', 'student_anrede',
            'student_id', 'student_geburtsdatum', 'student_geburtsort',
            'student_email_privat', 'student_email_dienstlich',
            'student_telefon', 'student_adresse',
        )}
    address = ''
    addr = getattr(student, 'address', None)
    if addr:
        address = (f'{addr.street} {addr.house_number}\n'
                   f'{addr.zip_code} {addr.city}')
    anrede = ''
    gender = getattr(student, 'gender', None)
    if gender is not None:
        anrede = getattr(gender, 'salutation', '') or getattr(gender, 'gender', '') or ''
    return {
        'student_vorname':           student.first_name or '',
        'student_nachname':          student.last_name or '',
        'student_anrede':            anrede,
        'student_id':                str(student.pk),
        'student_geburtsdatum':      _fmt_date(student.date_of_birth),
        'student_geburtsort':        student.place_of_birth or '',
        'student_email_privat':      student.email_private or '',
        'student_email_dienstlich':  student.email_id or '',
        'student_telefon':           student.phone_number or '',
        'student_adresse':           address,
    }


def course_context(course) -> dict:
    """Platzhalter für einen Kurs samt Berufsbild."""
    if course is None:
        return {key: '' for key in (
            'kurs_titel', 'kurs_beginn', 'kurs_ende',
            'kurs_berufsbild', 'kurs_berufsbild_beschreibung',
            'kurs_berufsbild_abschluss', 'kurs_berufsbild_gesetzesgrundlage',
            'kurs_berufsbild_laufbahn', 'kurs_berufsbild_fachrichtung',
        )}
    job_profile = getattr(course, 'job_profile', None)
    return {
        'kurs_titel':                          course.title or '',
        'kurs_beginn':                         _fmt_date(getattr(course, 'start_date', None)),
        'kurs_ende':                           _fmt_date(getattr(course, 'end_date', None)),
        'kurs_berufsbild':                     _safe(job_profile, 'job_profile'),
        'kurs_berufsbild_beschreibung':        _safe(job_profile, 'description'),
        'kurs_berufsbild_abschluss':           _safe(job_profile, 'degree'),
        'kurs_berufsbild_gesetzesgrundlage':   _safe(job_profile, 'legal_basis'),
        'kurs_berufsbild_laufbahn':            _safe(job_profile, 'career', 'description'),
        'kurs_berufsbild_fachrichtung':        _safe(job_profile, 'specialization', 'description'),
    }


def block_context(block) -> dict:
    """Platzhalter für einen Block (Theorie- oder Praxisblock)."""
    if block is None:
        return {key: '' for key in (
            'block_name', 'block_beginn', 'block_ende',
            'block_standort', 'block_standort_adresse',
        )}
    location = getattr(block, 'location', None)
    return {
        'block_name':              getattr(block, 'name', '') or getattr(block, 'title', '') or '',
        'block_beginn':            _fmt_date(getattr(block, 'start_date', None)),
        'block_ende':              _fmt_date(getattr(block, 'end_date', None)),
        'block_standort':          _safe(location, 'name'),
        'block_standort_adresse':  str(getattr(location, 'address', '') or ''),
    }


def einsatz_context(assignment) -> dict:
    """Platzhalter für einen Praktikumseinsatz."""
    if assignment is None:
        return {key: '' for key in (
            'einsatz_einheit', 'einsatz_einheit_beschreibung',
            'einsatz_beginn', 'einsatz_ende',
            'einsatz_standort', 'einsatz_praxistutor',
        )}
    unit = getattr(assignment, 'unit', None)
    location = getattr(assignment, 'location', None)
    tutor = getattr(assignment, 'practical_instructor', None) or getattr(assignment, 'instructor', None)
    return {
        'einsatz_einheit':              _safe(unit, 'name'),
        'einsatz_einheit_beschreibung': _safe(unit, 'label') or _safe(unit, 'description'),
        'einsatz_beginn':               _fmt_date(getattr(assignment, 'start_date', None)),
        'einsatz_ende':                 _fmt_date(getattr(assignment, 'end_date', None)),
        'einsatz_standort':             _safe(location, 'name'),
        'einsatz_praxistutor':          (
            f'{_safe(tutor, "first_name")} {_safe(tutor, "last_name")}'.strip()
            if tutor else ''
        ),
    }


def instructor_context(instructor) -> dict:
    """Platzhalter für einen Praxistutor (Empfänger eines Bestellschreibens)."""
    if instructor is None:
        return {key: '' for key in (
            'praxistutor', 'praxistutor_vorname', 'praxistutor_nachname',
            'praxistutor_email', 'praxistutor_einheit', 'praxistutor_standort',
        )}
    full = f'{instructor.first_name or ""} {instructor.last_name or ""}'.strip()
    unit = getattr(instructor, 'unit', None)
    location = getattr(instructor, 'location', None)
    return {
        'praxistutor':           full,
        'praxistutor_vorname':   instructor.first_name or '',
        'praxistutor_nachname':  instructor.last_name or '',
        'praxistutor_email':     getattr(instructor, 'email', '') or '',
        'praxistutor_einheit':   _safe(unit, 'name'),
        'praxistutor_standort':  str(location) if location else '',
    }


def creator_context(user) -> dict:
    """Platzhalter für den erstellenden Mitarbeitenden.

    **Wird in jedem Dokument gesetzt**, damit Vorlagen darauf vertrauen
    können, dass die Werte verfügbar sind.
    """
    if user is None:
        return {key: '' for key in (
            'ersteller_name', 'ersteller_vorname', 'ersteller_nachname',
            'ersteller_funktion', 'ersteller_standort',
            'ersteller_raum', 'ersteller_durchwahl', 'zeichnung',
        )}
    name = f'{user.first_name or ""} {user.last_name or ""}'.strip() or user.username
    profile = getattr(user, 'profile', None)
    return {
        'ersteller_name':       name,
        'ersteller_vorname':    user.first_name or '',
        'ersteller_nachname':   user.last_name or '',
        'ersteller_funktion':   _safe(profile, 'job_title'),
        'ersteller_standort':   _safe(profile, 'location', 'name'),
        'ersteller_raum':       _safe(profile, 'room'),
        'ersteller_durchwahl':  _safe(profile, 'phone'),
        'zeichnung':            (user.last_name or '').strip() or user.username,
    }


def meta_context(*, today: date | None = None) -> dict:
    """Globale Platzhalter (heute, …). ``today`` für deterministische Tests."""
    return {
        'heute': _fmt_date(today or date.today()),
    }