# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Report: Fehlzeitenstatistik pro Kurs (Krankmeldungen + Ampelstatus)."""
from __future__ import annotations

from ..base import BaseReport, Column, ModelFilter, ChoiceFilter
from ..registry import register


@register
class FehlzeitenReport(BaseReport):
    slug        = 'fehlzeiten'
    name        = 'Fehlzeitenstatistik'
    category    = 'Operativ'
    description = ('Krankmeldungen und Ampelstatus pro Kurs. Zeigt offene und insgesamt '
                   'erfasste Krankmeldungen sowie die Verteilung des Abwesenheits-Ampelstatus.')

    columns = [
        Column('course',         'Kurs',          sortable=True),
        Column('student_count',  'Azubis',        type='int', align='right', total=True),
        Column('green',          'Grün',          type='int', align='right', total=True),
        Column('yellow',         'Gelb',          type='int', align='right', total=True),
        Column('red',            'Rot',           type='int', align='right', total=True),
        Column('unknown',        'Unbekannt',     type='int', align='right', total=True),
        Column('open_sick',      'Offen krank',   type='int', align='right', total=True),
        Column('total_sick',     'Krankmeldungen gesamt', type='int', align='right', total=True),
    ]

    @property
    def filters(self):
        from course.models import Course
        return [
            ModelFilter('course', label='Kurs', multi=False,
                        queryset_factory=lambda: Course.objects.order_by('-start_date')),
            ChoiceFilter('only_active', label='Zeitraum',
                         choices=[('1', 'Nur laufende Kurse'),
                                  ('', 'Alle Kurse')],
                         default='1'),
        ]

    def get_rows(self, filter_values: dict) -> list[dict]:
        from datetime import date
        from course.models import Course
        from student.models import Student
        from absence.models import SickLeave, StudentAbsenceState

        today = date.today()
        course_pk = filter_values.get('course')
        only_active = filter_values.get('only_active') == '1'

        courses = Course.objects.order_by('-start_date')
        if course_pk:
            courses = courses.filter(pk=course_pk)
        if only_active:
            courses = courses.filter(end_date__gte=today)

        rows = []
        for course in courses:
            students = list(
                Student.objects
                .filter(course=course, anonymized_at__isnull=True)
                .prefetch_related('absence_state')
            )
            if not students:
                continue
            student_pks = [s.pk for s in students]

            traffic = {'green': 0, 'yellow': 0, 'red': 0, 'unknown': 0}
            for s in students:
                try:
                    tl = s.absence_state.traffic_light
                except StudentAbsenceState.DoesNotExist:
                    tl = 'unknown'
                traffic[tl] = traffic.get(tl, 0) + 1

            open_sick = SickLeave.objects.filter(
                student__in=student_pks, end_date__isnull=True
            ).count()
            total_sick = SickLeave.objects.filter(student__in=student_pks).count()

            rows.append({
                'course':        course.title,
                'student_count': len(students),
                'green':         traffic['green'],
                'yellow':        traffic['yellow'],
                'red':           traffic['red'],
                'unknown':       traffic['unknown'],
                'open_sick':     open_sick,
                'total_sick':    total_sick,
            })
        return rows
