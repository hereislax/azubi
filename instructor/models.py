# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Datenmodelle für Praxistutoren und Ausbildungskoordinationen."""

import uuid

from django.db import models

INSTRUCTOR_STATUS_PENDING   = 'pending'
INSTRUCTOR_STATUS_CONFIRMED = 'confirmed'


class Instructor(models.Model):
    """Praxistutor mit Zuordnung zu Organisationseinheit und Berufsbildern."""

    PENDING   = INSTRUCTOR_STATUS_PENDING
    CONFIRMED = INSTRUCTOR_STATUS_CONFIRMED
    STATUS_CHOICES = [
        (PENDING,   'Ausstehend'),
        (CONFIRMED, 'Bestätigt'),
    ]

    # Öffentliche, nicht erratbare ID – ersetzt int-PK in URLs gegen Enumeration.
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Öffentliche ID',
    )

    salutation = models.ForeignKey(
        'services.Gender',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Anrede",
    )
    first_name = models.CharField(max_length=100, verbose_name="Vorname")
    last_name = models.CharField(max_length=100, verbose_name="Nachname")
    email = models.EmailField(verbose_name="Dienstliche E-Mail")
    unit = models.ForeignKey(
        'organisation.OrganisationalUnit',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='instructors',
        verbose_name="Organisationseinheit",
    )
    location = models.ForeignKey(
        'organisation.Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='instructors',
        verbose_name="Standort",
    )
    job_profiles = models.ManyToManyField(
        'course.JobProfile',
        blank=True,
        related_name='instructors',
        verbose_name="Berufsbilder",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=PENDING,
        verbose_name="Status",
    )

    def __str__(self):
        salutation = self.salutation.description if self.salutation else ''
        return f"{salutation} {self.first_name} {self.last_name}".strip()

    class Meta:
        verbose_name = "Praxistutor"
        verbose_name_plural = "Praxistutoren"
        ordering = ['last_name', 'first_name']


class TrainingCoordination(models.Model):
    """
    Eine Ausbildungskoordination als organisatorische Einheit.
    Mehrere Personen (ChiefInstructor) können einer Koordination angehören
    und teilen sich deren Funktionspostfach und Zuständigkeitsbereich.
    """
    # Öffentliche, nicht erratbare ID – ersetzt int-PK in URLs gegen Enumeration.
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Öffentliche ID',
    )

    name = models.CharField(max_length=200, verbose_name="Bezeichnung")
    functional_email = models.EmailField(
        blank=True,
        verbose_name="Funktionspostfach",
        help_text="Gemeinsames Postfach aller Mitglieder (z. B. 4_ausbildung@…). "
                  "Zuweisungs-E-Mails werden hierhin gesendet.",
    )
    units = models.ManyToManyField(
        'organisation.OrganisationalUnit',
        blank=True,
        related_name='training_coordinations',
        verbose_name="Organisationseinheiten",
    )

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'instructor_koordination'
        verbose_name = "Ausbildungskoordination"
        verbose_name_plural = "Ausbildungskoordinationen"
        ordering = ['name']

# Abwärtskompatibilität
Koordination = TrainingCoordination


class ChiefInstructor(models.Model):
    """Person in der Ausbildungskoordination mit optionalem Portal-Benutzerkonto."""

    salutation = models.ForeignKey(
        'services.Gender',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Anrede",
    )
    first_name = models.CharField(max_length=100, verbose_name="Vorname")
    last_name = models.CharField(max_length=100, verbose_name="Nachname")
    email = models.EmailField(verbose_name="Dienstliche E-Mail")
    # Öffentliche, nicht erratbare ID – ersetzt int-PK in URLs gegen Enumeration.
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Öffentliche ID',
    )

    coordination = models.ForeignKey(
        TrainingCoordination,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='members',
        verbose_name="Ausbildungskoordination",
        db_column='koordination_id',
    )
    user = models.OneToOneField(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chief_instructor_profile',
        verbose_name="Benutzerkonto",
    )

    def __str__(self):
        salutation = self.salutation.description if self.salutation else ''
        return f"{salutation} {self.first_name} {self.last_name}".strip()

    class Meta:
        verbose_name = "Person (Ausbildungskoordination)"
        verbose_name_plural = "Personen (Ausbildungskoordination)"
        ordering = ['last_name', 'first_name']


class InstructorOrderTemplate(models.Model):
    """Word-Vorlage (.docx) für das Bestellungsschreiben eines Praxistutors."""

    name = models.CharField(max_length=100, verbose_name="Name")
    template_file = models.FileField(
        upload_to="instructor/templates/",
        verbose_name="Vorlage (.docx)",
    )
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    uploaded_at = models.DateTimeField(auto_now=True, verbose_name="Hochgeladen am")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Bestellungsvorlage Praxistutor"
        verbose_name_plural = "Bestellungsvorlagen Praxistutor"
        ordering = ['-uploaded_at']
