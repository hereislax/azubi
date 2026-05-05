# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Report: Compliance-Quote pro Nachwuchskraft (alle Pflichtschulungen)."""
from __future__ import annotations

from ..base import BaseReport, Column, ModelFilter, ChoiceFilter, BarChart
from ..registry import register


@register
class SchulungsQuoteReport(BaseReport):
    slug        = 'schulungs-quote'
    name        = 'Compliance-Quote Pflichtschulungen'
    category    = 'Compliance'
    description = ('Soll/Ist-Quote der Pflichtschulungen je Nachwuchskraft. '
                   'Berechnet aus Anzahl erfüllter vs. anwendbarer Pflichtschulungen.')

    columns = [
        Column('student',         'Nachwuchskraft', sortable=True),
        Column('course',          'Kurs',           sortable=True),
        Column('job_profile',     'Berufsbild',     sortable=True),
        Column('mandatory_total', 'Pflichten gesamt', type='int', align='right', total=True),
        Column('mandatory_ok',    'Erfüllt',          type='int', align='right', total=True),
        Column('mandatory_open',  'Offen',            type='int', align='right', total=True),
        Column('quote',           'Quote',            type='pct', align='right'),
        Column('overall',         'Status'),
    ]

    @property
    def filters(self):
        from course.models import Course, JobProfile
        return [
            ModelFilter('course', label='Kurs', multi=False,
                        queryset_factory=lambda: Course.objects.order_by('-start_date')),
            ModelFilter('job_profile', label='Berufsbild', multi=False,
                        queryset_factory=lambda: JobProfile.objects.order_by('description'),
                        label_field='description'),
            ChoiceFilter('only', label='Anzeige',
                         choices=[('', 'Alle'),
                                  ('not_full', 'Nur unter 100%'),
                                  ('red', 'Nur mit überfälligen Pflichten')],
                         default=''),
        ]

    chart = BarChart(x='student', y='quote', label='Compliance (%)')

    def get_rows(self, filter_values: dict) -> list[dict]:
        from student.models import Student
        from mandatorytraining.services import compliance_status_for_student

        students = (
            Student.objects.filter(anonymized_at__isnull=True)
            .select_related('course__job_profile')
        )
        course_pk = filter_values.get('course')
        jp_pk     = filter_values.get('job_profile')
        only      = filter_values.get('only') or ''
        if course_pk:
            students = students.filter(course_id=course_pk)
        if jp_pk:
            students = students.filter(course__job_profile_id=jp_pk)

        rows = []
        for s in students.order_by('last_name', 'first_name'):
            st = compliance_status_for_student(s)
            if st['mandatory_total'] == 0:
                continue
            quote = st['compliance_pct'] or 0
            if only == 'not_full' and quote >= 100:
                continue
            if only == 'red' and st['overall_status'] != 'red':
                continue
            rows.append({
                'student':         f'{s.first_name} {s.last_name}',
                'course':          s.course.title if s.course else '—',
                'job_profile':     s.course.job_profile.description if (s.course and s.course.job_profile) else '—',
                'mandatory_total': st['mandatory_total'],
                'mandatory_ok':    st['mandatory_ok'],
                'mandatory_open':  st['mandatory_total'] - st['mandatory_ok'],
                'quote':           quote,
                'overall':         {'red': '🔴 kritisch', 'yellow': '🟡 bald', 'green': '🟢 ok'}.get(st['overall_status'], '—'),
            })
        return rows
