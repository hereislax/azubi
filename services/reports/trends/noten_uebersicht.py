# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Report: Noten-Übersicht — Anzahl und Durchschnitt pro Notenart und Berufsbild."""
from __future__ import annotations

from ..base import BaseReport, Column, ModelFilter, BarChart
from ..registry import register


@register
class NotenUebersichtReport(BaseReport):
    slug        = 'noten-uebersicht'
    name        = 'Noten-Übersicht'
    category    = 'Trends'
    description = ('Anzahl und Durchschnitt pro Notenart und Berufsbild. '
                   'Zeigt nur Notenarten, für die mindestens eine Note erfasst ist.')

    columns = [
        Column('job_profile',  'Berufsbild',     sortable=True),
        Column('grade_type',   'Notenart',       sortable=True),
        Column('count',        'Anzahl Noten',   type='int',   align='right', total=True),
        Column('avg_value',    'Ø-Wert',         type='float', align='right'),
        Column('min_value',    'Bestnote',       type='float', align='right'),
        Column('max_value',    'Schlechteste',   type='float', align='right'),
    ]

    @property
    def filters(self):
        from course.models import JobProfile
        return [
            ModelFilter('job_profile', label='Berufsbild', multi=False,
                        queryset_factory=lambda: JobProfile.objects.order_by('description'),
                        label_field='description'),
        ]

    chart = BarChart(x='grade_type', y='avg_value', label='Durchschnitt')

    def get_rows(self, filter_values: dict) -> list[dict]:
        from course.models import JobProfile
        from student.models import Grade

        job_profile_pk = filter_values.get('job_profile')
        profiles = JobProfile.objects.prefetch_related('grade_types').order_by('description')
        if job_profile_pk:
            profiles = profiles.filter(pk=job_profile_pk)

        rows = []
        for jp in profiles:
            for gt in jp.grade_types.order_by('order', 'name'):
                grades = Grade.objects.filter(grade_type=gt).exclude(value='')
                values = []
                for g in grades:
                    try:
                        values.append(float(g.value.replace(',', '.')))
                    except (ValueError, AttributeError):
                        continue
                if not values:
                    continue
                rows.append({
                    'job_profile': jp.description,
                    'grade_type':  gt.name,
                    'count':       len(values),
                    'avg_value':   round(sum(values) / len(values), 2),
                    'min_value':   round(min(values), 2),
                    'max_value':   round(max(values), 2),
                })
        return rows
