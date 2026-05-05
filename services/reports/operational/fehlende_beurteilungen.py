# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Report: Fehlende Stationsbeurteilungen.

Stationseinsätze, deren Endedatum erreicht/überschritten ist und für die
keine Beurteilung im Status ``confirmed`` existiert. Sortiert nach Tagen
seit Einsatz-Ende (überfälligste zuerst).
"""
from __future__ import annotations

from datetime import date, timedelta

from ..base import BaseReport, Column, ModelFilter, ChoiceFilter, BarChart
from ..registry import register


@register
class FehlendeBeurteilungenReport(BaseReport):
    slug        = 'fehlende-beurteilungen'
    name        = 'Fehlende Stationsbeurteilungen'
    category    = 'Operativ'
    description = ('Stationseinsätze, deren Ende erreicht/überschritten ist und für die '
                   'keine bestätigte Beurteilung vorliegt.')

    columns = [
        Column('student',      'Nachwuchskraft',        sortable=True),
        Column('unit',         'Einheit',               sortable=True),
        Column('instructor',   'Praxistutor',           sortable=True),
        Column('end_date',     'Einsatz-Ende',          type='date'),
        Column('overdue_days', 'Überfällig (Tage)',     type='int', align='right', total=False),
        Column('status',       'Beurteilungs-Status'),
        Column('course',       'Kurs',                  sortable=True),
    ]

    @property
    def filters(self):
        from course.models import Course
        return [
            ModelFilter('course', label='Kurs', multi=False,
                        queryset_factory=lambda: Course.objects.order_by('-start_date')),
            ChoiceFilter('overdue_threshold', label='Mindest-Überfälligkeit',
                         choices=[('0', 'ab Einsatzende'),
                                  ('7', '> 7 Tage'),
                                  ('14', '> 14 Tage'),
                                  ('30', '> 30 Tage')],
                         default='0'),
        ]

    chart = BarChart(x='unit', y='overdue_days', label='Tage überfällig')

    def get_rows(self, filter_values: dict) -> list[dict]:
        from course.models import InternshipAssignment, ASSIGNMENT_STATUS_APPROVED
        from assessment.models import STATUS_CONFIRMED

        today = date.today()
        course_pk = filter_values.get('course')
        threshold = int(filter_values.get('overdue_threshold') or 0)
        cutoff = today - timedelta(days=threshold)

        qs = (
            InternshipAssignment.objects
            .filter(status=ASSIGNMENT_STATUS_APPROVED, end_date__lte=cutoff)
            .select_related('student', 'unit', 'instructor', 'schedule_block__course', 'assessment')
        )
        if course_pk:
            qs = qs.filter(schedule_block__course_id=course_pk)

        rows = []
        for a in qs:
            assessment = getattr(a, 'assessment', None)
            if assessment and assessment.status == STATUS_CONFIRMED:
                continue
            instructor_name = (
                f'{a.instructor.first_name} {a.instructor.last_name}'
                if a.instructor else '–'
            )
            status_label = 'fehlt komplett'
            if assessment:
                status_label = {
                    'pending':   'Token versendet, ausstehend',
                    'submitted': 'eingereicht, nicht bestätigt',
                }.get(assessment.status, assessment.status)
            rows.append({
                'student':      f'{a.student.first_name} {a.student.last_name}',
                'unit':         a.unit.name,
                'instructor':   instructor_name,
                'end_date':     a.end_date,
                'overdue_days': (today - a.end_date).days,
                'status':       status_label,
                'course':       a.schedule_block.course.title,
            })

        rows.sort(key=lambda r: r['overdue_days'], reverse=True)
        return rows
