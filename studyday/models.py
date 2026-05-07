# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Datenmodelle für Lern- und Studientage (Regelungen, Sperrzeiträume, Anträge, Kontingentberechnung)."""

from datetime import date

import uuid
from django.db import models


SCOPE_INTERNSHIP = 'internship_only'
SCOPE_ENTIRE = 'entire_course'
SCOPE_CHOICES = [
    (SCOPE_INTERNSHIP, 'Nur während Praktika'),
    (SCOPE_ENTIRE, 'Gesamter Ausbildungsverlauf'),
]

ALLOC_TOTAL = 'total'
ALLOC_PER_BLOCK = 'per_block'
ALLOC_PER_WEEK = 'per_week'
ALLOC_PER_MONTH = 'per_month'
ALLOCATION_CHOICES = [
    (ALLOC_TOTAL,     'Gesamtbudget (fester Betrag)'),
    (ALLOC_PER_BLOCK, 'Tage je Block'),
    (ALLOC_PER_WEEK,  'Tage je Woche'),
    (ALLOC_PER_MONTH, 'Tage je Monat'),
]

STATUS_PENDING   = 'pending'
STATUS_APPROVED  = 'approved'
STATUS_REJECTED  = 'rejected'
STATUS_CANCELLED = 'cancelled'
STATUS_CHOICES = [
    (STATUS_PENDING,   'Ausstehend'),
    (STATUS_APPROVED,  'Genehmigt'),
    (STATUS_REJECTED,  'Abgelehnt'),
    (STATUS_CANCELLED, 'Storniert'),
]

TYPE_STUDY     = 'study'
TYPE_EXAM_PREP = 'exam_prep'
REQUEST_TYPE_CHOICES = [
    (TYPE_STUDY,     'Lerntag'),
    (TYPE_EXAM_PREP, 'Prüfungsvorbereitung'),
]

WEEKDAY_SHORT = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
WEEKDAY_LONG  = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']


class StudyDayPolicy(models.Model):
    """Regelwerk für Lern- und Studientage je Berufsbild."""

    job_profile = models.OneToOneField(
        'course.JobProfile',
        on_delete=models.CASCADE,
        related_name='study_day_policy',
        verbose_name='Berufsbild',
    )

    # ── Grundregel ─────────────────────────────────────────────────────────────
    scope = models.CharField(
        max_length=20,
        choices=SCOPE_CHOICES,
        default=SCOPE_ENTIRE,
        verbose_name='Geltungsbereich',
        help_text='Legen Sie fest, in welchem Zeitraum Lern- und Studientage genommen werden dürfen.',
    )
    allocation_type = models.CharField(
        max_length=20,
        choices=ALLOCATION_CHOICES,
        default=ALLOC_TOTAL,
        verbose_name='Zuteilungsart',
    )
    amount = models.PositiveSmallIntegerField(
        verbose_name='Anzahl Tage (Jahr 1)',
        help_text=(
            'Anzahl der Tage entsprechend der gewählten Zuteilungsart. '
            'Bei Staffelung gilt dieser Wert für das 1. Ausbildungsjahr.'
        ),
    )

    # ── Staffelung nach Ausbildungsjahr ────────────────────────────────────────
    amount_year2 = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='Anzahl Tage (Jahr 2)',
        help_text='Überschreibt die Grundanzahl im 2. Ausbildungsjahr. Leer = wie Jahr 1.',
    )
    amount_year3 = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='Anzahl Tage (Jahr 3+)',
        help_text='Überschreibt die Grundanzahl ab dem 3. Ausbildungsjahr. Leer = wie Jahr 1.',
    )

    # ── Kombinationsregeln ──────────────────────────────────────────────────────
    cap_per_month = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='Max. Tage je Monat',
        help_text=(
            'Optionale monatliche Obergrenze, unabhängig von der Zuteilungsart. '
            'Leer = keine monatliche Begrenzung.'
        ),
    )

    # ── Übertragbarkeit ─────────────────────────────────────────────────────────
    allow_carryover = models.BooleanField(
        default=False,
        verbose_name='Übertragung ins Folgejahr erlaubt',
        help_text=(
            'Gibt an, ob nicht genutzte Tage in das nächste Ausbildungsjahr '
            'übertragen werden dürfen.'
        ),
    )

    # ── Prüfungsvorbereitungstage ───────────────────────────────────────────────
    exam_prep_days = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='Prüfungsvorbereitungstage je Jahr',
        help_text=(
            'Separates jährliches Budget für Prüfungsvorbereitung, zusätzlich zu '
            'den regulären Lerntagen. Leer = kein separates Kontingent.'
        ),
    )

    # ── Einschränkungen ─────────────────────────────────────────────────────────
    min_advance_days = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Beantragungsfrist (Tage)',
        help_text=(
            'Antrag muss mindestens diese Anzahl Tage im Voraus eingereicht werden. '
            '0 = keine Frist.'
        ),
    )
    max_days_per_request = models.PositiveSmallIntegerField(
        default=1,
        verbose_name='Max. Tage je Antrag',
        help_text=(
            'Maximale Anzahl aufeinanderfolgender Tage, die pro Antrag beantragt '
            'werden können. 1 = nur Einzeltage.'
        ),
    )
    allowed_weekdays = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Erlaubte Wochentage',
        help_text=(
            'Kommagetrennte Wochentage (0=Mo, 1=Di, …, 6=So). '
            'Leer = alle Tage erlaubt.'
        ),
    )

    # ── Interne Hinweise ────────────────────────────────────────────────────────
    notes = models.TextField(
        blank=True,
        verbose_name='Hinweise',
        help_text='Optionale interne Anmerkungen zu dieser Regelung.',
    )

    class Meta:
        verbose_name = 'Lerntage-Regelung'
        verbose_name_plural = 'Lerntage-Regelungen'
        ordering = ['job_profile__job_profile']

    def __str__(self):
        return f'{self.job_profile.job_profile} – {self.get_allocation_type_display()} ({self.amount} Tage)'

    def get_human_rule(self):
        """Gibt eine lesbare Kurzformel der Regelung zurück."""
        scope_label = 'während Praktika' if self.scope == SCOPE_INTERNSHIP else 'im gesamten Ausbildungsverlauf'
        alloc = self.get_allocation_type_display()
        parts = [f'{self.amount} Tag(e) {alloc.lower()}, {scope_label}']
        if self.amount_year2 or self.amount_year3:
            parts.append('gestaffelt')
        if self.cap_per_month:
            parts.append(f'max. {self.cap_per_month}/Monat')
        return ', '.join(parts)

    def get_allowed_weekday_ints(self):
        """Gibt erlaubte Wochentage als Integer-Liste zurück."""
        if not self.allowed_weekdays:
            return list(range(7))
        try:
            return [int(d) for d in self.allowed_weekdays.split(',') if d.strip()]
        except ValueError:
            return list(range(7))

    def get_allowed_weekday_short_names(self):
        """Gibt Kurzbezeichnungen der erlaubten Wochentage zurück."""
        return [WEEKDAY_SHORT[i] for i in self.get_allowed_weekday_ints() if 0 <= i <= 6]


class StudyDayBlackout(models.Model):
    """Gesperrter Zeitraum, in dem keine Lerntage beantragt werden können."""

    policy = models.ForeignKey(
        StudyDayPolicy,
        on_delete=models.CASCADE,
        related_name='blackouts',
        verbose_name='Regelung',
    )
    start_date = models.DateField(verbose_name='Beginn')
    end_date = models.DateField(verbose_name='Ende')
    label = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Bezeichnung',
        help_text='Z. B. „Prüfungszeitraum" oder „Betriebsferien".',
    )
    is_recurring_annually = models.BooleanField(
        default=False,
        verbose_name='Jährlich wiederkehrend',
        help_text=(
            'Wenn aktiviert, gilt die Sperre jedes Jahr in demselben Zeitraum '
            '(nur Monat und Tag werden geprüft).'
        ),
    )

    class Meta:
        verbose_name = 'Sperrzeitraum'
        verbose_name_plural = 'Sperrzeiträume'
        ordering = ['start_date']

    def __str__(self):
        label = self.label or 'Sperrzeitraum'
        return f'{label} ({self.start_date.strftime("%d.%m.")}–{self.end_date.strftime("%d.%m.%Y")})'

    def is_in_period(self, check_date):
        """Prüft, ob check_date in diesem Sperrzeitraum liegt."""
        if self.is_recurring_annually:
            start_md = (self.start_date.month, self.start_date.day)
            end_md = (self.end_date.month, self.end_date.day)
            check_md = (check_date.month, check_date.day)
            if start_md <= end_md:
                return start_md <= check_md <= end_md
            else:  # Sperrzeitraum überspannt Jahreswechsel
                return check_md >= start_md or check_md <= end_md
        return self.start_date <= check_date <= self.end_date


class StudyDayRequest(models.Model):
    """Antrag auf einen Lern- oder Studientag einer Nachwuchskraft."""

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
        related_name='study_day_requests',
        verbose_name='Nachwuchskraft',
    )
    date = models.DateField(verbose_name='Datum (von)')
    date_end = models.DateField(
        null=True,
        blank=True,
        verbose_name='Datum (bis)',
        help_text='Leer = eintägiger Antrag.',
    )
    request_type = models.CharField(
        max_length=20,
        choices=REQUEST_TYPE_CHOICES,
        default=TYPE_STUDY,
        verbose_name='Art',
    )
    reason = models.TextField(
        blank=True,
        verbose_name='Begründung',
        help_text='Optionale Begründung für den Lerntag.',
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name='Status',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Beantragt am')

    # Freigabe / Ablehnung
    approved_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='study_day_approvals',
        verbose_name='Freigegeben / Abgelehnt von',
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='Freigegeben / Abgelehnt am')
    rejection_reason = models.TextField(
        blank=True,
        verbose_name='Ablehnungsgrund',
    )

    # Stornierung (nur durch Ausbildungsreferat)
    cancelled_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='study_day_cancellations',
        verbose_name='Storniert von',
    )
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name='Storniert am')

    notification_sequence = models.PositiveIntegerField(
        default=0,
        verbose_name='iCal-Sequenznummer',
        help_text='Wird bei jedem Update inkrementiert; Outlook erkennt Termin-Updates über UID + SEQUENCE.',
    )

    class Meta:
        verbose_name = 'Lerntag-Antrag'
        verbose_name_plural = 'Lerntag-Anträge'
        ordering = ['-date']

    def __str__(self):
        return f'{self.student} – {self.date.strftime("%d.%m.%Y")} ({self.get_status_display()})'

    def bump_notification_sequence(self):
        """Erhöht die iCal-Sequenznummer; vor Re-Versand einer geänderten/stornierten Termin-Mail aufrufen."""
        self.notification_sequence = (self.notification_sequence or 0) + 1
        self.save(update_fields=['notification_sequence'])

    @property
    def days_count(self):
        """Anzahl beantragter Tage (1 bei Einzelantrag, n bei Bereichsantrag)."""
        if self.date_end and self.date_end > self.date:
            return (self.date_end - self.date).days + 1
        return 1

    @property
    def date_display(self):
        """Lesbare Datumsdarstellung."""
        if self.date_end and self.date_end != self.date:
            return f'{self.date.strftime("%d.%m.%Y")} – {self.date_end.strftime("%d.%m.%Y")}'
        return self.date.strftime('%d.%m.%Y')


def _sum_days(queryset):
    """Summiert days_count aller Anträge in einem QuerySet."""
    return sum(req.days_count for req in queryset)


def _add_years_safe(d, years):
    """Addiert Jahre auf ein Datum; fällt bei Feb-29-Problemen auf den 28. zurück."""
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        return d.replace(year=d.year + years, day=28)


def get_study_day_balance(student):
    """
    Berechnet das Lerntage-Guthaben einer Nachwuchskraft.

    Rückgabe: dict mit 'policy', 'total', 'approved', 'pending', 'remaining',
    optional 'monthly_cap', 'monthly_remaining', 'exam_prep'
    oder None, wenn keine Regelung für das Berufsbild existiert.
    """
    if not student.course or not student.course.job_profile:
        return None

    try:
        policy = StudyDayPolicy.objects.select_related('job_profile').get(
            job_profile=student.course.job_profile
        )
    except StudyDayPolicy.DoesNotExist:
        return None

    today = date.today()
    course = student.course

    # Laufendes Ausbildungsjahr bestimmen (0-basiert)
    training_year = min(2, (today - course.start_date).days // 365)
    year_amounts = [
        policy.amount,
        policy.amount_year2 if policy.amount_year2 is not None else policy.amount,
        policy.amount_year3 if policy.amount_year3 is not None else policy.amount,
    ]
    current_year_amount = year_amounts[training_year]

    # Gesamtbudget berechnen
    if policy.allocation_type == ALLOC_TOTAL:
        if policy.amount_year2 is not None or policy.amount_year3 is not None:
            # Gestaffelt: kumulierte Jahresbudgets
            total = sum(year_amounts[:training_year + 1])
        else:
            total = policy.amount

    elif policy.allocation_type == ALLOC_PER_BLOCK:
        from course.models import ScheduleBlock
        qs = ScheduleBlock.objects.filter(course=course, start_date__lte=today)
        if policy.scope == SCOPE_INTERNSHIP:
            qs = qs.filter(block_type='internship')
        total = qs.count() * current_year_amount

    elif policy.allocation_type == ALLOC_PER_WEEK:
        total = _calc_days_based_total(policy, course, today, divisor=7, amount=current_year_amount)

    elif policy.allocation_type == ALLOC_PER_MONTH:
        total = _calc_days_based_total(policy, course, today, divisor=30, amount=current_year_amount)

    else:
        total = 0

    approved_qs = StudyDayRequest.objects.filter(
        student=student,
        status=STATUS_APPROVED,
        request_type=TYPE_STUDY,
    )
    pending_qs = StudyDayRequest.objects.filter(
        student=student,
        status=STATUS_PENDING,
        request_type=TYPE_STUDY,
    )
    approved = _sum_days(approved_qs)
    pending = _sum_days(pending_qs)

    # Monatliche Obergrenze
    monthly_cap = policy.cap_per_month
    monthly_remaining = None
    if monthly_cap:
        month_start = today.replace(day=1)
        approved_this_month = _sum_days(approved_qs.filter(date__gte=month_start))
        monthly_remaining = max(0, monthly_cap - approved_this_month)

    # Prüfungsvorbereitungstage (jährliches Kontingent)
    exam_prep_balance = None
    if policy.exam_prep_days is not None:
        year_start = _add_years_safe(course.start_date, training_year)
        year_end   = _add_years_safe(course.start_date, training_year + 1)
        ep_approved = _sum_days(StudyDayRequest.objects.filter(
            student=student,
            status=STATUS_APPROVED,
            request_type=TYPE_EXAM_PREP,
            date__gte=year_start,
            date__lt=year_end,
        ))
        ep_pending = _sum_days(StudyDayRequest.objects.filter(
            student=student,
            status=STATUS_PENDING,
            request_type=TYPE_EXAM_PREP,
            date__gte=year_start,
            date__lt=year_end,
        ))
        exam_prep_balance = {
            'total':     policy.exam_prep_days,
            'approved':  ep_approved,
            'pending':   ep_pending,
            'remaining': max(0, policy.exam_prep_days - ep_approved),
        }

    return {
        'policy':            policy,
        'total':             total,
        'approved':          approved,
        'pending':           pending,
        'remaining':         max(0, total - approved),
        'monthly_cap':       monthly_cap,
        'monthly_remaining': monthly_remaining,
        'exam_prep':         exam_prep_balance,
    }


def _calc_days_based_total(policy, course, today, divisor, amount=None):
    """Hilfsfunktion für per_week / per_month Berechnungen."""
    if amount is None:
        amount = policy.amount
    if policy.scope == SCOPE_INTERNSHIP:
        from course.models import ScheduleBlock
        blocks = ScheduleBlock.objects.filter(
            course=course,
            block_type='internship',
            start_date__lte=today,
        )
        total_days = sum(
            max(0, (min(b.end_date, today) - b.start_date).days + 1)
            for b in blocks
        )
    else:
        start = course.start_date
        end = min(course.end_date, today)
        total_days = max(0, (end - start).days + 1)

    return int(total_days / divisor) * amount
