# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Datenmodelle für die Inventarverwaltung (Kategorien, Gegenstände, Ausgaben und Quittungsvorlagen)."""

import uuid
from django.db import models
from django.contrib.auth.models import User
from student.models import Student


class ReceiptTemplate(models.Model):
    """Word-Vorlage (.docx) für Ausgabequittungen bei der Inventarausgabe."""

    # Öffentliche, nicht erratbare ID – ersetzt int-PK in URLs gegen Enumeration.
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Öffentliche ID',
    )

    name = models.CharField(max_length=100, verbose_name="Name")
    template_file = models.FileField(
        upload_to="inventory/templates/",
        verbose_name="Vorlage (.docx)",
        help_text=(
            "Verfügbare Platzhalter: {{ vorname }}, {{ nachname }}, {{ student_id }}, "
            "{{ gegenstand }}, {{ seriennummer }}, {{ kategorie }}, "
            "{{ ausgabedatum }}, {{ ausgegeben_von }}, {{ heute }}"
        ),
    )
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    uploaded_at = models.DateTimeField(auto_now=True, verbose_name="Hochgeladen am")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Ausgabequittungs-Vorlage"
        verbose_name_plural = "Ausgabequittungs-Vorlagen"
        ordering = ["name"]


class InventoryCategory(models.Model):
    """Kategorie für Inventargegenstände (z. B. Laptop, Ausweis, Schlüssel)."""

    # Öffentliche, nicht erratbare ID – ersetzt int-PK in URLs gegen Enumeration.
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Öffentliche ID',
    )

    name = models.CharField(max_length=100, verbose_name="Bezeichnung")
    icon = models.CharField(
        max_length=50,
        blank=True,
        default="bi-box",
        verbose_name="Bootstrap-Icon",
        help_text="z. B. bi-laptop, bi-credit-card-2-front, bi-key",
    )
    description = models.TextField(blank=True, verbose_name="Beschreibung")
    receipt_template = models.ForeignKey(
        ReceiptTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="categories",
        verbose_name="Ausgabequittungs-Vorlage",
        help_text="Vorlage, die bei der Ausgabe von Gegenständen dieser Kategorie verwendet wird.",
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Kategorie"
        verbose_name_plural = "Kategorien"
        ordering = ["name"]


class InventoryItem(models.Model):
    """Einzelner Inventargegenstand mit Status und optionaler Seriennummer."""

    class Status(models.TextChoices):
        AVAILABLE = "verfuegbar",    "Verfügbar"
        ISSUED    = "ausgegeben",    "Ausgegeben"
        DEFECT    = "defekt",        "Defekt"
        RETIRED   = "ausgemustert",  "Ausgemustert"

    # Öffentliche, nicht erratbare ID – ersetzt int-PK in URLs gegen Enumeration.
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Öffentliche ID',
    )

    category = models.ForeignKey(
        InventoryCategory,
        on_delete=models.PROTECT,
        related_name="items",
        verbose_name="Kategorie",
    )
    name = models.CharField(max_length=200, verbose_name="Bezeichnung")
    serial_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Seriennummer / Kennung",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AVAILABLE,
        verbose_name="Status",
    )
    location = models.CharField(max_length=100, blank=True, verbose_name="Lagerort")
    notes = models.TextField(blank=True, verbose_name="Notizen")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        sn = f" ({self.serial_number})" if self.serial_number else ""
        return f"{self.name}{sn}"

    class Meta:
        verbose_name = "Gegenstand"
        verbose_name_plural = "Gegenstände"
        ordering = ["category", "name"]


class InventoryIssuance(models.Model):
    """Ausgabe eines Inventargegenstands an eine Nachwuchskraft mit Rückgabe-Tracking."""

    # Öffentliche, nicht erratbare ID – ersetzt int-PK in URLs gegen Enumeration.
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Öffentliche ID',
    )

    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.PROTECT,
        related_name="issuances",
        verbose_name="Gegenstand",
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.PROTECT,
        related_name="inventory_issuances",
        verbose_name="Nachwuchskraft",
    )
    issued_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="inventory_issuances_made",
        verbose_name="Ausgegeben von",
    )
    issued_at = models.DateTimeField(verbose_name="Ausgabedatum/-uhrzeit")
    returned_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Rückgabedatum/-uhrzeit"
    )
    returned_acknowledged_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="inventory_returns_acknowledged",
        verbose_name="Rückgabe bestätigt von",
    )
    notes = models.TextField(blank=True, verbose_name="Notizen")
    scanned_receipt_paperless_id = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="Eingescannte Quittung (Paperless-ID)",
        help_text="Paperless-Dokument-ID der eingescannten, unterschriebenen Quittung.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_returned(self):
        return self.returned_at is not None

    def __str__(self):
        return f"{self.item} → {self.student} ({self.issued_at.strftime('%d.%m.%Y')})"

    class Meta:
        verbose_name = "Ausgabe"
        verbose_name_plural = "Ausgaben"
        ordering = ["-issued_at"]
