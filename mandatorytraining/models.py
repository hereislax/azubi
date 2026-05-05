# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Datenmodelle für das Pflichtschulungs-Tracking.

- ``TrainingType``: Konfigurierbarer Schulungs-Typ (Datenschutz, Brandschutz, …).
  Drei Wiederholungs-Modi: rollierend, einmalig, fester Stichtag.
- ``TrainingCompletion``: Eine konkrete Teilnahme — Historie, jede Wiederholung
  erzeugt einen neuen Eintrag.
"""
from __future__ import annotations

from datetime import date, timedelta

import uuid
from django.db import models


# Recurrence-Modi
RECURRENCE_ROLLING  = 'rolling'    # gültig N Monate ab Teilnahme (rollierend)
RECURRENCE_ONE_TIME = 'one_time'   # einmalig, läuft nie ab
RECURRENCE_FIXED    = 'fixed'      # festes jährliches Stichdatum (z.B. 31.01.)

RECURRENCE_CHOICES = [
    (RECURRENCE_ROLLING,  'Rollierend (N Monate ab Teilnahme)'),
    (RECURRENCE_ONE_TIME, 'Einmalig (läuft nie ab)'),
    (RECURRENCE_FIXED,    'Fester Stichtag (z.B. jährlich zum 31.01.)'),
]


class TrainingType(models.Model):
    """Pflichtschulungs-Typ mit Gültigkeitsdauer und Berufsbild-Filter."""

    # Öffentliche, nicht erratbare ID – ersetzt int-PK in URLs gegen Enumeration.
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Öffentliche ID',
    )

    name = models.CharField(max_length=120, unique=True, verbose_name='Bezeichnung')
    description = models.TextField(blank=True, verbose_name='Beschreibung')
    icon = models.CharField(
        max_length=50,
        blank=True,
        default='bi-shield-check',
        verbose_name='Bootstrap-Icon',
        help_text='z.B. „bi-shield-check", „bi-fire", „bi-bandaid".',
    )
    recurrence = models.CharField(
        max_length=20,
        choices=RECURRENCE_CHOICES,
        default=RECURRENCE_ROLLING,
        verbose_name='Wiederholung',
        help_text='Bestimmt, wie das Ablaufdatum berechnet wird.',
    )
    validity_months = models.PositiveSmallIntegerField(
        default=12,
        verbose_name='Gültigkeitsdauer (Monate)',
        help_text='Nur bei „Rollierend" relevant: nach dieser Zeit gilt die Teilnahme als abgelaufen.',
    )
    fixed_deadline_month = models.PositiveSmallIntegerField(
        null=True, blank=True,
        verbose_name='Stichtag-Monat',
        help_text='Nur bei „Fester Stichtag": Monat (1=Januar, 12=Dezember).',
    )
    fixed_deadline_day = models.PositiveSmallIntegerField(
        null=True, blank=True,
        verbose_name='Stichtag-Tag',
        help_text='Nur bei „Fester Stichtag": Tag im Monat (z.B. 31).',
    )
    fixed_recurrence_years = models.PositiveSmallIntegerField(
        default=1,
        verbose_name='Wiederholung alle X Jahre',
        help_text='Nur bei „Fester Stichtag": meist 1 (jährlich) oder 2 (alle 2 Jahre).',
    )
    reminder_days_before = models.PositiveSmallIntegerField(
        default=30,
        verbose_name='Erinnerung X Tage vor Ablauf',
        help_text='Steuert, ab wann der Status „bald ablaufend" gilt und Erinnerungen versendet werden. '
                  'Bei einmaligen Schulungen ohne Wirkung.',
    )
    is_mandatory = models.BooleanField(
        default=True,
        verbose_name='Pflichtschulung',
        help_text='Wenn deaktiviert: optional (zählt nicht in die Compliance-Quote).',
    )
    applies_to_all_students = models.BooleanField(
        default=True,
        verbose_name='Gilt für alle Berufsbilder',
        help_text='Wenn deaktiviert: gilt nur für die unten ausgewählten Berufsbilder.',
    )
    applies_to_job_profiles = models.ManyToManyField(
        'course.JobProfile',
        blank=True,
        related_name='mandatory_training_types',
        verbose_name='Berufsbilder',
        help_text='Greift nur, wenn „Gilt für alle Berufsbilder" deaktiviert ist.',
    )
    active = models.BooleanField(default=True, verbose_name='Aktiv')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Aktualisiert am')

    class Meta:
        verbose_name = 'Schulungs-Typ'
        verbose_name_plural = 'Schulungs-Typen'
        ordering = ['name']

    def __str__(self):
        return self.name

    def applies_to(self, student) -> bool:
        """Gilt dieser Schulungs-Typ für die gegebene Nachwuchskraft?"""
        if not self.active:
            return False
        if self.applies_to_all_students:
            return True
        try:
            jp = student.course.job_profile
        except AttributeError:
            return False
        if jp is None:
            return False
        return self.applies_to_job_profiles.filter(pk=jp.pk).exists()

    def calculate_expires_on(self, completed_on: date) -> date | None:
        """Berechnet das passende ``expires_on`` für eine Teilnahme an diesem Datum.

        - ``rolling``: completed_on + validity_months
        - ``one_time``: ``None`` (läuft nie ab)
        - ``fixed``: nächster Stichtag, der **nach** completed_on liegt
        """
        if self.recurrence == RECURRENCE_ONE_TIME:
            return None
        if self.recurrence == RECURRENCE_FIXED:
            return _next_fixed_deadline(
                completed_on,
                month=self.fixed_deadline_month or 1,
                day=self.fixed_deadline_day or 31,
                years=self.fixed_recurrence_years or 1,
            )
        # rolling
        return _add_months(completed_on, self.validity_months)

    @property
    def is_one_time(self) -> bool:
        return self.recurrence == RECURRENCE_ONE_TIME

    @property
    def is_fixed(self) -> bool:
        return self.recurrence == RECURRENCE_FIXED


class TrainingCompletion(models.Model):
    """Eine Teilnahme einer Nachwuchskraft an einer Pflichtschulung.

    Historisch: bei jeder Wiederholung wird ein neuer Datensatz angelegt,
    bestehende werden nicht aktualisiert. So bleibt die Audit-Spur erhalten.
    """

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
        related_name='training_completions',
        verbose_name='Nachwuchskraft',
    )
    training_type = models.ForeignKey(
        TrainingType,
        on_delete=models.PROTECT,
        related_name='completions',
        verbose_name='Schulungs-Typ',
    )
    completed_on = models.DateField(verbose_name='Absolviert am')
    expires_on = models.DateField(
        null=True, blank=True,
        verbose_name='Gültig bis',
        help_text='Wird automatisch aus „Absolviert am" + Schulungs-Typ-Konfiguration berechnet. '
                  'Bei einmaligen Schulungen leer (lebenslang gültig).',
    )
    certificate_paperless_id = models.IntegerField(
        null=True, blank=True,
        verbose_name='Paperless-Dokument-ID',
        help_text='Optional: ID des hochgeladenen Zertifikats in Paperless.',
    )
    notes = models.TextField(blank=True, verbose_name='Anmerkungen')

    registered_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='registered_training_completions',
        verbose_name='Erfasst von',
    )
    registered_at = models.DateTimeField(auto_now_add=True, verbose_name='Erfasst am')

    # Erinnerungs-Tracking, damit pro Completion jede Stufe nur einmal verschickt wird
    reminder_30_sent = models.BooleanField(default=False, verbose_name='Erinnerung T-30 versendet')
    reminder_7_sent  = models.BooleanField(default=False, verbose_name='Erinnerung T-7 versendet')

    class Meta:
        verbose_name = 'Schulungs-Teilnahme'
        verbose_name_plural = 'Schulungs-Teilnahmen'
        ordering = ['-completed_on', 'training_type__name']
        indexes = [
            models.Index(fields=['student', 'training_type', '-completed_on']),
            models.Index(fields=['expires_on']),
        ]

    def __str__(self):
        return f'{self.student} – {self.training_type} ({self.completed_on:%d.%m.%Y})'

    def save(self, *args, **kwargs):
        if self.completed_on and self.expires_on is None and self.training_type_id:
            self.expires_on = self.training_type.calculate_expires_on(self.completed_on)
        super().save(*args, **kwargs)

    @property
    def days_until_expiry(self) -> int | None:
        if self.expires_on is None:
            return None
        return (self.expires_on - date.today()).days

    @property
    def status(self) -> str:
        """'completed' | 'soon_expiring' | 'expired'."""
        if self.expires_on is None:
            # Einmalige Schulung — sobald absolviert immer „erfüllt"
            return 'completed'
        today = date.today()
        if self.expires_on < today:
            return 'expired'
        days = (self.expires_on - today).days
        if days <= self.training_type.reminder_days_before:
            return 'soon_expiring'
        return 'completed'


def _add_months(d: date, months: int) -> date:
    """Addiert Monate auf ein Datum (ohne externe Lib)."""
    if not months:
        return d
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    day = min(d.day, last_day)
    return date(year, month, day)


def _next_fixed_deadline(after: date, month: int, day: int, years: int = 1) -> date:
    """Nächster fester Stichtag (Tag.Monat), der strikt **nach** ``after`` liegt.

    Bei mehrjähriger Wiederholung (``years > 1``) wird auf das nächste passende
    Jahr aufgerundet, sodass der Abstand zwischen zwei Stichtagen ``years`` Jahre beträgt.
    """
    import calendar

    def _safe_date(y, m, d):
        last = calendar.monthrange(y, m)[1]
        return date(y, m, min(d, last))

    candidate = _safe_date(after.year, month, day)
    if candidate <= after:
        candidate = _safe_date(after.year + 1, month, day)
    if years > 1 and (candidate.year - after.year) % years != 0:
        delta = years - ((candidate.year - after.year) % years)
        candidate = _safe_date(candidate.year + delta, month, day)
    return candidate
