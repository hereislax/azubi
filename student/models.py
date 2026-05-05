# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Datenmodelle für Nachwuchskräfte, Noten, Checklisten, Kontakthistorie und Anfragen."""

import os
import uuid
from secrets import token_hex
from django.core.validators import RegexValidator
from django.db import models
from course.models import Course
from services.models import Gender, Adress  # noqa: F401 – Re-Export für Abwärtskompatibilität
from services.storage import uuid_upload_to

template_field_key_validator = RegexValidator(
    regex=r'^[a-z][a-z0-9_]*$',
    message='Nur Kleinbuchstaben, Zahlen und Unterstriche; muss mit einem Buchstaben beginnen.',
)

class Status(models.Model):
    """Ausbildungsstatus einer Nachwuchskraft (z. B. aktiv, ausgeschieden) mit Farbcodierung."""

    COLOR_CHOICES = [
        ('success',   'Grün'),
        ('secondary', 'Grau'),
        ('danger',    'Rot'),
        ('warning',   'Gelb'),
        ('info',      'Blau'),
    ]

    status = models.AutoField(primary_key=True)
    description = models.CharField(
        max_length=100,
        verbose_name="Beschreibung"
    )
    color = models.CharField(
        max_length=20,
        choices=COLOR_CHOICES,
        default='secondary',
        verbose_name="Farbe",
    )

    def __str__(self):
        return self.description

    class Meta:
        verbose_name_plural = "Status"
        verbose_name = "Status"


class Employment(models.Model):
    """Art des Beschäftigungsverhältnisses (z. B. Beamtenanwärter, Tarifbeschäftigte)."""

    type = models.AutoField(
        primary_key=True,
        verbose_name="Art"
    )
    description = models.CharField(
        max_length=100,
        verbose_name="Beschreibung"
    )

    def __str__(self):
        return f"{self.description}"

    class Meta:
        verbose_name_plural = "Beschäftigungsverhältnisse"
        verbose_name = "Beschäftigungsverhältnis"


def create_student_id():
    """Erzeugt eine eindeutige Nachwuchskraft-ID (z. B. 'azubi-a1b2c3d4')."""
    return 'azubi-' + token_hex(4)

class Student(models.Model):
    """Nachwuchskraft mit persönlichen Daten, Kurszugehörigkeit und optionalem Portal-Zugang."""
    id = models.CharField(
        primary_key=True,
        unique=True,
        default=create_student_id,
        editable=False
    )
    gender = models.ForeignKey(
        Gender,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Geschlecht"
    )
    first_name = models.CharField(
        max_length=100,
        verbose_name="Vorname"
    )
    last_name = models.CharField(
        max_length=100,
        verbose_name="Nachname"
    )
    date_of_birth = models.DateField(verbose_name="Geburtsdatum")
    place_of_birth = models.CharField(max_length=100, verbose_name="Geburtsort")
    phone_number = models.CharField(
        max_length=12,
        null=True,
        blank=True,
        verbose_name="Telefonnummer"
    )
    email_private = models.EmailField(
        max_length=254,
        null=True,
        blank=True,
        verbose_name="E-Mail (privat)"
    )
    email_id = models.CharField(
        max_length=254,
        null=True,
        blank=True,
        verbose_name="E-Mail-Kennung (dienstlich)"
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="students",
        verbose_name="Kurs"
    )
    employment = models.ForeignKey(
        Employment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Beschäftigungsverhältnis"
    )
    status = models.ForeignKey(
        Status, on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Status"
    )
    status_changed_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Status geändert am"
    )
    address = models.OneToOneField(
        'services.Adress',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Adresse",
    )
    user = models.OneToOneField(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='student_profile',
        verbose_name="Portal-Benutzerkonto",
    )
    anonymized_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Anonymisiert am"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Erstellt am"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Geändert am"
    )

    def save(self, *args, **kwargs):
        if self.pk:
            try:
                old = Student.objects.get(pk=self.pk)
                if old.status_id != self.status_id:
                    from django.utils import timezone
                    self.status_changed_at = timezone.now()
            except Student.DoesNotExist:
                pass
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.gender} {self.first_name} {self.last_name}"

    def get_id(self):
        return self.id

    class Meta:
        verbose_name_plural = "Nachwuchskräfte"
        verbose_name = "Nachwuchskraft"


class TrainingResponsibleAccess(models.Model):
    """Lesezugriff eines Ausbildungsverantwortlichen auf eine Nachwuchskraft."""
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='training_responsible_access_grants',
    )
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='training_responsible_student_access',
        verbose_name="Ausbildungsverantwortliche-Benutzer",
    )
    granted_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='training_responsible_access_granted',
        verbose_name="Erteilt von",
    )
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'student_personalstelleaccess'
        unique_together = ['student', 'user']
        verbose_name = "Ausbildungsverantwortliche-Zugriff"
        verbose_name_plural = "Ausbildungsverantwortliche-Zugriffe"

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} → {self.student}"

# Abwärtskompatibilität (alter Modellname)
PersonalstelleAccess = TrainingResponsibleAccess


class Grade(models.Model):
    """Eine Note / ein Leistungsnachweis einer Nachwuchskraft."""
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
        related_name='grades',
        verbose_name="Nachwuchskraft",
    )
    grade_type = models.ForeignKey(
        'course.GradeType',
        on_delete=models.PROTECT,
        related_name='grades',
        verbose_name="Notenart",
    )
    value = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Note",
        help_text="z. B. 1,5 oder 87 Punkte",
    )
    date = models.DateField(null=True, blank=True, verbose_name="Datum")
    notes = models.TextField(blank=True, verbose_name="Anmerkungen")
    paperless_document_id = models.IntegerField(
        null=True, blank=True,
        verbose_name="Paperless-Dokument-ID",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.grade_type.name}: {self.value or '–'}"

    class Meta:
        verbose_name = "Note"
        verbose_name_plural = "Noten"
        ordering = ['grade_type__order', 'grade_type__name', '-date']


class StudentDocumentTemplate(models.Model):
    """Word-Vorlage (.docx) zur Generierung von Dokumenten für Nachwuchskräfte."""
    name = models.CharField(max_length=100, verbose_name="Name")
    description = models.TextField(blank=True, verbose_name="Beschreibung",
                                   help_text="Verfügbare Platzhalter – "
                                             "Nachwuchskraft: {{ vorname }}, {{ nachname }}, {{ student_id }}, "
                                             "{{ geburtsdatum }}, {{ geburtsort }}, {{ email_privat }}, "
                                             "{{ email_dienstlich }}, {{ telefon }} | "
                                             "Kurs: {{ kurs }}, {{ kurs_beginn }}, {{ kurs_ende }} | "
                                             "Berufsbild: {{ berufsbild }}, {{ berufsbild_beschreibung }}, "
                                             "{{ abschluss }}, {{ gesetzesgrundlage }}, {{ laufbahn }}, {{ fachrichtung }} | "
                                             "Meta: {{ heute }}, {{ erstellt_von }}, {{ ersteller_funktion }}, "
                                             "{{ ersteller_standort }}, {{ ersteller_raum }}, {{ ersteller_durchwahl }}")
    template_file = models.FileField(
        upload_to='student/dokument_vorlagen/',
        verbose_name="Vorlage (.docx)",
    )
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    available_in_portal = models.BooleanField(
        default=False,
        verbose_name="Im Portal verfügbar",
        help_text="Nachwuchskräfte können dieses Dokument selbst im Portal generieren.",
    )
    uploaded_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Dokumentvorlage"
        verbose_name_plural = "Dokumentvorlagen"
        ordering = ['name']


class StudentDocumentTemplateField(models.Model):
    """Zusätzliches Eingabefeld einer Dokumentvorlage (frei definierbarer Platzhalter)."""

    FIELD_TYPE_TEXT = 'text'
    FIELD_TYPE_TEXTAREA = 'textarea'
    FIELD_TYPE_DATE = 'date'
    FIELD_TYPE_NUMBER = 'number'
    FIELD_TYPE_SELECT = 'select'
    FIELD_TYPE_CHOICES = [
        (FIELD_TYPE_TEXT, 'Text (einzeilig)'),
        (FIELD_TYPE_TEXTAREA, 'Text (mehrzeilig)'),
        (FIELD_TYPE_DATE, 'Datum'),
        (FIELD_TYPE_NUMBER, 'Zahl'),
        (FIELD_TYPE_SELECT, 'Auswahl-Liste'),
    ]

    template = models.ForeignKey(
        StudentDocumentTemplate,
        on_delete=models.CASCADE,
        related_name='extra_fields',
        verbose_name='Dokumentvorlage',
    )
    key = models.CharField(
        max_length=64,
        validators=[template_field_key_validator],
        verbose_name='Schlüssel',
        help_text='Wird in der Word-Vorlage als {{ schlüssel }} verwendet.',
    )
    label = models.CharField(max_length=200, verbose_name='Beschriftung')
    field_type = models.CharField(
        max_length=20,
        choices=FIELD_TYPE_CHOICES,
        default=FIELD_TYPE_TEXT,
        verbose_name='Feldtyp',
    )
    required = models.BooleanField(default=False, verbose_name='Pflichtfeld')
    help_text = models.CharField(max_length=200, blank=True, verbose_name='Hilfetext')
    options = models.TextField(
        blank=True,
        verbose_name='Optionen',
        help_text='Bei Auswahl-Liste: eine Option pro Zeile.',
    )
    order = models.PositiveIntegerField(default=0, verbose_name='Reihenfolge')

    def get_options_list(self) -> list[str]:
        return [line.strip() for line in self.options.splitlines() if line.strip()]

    def __str__(self) -> str:
        return f'{self.template.name} – {self.label}'

    class Meta:
        verbose_name = 'Vorlagenfeld'
        verbose_name_plural = 'Vorlagenfelder'
        ordering = ['order', 'pk']
        unique_together = [('template', 'key')]


class StudentFieldDefinition(models.Model):
    """Definition eines benutzerdefinierten Feldes für Nachwuchskräfte."""

    FIELD_TYPES = [
        ('text',    'Text'),
        ('number',  'Zahl'),
        ('date',    'Datum'),
        ('boolean', 'Ja/Nein'),
    ]
    name = models.CharField(max_length=100, unique=True, verbose_name="Feldname")
    field_type = models.CharField(
        max_length=20,
        choices=FIELD_TYPES,
        default='text',
        verbose_name="Feldtyp",
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Benutzerdefiniertes Feld"
        verbose_name_plural = "Benutzerdefinierte Felder"
        ordering = ["name"]


class ContactEntry(models.Model):
    """Kontakteintrag in der Kontakthistorie einer Nachwuchskraft."""
    TYPE_PHONE = 'phone'
    TYPE_ON_SITE = 'on_site'
    TYPE_EMAIL = 'email'
    CONTACT_TYPE_CHOICES = [
        (TYPE_PHONE, 'Telefonisch'),
        (TYPE_ON_SITE, 'Vor Ort'),
        (TYPE_EMAIL, 'E-Mail'),
    ]
    TYPE_ICON = {
        TYPE_PHONE: 'bi-telephone',
        TYPE_ON_SITE: 'bi-geo-alt',
        TYPE_EMAIL: 'bi-envelope',
    }
    TYPE_COLOR = {
        TYPE_PHONE: 'info',
        TYPE_ON_SITE: 'success',
        TYPE_EMAIL: 'warning',
    }

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
        related_name='contact_entries',
        verbose_name='Nachwuchskraft',
    )
    contact_type = models.CharField(
        max_length=20,
        choices=CONTACT_TYPE_CHOICES,
        verbose_name='Art',
    )
    inquiry = models.TextField(verbose_name='Anfrage / Anliegen')
    response = models.TextField(blank=True, verbose_name='Gegebene Antwort')
    contacted_at = models.DateTimeField(verbose_name='Kontaktzeitpunkt')
    recorded_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Erfasst von',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def type_icon(self):
        return self.TYPE_ICON.get(self.contact_type, 'bi-chat-left')

    @property
    def type_color(self):
        return self.TYPE_COLOR.get(self.contact_type, 'secondary')

    def __str__(self):
        return f"{self.get_contact_type_display()} – {self.student} – {self.contacted_at:%d.%m.%Y}"

    class Meta:
        ordering = ['-contacted_at']
        verbose_name = 'Kontakteintrag'
        verbose_name_plural = 'Kontakteinträge'


class InternalNote(models.Model):
    """Interne Notiz zu einer Nachwuchskraft – nur für Ausbildungsreferat/-leitung sichtbar."""

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
        related_name='internal_notes',
        verbose_name='Nachwuchskraft',
    )
    text = models.TextField(verbose_name='Notiz')
    is_pinned = models.BooleanField(default=False, verbose_name='Angepinnt')
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Erstellt von',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Geändert am')

    class Meta:
        ordering = ['-is_pinned', '-created_at']
        verbose_name = 'Interne Notiz'
        verbose_name_plural = 'Interne Notizen'

    def __str__(self):
        return f'Notiz ({self.student}, {self.created_at:%d.%m.%Y})'


class StudentInquiry(models.Model):
    """Anfrage einer Nachwuchskraft an das Ausbildungsreferat."""
    id = models.CharField(primary_key=True, default=uuid.uuid4, editable=False)

    STATUS_CHOICES = [
        ('open', 'Offen'),
        ('in_progress', 'In Bearbeitung'),
        ('closed', 'Geschlossen'),
    ]

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='inquiries',
        verbose_name='Nachwuchskraft',
    )
    subject = models.CharField(max_length=200, verbose_name='Betreff')
    message = models.TextField(verbose_name='Nachricht')
    attachment = models.FileField(
        upload_to=uuid_upload_to('inquiries/attachments/'),
        blank=True,
        verbose_name='Anhang',
    )
    attachment_filename = models.CharField(
        max_length=255, blank=True, verbose_name='Originalname des Anhangs',
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='open',
        verbose_name='Status',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Aktualisiert am')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Anfrage'
        verbose_name_plural = 'Anfragen'

    def __str__(self):
        return f'{self.subject} ({self.student}, {self.get_status_display()})'

    def save(self, *args, **kwargs):
        if self.attachment and not self.attachment_filename:
            self.attachment_filename = os.path.basename(self.attachment.name)
        super().save(*args, **kwargs)


class InquiryReply(models.Model):
    """Antwort auf eine Anfrage (von Nachwuchskraft oder Personal)."""
    inquiry = models.ForeignKey(
        StudentInquiry,
        on_delete=models.CASCADE,
        related_name='replies',
        verbose_name='Anfrage',
    )
    author = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Verfasser',
    )
    message = models.TextField(verbose_name='Nachricht')
    attachment = models.FileField(
        upload_to=uuid_upload_to('inquiries/attachments/'),
        blank=True,
        verbose_name='Anhang',
    )
    attachment_filename = models.CharField(
        max_length=255, blank=True, verbose_name='Originalname des Anhangs',
    )
    is_staff_reply = models.BooleanField(default=False, verbose_name='Antwort vom Personal')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Antwort'
        verbose_name_plural = 'Antworten'

    def __str__(self):
        return f'Antwort auf „{self.inquiry.subject}" ({self.created_at:%d.%m.%Y})'

    def save(self, *args, **kwargs):
        if self.attachment and not self.attachment_filename:
            self.attachment_filename = os.path.basename(self.attachment.name)
        super().save(*args, **kwargs)


class StudentFieldValue(models.Model):
    """Wert eines benutzerdefinierten Feldes für eine bestimmte Nachwuchskraft."""

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="custom_field_values",
    )
    field = models.ForeignKey(
        StudentFieldDefinition,
        on_delete=models.CASCADE,
        verbose_name="Feld",
    )
    value = models.TextField(blank=True, verbose_name="Wert")

    def __str__(self):
        return f"{self.field.name}: {self.value}"

    class Meta:
        unique_together = ("student", "field")
        verbose_name = "Feldwert"
        verbose_name_plural = "Feldwerte"


# ── Checklisten / Onboarding-Tracking ─────────────────────────────────────────

class ChecklistTemplate(models.Model):
    """Vorlage für eine Onboarding-Checkliste."""
    name = models.CharField(max_length=100, verbose_name='Name')
    description = models.TextField(blank=True, verbose_name='Beschreibung')
    job_profiles = models.ManyToManyField(
        'course.JobProfile',
        blank=True,
        related_name='checklist_templates',
        verbose_name='Berufsbilder',
        help_text='Leer lassen = für alle Berufsbilder verfügbar.',
    )
    is_active = models.BooleanField(default=True, verbose_name='Aktiv')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Checklisten-Vorlage'
        verbose_name_plural = 'Checklisten-Vorlagen'
        ordering = ['name']


class ChecklistTemplateItem(models.Model):
    """Ein Punkt einer Checklisten-Vorlage."""
    template = models.ForeignKey(
        ChecklistTemplate,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Vorlage',
    )
    text = models.CharField(max_length=300, verbose_name='Aufgabe')
    order = models.PositiveIntegerField(default=0, verbose_name='Reihenfolge')

    def __str__(self):
        return self.text

    class Meta:
        verbose_name = 'Checklisten-Punkt (Vorlage)'
        verbose_name_plural = 'Checklisten-Punkte (Vorlage)'
        ordering = ['template', 'order', 'text']


class StudentChecklist(models.Model):
    """Eine Checkliste (Instanz) für eine Nachwuchskraft."""
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
        related_name='checklists',
        verbose_name='Nachwuchskraft',
    )
    template = models.ForeignKey(
        ChecklistTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Vorlage',
    )
    name = models.CharField(max_length=100, verbose_name='Name')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Erstellt von',
    )

    @property
    def progress(self):
        total = self.items.count()
        if not total:
            return 0
        done = self.items.filter(completed=True).count()
        return int(done / total * 100)

    @property
    def done_count(self):
        return self.items.filter(completed=True).count()

    @property
    def total_count(self):
        return self.items.count()

    def __str__(self):
        return f'{self.name} – {self.student}'

    class Meta:
        verbose_name = 'Checkliste'
        verbose_name_plural = 'Checklisten'
        ordering = ['-created_at']


class StudentChecklistItem(models.Model):
    """Ein einzelner Punkt einer NK-Checkliste mit Erledigungsstatus."""
    # Öffentliche, nicht erratbare ID – ersetzt int-PK in URLs gegen Enumeration.
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Öffentliche ID',
    )

    checklist = models.ForeignKey(
        StudentChecklist,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Checkliste',
    )
    text = models.CharField(max_length=300, verbose_name='Aufgabe')
    order = models.PositiveIntegerField(default=0, verbose_name='Reihenfolge')
    completed = models.BooleanField(default=False, verbose_name='Erledigt')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Erledigt am')
    completed_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='completed_checklist_items',
        verbose_name='Erledigt von',
    )

    def __str__(self):
        return self.text

    class Meta:
        verbose_name = 'Checklisten-Punkt'
        verbose_name_plural = 'Checklisten-Punkte'
        ordering = ['order', 'text']


class InternshipPreference(models.Model):
    """Wünsche einer Nachwuchskraft für Praktikumseinsätze."""
    student = models.OneToOneField(
        Student,
        on_delete=models.CASCADE,
        related_name='internship_preference',
        verbose_name='Nachwuchskraft',
    )
    preferred_units = models.ManyToManyField(
        'organisation.OrganisationalUnit',
        blank=True,
        related_name='preferred_by_students',
        verbose_name='Gewünschte Abteilungen / Behörden',
        help_text='Nur Ebene Abteilung oder Behörde.',
        limit_choices_to={'unit_type__in': ['authority', 'department']},
    )
    preferred_locations = models.ManyToManyField(
        'organisation.Location',
        blank=True,
        related_name='preferred_by_students',
        verbose_name='Gewünschte Standorte',
    )
    notes = models.TextField(
        blank=True,
        verbose_name='Weitere Wünsche / Anmerkungen',
        help_text='Freitext für individuelle Wünsche.',
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Aktualisiert am')

    class Meta:
        verbose_name = 'Einsatzwunsch'
        verbose_name_plural = 'Einsatzwünsche'

    def __str__(self):
        return f'Einsatzwünsche von {self.student}'
