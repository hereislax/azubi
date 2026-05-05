# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Datenmodelle für wöchentliche Ausbildungsnachweise (Nachweise, Tage, Exportvorlagen)."""

import uuid

from django.db import models

STATUS_DRAFT = 'draft'
STATUS_SUBMITTED = 'submitted'
STATUS_APPROVED = 'approved'
STATUS_REJECTED = 'rejected'

STATUS_CHOICES = [
    (STATUS_DRAFT,     'Entwurf'),
    (STATUS_SUBMITTED, 'Eingereicht'),
    (STATUS_APPROVED,  'Angenommen'),
    (STATUS_REJECTED,  'Korrekturbedarf'),
]

STATUS_COLORS = {
    STATUS_DRAFT:     'secondary',
    STATUS_SUBMITTED: 'primary',
    STATUS_APPROVED:  'success',
    STATUS_REJECTED:  'warning',
}

DAY_TYPE_CHOICES = [
    ('praxis',    'Praktische Ausbildung'),
    ('schule',    'Berufsschule / Lehrveranstaltung'),
    ('sonstiges', 'Urlaub / Krank / Feiertag'),
]


class TrainingRecord(models.Model):
    """Wöchentlicher Ausbildungsnachweis einer Nachwuchskraft."""

    # Öffentliche, nicht erratbare ID – ersetzt int-PK in URLs gegen Enumeration.
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Öffentliche ID',
    )

    student = models.ForeignKey(
        'student.Student',
        on_delete=models.CASCADE,
        related_name='training_records',
        verbose_name='Nachwuchskraft',
    )
    week_start = models.DateField(verbose_name='Wochenbeginn (Montag)')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        verbose_name='Status',
    )
    submitted_at = models.DateTimeField(null=True, blank=True, verbose_name='Eingereicht am')
    reviewed_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_training_records',
        verbose_name='Geprüft von',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='Geprüft am')
    rejection_reason = models.TextField(blank=True, verbose_name='Korrekturhinweis')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['student', 'week_start']
        ordering = ['-week_start']
        verbose_name = 'Ausbildungsnachweis'
        verbose_name_plural = 'Ausbildungsnachweise'

    @property
    def week_end(self):
        from datetime import timedelta
        return self.week_start + timedelta(days=4)

    @property
    def calendar_week(self):
        return self.week_start.isocalendar()[1]

    @property
    def status_color(self):
        return STATUS_COLORS.get(self.status, 'secondary')

    def __str__(self):
        return f"KW {self.calendar_week}/{self.week_start.year} – {self.student}"


class TrainingRecordExportTemplate(models.Model):
    """Word-Vorlage (.docx) für den Export aller Ausbildungsnachweise einer Nachwuchskraft."""

    name = models.CharField(max_length=100, verbose_name='Name')
    template_file = models.FileField(
        upload_to='proofoftraining/vorlagen/',
        verbose_name='Vorlage (.docx)',
    )
    is_active = models.BooleanField(default=True, verbose_name='Aktiv')
    uploaded_at = models.DateTimeField(auto_now=True)

    HELP_TEXT = (
        'Verfügbare Variablen: {{ vorname }}, {{ nachname }}, {{ kurs }}, {{ berufsbild }}, {{ heute }} | '
        'Liste: {% for nachweis in nachweise %} ... {% endfor %} mit: '
        '{{ nachweis.kw }}, {{ nachweis.jahr }}, {{ nachweis.von }}, {{ nachweis.bis }}, {{ nachweis.status }} | '
        'Tage: {% for tag in nachweis.tage %} ... {% endfor %} mit: '
        '{{ tag.datum }}, {{ tag.wochentag }}, {{ tag.art }}, {{ tag.beschreibung }}, {{ tag.korrekturhinweis }}'
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Exportvorlage'
        verbose_name_plural = 'Exportvorlagen'
        ordering = ['name']


class TrainingDay(models.Model):
    """Ein Ausbildungstag innerhalb eines wöchentlichen Nachweises."""

    record = models.ForeignKey(
        TrainingRecord,
        on_delete=models.CASCADE,
        related_name='days',
        verbose_name='Ausbildungsnachweis',
    )
    date = models.DateField(verbose_name='Datum')
    day_type = models.CharField(
        max_length=20,
        choices=DAY_TYPE_CHOICES,
        default='praxis',
        verbose_name='Art des Tages',
    )
    content = models.TextField(
        blank=True,
        verbose_name='Beschreibung der Tätigkeiten / Lerninhalte',
    )
    correction_note = models.TextField(
        blank=True,
        verbose_name='Korrekturhinweis (Prüfer)',
    )

    class Meta:
        ordering = ['date']
        unique_together = ['record', 'date']
        verbose_name = 'Ausbildungstag'
        verbose_name_plural = 'Ausbildungstage'

    WEEKDAY_NAMES = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']

    @property
    def weekday_name(self):
        return self.WEEKDAY_NAMES[self.date.weekday()]

    def __str__(self):
        return f"{self.weekday_name}, {self.date.strftime('%d.%m.%Y')}"
