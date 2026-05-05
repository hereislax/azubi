# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Modelle für das Maßnahmen-Management (Interventionen und Kategorien)."""

import uuid
from django.db import models

# ── Status ────────────────────────────────────────────────────────────────────

STATUS_OPEN         = 'open'
STATUS_IN_PROGRESS  = 'in_progress'
STATUS_CLOSED       = 'closed'
STATUS_ESCALATED    = 'escalated'

STATUS_CHOICES = [
    (STATUS_OPEN,        'Offen'),
    (STATUS_IN_PROGRESS, 'In Bearbeitung'),
    (STATUS_CLOSED,      'Abgeschlossen'),
    (STATUS_ESCALATED,   'Eskaliert'),
]

STATUS_BADGE = {
    STATUS_OPEN:        'warning',
    STATUS_IN_PROGRESS: 'primary',
    STATUS_CLOSED:      'success',
    STATUS_ESCALATED:   'danger',
}

# ── Auslöser ─────────────────────────────────────────────────────────────────

TRIGGER_ABSENCE    = 'absence'
TRIGGER_ASSESSMENT = 'assessment'
TRIGGER_BEHAVIOUR  = 'behaviour'
TRIGGER_OTHER      = 'other'

TRIGGER_CHOICES = [
    (TRIGGER_ABSENCE,    'Fehlzeiten'),
    (TRIGGER_ASSESSMENT, 'Beurteilung'),
    (TRIGGER_BEHAVIOUR,  'Verhalten / Disziplin'),
    (TRIGGER_OTHER,      'Sonstiges'),
]

TRIGGER_ICON = {
    TRIGGER_ABSENCE:    'bi-thermometer-high',
    TRIGGER_ASSESSMENT: 'bi-clipboard-check',
    TRIGGER_BEHAVIOUR:  'bi-exclamation-triangle',
    TRIGGER_OTHER:      'bi-three-dots',
}

# ── Farben (Bootstrap) ────────────────────────────────────────────────────────

COLOR_CHOICES = [
    ('secondary', 'Grau'),
    ('primary',   'Blau'),
    ('info',      'Hellblau'),
    ('success',   'Grün'),
    ('warning',   'Gelb'),
    ('danger',    'Rot'),
    ('dark',      'Dunkel'),
]


# ── Kategorie (konfigurierbar) ────────────────────────────────────────────────

class InterventionCategory(models.Model):
    """Frei konfigurierbare Maßnahmen-Kategorie (z. B. Fördergespräch, Abmahnung)."""

    # Öffentliche, nicht erratbare ID – ersetzt int-PK in URLs gegen Enumeration.
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Öffentliche ID',
    )

    name = models.CharField(max_length=100, unique=True, verbose_name='Bezeichnung')
    escalation_level = models.PositiveSmallIntegerField(
        default=1,
        verbose_name='Eskalationsstufe',
        help_text='1 = niedrig, 2 = mittel, 3 = hoch, 4 = kritisch',
    )
    color = models.CharField(
        max_length=20,
        choices=COLOR_CHOICES,
        default='secondary',
        verbose_name='Farbe',
    )
    requires_followup = models.BooleanField(
        default=False,
        verbose_name='Folgetermin erforderlich',
        help_text='Wenn aktiv, muss bei der Maßnahme eine Frist angegeben werden.',
    )
    is_active = models.BooleanField(default=True, verbose_name='Aktiv')

    def __str__(self):
        return self.name

    @property
    def escalation_label(self):
        labels = {1: 'Niedrig', 2: 'Mittel', 3: 'Hoch', 4: 'Kritisch'}
        return labels.get(self.escalation_level, str(self.escalation_level))

    class Meta:
        verbose_name = 'Maßnahmen-Kategorie'
        verbose_name_plural = 'Maßnahmen-Kategorien'
        ordering = ['escalation_level', 'name']


# ── Maßnahme ──────────────────────────────────────────────────────────────────

class Intervention(models.Model):
    """Eine dokumentierte Maßnahme oder Intervention für eine Nachwuchskraft."""

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
        related_name='interventions',
        verbose_name='Nachwuchskraft',
    )
    category = models.ForeignKey(
        InterventionCategory,
        on_delete=models.PROTECT,
        related_name='interventions',
        verbose_name='Kategorie',
    )

    # Auslöser (Pflichtfeld)
    trigger_type = models.CharField(
        max_length=20,
        choices=TRIGGER_CHOICES,
        verbose_name='Auslöser',
    )
    trigger_sick_leave = models.ForeignKey(
        'absence.SickLeave',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='interventions',
        verbose_name='Verknüpfte Krankmeldung',
    )
    trigger_assessment = models.ForeignKey(
        'assessment.Assessment',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='interventions',
        verbose_name='Verknüpfte Beurteilung',
    )

    # Kern-Felder
    date = models.DateField(verbose_name='Datum der Maßnahme')
    description = models.TextField(verbose_name='Beschreibung / Gesprächsinhalt')
    participants = models.ManyToManyField(
        'auth.User',
        blank=True,
        related_name='interventions_as_participant',
        verbose_name='Beteiligte',
        help_text='Weitere Personen, die an der Maßnahme beteiligt waren.',
    )

    # Vereinbarung & Folgetermin
    agreement = models.TextField(blank=True, verbose_name='Getroffene Vereinbarungen')
    followup_date = models.DateField(
        null=True, blank=True,
        verbose_name='Frist / Folgetermin',
    )

    # Status & Ergebnis
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN,
        verbose_name='Status',
    )
    outcome = models.TextField(blank=True, verbose_name='Ergebnis / Abschlussbemerkung')
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name='Abgeschlossen am')
    closed_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='interventions_closed',
        verbose_name='Abgeschlossen von',
    )

    # Eskalation (self-referential: Folge-Maßnahme zeigt zurück auf Vorgänger)
    follow_up = models.OneToOneField(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='predecessor',
        verbose_name='Folge-Maßnahme',
    )

    # Metadaten
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='interventions_created',
        verbose_name='Erstellt von',
    )
    created_at  = models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')
    updated_at  = models.DateTimeField(auto_now=True, verbose_name='Aktualisiert am')

    def __str__(self):
        return (
            f'{self.category} – {self.student} '
            f'({self.date.strftime("%d.%m.%Y")})'
        )

    @property
    def status_badge(self):
        return STATUS_BADGE.get(self.status, 'secondary')

    @property
    def trigger_icon(self):
        return TRIGGER_ICON.get(self.trigger_type, 'bi-three-dots')

    @property
    def is_open(self):
        return self.status in (STATUS_OPEN, STATUS_IN_PROGRESS)

    class Meta:
        verbose_name = 'Maßnahme'
        verbose_name_plural = 'Maßnahmen'
        ordering = ['-date', '-created_at']
