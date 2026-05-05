# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Datenmodelle der Raumbuchung (Arbeitsplätze, Buchungen, Sperrzeiträume).

Workspace = Oberbegriff für jede tageweise buchbare Ressource: Azubi-Büro,
Lerninsel, Besprechungsraum etc. Pro Tag werden bis zu ``capacity`` Buchungen
zugelassen; eine Nachwuchskraft darf pro Tag nur **einen** Workspace buchen.
"""
from __future__ import annotations

from datetime import date as date_type, timedelta

from django.core.exceptions import ValidationError
import uuid
from django.db import models
from django.db.models import Q


STATUS_CONFIRMED = 'confirmed'
STATUS_CANCELLED = 'cancelled'

STATUS_CHOICES = [
    (STATUS_CONFIRMED, 'Bestätigt'),
    (STATUS_CANCELLED, 'Storniert'),
]


class WorkspaceType(models.Model):
    """Typ eines buchbaren Arbeitsplatzes (Azubi-Büro, Lerninsel, ...)."""

    name = models.CharField(max_length=100, unique=True, verbose_name='Bezeichnung')
    icon = models.CharField(
        max_length=50,
        blank=True,
        default='bi-door-closed',
        verbose_name='Bootstrap-Icon',
        help_text='Bootstrap-Icon-Klasse, z.B. "bi-door-closed", "bi-people".',
    )
    description = models.TextField(blank=True, verbose_name='Beschreibung')
    is_active = models.BooleanField(default=True, verbose_name='Aktiv')

    class Meta:
        verbose_name = 'Arbeitsplatz-Typ'
        verbose_name_plural = 'Arbeitsplatz-Typen'
        ordering = ['name']

    def __str__(self):
        return self.name


class Workspace(models.Model):
    """Einzelner buchbarer Arbeitsplatz (z.B. „Büro 3.14" oder „Lerninsel Nord")."""

    name = models.CharField(max_length=100, verbose_name='Bezeichnung')
    # Öffentliche, nicht erratbare ID – ersetzt int-PK in URLs gegen Enumeration.
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Öffentliche ID',
    )

    workspace_type = models.ForeignKey(
        WorkspaceType,
        on_delete=models.PROTECT,
        related_name='workspaces',
        verbose_name='Typ',
    )
    location = models.ForeignKey(
        'organisation.Location',
        on_delete=models.PROTECT,
        related_name='workspaces',
        verbose_name='Standort',
    )
    unit = models.ForeignKey(
        'organisation.OrganisationalUnit',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='workspaces',
        verbose_name='Organisationseinheit',
        help_text='Optional: zugeordnete Einheit (rein informativ).',
    )
    capacity = models.PositiveIntegerField(
        default=1,
        verbose_name='Kapazität',
        help_text='Anzahl gleichzeitig möglicher Buchungen pro Tag '
                  '(1 für Einzelbüro, mehr für Lerninseln).',
    )
    description = models.TextField(blank=True, verbose_name='Beschreibung')
    equipment = models.TextField(
        blank=True,
        verbose_name='Ausstattung',
        help_text='Freitext, z.B. „1x PC, 2x Monitor, Whiteboard".',
    )
    booking_horizon_days = models.PositiveIntegerField(
        default=28,
        verbose_name='Buchungs-Horizont (Tage)',
        help_text='Wie viele Tage im Voraus dürfen Buchungen angelegt werden?',
    )
    is_active = models.BooleanField(default=True, verbose_name='Aktiv (buchbar)')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Aktualisiert am')

    class Meta:
        verbose_name = 'Arbeitsplatz'
        verbose_name_plural = 'Arbeitsplätze'
        ordering = ['location__name', 'workspace_type__name', 'name']

    def __str__(self):
        return f'{self.name} ({self.location.name})'

    def confirmed_bookings_on(self, day: date_type):
        """QuerySet aller bestätigten Buchungen für diesen Workspace an einem Datum."""
        return self.bookings.filter(date=day, status=STATUS_CONFIRMED)

    def is_blocked_on(self, day: date_type):
        """Liefert eine ggf. wirksame Sperrung für den Tag, sonst None."""
        return self.closures.filter(start_date__lte=day, end_date__gte=day).first()

    def remaining_capacity_on(self, day: date_type) -> int:
        """Verbleibende Plätze an einem Tag (0 wenn gesperrt oder voll)."""
        if self.is_blocked_on(day):
            return 0
        used = self.confirmed_bookings_on(day).count()
        return max(0, self.capacity - used)


class WorkspaceClosure(models.Model):
    """Zeitraum, in dem ein Arbeitsplatz nicht buchbar ist (Wartung, Reservierung, ...)."""

    # Öffentliche, nicht erratbare ID – ersetzt int-PK in URLs gegen Enumeration.
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Öffentliche ID',
    )

    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name='closures',
        verbose_name='Arbeitsplatz',
    )
    start_date = models.DateField(verbose_name='Von')
    end_date = models.DateField(verbose_name='Bis')
    reason = models.CharField(max_length=200, blank=True, verbose_name='Grund')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')

    class Meta:
        verbose_name = 'Sperrzeitraum'
        verbose_name_plural = 'Sperrzeiträume'
        ordering = ['-start_date']

    def __str__(self):
        return (
            f'{self.workspace} gesperrt '
            f'({self.start_date.strftime("%d.%m.%Y")} – {self.end_date.strftime("%d.%m.%Y")})'
        )

    def clean(self):
        if self.end_date < self.start_date:
            raise ValidationError({'end_date': 'Das Enddatum muss nach dem Startdatum liegen.'})


class WorkspaceBooking(models.Model):
    """Tageweise Buchung eines Arbeitsplatzes durch eine Nachwuchskraft."""

    # Öffentliche, nicht erratbare ID – ersetzt int-PK in URLs gegen Enumeration.
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Öffentliche ID',
    )

    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name='bookings',
        verbose_name='Arbeitsplatz',
    )
    student = models.ForeignKey(
        'student.Student',
        on_delete=models.CASCADE,
        related_name='workspace_bookings',
        verbose_name='Nachwuchskraft',
    )
    date = models.DateField(verbose_name='Datum')
    booked_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='workspace_bookings_made',
        verbose_name='Gebucht von',
        help_text='Konto, das die Buchung angelegt hat (Nachwuchskraft selbst oder Koordination).',
    )
    purpose = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Zweck',
        help_text='Optional: kurzer Verwendungszweck.',
    )
    notes = models.TextField(blank=True, verbose_name='Notizen')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_CONFIRMED,
        verbose_name='Status',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name='Storniert am')
    cancelled_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='workspace_bookings_cancelled',
        verbose_name='Storniert von',
    )
    notification_sequence = models.PositiveIntegerField(
        default=0,
        verbose_name='iCal-Sequenznummer',
        help_text='Wird bei Stornierung erhöht; Outlook erkennt Updates über UID + SEQUENCE.',
    )

    class Meta:
        verbose_name = 'Raumbuchung'
        verbose_name_plural = 'Raumbuchungen'
        ordering = ['-date', 'workspace__name']
        constraints = [
            models.UniqueConstraint(
                fields=['workspace', 'student', 'date'],
                condition=Q(status=STATUS_CONFIRMED),
                name='uniq_active_workspace_booking',
            ),
        ]

    def __str__(self):
        return f'{self.student} → {self.workspace} ({self.date.strftime("%d.%m.%Y")})'

    def clean(self):
        """Validiert die Buchung gegen Buchungs-Horizont, Sperrungen, Kapazität, Doppel-Buchung."""
        if not self.workspace_id or not self.date:
            return

        today = date_type.today()

        if self.status == STATUS_CONFIRMED and self.date < today:
            raise ValidationError({'date': 'Buchungen können nicht für vergangene Tage angelegt werden.'})

        horizon = self.workspace.booking_horizon_days
        if horizon and self.date > today + timedelta(days=horizon):
            raise ValidationError({
                'date': f'Dieser Arbeitsplatz kann höchstens {horizon} Tage im Voraus '
                        f'gebucht werden (frühestmögliches Datum: '
                        f'{(today + timedelta(days=horizon)).strftime("%d.%m.%Y")}).',
            })

        if not self.workspace.is_active:
            raise ValidationError({'workspace': 'Dieser Arbeitsplatz ist derzeit nicht buchbar.'})

        if self.status == STATUS_CONFIRMED:
            blocking = self.workspace.is_blocked_on(self.date)
            if blocking:
                reason = f' ({blocking.reason})' if blocking.reason else ''
                raise ValidationError({
                    'date': f'Der Arbeitsplatz ist am {self.date.strftime("%d.%m.%Y")} '
                            f'gesperrt{reason}.',
                })

        if self.status == STATUS_CONFIRMED:
            existing = (
                WorkspaceBooking.objects
                .filter(workspace=self.workspace, date=self.date, status=STATUS_CONFIRMED)
                .exclude(pk=self.pk)
            )
            if existing.count() >= self.workspace.capacity:
                raise ValidationError({
                    'workspace': f'Der Arbeitsplatz ist am {self.date.strftime("%d.%m.%Y")} '
                                 f'bereits voll belegt (Kapazität: {self.workspace.capacity}).',
                })

        # Eine Nachwuchskraft darf pro Tag nur einen Workspace buchen.
        # Im Portal-Flow wird student erst nach form.is_valid() gesetzt – dann
        # läuft diese Prüfung beim anschließenden booking.full_clean() noch.
        if self.status == STATUS_CONFIRMED and self.student_id:
            other = (
                WorkspaceBooking.objects
                .filter(student_id=self.student_id, date=self.date, status=STATUS_CONFIRMED)
                .exclude(pk=self.pk)
                .first()
            )
            if other:
                raise ValidationError({
                    'student': f'{self.student} hat am {self.date.strftime("%d.%m.%Y")} '
                               f'bereits eine andere Buchung ({other.workspace.name}).',
                })

    def cancel(self, user=None):
        """Setzt die Buchung auf storniert und erhöht die iCal-Sequenz."""
        from django.utils import timezone
        self.status = STATUS_CANCELLED
        self.cancelled_at = timezone.now()
        self.cancelled_by = user
        self.notification_sequence = (self.notification_sequence or 0) + 1
        self.save(update_fields=[
            'status', 'cancelled_at', 'cancelled_by', 'notification_sequence',
        ])