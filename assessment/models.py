# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""
Modelle für das strukturierte Beurteilungssystem.

Beurteilungen sind immer an einen InternshipAssignment gekoppelt (Stationsbeurteilung).
Praxistutoren greifen über einen tokenbasierten Link zu – kein Login erforderlich.
Azubis können parallel eine Selbstbeurteilung im Portal ausfüllen.
"""
import uuid

from django.db import models

# ── Bewertungsskalen ──────────────────────────────────────────────────────────

SCALE_GRADE = 'grade'
SCALE_POINTS = 'points'
SCALE_CHOICES = [
    (SCALE_GRADE,  'Notenskala (1,0–6,0)'),
    (SCALE_POINTS, 'Punkteskala (0–15)'),
]

# Gültige Notenwerte für die Notenskala
GRADE_VALUES = ['1,0', '1,3', '1,7', '2,0', '2,3', '2,7', '3,0', '3,3', '3,7', '4,0', '5,0', '6,0']

# ── Status-Konstanten ─────────────────────────────────────────────────────────

STATUS_PENDING   = 'pending'
STATUS_SUBMITTED = 'submitted'
STATUS_CONFIRMED = 'confirmed'
STATUS_CHOICES_ASSESSMENT = [
    (STATUS_PENDING,   'Ausstehend'),
    (STATUS_SUBMITTED, 'Eingereicht'),
    (STATUS_CONFIRMED, 'Bestätigt'),
]

STATUS_DRAFT     = 'draft'
STATUS_CHOICES_SELF = [
    (STATUS_DRAFT,     'Entwurf'),
    (STATUS_SUBMITTED, 'Eingereicht'),
]


# ── Kriterium ─────────────────────────────────────────────────────────────────

class AssessmentCriterion(models.Model):
    """Ein einzelnes Beurteilungskriterium, das zu einem Berufsbild gehört."""
    job_profile = models.ForeignKey(
        'course.JobProfile',
        on_delete=models.CASCADE,
        related_name='assessment_criteria',
        verbose_name='Berufsbild',
    )
    name = models.CharField(max_length=200, verbose_name='Kriterium')
    category = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Kategorie',
        help_text='Optionale Gruppierung, z.B. „Fachkompetenz" oder „Sozialkompetenz".',
    )
    order = models.PositiveIntegerField(default=0, verbose_name='Reihenfolge')
    help_text = models.TextField(
        blank=True,
        verbose_name='Hinweistext',
        help_text='Erläuterung für Praxistutoren und Auszubildende.',
    )

    competences = models.ManyToManyField(
        'organisation.Competence',
        through='CriterionCompetenceWeight',
        related_name='assessment_criteria',
        blank=True,
        verbose_name='Kompetenz-Mapping',
        help_text='Auf welche Kompetenzen zahlt dieses Kriterium ein? '
                  'Grundlage für die Kompetenzmatrix.',
    )

    def __str__(self):
        return f'{self.name} ({self.job_profile})'

    class Meta:
        verbose_name = 'Beurteilungskriterium'
        verbose_name_plural = 'Beurteilungskriterien'
        ordering = ['job_profile', 'order', 'name']


class CriterionCompetenceWeight(models.Model):
    """N:M-Brücke zwischen Beurteilungskriterium und Kompetenz mit optionaler Gewichtung.

    Eine Bewertung eines Kriteriums fließt mit ``weight`` in den Kompetenzwert ein.
    Default 1.0 = volle Wirkung. Mit kleineren Werten lässt sich differenzieren,
    falls ein Kriterium nur teilweise auf eine Kompetenz wirkt.
    """
    criterion = models.ForeignKey(
        AssessmentCriterion,
        on_delete=models.CASCADE,
        related_name='competence_weights',
        verbose_name='Kriterium',
    )
    competence = models.ForeignKey(
        'organisation.Competence',
        on_delete=models.CASCADE,
        related_name='criterion_weights',
        verbose_name='Kompetenz',
    )
    weight = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=1.0,
        verbose_name='Gewicht',
        help_text='1.0 = volles Gewicht. Niedrigere Werte für teilweise Wirkung.',
    )

    class Meta:
        unique_together = ('criterion', 'competence')
        verbose_name = 'Kriterium → Kompetenz'
        verbose_name_plural = 'Kriterium → Kompetenz'

    def __str__(self):
        return f'{self.criterion.name} → {self.competence.name} (×{self.weight})'


# ── Vorlage ───────────────────────────────────────────────────────────────────

class AssessmentTemplate(models.Model):
    """Beurteilungsvorlage: Legt Bewertungsskala und Kriterien für ein Berufsbild fest."""
    job_profile = models.ForeignKey(
        'course.JobProfile',
        on_delete=models.CASCADE,
        related_name='assessment_templates',
        verbose_name='Berufsbild',
    )
    name = models.CharField(max_length=200, verbose_name='Bezeichnung')
    rating_scale = models.CharField(
        max_length=20,
        choices=SCALE_CHOICES,
        verbose_name='Bewertungsskala',
    )
    criteria = models.ManyToManyField(
        AssessmentCriterion,
        through='AssessmentTemplateCriterion',
        verbose_name='Kriterien',
        blank=True,
    )
    instructions_assessor = models.TextField(
        blank=True,
        verbose_name='Hinweise für Praxistutoren',
        help_text='Wird im Beurteilungsformular für Praxistutoren angezeigt.',
    )
    instructions_self = models.TextField(
        blank=True,
        verbose_name='Hinweise für Selbstbeurteilung',
        help_text='Wird im Portal-Formular für Auszubildende angezeigt.',
    )
    active = models.BooleanField(default=True, verbose_name='Aktiv')

    def __str__(self):
        return f'{self.name} – {self.job_profile}'

    def ordered_criteria(self):
        """Gibt Kriterien in der definierten Reihenfolge zurück."""
        return (
            self.criteria
            .through.objects
            .filter(template=self)
            .select_related('criterion')
            .order_by('order')
        )

    class Meta:
        verbose_name = 'Beurteilungsvorlage'
        verbose_name_plural = 'Beurteilungsvorlagen'
        ordering = ['job_profile', 'name']


class AssessmentTemplateCriterion(models.Model):
    """Verknüpfung zwischen Vorlage und Kriterium mit expliziter Reihenfolge."""
    template  = models.ForeignKey(AssessmentTemplate, on_delete=models.CASCADE)
    criterion = models.ForeignKey(AssessmentCriterion, on_delete=models.CASCADE)
    order     = models.PositiveIntegerField(default=0, verbose_name='Reihenfolge')

    class Meta:
        ordering = ['order']
        unique_together = ('template', 'criterion')
        verbose_name = 'Vorlagen-Kriterium'
        verbose_name_plural = 'Vorlagen-Kriterien'


# ── Beurteilung (Praxistutoren) ───────────────────────────────────────────────

class Assessment(models.Model):
    """
    Stationsbeurteilung durch den Praxistutoren.
    Zugriff via tokenbasiertem Link – kein Login erforderlich.
    """
    assignment = models.OneToOneField(
        'course.InternshipAssignment',
        on_delete=models.CASCADE,
        related_name='assessment',
        verbose_name='Praktikumseinsatz',
    )
    template = models.ForeignKey(
        AssessmentTemplate,
        on_delete=models.PROTECT,
        verbose_name='Beurteilungsvorlage',
    )
    # Öffentliche, nicht erratbare ID – ersetzt int-PK in URLs gegen Enumeration.
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Öffentliche ID',
    )
    token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        verbose_name='Token',
    )
    token_sent_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Token gesendet am',
    )
    reminder_count = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Anzahl Erinnerungen',
        help_text='Wie oft eine automatische Erinnerung an den Praxistutor gesendet wurde.',
    )
    last_reminder_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Letzte Erinnerung am',
    )
    escalated_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Eskaliert am',
        help_text='Zeitpunkt der Eskalation an die zuständige Ausbildungskoordination.',
    )
    escalated_to = models.ForeignKey(
        'instructor.TrainingCoordination',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='escalated_assessments',
        verbose_name='Eskaliert an',
    )
    assessor_name = models.CharField(
        max_length=200, blank=True,
        verbose_name='Name des Praxistutors',
    )
    assessor_email = models.CharField(
        max_length=254, blank=True,
        verbose_name='E-Mail des Praxistutors',
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES_ASSESSMENT,
        default=STATUS_PENDING,
        verbose_name='Status',
    )
    overall_comment = models.TextField(
        blank=True,
        verbose_name='Gesamtkommentar',
    )
    submitted_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Eingereicht am',
    )
    confirmed_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='confirmed_assessments',
        verbose_name='Bestätigt von',
    )
    confirmed_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Bestätigt am',
    )

    def __str__(self):
        return f'Beurteilung: {self.assignment}'

    @property
    def average_grade(self):
        """
        Berechnet den Durchschnittswert aller Kriterienbewertungen.
        Gibt einen formatierten String zurück (z.B. „2,3" oder „11,5")
        oder None wenn noch keine Ratings vorhanden.
        """
        values = list(self.ratings.values_list('value', flat=True))
        if not values:
            return None
        try:
            nums = [float(v.replace(',', '.')) for v in values]
            avg = sum(nums) / len(nums)
            if self.template.rating_scale == SCALE_GRADE:
                return f'{avg:.1f}'.replace('.', ',')
            else:
                return f'{avg:.1f}'.replace('.', ',')
        except (ValueError, TypeError):
            return None

    @property
    def status_badge(self):
        return {
            STATUS_PENDING:   'secondary',
            STATUS_SUBMITTED: 'warning',
            STATUS_CONFIRMED: 'success',
        }.get(self.status, 'light')

    class Meta:
        verbose_name = 'Stationsbeurteilung'
        verbose_name_plural = 'Stationsbeurteilungen'
        ordering = ['-assignment__end_date']


class AssessmentRating(models.Model):
    """Einzelbewertung eines Kriteriums innerhalb einer Stationsbeurteilung."""
    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name='ratings',
    )
    criterion = models.ForeignKey(
        AssessmentCriterion,
        on_delete=models.PROTECT,
        verbose_name='Kriterium',
    )
    value = models.CharField(
        max_length=20,
        verbose_name='Bewertung',
        help_text='Notenwert (z.B. „2,3") oder Punktzahl (z.B. „12").',
    )
    comment = models.TextField(blank=True, verbose_name='Kommentar')

    class Meta:
        unique_together = ('assessment', 'criterion')
        verbose_name = 'Kriteriumbewertung'
        verbose_name_plural = 'Kriteriumbewertungen'


# ── Selbstbeurteilung (Azubi) ─────────────────────────────────────────────────

class SelfAssessment(models.Model):
    """Selbstbeurteilung durch die Auszubildende Person im Portal."""
    assignment = models.OneToOneField(
        'course.InternshipAssignment',
        on_delete=models.CASCADE,
        related_name='self_assessment',
        verbose_name='Praktikumseinsatz',
    )
    template = models.ForeignKey(
        AssessmentTemplate,
        on_delete=models.PROTECT,
        verbose_name='Beurteilungsvorlage',
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES_SELF,
        default=STATUS_DRAFT,
        verbose_name='Status',
    )
    overall_comment = models.TextField(
        blank=True,
        verbose_name='Gesamtkommentar',
    )
    submitted_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Eingereicht am',
    )

    def __str__(self):
        return f'Selbstbeurteilung: {self.assignment}'

    @property
    def average_grade(self):
        """Durchschnittswert aller Selbstbewertungen."""
        values = list(self.ratings.values_list('value', flat=True))
        if not values:
            return None
        try:
            nums = [float(v.replace(',', '.')) for v in values]
            avg = sum(nums) / len(nums)
            return f'{avg:.1f}'.replace('.', ',')
        except (ValueError, TypeError):
            return None

    @property
    def status_badge(self):
        return {
            STATUS_DRAFT:     'secondary',
            STATUS_SUBMITTED: 'success',
        }.get(self.status, 'light')

    class Meta:
        verbose_name = 'Selbstbeurteilung'
        verbose_name_plural = 'Selbstbeurteilungen'
        ordering = ['-assignment__end_date']


class SelfAssessmentRating(models.Model):
    """Einzelbewertung eines Kriteriums in der Selbstbeurteilung."""
    self_assessment = models.ForeignKey(
        SelfAssessment,
        on_delete=models.CASCADE,
        related_name='ratings',
    )
    criterion = models.ForeignKey(
        AssessmentCriterion,
        on_delete=models.PROTECT,
        verbose_name='Kriterium',
    )
    value = models.CharField(
        max_length=20,
        verbose_name='Selbsteinschätzung',
    )
    comment = models.TextField(blank=True, verbose_name='Kommentar')

    class Meta:
        unique_together = ('self_assessment', 'criterion')
        verbose_name = 'Selbstbewertung (Kriterium)'
        verbose_name_plural = 'Selbstbewertungen (Kriterien)'


# ── Anonyme Stationsbewertung ─────────────────────────────────────────────────

class StationFeedbackCategory(models.Model):
    """
    Eine Bewertungskategorie für die anonyme Stationsbewertung.
    Konfigurierbar über den Admin – wird einmalig per Datenmigration befüllt.
    """
    name = models.CharField(
        max_length=80,
        unique=True,
        verbose_name='Interner Name',
        help_text='Kurzbezeichnung für die interne Verwaltung.',
    )
    label = models.CharField(
        max_length=120,
        verbose_name='Bezeichnung',
        help_text='Wird im Bewertungsformular angezeigt.',
    )
    help_text = models.TextField(
        blank=True,
        verbose_name='Erläuterung',
        help_text='Optionaler Hinweistext für Nachwuchskräfte.',
    )
    order = models.PositiveIntegerField(default=0, verbose_name='Reihenfolge')
    active = models.BooleanField(default=True, verbose_name='Aktiv')

    def __str__(self):
        return self.label

    class Meta:
        verbose_name = 'Stationsbewertungs-Kategorie'
        verbose_name_plural = 'Stationsbewertungs-Kategorien'
        ordering = ['order', 'name']


class StationFeedback(models.Model):
    """
    Anonyme Bewertung eines Praxisabschnitts durch eine Nachwuchskraft.

    Bewusst KEIN Fremdschlüssel auf Student/Nachwuchskraft –
    dadurch ist die Bewertung nicht auf einzelne Personen rückverfolgbar.
    Duplikat-Schutz läuft über InternshipAssignment.station_feedback_submitted.
    """
    unit = models.ForeignKey(
        'organisation.OrganisationalUnit',
        on_delete=models.PROTECT,
        related_name='station_feedbacks',
        verbose_name='Organisationseinheit',
    )
    schedule_block = models.ForeignKey(
        'course.ScheduleBlock',
        on_delete=models.PROTECT,
        related_name='station_feedbacks',
        verbose_name='Praxisblock',
    )
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name='Eingereicht am')
    comment = models.TextField(
        blank=True,
        verbose_name='Anmerkungen',
        help_text='Optionaler allgemeiner Kommentar (anonym).',
    )

    def __str__(self):
        return f'Stationsbewertung {self.unit} ({self.submitted_at.strftime("%d.%m.%Y") if self.submitted_at else "–"})'

    @property
    def average_grade(self):
        """Durchschnittsnote über alle Kategorien dieser Bewertung."""
        values = list(self.ratings.values_list('value', flat=True))
        if not values:
            return None
        return round(sum(values) / len(values), 1)

    class Meta:
        verbose_name = 'Stationsbewertung'
        verbose_name_plural = 'Stationsbewertungen'
        ordering = ['-submitted_at']


class StationFeedbackRating(models.Model):
    """Einzelbewertung einer Kategorie innerhalb einer anonymen Stationsbewertung."""
    feedback = models.ForeignKey(
        StationFeedback,
        on_delete=models.CASCADE,
        related_name='ratings',
    )
    category = models.ForeignKey(
        StationFeedbackCategory,
        on_delete=models.PROTECT,
        verbose_name='Kategorie',
    )
    value = models.PositiveSmallIntegerField(
        verbose_name='Note',
        help_text='Schulnote 1 (sehr gut) bis 6 (ungenügend).',
    )

    class Meta:
        unique_together = ('feedback', 'category')
        verbose_name = 'Stationsbewertung (Kategorie)'
        verbose_name_plural = 'Stationsbewertungen (Kategorien)'
