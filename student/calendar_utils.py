# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""
Hilfsfunktionen für den Unified Student Calendar.

Semantische Zuordnung der Kalender-Ereignistypen zu Farben aus dem
Stilguide der Bundesregierung. Die eigentlichen Hex-Werte stammen aus
`services.colors.BUNDESFARBEN_BY_NAME` – ändert sich dort die Palette,
greifen die Änderungen automatisch im Kalender.
"""
from datetime import date, timedelta

from django.db import models as dj_models

from services.colors import BUNDESFARBEN_BY_NAME as _BF

CAL_COLOR_LESSON       = _BF['Blau']         # Lehrphasen
CAL_COLOR_BLOCK        = _BF['Petrol']       # Praktikumsphasen (Block)
CAL_COLOR_INTERNSHIP   = _BF['Türkis']       # Einzelpraktika
CAL_COLOR_VACATION     = _BF['Grün']         # Urlaub
CAL_COLOR_STUDY_DAY    = _BF['Oliv']         # Lerntage
CAL_COLOR_SICK         = _BF['Rot']          # Krankmeldungen
CAL_COLOR_INTERVENTION = _BF['Violett']      # Maßnahmen-Fristen (Fallback)


def _bar(label, start, end, color, url, year_start, year_days, is_marker=False):
    """Gibt ein Event-Dict zurück oder None wenn außerhalb des Jahres."""
    clip_s = max(start, year_start)
    clip_e = min(end, date(year_start.year, 12, 31))
    if clip_s > clip_e:
        return None
    offset = (clip_s - year_start).days / year_days * 100
    width  = max(((clip_e - clip_s).days + 1) / year_days * 100, 0.4)
    return {
        'label':     label,
        'start_fmt': start.strftime('%d.%m.%Y'),
        'end_fmt':   end.strftime('%d.%m.%Y'),
        'offset':    f'{offset:.4f}',
        'width':     f'{width:.4f}',
        'color':     color,
        'url':       url,
        'is_marker': is_marker,
    }


def build_student_calendar(student, year, include_interventions=False, portal_view=False):
    """
    Baut alle Kalender-Ereignisse für einen Azubi in einem Jahr auf.

    portal_view=True  → Krankmeldungen werden ausgeblendet, Portal-URLs verwendet.
    include_interventions=True → Maßnahmen-Fristen als Marker einbeziehen (nur Staff).
    """
    year_start = date(year, 1, 1)
    year_end   = date(year, 12, 31)
    year_days  = (year_end - year_start).days + 1

    def b(label, start, end, color, url='', is_marker=False):
        return _bar(label, start, end, color, url, year_start, year_days, is_marker)

    rows = []
    intervention_categories = []  # Für Legende: tatsächlich verwendete Kategorien

    # ── 1. Ausbildungsplan (ScheduleBlöcke) ───────────────────────────────────
    if student.course_id:
        from course.models import ScheduleBlock
        blocks = ScheduleBlock.objects.filter(
            course_id=student.course_id,
            end_date__gte=year_start,
            start_date__lte=year_end,
        ).order_by('start_date')
        events = [
            b(blk.name, blk.start_date, blk.end_date,
              CAL_COLOR_BLOCK if blk.is_internship else CAL_COLOR_LESSON)
            for blk in blocks
        ]
        events = [e for e in events if e]
        if events:
            rows.append({'label': 'Ausbildungsplan', 'icon': 'bi-calendar3', 'events': events})

    # ── 2. Praktikumseinsätze (genehmigt) ─────────────────────────────────────
    from course.models import InternshipAssignment, ASSIGNMENT_STATUS_APPROVED
    assignments = InternshipAssignment.objects.filter(
        student=student,
        status=ASSIGNMENT_STATUS_APPROVED,
        end_date__gte=year_start,
        start_date__lte=year_end,
    ).select_related('unit').order_by('start_date')
    if assignments:
        url = '/portal/stationsplan/' if portal_view else f'/student/{student.pk}/?tab=praktika'
        events = [b(ia.unit.name, ia.start_date, ia.end_date, CAL_COLOR_INTERNSHIP, url) for ia in assignments]
        events = [e for e in events if e]
        if events:
            rows.append({'label': 'Praktikumseinsätze', 'icon': 'bi-briefcase', 'events': events})

    # ── 3. Urlaub (genehmigt) ─────────────────────────────────────────────────
    from absence.models import VacationRequest, STATUS_APPROVED, STATUS_PROCESSED
    vacations = VacationRequest.objects.filter(
        student=student,
        status__in=[STATUS_APPROVED, STATUS_PROCESSED],
        is_cancellation=False,
        end_date__gte=year_start,
        start_date__lte=year_end,
    ).order_by('start_date')
    if vacations:
        events = []
        for vr in vacations:
            url = '/portal/urlaub/' if portal_view else f'/abwesenheiten/urlaub/{vr.pk}/'
            e = b('Urlaub', vr.start_date, vr.end_date, CAL_COLOR_VACATION, url)
            if e:
                events.append(e)
        if events:
            rows.append({'label': 'Urlaub', 'icon': 'bi-sun', 'events': events})

    # ── 4. Lerntage (genehmigt) ───────────────────────────────────────────────
    from studyday.models import StudyDayRequest, STATUS_APPROVED as SD_OK
    study_days = StudyDayRequest.objects.filter(
        student=student,
        status=SD_OK,
        date__gte=year_start,
        date__lte=year_end,
    ).order_by('date')
    if study_days:
        url = '/portal/lerntage/' if portal_view else ''
        events = [b('Lerntag', sd.date, sd.date, CAL_COLOR_STUDY_DAY, url, is_marker=True) for sd in study_days]
        events = [e for e in events if e]
        if events:
            rows.append({'label': 'Lerntage', 'icon': 'bi-book', 'events': events})

    # ── 5. Krankmeldungen ────────────────────────────────────────────────────
    from absence.models import SickLeave
    sick_qs = SickLeave.objects.filter(
        student=student,
        start_date__lte=year_end,
    ).filter(
        dj_models.Q(end_date__gte=year_start) | dj_models.Q(end_date__isnull=True)
    ).order_by('start_date')
    if sick_qs:
        events = [b('Krank', sl.start_date, sl.end_date or date.today(), CAL_COLOR_SICK) for sl in sick_qs]
        events = [e for e in events if e]
        if events:
            rows.append({'label': 'Krankmeldungen', 'icon': 'bi-thermometer-high', 'events': events})

    # ── 6. Maßnahmen-Fristen (nur Staff, optional) ────────────────────────────
    if include_interventions and not portal_view:
        from intervention.models import Intervention
        from services.colors import bootstrap_to_hex
        interventions = Intervention.objects.filter(
            student=student,
            followup_date__gte=year_start,
            followup_date__lte=year_end,
            status__in=['open', 'in_progress'],
        ).select_related('category').order_by('followup_date')
        if interventions:
            seen = {}
            events = []
            for iv in interventions:
                hex_color = bootstrap_to_hex(iv.category.color, default=CAL_COLOR_INTERVENTION)
                event = b(str(iv.category), iv.followup_date, iv.followup_date,
                          hex_color, f'/massnahmen/{iv.pk}/', is_marker=True)
                if event:
                    events.append(event)
                    if iv.category.pk not in seen:
                        seen[iv.category.pk] = {'name': str(iv.category), 'color': hex_color}
            if events:
                rows.append({'label': 'Maßnahmen-Fristen', 'icon': 'bi-shield-exclamation', 'events': events})
                intervention_categories.extend(seen.values())

    # ── Monatskopfzeile ────────────────────────────────────────────────────────
    months_data = []
    for m in range(1, 13):
        m_start = date(year, m, 1)
        m_end   = (date(year, m + 1, 1) - timedelta(days=1)) if m < 12 else year_end
        m_days  = (m_end - m_start).days + 1
        months_data.append({
            'name':  m_start.strftime('%B'),
            'short': m_start.strftime('%b'),
            'width': f'{m_days / year_days * 100:.4f}',
        })

    today = date.today()
    today_offset = f'{(today - year_start).days / year_days * 100:.4f}' \
        if year_start <= today <= year_end else None

    return {
        'year':         year,
        'prev_year':    year - 1,
        'next_year':    year + 1,
        'months_data':  months_data,
        'today_offset': today_offset,
        'rows':         rows,
        'has_data':     bool(rows),
        'intervention_categories': intervention_categories,
    }


def build_course_calendar(course, year, include_interventions=False):
    """
    Kalender-Übersicht für alle Azubis eines Kurses (Koordinationsansicht).

    Gibt eine gemeinsame Monatskopfzeile und pro Student dessen Kalender-Reihen
    zurück, sodass eine gestapelte Gantt-Ansicht gerendert werden kann.
    """
    from student.models import Student

    year_start = date(year, 1, 1)
    year_end   = date(year, 12, 31)
    year_days  = (year_end - year_start).days + 1

    students = Student.objects.filter(course=course).order_by('last_name', 'first_name')

    student_cals = []
    intervention_categories = {}
    for student in students:
        cal = build_student_calendar(
            student, year,
            include_interventions=include_interventions,
            portal_view=False,
        )
        student_cals.append({
            'student': student,
            'rows':     cal['rows'],
            'has_data': cal['has_data'],
        })
        for cat in cal.get('intervention_categories', []):
            intervention_categories.setdefault(cat['name'], cat)

    months_data = []
    for m in range(1, 13):
        m_start = date(year, m, 1)
        m_end   = (date(year, m + 1, 1) - timedelta(days=1)) if m < 12 else year_end
        m_days  = (m_end - m_start).days + 1
        months_data.append({
            'name':  m_start.strftime('%B'),
            'short': m_start.strftime('%b'),
            'width': f'{m_days / year_days * 100:.4f}',
        })

    today = date.today()
    today_offset = f'{(today - year_start).days / year_days * 100:.4f}' \
        if year_start <= today <= year_end else None

    return {
        'year':          year,
        'prev_year':     year - 1,
        'next_year':     year + 1,
        'months_data':   months_data,
        'today_offset':  today_offset,
        'student_cals':  student_cals,
        'has_data':      bool(student_cals),
        'intervention_categories': sorted(intervention_categories.values(), key=lambda c: c['name']),
    }
