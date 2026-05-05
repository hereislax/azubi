# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Datenmodelle für die Wohnheimverwaltung (Wohnheime, Zimmer, Belegungen, Sperrungen)."""

from datetime import date as date_type
import uuid
from django.db import models
from django.core.exceptions import ValidationError
from student.models import Student


class Dormitory(models.Model):
    """Ein Wohnheim mit Name, Adresse und optionaler Beschreibung."""

    # Öffentliche, nicht erratbare ID – ersetzt int-PK in URLs gegen Enumeration.
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Öffentliche ID',
    )

    name = models.CharField(max_length=100, verbose_name="Name")
    address = models.CharField(max_length=200, verbose_name="Adresse")
    description = models.TextField(blank=True, verbose_name="Beschreibung")
    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Wohnheim"
        verbose_name_plural = "Wohnheime"
        ordering = ["name"]


class Room(models.Model):
    """Zimmer innerhalb eines Wohnheims mit Kapazitätsangabe."""

    # Öffentliche, nicht erratbare ID – ersetzt int-PK in URLs gegen Enumeration.
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Öffentliche ID',
    )

    dormitory = models.ForeignKey(
        Dormitory,
        on_delete=models.CASCADE,
        related_name="rooms",
        verbose_name="Wohnheim"
    )
    number = models.CharField(max_length=20, verbose_name="Zimmer")
    capacity = models.PositiveIntegerField(default=1, verbose_name="Kapazität")
    description = models.TextField(blank=True, verbose_name="Beschreibung")

    def __str__(self):
        return f"{self.dormitory.name} – Zimmer {self.number}"

    class Meta:
        verbose_name = "Zimmer"
        verbose_name_plural = "Zimmer"
        ordering = ["dormitory", "number"]
        unique_together = [("dormitory", "number")]


class RoomAssignment(models.Model):
    """Belegung eines Zimmers durch eine Nachwuchskraft mit Zeitraum und Validierung."""

    # Öffentliche, nicht erratbare ID – ersetzt int-PK in URLs gegen Enumeration.
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Öffentliche ID',
    )

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="room_assignments",
        verbose_name="Nachwuchskraft"
    )
    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name="assignments",
        verbose_name="Zimmer"
    )
    start_date = models.DateField(verbose_name="Einzugsdatum")
    end_date = models.DateField(null=True, blank=True, verbose_name="Auszugsdatum")
    notes = models.TextField(blank=True, verbose_name="Notizen")
    paperless_confirmation_id = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="Paperless-Bestätigungs-ID",
        help_text="Paperless-Dokument-ID der generierten Reservierungsbestätigung.",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")

    def clean(self):
        """
        Validiert die Zimmerbelegung auf Konsistenz.

        Prüft:
        - Das Auszugsdatum darf nicht vor dem Einzugsdatum liegen.
        - Die Belegung darf die Zimmerkapazität im gewählten Zeitraum nicht überschreiten
          (offene Belegungen ohne Enddatum werden bis zum 31.12.9999 behandelt).
        - Im gewählten Zeitraum darf keine aktive Zimmer-Sperrung vorliegen.
        """
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError("Das Enddatum muss nach dem Startdatum liegen.")

        # Überlappende Belegungen desselben Zimmers ermitteln (ohne aktuelle Instanz)
        # Bedingung: bestehend.start < neu.end UND bestehend.end > neu.start
        # Offene Belegungen (end_date=None) gelten bis weit in die Zukunft
        qs = RoomAssignment.objects.filter(room=self.room).exclude(pk=self.pk)
        new_end = self.end_date or date_type(9999, 12, 31)
        overlapping = qs.filter(
            start_date__lt=new_end
        ).filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gt=self.start_date)
        )

        if overlapping.count() >= self.room.capacity:
            raise ValidationError(
                f"Das Zimmer {self.room} ist im gewählten Zeitraum voll belegt (Kapazität: {self.room.capacity})."
            )

        # Prüfen ob eine Zimmer-Sperrung im Zeitraum liegt
        new_end = self.end_date or date_type(9999, 12, 31)
        blocking = RoomBlock.objects.filter(
            room=self.room,
            start_date__lt=new_end,
            end_date__gt=self.start_date,
        ).first()
        if blocking:
            reason = f" ({blocking.reason})" if blocking.reason else ""
            raise ValidationError(
                f"Das Zimmer {self.room} ist vom {blocking.start_date.strftime('%d.%m.%Y')} "
                f"bis {blocking.end_date.strftime('%d.%m.%Y')} gesperrt{reason}."
            )

    def __str__(self):
        end = self.end_date.strftime("%d.%m.%Y") if self.end_date else "offen"
        return f"{self.student} → {self.room} ({self.start_date.strftime('%d.%m.%Y')} – {end})"

    class Meta:
        verbose_name = "Zimmerbelegung"
        verbose_name_plural = "Zimmerbelegungen"
        ordering = ["-start_date"]


class RoomBlock(models.Model):
    """Zeitliche Sperrung eines Zimmers (z. B. wegen Renovierung)."""

    # Öffentliche, nicht erratbare ID – ersetzt int-PK in URLs gegen Enumeration.
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Öffentliche ID',
    )

    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name="blocks",
        verbose_name="Zimmer",
    )
    start_date = models.DateField(verbose_name="Von")
    end_date = models.DateField(verbose_name="Bis")
    reason = models.CharField(max_length=200, blank=True, verbose_name="Grund")

    def clean(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError("Das Enddatum muss nach dem Startdatum liegen.")

    def __str__(self):
        return f"{self.room} gesperrt ({self.start_date.strftime('%d.%m.%Y')} – {self.end_date.strftime('%d.%m.%Y')})"

    class Meta:
        verbose_name = "Zimmer-Sperrung"
        verbose_name_plural = "Zimmer-Sperrungen"
        ordering = ["-start_date"]


class DormitoryManagementProfile(models.Model):
    """Verknüpft einen Hausverwaltungs-Benutzer mit einem Wohnheim."""
    user = models.OneToOneField(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='dormitory_management_profile',
        verbose_name="Benutzer",
    )
    dormitory = models.ForeignKey(
        Dormitory,
        on_delete=models.PROTECT,
        related_name='dormitory_management_profiles',
        verbose_name="Wohnheim",
    )

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} → {self.dormitory.name}"

    class Meta:
        db_table = 'dormitory_hausverwaltungprofile'
        verbose_name = "Hausverwaltungs-Profil"
        verbose_name_plural = "Hausverwaltungs-Profile"

# Abwärtskompatibilität (alter Modellname)
HausverwaltungProfile = DormitoryManagementProfile


class ReservationTemplate(models.Model):
    """Word-Vorlage (.docx) für Wohnheim-Reservierungsbestätigungen."""

    name = models.CharField(max_length=100, verbose_name="Name")
    dormitory = models.ForeignKey(
        Dormitory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reservation_templates',
        verbose_name='Wohnheim',
        help_text='Leer lassen für ein allgemeines Standardschreiben (Fallback für alle Wohnheime).',
    )
    template_file = models.FileField(
        upload_to="dormitory/templates/",
        verbose_name="Vorlage (.docx)",
    )
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    uploaded_at = models.DateTimeField(auto_now=True, verbose_name="Hochgeladen am")

    def __str__(self):
        if self.dormitory:
            return f"{self.name} ({self.dormitory.name})"
        return f"{self.name} (Standard)"

    class Meta:
        verbose_name = "Reservierungsvorlage"
        verbose_name_plural = "Reservierungsvorlagen"
