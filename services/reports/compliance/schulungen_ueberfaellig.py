# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Report: Überfällige / nie absolvierte Pflichtschulungen."""
from __future__ import annotations

from ..base import BaseReport, Column, ModelFilter
from ..registry import register


@register
class SchulungenUeberfaelligReport(BaseReport):
    slug        = 'schulungen-ueberfaellig'
    name        = 'Überfällige Pflichtschulungen'
    category    = 'Compliance'
    description = ('Pflicht-Schulungen, deren Gültigkeit abgelaufen ist oder die noch nie '
                   'absolviert wurden. Sortiert nach Tagen seit Ablauf (überfälligste zuerst).')

    columns = [
        Column('student',       'Nachwuchskraft', sortable=True),
        Column('course',        'Kurs',           sortable=True),
        Column('training_type', 'Schulung',       sortable=True),
        Column('last_done',     'Letzte Teilnahme', type='date'),
        Column('expired_on',    'Abgelaufen am',  type='date'),
        Column('days_overdue',  'Tage überfällig', type='int', align='right'),
        Column('status',        'Status'),
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
        ]

    def get_rows(self, filter_values: dict) -> list[dict]:
        from datetime import date
        from mandatorytraining.services import overdue_completions_for_office

        course_pk = filter_values.get('course')
        jp_pk     = filter_values.get('job_profile')
        items = overdue_completions_for_office()

        rows = []
        today = date.today()
        for it in items:
            s = it['student']
            if course_pk and (not s.course or str(s.course.pk) != str(course_pk)):
                continue
            if jp_pk and (not s.course or not s.course.job_profile_id or str(s.course.job_profile_id) != str(jp_pk)):
                continue
            c = it['latest']
            rows.append({
                'student':       f'{s.first_name} {s.last_name}',
                'course':        s.course.title if s.course else '—',
                'training_type': it['training_type'].name,
                'last_done':     c.completed_on if c else None,
                'expired_on':    c.expires_on if c else None,
                'days_overdue':  it['days_overdue'] if it['days_overdue'] is not None else 0,
                'status':        'abgelaufen' if it['status'] == 'expired' else 'nicht absolviert',
            })
        rows.sort(key=lambda r: r['days_overdue'] or 0, reverse=True)
        return rows
