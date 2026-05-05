# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Report: Pflichtschulungen, die in den nächsten N Tagen ablaufen."""
from __future__ import annotations

from ..base import BaseReport, Column, ChoiceFilter, ModelFilter
from ..registry import register


@register
class SchulungenBaldAblaufendReport(BaseReport):
    slug        = 'schulungen-bald-ablaufend'
    name        = 'Bald ablaufende Pflichtschulungen'
    category    = 'Compliance'
    description = 'Gültige Pflicht-Teilnahmen, deren Gültigkeit innerhalb des Filters abläuft.'

    columns = [
        Column('student',       'Nachwuchskraft', sortable=True),
        Column('course',        'Kurs',           sortable=True),
        Column('training_type', 'Schulung',       sortable=True),
        Column('last_done',     'Absolviert am',  type='date'),
        Column('expires_on',    'Gültig bis',     type='date'),
        Column('days_left',     'Tage verbleibend', type='int', align='right'),
    ]

    @property
    def filters(self):
        from course.models import Course
        return [
            ModelFilter('course', label='Kurs', multi=False,
                        queryset_factory=lambda: Course.objects.order_by('-start_date')),
            ChoiceFilter('horizon', label='Horizont',
                         choices=[('30', 'nächste 30 Tage'),
                                  ('60', 'nächste 60 Tage'),
                                  ('90', 'nächste 90 Tage'),
                                  ('180', 'nächste 6 Monate')],
                         default='60'),
        ]

    def get_rows(self, filter_values: dict) -> list[dict]:
        from datetime import date, timedelta
        from mandatorytraining.models import TrainingCompletion
        from mandatorytraining.services import latest_completions, applicable_training_types
        from student.models import Student

        try:
            horizon = int(filter_values.get('horizon') or 60)
        except (TypeError, ValueError):
            horizon = 60
        course_pk = filter_values.get('course')
        today = date.today()
        cutoff = today + timedelta(days=horizon)

        students = Student.objects.filter(anonymized_at__isnull=True).select_related('course__job_profile')
        if course_pk:
            students = students.filter(course_id=course_pk)

        rows = []
        for s in students:
            applicable_pks = {tt.pk for tt in applicable_training_types(s) if tt.is_mandatory}
            if not applicable_pks:
                continue
            latest = latest_completions(s)
            for tt_pk, c in latest.items():
                if tt_pk not in applicable_pks:
                    continue
                if c.expires_on < today or c.expires_on > cutoff:
                    continue
                rows.append({
                    'student':       f'{s.first_name} {s.last_name}',
                    'course':        s.course.title if s.course else '—',
                    'training_type': c.training_type.name,
                    'last_done':     c.completed_on,
                    'expires_on':    c.expires_on,
                    'days_left':     (c.expires_on - today).days,
                })
        rows.sort(key=lambda r: r['days_left'])
        return rows
