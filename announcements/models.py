# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Datenmodelle für Ankündigungen an Nachwuchskräfte mit Zielgruppen-Steuerung und Lesebestätigung."""

import os
import uuid
from django.db import models
from django.utils import timezone

from services.storage import uuid_upload_to

# ── Status ────────────────────────────────────────────────────────────────────

STATUS_DRAFT     = 'draft'
STATUS_PUBLISHED = 'published'

STATUS_CHOICES = [
    (STATUS_DRAFT,     'Entwurf'),
    (STATUS_PUBLISHED, 'Veröffentlicht'),
]

# ── Zielgruppe ────────────────────────────────────────────────────────────────

TARGET_ALL_STUDENTS  = 'all_students'
TARGET_COURSE        = 'course'
TARGET_JOB_PROFILE   = 'job_profile'
TARGET_COORDINATION  = 'koordination'
TARGET_CAREER        = 'career'
TARGET_INDIVIDUAL    = 'individual'

TARGET_CHOICES = [
    (TARGET_ALL_STUDENTS, 'Alle Nachwuchskräfte'),
    (TARGET_COURSE,       'Bestimmter Kurs'),
    (TARGET_JOB_PROFILE,  'Bestimmtes Berufsbild'),
    (TARGET_COORDINATION, 'Bestimmte Koordination'),
    (TARGET_CAREER,       'Bestimmte Laufbahn'),
    (TARGET_INDIVIDUAL,   'Einzelne Nachwuchskräfte'),
]


class Announcement(models.Model):
    """Ankündigung mit Zielgruppen-Auswahl, optionalem E-Mail-Versand und Bestätigungspflicht."""

    # Öffentliche, nicht erratbare ID – ersetzt int-PK in URLs gegen Enumeration.
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Öffentliche ID',
    )

    title = models.CharField(max_length=200, verbose_name='Titel')
    body  = models.TextField(verbose_name='Inhalt (HTML)')

    sender = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='sent_announcements',
        verbose_name='Absender',
    )
    status     = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, verbose_name='Status')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')
    published_at = models.DateTimeField(null=True, blank=True, verbose_name='Veröffentlicht am')

    requires_acknowledgement = models.BooleanField(
        default=False,
        verbose_name='Bestätigung erforderlich',
        help_text='Empfänger müssen den Erhalt aktiv bestätigen.',
    )
    send_email = models.BooleanField(
        default=True,
        verbose_name='Per E-Mail versenden',
        help_text='Beim Veröffentlichen eine E-Mail an alle Empfänger senden.',
    )

    target_type = models.CharField(
        max_length=20, choices=TARGET_CHOICES, default=TARGET_ALL_STUDENTS,
        verbose_name='Zielgruppe',
    )
    target_course = models.ForeignKey(
        'course.Course',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
        verbose_name='Ziel-Kurs',
    )
    target_job_profile = models.ForeignKey(
        'course.JobProfile',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
        verbose_name='Ziel-Berufsbild',
    )
    target_coordination = models.ForeignKey(
        'instructor.TrainingCoordination',
        on_delete=models.SET_NULL, null=True, blank=True,
        db_column='target_koordination_id',
        related_name='+',
        verbose_name='Ziel-Koordination',
    )
    target_career = models.ForeignKey(
        'course.Career',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
        verbose_name='Ziel-Laufbahn',
    )
    target_students = models.ManyToManyField(
        'student.Student',
        blank=True,
        related_name='+',
        verbose_name='Einzelne Nachwuchskräfte',
    )

    class Meta:
        verbose_name = 'Ankündigung'
        verbose_name_plural = 'Ankündigungen'
        ordering = ['-published_at', '-created_at']

    def __str__(self):
        return self.title

    @property
    def is_published(self):
        return self.status == STATUS_PUBLISHED

    def publish(self, commit=True):
        self.status = STATUS_PUBLISHED
        self.published_at = timezone.now()
        if commit:
            self.save()

    def get_target_students(self):
        """Gibt ein QuerySet der Nachwuchskräfte zurück, die zur Zielgruppe gehören."""
        from student.models import Student
        if self.target_type == TARGET_INDIVIDUAL:
            return self.target_students.filter(anonymized_at__isnull=True)
        qs = Student.objects.filter(anonymized_at__isnull=True)
        if self.target_type == TARGET_COURSE and self.target_course:
            qs = qs.filter(course=self.target_course)
        elif self.target_type == TARGET_JOB_PROFILE and self.target_job_profile:
            qs = qs.filter(course__job_profile=self.target_job_profile)
        elif self.target_type == TARGET_COORDINATION and self.target_coordination:
            qs = qs.filter(course__coordination=self.target_coordination)
        elif self.target_type == TARGET_CAREER and self.target_career:
            qs = qs.filter(course__job_profile__career=self.target_career)
        return qs

    def create_recipients(self):
        """Erstellt Empfänger-Einträge für alle Nachwuchskräfte mit Portal-Benutzerkonto."""
        students = self.get_target_students().filter(user__isnull=False).select_related('user')
        existing = set(
            AnnouncementRecipient.objects.filter(announcement=self)
            .values_list('user_id', flat=True)
        )
        new_recipients = [
            AnnouncementRecipient(announcement=self, user=s.user)
            for s in students
            if s.user_id not in existing
        ]
        AnnouncementRecipient.objects.bulk_create(new_recipients, ignore_conflicts=True)
        return len(new_recipients)

    def get_target_emails(self):
        """Gibt eine Liste von (Name, E-Mail) zurück, basierend auf der dienstlichen E-Mail-Kennung."""
        students = self.get_target_students().only(
            'first_name', 'last_name', 'email_id'
        )
        return [
            (f'{s.first_name} {s.last_name}', s.email_id)
            for s in students
            if s.email_id
        ]


class AnnouncementAttachment(models.Model):
    """Dateianhang zu einer Ankündigung."""

    announcement = models.ForeignKey(
        Announcement,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name='Ankündigung',
    )
    file     = models.FileField(upload_to=uuid_upload_to('announcements/attachments/'), verbose_name='Datei')
    filename = models.CharField(max_length=255, verbose_name='Dateiname', blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Anhang'
        verbose_name_plural = 'Anhänge'
        ordering = ['uploaded_at']

    def __str__(self):
        return self.filename or os.path.basename(self.file.name)

    def save(self, *args, **kwargs):
        # Original-Dateinamen festhalten, BEVOR Django den UUID-Pfad zuweist.
        # FieldFile.name ist beim ersten Save noch der vom Browser gelieferte Name.
        if not self.filename and self.file:
            self.filename = os.path.basename(self.file.name)
        super().save(*args, **kwargs)


class AnnouncementRecipient(models.Model):
    """Empfänger einer Ankündigung mit Lese- und Bestätigungsstatus."""

    announcement = models.ForeignKey(
        Announcement,
        on_delete=models.CASCADE,
        related_name='recipients',
        verbose_name='Ankündigung',
    )
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='received_announcements',
        verbose_name='Empfänger',
    )
    read_at          = models.DateTimeField(null=True, blank=True, verbose_name='Gelesen am')
    acknowledged_at  = models.DateTimeField(null=True, blank=True, verbose_name='Bestätigt am')

    class Meta:
        verbose_name = 'Empfänger'
        verbose_name_plural = 'Empfänger'
        unique_together = ('announcement', 'user')
        ordering = ['user__last_name', 'user__first_name']

    def __str__(self):
        return f'{self.user} → {self.announcement}'

    @property
    def is_read(self):
        return self.read_at is not None

    @property
    def is_acknowledged(self):
        return self.acknowledged_at is not None
