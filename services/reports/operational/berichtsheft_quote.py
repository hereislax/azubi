# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Report: Berichtsheft-Quote pro Nachwuchskraft.

Zeigt Soll vs. Ist der wöchentlichen Ausbildungsnachweise.
Soll = Wochen seit Kursbeginn (max. bis Kursende).
Ist  = Anzahl genehmigter Nachweise.
"""
from __future__ import annotations

from datetime import date

from ..base import BaseReport, Column, ModelFilter, ChoiceFilter, BarChart
from ..registry import register


@register
class BerichtsheftQuoteReport(BaseReport):
    slug        = 'berichtsheft-quote'
    name        = 'Berichtsheft-Quote'
    category    = 'Operativ'
    description = ('Soll/Ist der wöchentlichen Ausbildungsnachweise pro Nachwuchskraft. '
                   'Soll = Wochen seit Kursbeginn, Ist = Anzahl genehmigter Nachweise.')

    columns = [
        Column('student',       'Nachwuchskraft', sortable=True),
        Column('course',        'Kurs',           sortable=True),
        Column('job_profile',   'Berufsbild',     sortable=True),
        Column('weeks_elapsed', 'Wochen Soll',    type='int', align='right', total=True),
        Column('approved',      'Genehmigt',      type='int', align='right', total=True),
        Column('submitted',     'Eingereicht',    type='int', align='right', total=True),
        Column('rejected',      'Korrektur',      type='int', align='right', total=True),
        Column('draft',         'Entwurf',        type='int', align='right', total=True),
        Column('missing',       'Fehlend',        type='int', align='right', total=True),
        Column('quote',         'Quote',          type='pct', align='right'),
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
            ChoiceFilter('only_below', label='Nur unter Schwelle',
                         choices=[('', 'Alle'), ('80', '< 80%'), ('50', '< 50%'), ('0', '0%')],
                         default=''),
        ]

    chart = BarChart(x='student', y='quote', label='Quote (%)')

    def get_rows(self, filter_values: dict) -> list[dict]:
        from course.models import Course
        from student.models import Student
        from proofoftraining.models import (
            TrainingRecord,
            STATUS_APPROVED, STATUS_SUBMITTED, STATUS_DRAFT, STATUS_REJECTED,
        )

        today = date.today()
        course_pk     = filter_values.get('course')
        job_profile_pk = filter_values.get('job_profile')
        threshold_str = filter_values.get('only_below') or ''

        students = (
            Student.objects
            .filter(anonymized_at__isnull=True)
            .select_related('course__job_profile')
        )
        if course_pk:
            students = students.filter(course_id=course_pk)
        if job_profile_pk:
            students = students.filter(course__job_profile_id=job_profile_pk)

        rows = []
        for s in students.order_by('last_name', 'first_name'):
            course = s.course
            if course is None:
                continue
            jp = course.job_profile
            if jp is None or not getattr(jp, 'requires_proof_of_training', False):
                continue

            course_start = course.start_date
            course_end   = min(course.end_date, today) if course.end_date else today
            if course_end < course_start:
                continue
            weeks_elapsed = max(0, (course_end - course_start).days // 7)
            if weeks_elapsed == 0:
                continue

            qs = TrainingRecord.objects.filter(student=s)
            approved  = qs.filter(status=STATUS_APPROVED).count()
            submitted = qs.filter(status=STATUS_SUBMITTED).count()
            rejected  = qs.filter(status=STATUS_REJECTED).count()
            draft     = qs.filter(status=STATUS_DRAFT).count()
            missing   = max(0, weeks_elapsed - approved - submitted - rejected - draft)
            quote = (approved / weeks_elapsed * 100) if weeks_elapsed else 0.0

            if threshold_str:
                try:
                    threshold = float(threshold_str)
                    if quote >= threshold and threshold > 0:
                        continue
                    if threshold == 0 and quote > 0:
                        continue
                except ValueError:
                    pass

            rows.append({
                'student':       f'{s.first_name} {s.last_name}',
                'course':        course.title,
                'job_profile':   jp.description,
                'weeks_elapsed': weeks_elapsed,
                'approved':      approved,
                'submitted':     submitted,
                'rejected':      rejected,
                'draft':         draft,
                'missing':       missing,
                'quote':         round(quote, 1),
            })
        return rows
