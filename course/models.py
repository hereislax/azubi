# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Datenmodelle für Kurse, Berufsbilder, Ablaufpläne, Praktikumseinsätze und Zuweisungsschreiben."""

import uuid
from secrets import token_hex

from django.db import models
class Career(models.Model):
    """Laufbahn"""
    abbreviation = models.CharField(
        primary_key=True,
        unique=True,
        max_length=2,
        verbose_name="Abkürzung"
    )
    description = models.CharField(
        max_length=100,
        verbose_name="Bezeichnung"
    )

    def __str__(self):
        return f"{self.description} ({self.abbreviation})"

    class Meta:
        verbose_name_plural = "Laufbahnen"
        verbose_name = "Laufbahn"

class Specialization(models.Model):
    """Fachrichtung"""
    specialization = models.CharField(
        primary_key=True,
        unique=True,
        max_length=2,
        verbose_name="Abkürzung"
    )
    description = models.CharField(
        max_length=100,
        verbose_name="Beschreibung"
    )

    def __str__(self):
        return f"{self.specialization} ({self.description})"

    class Meta:
        verbose_name_plural = "Fachrichtungen"
        verbose_name = "Fachrichtung"

class JobProfile(models.Model):
    """Berufsbild"""
    job_profile = models.CharField(
        max_length=120,
        verbose_name="Berufsbild"
    )
    description = models.TextField(
        verbose_name="Beschreibung"
    )
    degree = models.CharField(
        max_length=120,
        verbose_name="Abschluss"
    )
    legal_basis = models.CharField(
        max_length=120,
        verbose_name="Gesetzesgrundlage"
    )
    career = models.ForeignKey(
        Career,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Laufbahn"
    )
    specialization = models.ForeignKey(
        Specialization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Fachrichtung"
    )

    requires_proof_of_training = models.BooleanField(
        default=False,
        verbose_name="Ausbildungsnachweis erforderlich",
        help_text="Nachwuchskräfte mit diesem Berufsbild müssen wöchentliche Ausbildungsnachweise führen.",
    )

    def __str__(self):
        return f"{self.description} ({self.job_profile})"

    class Meta:
        verbose_name_plural = "Berufsbilder"
        verbose_name = "Berufsbild"


class GradeType(models.Model):
    """Eine Art von Prüfung/Leistungsnachweis, die zu einem Berufsbild gehört."""
    job_profile = models.ForeignKey(
        JobProfile,
        on_delete=models.CASCADE,
        related_name='grade_types',
        verbose_name="Berufsbild",
    )
    name = models.CharField(max_length=200, verbose_name="Bezeichnung")
    order = models.PositiveIntegerField(default=0, verbose_name="Reihenfolge")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Notenart"
        verbose_name_plural = "Notenarten"
        ordering = ['job_profile', 'order', 'name']


class CurriculumRequirement(models.Model):
    """Ausbildungsplan-Anforderung: eine Pflicht- oder Wahlstation im Berufsbild."""

    # Öffentliche, nicht erratbare ID – ersetzt int-PK in URLs gegen Enumeration.
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Öffentliche ID',
    )

    job_profile = models.ForeignKey(
        JobProfile,
        on_delete=models.CASCADE,
        related_name='curriculum_requirements',
        verbose_name='Berufsbild',
    )
    name = models.CharField(max_length=200, verbose_name='Bezeichnung',
                            help_text='z. B. „Sachgebiet Personal" oder „Abteilung Haushalt"')
    description = models.TextField(blank=True, verbose_name='Beschreibung / Lernziel')
    target_competence = models.ForeignKey(
        'organisation.Competence',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='curriculum_requirements',
        verbose_name='Ziel-Kompetenz',
        help_text='Wenn gesetzt, erfüllt jede OE mit dieser Kompetenz die Anforderung.',
    )
    target_units = models.ManyToManyField(
        'organisation.OrganisationalUnit',
        blank=True,
        related_name='curriculum_requirements',
        verbose_name='Ziel-Organisationseinheiten',
        help_text='Wenn gesetzt, erfüllt nur eine dieser OE die Anforderung (hat Vorrang vor Kompetenz).',
    )
    min_duration_weeks = models.PositiveIntegerField(
        default=1,
        verbose_name='Mindestdauer (Wochen)',
    )
    is_mandatory = models.BooleanField(default=True, verbose_name='Pflicht')
    order = models.PositiveIntegerField(default=0, verbose_name='Reihenfolge')

    class Meta:
        verbose_name = 'Ausbildungsplan-Anforderung'
        verbose_name_plural = 'Ausbildungsplan-Anforderungen'
        ordering = ['job_profile', 'order', 'name']

    def __str__(self):
        tag = 'Pflicht' if self.is_mandatory else 'Optional'
        return f'{self.name} ({self.job_profile}, {tag})'


class CompetenceTarget(models.Model):
    """Soll-Endwert einer Kompetenz pro Berufsbild für die Kompetenzmatrix.

    Der Wert beschreibt das **Endziel** am Abschluss der Ausbildung
    (0–100). In der Visualisierung wird linear vom Kursstart (0) bis
    Kursende (target_value) interpoliert, um den jeweiligen Soll-Wert
    zum aktuellen Zeitpunkt zu berechnen.
    """
    job_profile = models.ForeignKey(
        JobProfile,
        on_delete=models.CASCADE,
        related_name='competence_targets',
        verbose_name='Berufsbild',
    )
    competence = models.ForeignKey(
        'organisation.Competence',
        on_delete=models.CASCADE,
        related_name='targets',
        verbose_name='Kompetenz',
    )
    target_value = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=80.0,
        verbose_name='Endziel-Wert (0–100)',
        help_text='Wert, der am Ende der Ausbildung erreicht sein soll.',
    )

    class Meta:
        unique_together = ('job_profile', 'competence')
        verbose_name = 'Kompetenz-Endziel'
        verbose_name_plural = 'Kompetenz-Endziele'
        ordering = ['job_profile', 'competence__name']

    def __str__(self):
        return f'{self.competence.name} → {self.target_value} ({self.job_profile})'


class CurriculumCompletion(models.Model):
    """Manuelle Bestätigung einer Ausbildungsplan-Anforderung durch Staff."""
    requirement = models.ForeignKey(
        CurriculumRequirement,
        on_delete=models.CASCADE,
        related_name='completions',
        verbose_name='Anforderung',
    )
    student = models.ForeignKey(
        'student.Student',
        on_delete=models.CASCADE,
        related_name='curriculum_completions',
        verbose_name='Nachwuchskraft',
    )
    completed_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Bestätigt von',
    )
    completed_at = models.DateTimeField(auto_now_add=True, verbose_name='Bestätigt am')
    notes = models.TextField(blank=True, verbose_name='Anmerkung')

    class Meta:
        unique_together = ['requirement', 'student']
        verbose_name = 'Ausbildungsplan-Bestätigung'
        verbose_name_plural = 'Ausbildungsplan-Bestätigungen'

    def __str__(self):
        return f'{self.requirement.name} – {self.student} (bestätigt)'


class Course(models.Model):
    """Kurs"""
    title = models.CharField(
        primary_key=True,
        unique=True,
        max_length=100,
        verbose_name="Kursnummer"
    )
    start_date = models.DateField(verbose_name="Startdatum")
    end_date = models.DateField(verbose_name="Enddatum")
    job_profile = models.ForeignKey(
        JobProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Berufsbild",
    )

    def __str__(self):
        return self.title

    class Meta:
        verbose_name_plural = "Kurse"
        verbose_name = "Kurs"


def create_schedule_block_id():
    """Historischer Default-Generator für die alte CharField-PK von ScheduleBlock.
    Bleibt für historische Migrations referenzierbar – wird im aktuellen Modell
    nicht mehr verwendet (id ist jetzt BigAutoField).
    """
    return 'block-' + token_hex(4)


BLOCK_TYPE_NORMAL = 'normal'
BLOCK_TYPE_INTERNSHIP = 'internship'
BLOCK_TYPE_SEMINAR = 'seminar'
BLOCK_TYPE_CHOICES = [
    (BLOCK_TYPE_NORMAL, 'Theoriephase'),
    (BLOCK_TYPE_INTERNSHIP, 'Praktikum'),
    (BLOCK_TYPE_SEMINAR, 'Seminar'),
]


class ScheduleBlock(models.Model):
    """Block im Ablaufplan"""
    # id = BigAutoField (Django-Default). public_id (UUID) wird in URLs verwendet.
    # Öffentliche, nicht erratbare ID – ersetzt die schwächere Token-ID in URLs gegen Enumeration.
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Öffentliche ID',
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='schedule_blocks',
        verbose_name="Kurs"
    )
    name = models.CharField(max_length=200, verbose_name="Name")
    location = models.ForeignKey(
        'organisation.Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='schedule_blocks',
        verbose_name="Standort",
    )
    start_date = models.DateField(verbose_name="Beginn")
    end_date = models.DateField(verbose_name="Ende")
    block_type = models.CharField(
        max_length=20,
        choices=BLOCK_TYPE_CHOICES,
        default=BLOCK_TYPE_NORMAL,
        verbose_name="Blocktyp",
    )

    @property
    def is_internship(self) -> bool:
        return self.block_type == BLOCK_TYPE_INTERNSHIP

    @property
    def is_seminar(self) -> bool:
        return self.block_type == BLOCK_TYPE_SEMINAR

    def __str__(self):
        return f"{self.name} ({self.start_date} – {self.end_date})"

    class Meta:
        verbose_name = "Ablaufblock"
        verbose_name_plural = "Ablaufblöcke"
        ordering = ['start_date']


def pick_active_letter_template(model, job_profile):
    """Wählt die aktive Vorlage für ein Berufsbild – mit Fallback auf eine
    globale Vorlage (``job_profile=None``).

    Reihenfolge:
    1. Aktive Vorlage mit passendem ``job_profile``
    2. Aktive Vorlage ohne ``job_profile`` (globaler Default)

    Innerhalb der jeweiligen Gruppe gewinnt die zuletzt hochgeladene Variante.
    """
    qs = model.objects.filter(is_active=True)
    if job_profile is not None:
        specific = qs.filter(job_profile=job_profile).order_by('-uploaded_at').first()
        if specific:
            return specific
    return qs.filter(job_profile__isnull=True).order_by('-uploaded_at').first()


BLOCK_LETTER_STATUS_PENDING = 'pending_approval'
BLOCK_LETTER_STATUS_SENT = 'sent'
BLOCK_LETTER_STATUS_CHOICES = [
    (BLOCK_LETTER_STATUS_PENDING, 'Freigabe ausstehend'),
    (BLOCK_LETTER_STATUS_SENT, 'Versendet'),
]


class BlockLetterTemplate(models.Model):
    """Word-Vorlage (.docx) für Zuweisungsschreiben."""
    name = models.CharField(max_length=100, verbose_name="Name")
    description = models.TextField(blank=True, verbose_name="Beschreibung",
                                   help_text="Verfügbare Platzhalter: {{ block_name }}, {{ block_start }}, {{ block_end }}, "
                                             "{{ block_location }}, {{ freitext }}, {{ student_vorname }}, {{ student_nachname }}, "
                                             "{{ anrede }}, {{ kurs }}, {{ heute }}, {{ ersteller_vorname }}, {{ ersteller_nachname }}, "
                                             "{{ ersteller_funktion }}, {{ ersteller_standort }}, {{ ersteller_durchwahl }}")
    template_file = models.FileField(upload_to='course/zuweisungsschreiben_vorlagen/', verbose_name="Vorlage (.docx)")
    job_profile = models.ForeignKey(
        JobProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='block_letter_templates',
        verbose_name="Berufsbild",
        help_text="Wenn gesetzt, gilt diese Vorlage nur für Kurse dieses Berufsbilds. "
                  "Wenn leer, dient sie als Fallback für alle Berufsbilder.",
    )
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    uploaded_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Zuweisungsschreiben-Vorlage"
        verbose_name_plural = "Zuweisungsschreiben-Vorlagen"
        ordering = ['name']


class BlockLetter(models.Model):
    """Ein Zuweisungsschreiben-Stapel für alle NK eines Blocks."""
    schedule_block = models.ForeignKey(
        ScheduleBlock, on_delete=models.CASCADE,
        related_name='letters', verbose_name="Ablaufblock",
    )
    free_text = models.TextField(blank=True, verbose_name="Freitext")
    status = models.CharField(
        max_length=20, choices=BLOCK_LETTER_STATUS_CHOICES,
        default=BLOCK_LETTER_STATUS_PENDING, verbose_name="Status",
    )
    generated_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True,
        related_name='generated_block_letters', verbose_name="Erstellt von",
    )
    generated_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    approved_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approved_block_letters', verbose_name="Freigegeben von",
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name="Freigegeben am")

    def __str__(self):
        return f"Zuweisungsschreiben {self.schedule_block}"

    class Meta:
        verbose_name = "Zuweisungsschreiben"
        verbose_name_plural = "Zuweisungsschreiben"
        ordering = ['-generated_at']


class BlockLetterItem(models.Model):
    """Ein einzelnes Zuweisungsschreiben für eine Nachwuchskraft."""
    letter = models.ForeignKey(
        BlockLetter, on_delete=models.CASCADE,
        related_name='items', verbose_name="Zuweisungsschreiben",
    )
    student = models.ForeignKey(
        'student.Student', on_delete=models.CASCADE, verbose_name="Nachwuchskraft",
    )
    paperless_id = models.IntegerField(null=True, blank=True, verbose_name="Paperless-ID")
    email_sent = models.BooleanField(default=False, verbose_name="E-Mail gesendet")

    class Meta:
        verbose_name = "Zuweisungsschreiben-Eintrag"
        verbose_name_plural = "Zuweisungsschreiben-Einträge"
        unique_together = ['letter', 'student']


def _letter_status_fields():
    """Gemeinsame Felder für Letter-Batch-Modelle."""
    return dict(
        free_text=models.TextField(blank=True, verbose_name="Freitext"),
        status=models.CharField(
            max_length=20, choices=BLOCK_LETTER_STATUS_CHOICES,
            default=BLOCK_LETTER_STATUS_PENDING, verbose_name="Status",
        ),
        generated_at=models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am"),
        approved_at=models.DateTimeField(null=True, blank=True, verbose_name="Freigegeben am"),
    )


class InternshipPlanTemplate(models.Model):
    """Word-Vorlage (.docx) für Praktikumspläne."""
    name = models.CharField(max_length=100, verbose_name="Name")
    description = models.TextField(
        blank=True, verbose_name="Beschreibung",
        help_text=(
            "Verfügbare Platzhalter: {{ student_vorname }}, {{ student_nachname }}, {{ anrede }}, "
            "{{ kurs }}, {{ block_name }}, {{ block_start }}, {{ block_end }}, {{ freitext }}, {{ heute }}, "
            "{{ ersteller_name }}, {{ ersteller_funktion }}, {{ ersteller_standort }}, {{ ersteller_durchwahl }} | "
            "Liste: {% for e in einsaetze %} {{ e.einheit }}, {{ e.von }}, {{ e.bis }}, "
            "{{ e.standort }}, {{ e.praxistutor }} {% endfor %}"
        ),
    )
    template_file = models.FileField(upload_to='course/praktikumsplan_vorlagen/', verbose_name="Vorlage (.docx)")
    job_profile = models.ForeignKey(
        JobProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='internship_plan_templates',
        verbose_name="Berufsbild",
        help_text="Wenn gesetzt, gilt diese Vorlage nur für Kurse dieses Berufsbilds. "
                  "Wenn leer, dient sie als Fallback für alle Berufsbilder.",
    )
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    uploaded_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Praktikumsplan-Vorlage"
        verbose_name_plural = "Praktikumsplan-Vorlagen"
        ordering = ['name']


class InternshipPlanLetter(models.Model):
    """Batch: Praktikumspläne für alle Nachwuchskräfte eines Blocks."""
    schedule_block = models.ForeignKey(
        ScheduleBlock, on_delete=models.CASCADE,
        related_name='plan_letters', verbose_name="Ablaufblock",
    )
    free_text = models.TextField(blank=True, verbose_name="Freitext")
    status = models.CharField(
        max_length=20, choices=BLOCK_LETTER_STATUS_CHOICES,
        default=BLOCK_LETTER_STATUS_PENDING, verbose_name="Status",
    )
    generated_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True,
        related_name='generated_plan_letters', verbose_name="Erstellt von",
    )
    generated_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    approved_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approved_plan_letters', verbose_name="Freigegeben von",
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name="Freigegeben am")

    def __str__(self):
        return f"Praktikumsplan {self.schedule_block}"

    class Meta:
        verbose_name = "Praktikumsplan"
        verbose_name_plural = "Praktikumspläne"
        ordering = ['-generated_at']


class InternshipPlanItem(models.Model):
    """Ein Praktikumsplan für eine Nachwuchskraft."""
    letter = models.ForeignKey(
        InternshipPlanLetter, on_delete=models.CASCADE,
        related_name='items', verbose_name="Praktikumsplan",
    )
    student = models.ForeignKey(
        'student.Student', on_delete=models.CASCADE, verbose_name="Nachwuchskraft",
    )
    paperless_id = models.IntegerField(null=True, blank=True, verbose_name="Paperless-ID")
    email_sent = models.BooleanField(default=False, verbose_name="E-Mail gesendet")

    class Meta:
        verbose_name = "Praktikumsplan-Eintrag"
        verbose_name_plural = "Praktikumsplan-Einträge"
        unique_together = ['letter', 'student']


class StationLetterTemplate(models.Model):
    """Word-Vorlage (.docx) für Stationszuweisungsschreiben."""
    name = models.CharField(max_length=100, verbose_name="Name")
    description = models.TextField(
        blank=True, verbose_name="Beschreibung",
        help_text=(
            "Verfügbare Platzhalter: {{ student_vorname }}, {{ student_nachname }}, {{ anrede }}, "
            "{{ kurs }}, {{ block_name }}, {{ block_start }}, {{ block_end }}, {{ freitext }}, {{ heute }}, "
            "{{ einheit }}, {{ einheit_beschreibung }}, {{ einsatz_von }}, {{ einsatz_bis }}, "
            "{{ standort }}, {{ praxistutor }}, "
            "{{ ersteller_name }}, {{ ersteller_funktion }}, {{ ersteller_standort }}, {{ ersteller_durchwahl }}"
        ),
    )
    template_file = models.FileField(upload_to='course/stationsschreiben_vorlagen/', verbose_name="Vorlage (.docx)")
    job_profile = models.ForeignKey(
        JobProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='station_letter_templates',
        verbose_name="Berufsbild",
        help_text="Wenn gesetzt, gilt diese Vorlage nur für Kurse dieses Berufsbilds. "
                  "Wenn leer, dient sie als Fallback für alle Berufsbilder.",
    )
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    uploaded_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Stationsschreiben-Vorlage"
        verbose_name_plural = "Stationsschreiben-Vorlagen"
        ordering = ['name']


class StationLetter(models.Model):
    """Batch: Stationszuweisungsschreiben für alle Einsätze eines Blocks."""
    schedule_block = models.ForeignKey(
        ScheduleBlock, on_delete=models.CASCADE,
        related_name='station_letters', verbose_name="Ablaufblock",
    )
    free_text = models.TextField(blank=True, verbose_name="Freitext")
    status = models.CharField(
        max_length=20, choices=BLOCK_LETTER_STATUS_CHOICES,
        default=BLOCK_LETTER_STATUS_PENDING, verbose_name="Status",
    )
    generated_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True,
        related_name='generated_station_letters', verbose_name="Erstellt von",
    )
    generated_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    approved_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approved_station_letters', verbose_name="Freigegeben von",
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name="Freigegeben am")

    def __str__(self):
        return f"Stationsschreiben {self.schedule_block}"

    class Meta:
        verbose_name = "Stationszuweisungsschreiben"
        verbose_name_plural = "Stationszuweisungsschreiben"
        ordering = ['-generated_at']


class StationLetterItem(models.Model):
    """Ein Stationszuweisungsschreiben für einen Einsatz."""
    letter = models.ForeignKey(
        StationLetter, on_delete=models.CASCADE,
        related_name='items', verbose_name="Stationsschreiben",
    )
    assignment = models.ForeignKey(
        'InternshipAssignment', on_delete=models.CASCADE, verbose_name="Einsatz",
    )
    paperless_id = models.IntegerField(null=True, blank=True, verbose_name="Paperless-ID")
    email_sent = models.BooleanField(default=False, verbose_name="E-Mail gesendet")

    class Meta:
        verbose_name = "Stationsschreiben-Eintrag"
        verbose_name_plural = "Stationsschreiben-Einträge"
        unique_together = ['letter', 'assignment']


ASSIGNMENT_STATUS_PENDING = 'pending'
ASSIGNMENT_STATUS_APPROVED = 'approved'
ASSIGNMENT_STATUS_REJECTED = 'rejected'

ASSIGNMENT_STATUS_CHOICES = [
    (ASSIGNMENT_STATUS_PENDING,  'Ausstehend'),
    (ASSIGNMENT_STATUS_APPROVED, 'Angenommen'),
    (ASSIGNMENT_STATUS_REJECTED, 'Abgelehnt'),
]

def create_internship_assignment_id():
    return 'prax-' + token_hex(8)

class InternshipAssignment(models.Model):
    """Praktikumseinsatz einer Nachwuchskraft bei einer Organisationseinheit mit Genehmigungs-Workflow."""

    id = models.CharField(
        primary_key=True,
        unique=True,
        default=create_internship_assignment_id,
        editable=False
    )
    schedule_block = models.ForeignKey(
        ScheduleBlock,
        on_delete=models.CASCADE,
        related_name='internship_assignments',
        verbose_name="Praktikumsblock"
    )
    student = models.ForeignKey(
        'student.Student',
        on_delete=models.CASCADE,
        related_name='internship_assignments',
        verbose_name="Nachwuchskraft"
    )
    unit = models.ForeignKey(
        'organisation.OrganisationalUnit',
        on_delete=models.PROTECT,
        verbose_name="Organisationseinheit"
    )
    start_date = models.DateField(verbose_name="Beginn")
    end_date = models.DateField(verbose_name="Ende")
    instructor = models.ForeignKey(
        'instructor.Instructor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Praxistutor",
    )
    location = models.ForeignKey(
        'organisation.Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='internship_assignments',
        verbose_name="Standort",
    )
    notes = models.TextField(blank=True, default='', verbose_name="Notizen")
    status = models.CharField(
        max_length=20,
        choices=ASSIGNMENT_STATUS_CHOICES,
        default=ASSIGNMENT_STATUS_PENDING,
        verbose_name='Status',
    )
    rejection_reason = models.TextField(blank=True, default='', verbose_name='Ablehnungsgrund')
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_assignments',
        verbose_name='Angelegt von',
    )
    station_feedback_submitted = models.BooleanField(
        default=False,
        verbose_name='Stationsbewertung abgegeben',
        help_text='Wird gesetzt, wenn die Nachwuchskraft die anonyme Stationsbewertung eingereicht hat.',
    )
    notification_sequence = models.PositiveIntegerField(
        default=0,
        verbose_name='iCal-Sequenznummer',
        help_text='Wird bei jedem Update inkrementiert; Outlook erkennt Termin-Updates über UID + SEQUENCE.',
    )

    def __str__(self):
        return f"{self.student} – {self.unit} ({self.start_date} – {self.end_date})"

    def bump_notification_sequence(self):
        """Erhöht die iCal-Sequenznummer; vor Re-Versand einer geänderten/abgesagten Termin-Mail aufrufen."""
        self.notification_sequence = (self.notification_sequence or 0) + 1
        self.save(update_fields=['notification_sequence'])

    class Meta:
        verbose_name = "Praktikumseinsatz"
        verbose_name_plural = "Praktikumseinsätze"
        ordering = ['start_date']


# ── Generischer Änderungsantrag ──────────────────────────────────────────────

CHANGE_TYPE_SPLIT       = 'split'
CHANGE_TYPE_SHIFT       = 'shift'
CHANGE_TYPE_UNIT_CHANGE = 'unit_change'
CHANGE_TYPE_INSTRUCTOR  = 'instructor'
CHANGE_TYPE_LOCATION    = 'location'
CHANGE_TYPE_CANCEL      = 'cancel'

CHANGE_TYPE_CHOICES = [
    (CHANGE_TYPE_SPLIT,       'Einsatz teilen'),
    (CHANGE_TYPE_SHIFT,       'Zeitraum verschieben'),
    (CHANGE_TYPE_UNIT_CHANGE, 'Stationswechsel'),
    (CHANGE_TYPE_INSTRUCTOR,  'Praxistutor wechseln'),
    (CHANGE_TYPE_LOCATION,    'Standortwechsel'),
    (CHANGE_TYPE_CANCEL,      'Einsatz stornieren'),
]

# Praxistutor-Wechsel läuft direkt durch die Koordination ohne Antrag.
CHANGE_TYPES_REQUIRING_APPROVAL = {
    CHANGE_TYPE_SPLIT,
    CHANGE_TYPE_SHIFT,
    CHANGE_TYPE_UNIT_CHANGE,
    CHANGE_TYPE_LOCATION,
    CHANGE_TYPE_CANCEL,
}

CHANGE_REQUEST_STATUS_PENDING  = 'pending'
CHANGE_REQUEST_STATUS_APPROVED = 'approved'
CHANGE_REQUEST_STATUS_REJECTED = 'rejected'

CHANGE_REQUEST_STATUS_CHOICES = [
    (CHANGE_REQUEST_STATUS_PENDING,  'Ausstehend'),
    (CHANGE_REQUEST_STATUS_APPROVED, 'Angenommen'),
    (CHANGE_REQUEST_STATUS_REJECTED, 'Abgelehnt'),
]


class AssignmentChangeRequest(models.Model):
    """Allgemeiner Änderungsantrag für einen Praktikumseinsatz.

    Ersetzt ``InternshipSplitRequest`` und deckt darüber hinaus weitere
    Änderungstypen ab (siehe ``CHANGE_TYPE_CHOICES``). Die typabhängigen
    Daten liegen im ``payload``-JSON-Feld; die konkreten Änderungen werden
    durch ``course.change_handlers.apply_change_request`` ausgeführt.
    """
    # Öffentliche, nicht erratbare ID – ersetzt int-PK in URLs gegen Enumeration.
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Öffentliche ID',
    )
    assignment = models.ForeignKey(
        InternshipAssignment,
        on_delete=models.CASCADE,
        related_name='change_requests',
        verbose_name='Praktikumseinsatz',
    )
    change_type = models.CharField(
        max_length=20,
        choices=CHANGE_TYPE_CHOICES,
        verbose_name='Änderungstyp',
    )
    payload = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Daten',
        help_text='Typabhängige Felder, z. B. {"split_date": "2026-06-01"}.',
    )
    reason = models.TextField(blank=True, verbose_name='Begründung')
    requested_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='change_requests_made',
        verbose_name='Beantragt von',
    )
    requested_at = models.DateTimeField(auto_now_add=True, verbose_name='Beantragt am')
    status = models.CharField(
        max_length=20,
        choices=CHANGE_REQUEST_STATUS_CHOICES,
        default=CHANGE_REQUEST_STATUS_PENDING,
        verbose_name='Status',
    )
    decided_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='change_requests_decided',
        verbose_name='Entschieden von',
    )
    decided_at = models.DateTimeField(null=True, blank=True, verbose_name='Entschieden am')
    rejection_reason = models.TextField(blank=True, verbose_name='Ablehnungsgrund')

    def __str__(self):
        return f'{self.get_change_type_display()}: {self.assignment}'

    @property
    def requires_approval(self) -> bool:
        return self.change_type in CHANGE_TYPES_REQUIRING_APPROVAL

    @property
    def days_until_start(self) -> int:
        """Tage bis zum Einsatzbeginn (für conditional Routing)."""
        from datetime import date
        return (self.assignment.start_date - date.today()).days

    @property
    def is_short_notice(self) -> bool:
        """``True``, wenn der Einsatz innerhalb der nächsten 14 Tage beginnt.

        Wird in der Workflow-pre_condition genutzt, um „kurzfristige" Änderungen
        strenger zu behandeln (z. B. Genehmigungspflicht nur bei < 14 Tagen).
        """
        return self.days_until_start < 14

    def summary(self) -> str:
        """Menschenlesbare Beschreibung der beantragten Änderung."""
        from datetime import date as _date
        p = self.payload or {}

        def _fmt(value):
            try:
                return _date.fromisoformat(value).strftime('%d.%m.%Y')
            except (TypeError, ValueError):
                return value or '–'

        if self.change_type == CHANGE_TYPE_SPLIT:
            return f'Teilung am {_fmt(p.get("split_date"))}'
        if self.change_type == CHANGE_TYPE_SHIFT:
            return f'Verschiebung auf {_fmt(p.get("new_start_date"))} – {_fmt(p.get("new_end_date"))}'
        if self.change_type == CHANGE_TYPE_UNIT_CHANGE:
            return f'Wechsel zu Einheit #{p.get("new_unit_id", "–")}'
        if self.change_type == CHANGE_TYPE_INSTRUCTOR:
            return f'Wechsel zu Praxistutor #{p.get("new_instructor_id", "–")}'
        if self.change_type == CHANGE_TYPE_LOCATION:
            return f'Wechsel zu Standort #{p.get("new_location_id", "–")}'
        if self.change_type == CHANGE_TYPE_CANCEL:
            return 'Einsatz stornieren'
        return self.get_change_type_display()

    class Meta:
        verbose_name = 'Änderungsantrag'
        verbose_name_plural = 'Änderungsanträge'
        ordering = ['-requested_at']
        constraints = [
            models.UniqueConstraint(
                fields=['assignment', 'change_type'],
                condition=models.Q(status='pending'),
                name='unique_pending_change_request_per_type',
            ),
        ]


class CourseChecklist(models.Model):
    """Eine Checkliste (Instanz) für einen Kurs."""
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='checklists',
        verbose_name='Kurs',
    )
    template = models.ForeignKey(
        'student.ChecklistTemplate',
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
        return int(self.items.filter(completed=True).count() / total * 100)

    @property
    def done_count(self):
        return self.items.filter(completed=True).count()

    @property
    def total_count(self):
        return self.items.count()

    def __str__(self):
        return f'{self.name} – {self.course}'

    class Meta:
        verbose_name = 'Kurs-Checkliste'
        verbose_name_plural = 'Kurs-Checklisten'
        ordering = ['-created_at']


class CourseChecklistItem(models.Model):
    """Ein einzelner Punkt einer Kurs-Checkliste mit Erledigungsstatus."""
    checklist = models.ForeignKey(
        CourseChecklist,
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
        related_name='completed_course_checklist_items',
        verbose_name='Erledigt von',
    )

    def __str__(self):
        return self.text

    class Meta:
        verbose_name = 'Kurs-Checklisten-Punkt'
        verbose_name_plural = 'Kurs-Checklisten-Punkte'
        ordering = ['checklist', 'order', 'text']


LECTURE_STATUS_PENDING = 'pending'
LECTURE_STATUS_CONFIRMED = 'confirmed'
LECTURE_STATUS_DECLINED = 'declined'
LECTURE_STATUS_CHOICES = [
    (LECTURE_STATUS_PENDING, 'Bestätigung ausstehend'),
    (LECTURE_STATUS_CONFIRMED, 'Bestätigt'),
    (LECTURE_STATUS_DECLINED, 'Abgelehnt'),
]


class SeminarLecture(models.Model):
    """Einzelner Vortrag innerhalb eines Seminarblocks."""
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Öffentliche ID',
    )
    schedule_block = models.ForeignKey(
        ScheduleBlock,
        on_delete=models.CASCADE,
        related_name='lectures',
        verbose_name='Seminarblock',
    )
    topic = models.CharField(max_length=200, verbose_name='Thema')
    description = models.TextField(blank=True, verbose_name='Inhalt')
    location = models.CharField(max_length=200, blank=True, verbose_name='Ort')
    start_datetime = models.DateTimeField(verbose_name='Beginn')
    end_datetime = models.DateTimeField(verbose_name='Ende')
    speaker_name = models.CharField(max_length=150, verbose_name='Vortragender')
    speaker_email = models.EmailField(verbose_name='E-Mail Vortragender')
    status = models.CharField(
        max_length=20,
        choices=LECTURE_STATUS_CHOICES,
        default=LECTURE_STATUS_PENDING,
        verbose_name='Status',
    )
    confirmation_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Bestätigungs-Token',
    )
    decline_reason = models.TextField(blank=True, verbose_name='Ablehnungsgrund')
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name='Anfrage gesendet')
    responded_at = models.DateTimeField(null=True, blank=True, verbose_name='Antwort erhalten')
    reminder_sent_at = models.DateTimeField(null=True, blank=True, verbose_name='Erinnerung gesendet')
    notification_sequence = models.PositiveIntegerField(default=0, verbose_name='iCal-Sequenz')
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_lectures',
        verbose_name='Erstellt von',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Aktualisiert am')

    def __str__(self):
        return f'{self.topic} – {self.speaker_name} ({self.start_datetime:%d.%m.%Y %H:%M})'

    @property
    def is_pending(self) -> bool:
        return self.status == LECTURE_STATUS_PENDING

    @property
    def is_confirmed(self) -> bool:
        return self.status == LECTURE_STATUS_CONFIRMED

    @property
    def is_declined(self) -> bool:
        return self.status == LECTURE_STATUS_DECLINED

    class Meta:
        verbose_name = 'Vortrag'
        verbose_name_plural = 'Vorträge'
        ordering = ['start_datetime']
