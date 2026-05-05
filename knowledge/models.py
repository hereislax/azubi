# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Datenmodelle für die Wissensdatenbank (Kategorien und Dokumente mit Zielgruppen-Sichtbarkeit)."""

import os
import uuid

from django.db import models

from services.storage import uuid_upload_to


VIS_ALL         = 'all'
VIS_JOB_PROFILE = 'job_profile'
VIS_COURSE      = 'course'
VIS_CAREER      = 'career'

VIS_CHOICES = [
    (VIS_ALL,         'Alle Nachwuchskräfte'),
    (VIS_JOB_PROFILE, 'Bestimmtes Berufsbild'),
    (VIS_COURSE,      'Bestimmter Kurs'),
    (VIS_CAREER,      'Bestimmte Laufbahn'),
]


class KBCategory(models.Model):
    """Kategorie zur Gliederung der Wissensdatenbank-Dokumente."""

    # Öffentliche, nicht erratbare ID – ersetzt int-PK in URLs gegen Enumeration.
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Öffentliche ID',
    )
    name      = models.CharField(max_length=100, verbose_name='Name')
    icon      = models.CharField(
        max_length=60, default='bi-folder', verbose_name='Bootstrap-Icon-Klasse',
        help_text='z. B. bi-folder, bi-file-earmark-text, bi-info-circle',
    )
    order     = models.PositiveSmallIntegerField(default=0, verbose_name='Reihenfolge')
    is_active = models.BooleanField(default=True, verbose_name='Aktiv')

    class Meta:
        verbose_name = 'Kategorie'
        verbose_name_plural = 'Kategorien'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class KBDocument(models.Model):
    """Dokument in der Wissensdatenbank (Datei, externer Link oder Textinhalt) mit Zielgruppen-Filterung."""

    # Öffentliche, nicht erratbare ID – ersetzt int-PK in URLs gegen Enumeration.
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Öffentliche ID',
    )
    title       = models.CharField(max_length=200, verbose_name='Titel')
    description = models.TextField(blank=True, verbose_name='Beschreibung')
    category    = models.ForeignKey(
        KBCategory, on_delete=models.PROTECT,
        related_name='documents', verbose_name='Kategorie',
    )

    # Inhalt: Datei, externe URL oder Freitext
    file         = models.FileField(
        upload_to=uuid_upload_to('knowledge/documents/'), blank=True, null=True,
        verbose_name='Datei',
    )
    filename     = models.CharField(max_length=255, blank=True, verbose_name='Dateiname')
    external_url = models.URLField(blank=True, verbose_name='Externe URL')
    content      = models.TextField(blank=True, verbose_name='Textinhalt')

    # Zielgruppen-Filterung
    visibility         = models.CharField(
        max_length=20, choices=VIS_CHOICES, default=VIS_ALL,
        verbose_name='Sichtbarkeit',
    )
    target_job_profile = models.ForeignKey(
        'course.JobProfile', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+', verbose_name='Ziel-Berufsbild',
    )
    target_course      = models.ForeignKey(
        'course.Course', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+', verbose_name='Ziel-Kurs',
    )
    target_career      = models.ForeignKey(
        'course.Career', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+', verbose_name='Ziel-Laufbahn',
    )

    is_active  = models.BooleanField(default=True, verbose_name='Aktiv')
    order      = models.PositiveSmallIntegerField(default=0, verbose_name='Reihenfolge')
    created_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, related_name='+', verbose_name='Erstellt von',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Geändert am')

    class Meta:
        verbose_name = 'Dokument'
        verbose_name_plural = 'Dokumente'
        ordering = ['category__order', 'category__name', 'order', 'title']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.file and not self.filename:
            self.filename = os.path.basename(self.file.name)
        super().save(*args, **kwargs)

    @property
    def is_link(self):
        return bool(self.external_url)

    @property
    def has_attachment(self):
        return bool(self.file or self.external_url)

    @property
    def file_extension(self):
        if self.filename and '.' in self.filename:
            return self.filename.rsplit('.', 1)[-1].lower()
        return ''

    def is_visible_to_student(self, student) -> bool:
        """Prüft, ob das Dokument für die gegebene Nachwuchskraft sichtbar ist."""
        if not self.is_active:
            return False
        if self.visibility == VIS_ALL:
            return True
        if self.visibility == VIS_JOB_PROFILE and self.target_job_profile_id:
            try:
                return student.course.job_profile_id == self.target_job_profile_id
            except AttributeError:
                return False
        if self.visibility == VIS_COURSE and self.target_course_id:
            return student.course_id == self.target_course_id
        if self.visibility == VIS_CAREER and self.target_career_id:
            try:
                return student.course.job_profile.career_id == self.target_career_id
            except AttributeError:
                return False
        return False
