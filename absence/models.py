# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""
Modelle für das Abwesenheitsmanagement (Urlaub & Krankmeldungen).
"""
import uuid
from datetime import date, timedelta

from django.db import models

from services.models import HOLIDAY_STATE_CHOICES  # noqa: F401  (re-export)


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _working_days_between(start: date, end: date, holiday_dates=frozenset()) -> int:
    """Anzahl der Arbeitstage (Mo–Fr) zwischen start und end (beide inklusiv), ohne Feiertage."""
    if not start or not end or start > end:
        return 0
    total = 0
    current = start
    while current <= end:
        if current.weekday() < 5 and current not in holiday_dates:  # 0=Mo … 4=Fr
            total += 1
        current += timedelta(days=1)
    return total


def _get_public_holidays(start: date, end: date, state: str = None) -> frozenset:
    """Gesetzliche Feiertage im Zeitraum.

    `state` (Bundesland-Kürzel) hat Vorrang. Wenn None, wird `AbsenceSettings.holiday_state`
    als Fallback verwendet (globale Default-Konfiguration).
    """
    try:
        import holidays as holidays_lib
        if state is None:
            state = AbsenceSettings.objects.values_list('holiday_state', flat=True).first() or ''
        years = list(range(start.year, end.year + 1))
        if state:
            h = holidays_lib.Germany(subdiv=state, years=years)
        else:
            h = holidays_lib.Germany(years=years)
        return frozenset(h.keys())
    except Exception:
        return frozenset()


def _resolve_location(student, target_date: date):
    """Standort an dem die Nachwuchskraft am `target_date` ist.

    Reihenfolge:
    1. `course.InternshipAssignment` der den Tag überlappt (genehmigt o. ä.)
    2. `course.ScheduleBlock` des Studenten-Kurses der den Tag überlappt
    3. None
    """
    if not student or not target_date:
        return None
    try:
        from course.models import InternshipAssignment, ScheduleBlock
    except Exception:
        return None

    assignment = (
        InternshipAssignment.objects
        .filter(
            student=student,
            start_date__lte=target_date,
            end_date__gte=target_date,
            location__isnull=False,
        )
        .select_related('location__address')
        .first()
    )
    if assignment and assignment.location:
        return assignment.location

    if getattr(student, 'course_id', None):
        block = (
            ScheduleBlock.objects
            .filter(
                course_id=student.course_id,
                start_date__lte=target_date,
                end_date__gte=target_date,
                location__isnull=False,
            )
            .select_related('location__address')
            .first()
        )
        if block and block.location:
            return block.location

    return None


def _resolve_holiday_state(student, target_date: date) -> str:
    """Bundesland für Feiertagsberechnung am `target_date`.

    Adress-Bundesland des Standorts → Fallback auf `AbsenceSettings.holiday_state` → ''.
    """
    location = _resolve_location(student, target_date)
    address = getattr(location, 'address', None) if location else None
    if address and address.holiday_state:
        return address.holiday_state
    try:
        return AbsenceSettings.objects.values_list('holiday_state', flat=True).first() or ''
    except Exception:
        return ''


def _working_days_in_course(course) -> int:
    """Gesamtzahl der Arbeitstage im Kurszeitraum (ohne Feiertage)."""
    if not course or not course.start_date or not course.end_date:
        return 0
    holiday_dates = _get_public_holidays(course.start_date, course.end_date)
    return _working_days_between(course.start_date, course.end_date, holiday_dates)


# ── Einstellungen (Singleton) ─────────────────────────────────────────────────

class AbsenceSettings(models.Model):
    """Konfiguration für das Abwesenheitsmodul – wird als Singleton verwendet."""

    vacation_office_email = models.EmailField(
        blank=True,
        db_column='urlaubsstelle_email',
        verbose_name='E-Mail Urlaubsstelle',
        help_text='Täglich werden Urlaubsanträge und Krankmeldungen an diese Adresse gesendet.',
    )
    holiday_state = models.CharField(
        max_length=2,
        blank=True,
        choices=HOLIDAY_STATE_CHOICES,
        default='',
        verbose_name='Bundesland (Feiertage)',
        help_text='Bundesland für die Berechnung gesetzlicher Feiertage bei der Arbeitstagsermittlung.',
    )

    class Meta:
        verbose_name        = 'Abwesenheitseinstellungen'
        verbose_name_plural = 'Abwesenheitseinstellungen'

    def __str__(self):
        return 'Abwesenheitseinstellungen'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


# ── Urlaubsantrag ─────────────────────────────────────────────────────────────

STATUS_PENDING   = 'pending'
STATUS_APPROVED  = 'approved'
STATUS_REJECTED  = 'rejected'
STATUS_PROCESSED = 'processed'
STATUS_CANCELLED = 'cancelled'

STATUS_CHOICES = [
    (STATUS_PENDING,   'Ausstehend'),
    (STATUS_APPROVED,  'Genehmigt'),
    (STATUS_REJECTED,  'Abgelehnt'),
    (STATUS_PROCESSED, 'Durch Urlaubsstelle bearbeitet'),
    (STATUS_CANCELLED, 'Storniert'),
]

STATUS_BADGE = {
    STATUS_PENDING:   'warning',
    STATUS_APPROVED:  'success',
    STATUS_REJECTED:  'danger',
    STATUS_PROCESSED: 'primary',
    STATUS_CANCELLED: 'secondary',
}


class VacationBatch(models.Model):
    """Tägliches Paket genehmigter Urlaubsanträge für die Urlaubsstelle."""

    token        = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    sent_at      = models.DateTimeField(auto_now_add=True, verbose_name='Versendet am')
    processed_at = models.DateTimeField(null=True, blank=True, verbose_name='Bearbeitet am')
    processed_by_name = models.CharField(max_length=200, blank=True, verbose_name='Bearbeitet von')

    class Meta:
        verbose_name        = 'Urlaubsantragspaket'
        verbose_name_plural = 'Urlaubsantragspakete'
        ordering = ['-sent_at']

    def __str__(self):
        return f'Paket vom {self.sent_at.strftime("%d.%m.%Y %H:%M")}'

    @property
    def is_processed(self):
        return self.processed_at is not None


class VacationRequest(models.Model):
    """Urlaubsantrag einer Nachwuchskraft."""

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
        related_name='vacation_requests',
        verbose_name='Nachwuchskraft',
    )
    start_date = models.DateField(verbose_name='Von')
    end_date   = models.DateField(verbose_name='Bis')
    notes      = models.TextField(blank=True, verbose_name='Anmerkungen')

    is_cancellation = models.BooleanField(default=False, verbose_name='Stornierungsantrag')
    original_request = models.ForeignKey(
        'self',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='cancellation_requests',
        verbose_name='Ursprünglicher Antrag',
    )
    submitted_via_portal = models.BooleanField(default=False, verbose_name='Im Portal eingereicht')

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name='Status',
    )

    # Genehmigung / Ablehnung
    approved_by      = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL,
                                          related_name='vacation_approvals',
                                          verbose_name='Freigegeben/Abgelehnt von')
    approved_at      = models.DateTimeField(null=True, blank=True, verbose_name='Freigegeben/Abgelehnt am')
    rejection_reason = models.TextField(blank=True, verbose_name='Ablehnungsgrund')

    # Stornierung (manuell durch Ausbildungsreferat)
    cancelled_by = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL,
                                      related_name='vacation_cancellations', verbose_name='Storniert von')
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name='Storniert am')

    # Urlaubsstelle
    batch = models.ForeignKey(
        VacationBatch,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='requests',
        verbose_name='Paket',
    )
    remaining_days_current_year  = models.SmallIntegerField(null=True, blank=True,
                                                              verbose_name='Resturlaub aktuelles Jahr')
    remaining_days_previous_year = models.SmallIntegerField(null=True, blank=True,
                                                              verbose_name='Resturlaub Vorjahr')
    manual_working_days = models.SmallIntegerField(
        null=True, blank=True,
        verbose_name='Arbeitstage (manuell)',
        help_text='Wenn gesetzt, überschreibt diese Zahl die automatisch berechneten Arbeitstage '
                  '(z. B. wegen interner Regelungen).',
    )
    location_override = models.ForeignKey(
        'organisation.Location',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='vacation_request_overrides',
        verbose_name='Standort (manuell)',
        help_text='Wenn gesetzt, überschreibt dieser Standort den automatisch ermittelten Standort '
                  'für die Feiertagsberechnung. Nur durch Ausbildungsreferat/Ausbildungsleitung änderbar.',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Urlaubsantrag'
        verbose_name_plural = 'Urlaubsanträge'
        ordering = ['-start_date', '-created_at']

    def __str__(self):
        kind = 'Stornierung' if self.is_cancellation else 'Urlaub'
        return (
            f'{kind}: {self.student} '
            f'{self.start_date.strftime("%d.%m.%Y")}–{self.end_date.strftime("%d.%m.%Y")} '
            f'({self.get_status_display()})'
        )

    @property
    def resolved_location(self):
        """Standort der für die Feiertagsberechnung gilt (Override > Auto > None)."""
        if self.location_override_id:
            return self.location_override
        if self.student_id and self.start_date:
            return _resolve_location(self.student, self.start_date)
        return None

    @property
    def resolved_holiday_state(self) -> str:
        loc = self.resolved_location
        address = getattr(loc, 'address', None) if loc else None
        if address and address.holiday_state:
            return address.holiday_state
        try:
            return AbsenceSettings.objects.values_list('holiday_state', flat=True).first() or ''
        except Exception:
            return ''

    @property
    def duration_working_days(self):
        state = self.resolved_holiday_state if self.student_id else None
        holiday_dates = _get_public_holidays(self.start_date, self.end_date, state=state)
        return _working_days_between(self.start_date, self.end_date, holiday_dates)

    @property
    def effective_working_days(self):
        """Manuell durch die Urlaubsstelle gesetzter Wert oder die Berechnung."""
        if self.manual_working_days is not None:
            return self.manual_working_days
        return self.duration_working_days

    @property
    def status_badge(self):
        return STATUS_BADGE.get(self.status, 'secondary')


class VacationConfirmationTemplate(models.Model):
    """Word-Vorlage (.docx) für die Urlaubsbestätigung durch die Urlaubsstelle."""

    name = models.CharField(max_length=100, verbose_name='Name')
    description = models.TextField(
        blank=True,
        verbose_name='Beschreibung',
        help_text=(
            'Verfügbare Platzhalter je Antrag (in {% for antrag in antraege %}-Schleife): '
            '{{ antrag.vorname }}, {{ antrag.nachname }}, {{ antrag.von }}, {{ antrag.bis }}, '
            '{{ antrag.arbeitstage }}, {{ antrag.resturlaub_aktuell }}, '
            '{{ antrag.resturlaub_vorjahr }}, {{ antrag.antragsart }}, {{ antrag.kurs }} | '
            'Global: {{ heute }}, {{ bearbeitet_von }}'
        ),
    )
    template_file = models.FileField(upload_to='absence/vorlagen/', verbose_name='Vorlage (.docx)')
    is_active     = models.BooleanField(default=True, verbose_name='Aktiv')
    uploaded_at   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Urlaubsbestätigungs-Vorlage'
        verbose_name_plural = 'Urlaubsbestätigungs-Vorlagen'
        ordering = ['name']

    def __str__(self):
        return self.name


# ── Krankmeldung ──────────────────────────────────────────────────────────────

SICK_TYPE_SELBST = 'selbstauskunft'
SICK_TYPE_KTASTE = 'k_taste'
SICK_TYPE_ATTEST = 'attest'

SICK_TYPE_CHOICES = [
    (SICK_TYPE_SELBST, 'Selbstauskunft'),
    (SICK_TYPE_KTASTE, 'K-Taste'),
    (SICK_TYPE_ATTEST, 'Attest'),
]

SICK_TYPE_BADGE = {
    SICK_TYPE_SELBST: 'info',
    SICK_TYPE_KTASTE: 'warning',
    SICK_TYPE_ATTEST: 'primary',
}

# Abwesenheitsampel
TRAFFIC_LIGHT_GREEN   = 'green'
TRAFFIC_LIGHT_YELLOW  = 'yellow'
TRAFFIC_LIGHT_RED     = 'red'
TRAFFIC_LIGHT_UNKNOWN = 'unknown'

TRAFFIC_LIGHT_CHOICES = [
    (TRAFFIC_LIGHT_GREEN,   'Grün (< 5 %)'),
    (TRAFFIC_LIGHT_YELLOW,  'Gelb (≥ 5 %)'),
    (TRAFFIC_LIGHT_RED,     'Rot (≥ 10 %)'),
    (TRAFFIC_LIGHT_UNKNOWN, 'Unbekannt'),
]

TRAFFIC_LIGHT_ICON = {
    TRAFFIC_LIGHT_GREEN:   ('success', 'bi-circle-fill', '< 5 % Fehlzeiten'),
    TRAFFIC_LIGHT_YELLOW:  ('warning', 'bi-circle-fill', '≥ 5 % Fehlzeiten'),
    TRAFFIC_LIGHT_RED:     ('danger',  'bi-circle-fill', '≥ 10 % Fehlzeiten'),
    TRAFFIC_LIGHT_UNKNOWN: ('secondary', 'bi-circle',    'Kein Kurs hinterlegt'),
}


class SickLeave(models.Model):
    """Krankmeldung einer Nachwuchskraft."""

    # Öffentliche, nicht erratbare ID – ersetzt int-PK in URLs gegen Enumeration.
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Öffentliche ID',
    )
    student    = models.ForeignKey('student.Student', on_delete=models.CASCADE,
                                    related_name='sick_leaves', verbose_name='Nachwuchskraft')
    start_date = models.DateField(verbose_name='Erster Krankheitstag')
    end_date   = models.DateField(null=True, blank=True, verbose_name='Letzter Krankheitstag')
    sick_type  = models.CharField(max_length=20, choices=SICK_TYPE_CHOICES,
                                   default=SICK_TYPE_SELBST, verbose_name='Art')
    notes      = models.TextField(blank=True, verbose_name='Anmerkungen')

    created_by = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='sick_leaves_created', verbose_name='Erfasst von')
    created_at = models.DateTimeField(auto_now_add=True)

    closed_by = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='sick_leaves_closed', verbose_name='Gesundgemeldet von')
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name='Gesundgemeldet am')

    # Für täglichen Bericht: wurden Öffnung/Schließung schon gemeldet?
    opening_reported = models.BooleanField(default=False, verbose_name='Öffnung gemeldet')
    closing_reported = models.BooleanField(default=False, verbose_name='Schließung gemeldet')

    class Meta:
        verbose_name        = 'Krankmeldung'
        verbose_name_plural = 'Krankmeldungen'
        ordering = ['-start_date']

    def __str__(self):
        end = self.end_date.strftime('%d.%m.%Y') if self.end_date else 'offen'
        return f'{self.student}: {self.start_date.strftime("%d.%m.%Y")}–{end}'

    @property
    def is_open(self):
        return self.end_date is None

    @property
    def resolved_location(self):
        if self.student_id and self.start_date:
            return _resolve_location(self.student, self.start_date)
        return None

    @property
    def resolved_holiday_state(self) -> str:
        loc = self.resolved_location
        address = getattr(loc, 'address', None) if loc else None
        if address and address.holiday_state:
            return address.holiday_state
        try:
            return AbsenceSettings.objects.values_list('holiday_state', flat=True).first() or ''
        except Exception:
            return ''

    @property
    def duration_working_days(self):
        end = self.end_date if self.end_date else date.today()
        state = self.resolved_holiday_state if self.student_id else None
        holiday_dates = _get_public_holidays(self.start_date, end, state=state)
        return _working_days_between(self.start_date, end, holiday_dates)

    @property
    def sick_type_badge(self):
        return SICK_TYPE_BADGE.get(self.sick_type, 'secondary')


class StudentAbsenceState(models.Model):
    """Speichert den aktuellen Abwesenheits-Ampelstatus einer Nachwuchskraft."""

    student = models.OneToOneField(
        'student.Student',
        on_delete=models.CASCADE,
        related_name='absence_state',
        verbose_name='Nachwuchskraft',
    )
    traffic_light = models.CharField(
        max_length=10,
        choices=TRAFFIC_LIGHT_CHOICES,
        default=TRAFFIC_LIGHT_UNKNOWN,
        verbose_name='Ampel',
    )
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Abwesenheitsstatus'
        verbose_name_plural = 'Abwesenheitsstatus'

    def __str__(self):
        return f'{self.student} – {self.get_traffic_light_display()}'


# ── Ampel-Berechnung ──────────────────────────────────────────────────────────

def compute_traffic_light(student) -> str:
    """
    Berechnet die Abwesenheitsampel für eine Nachwuchskraft.

    Grundlage: Arbeitstage im Kurs vs. krankheitsbedingte Fehltage.
    Rot    ≥ 10 %, Gelb ≥ 5 %, Grün < 5 %.
    """
    course = student.course if student.course_id else None
    if not course or not course.start_date or not course.end_date:
        return TRAFFIC_LIGHT_UNKNOWN

    total_days = _working_days_in_course(course)
    if total_days == 0:
        return TRAFFIC_LIGHT_UNKNOWN

    sick_days = sum(
        sl.duration_working_days  # uses _get_public_holidays internally
        for sl in SickLeave.objects.filter(student=student)
    )

    pct = sick_days / total_days * 100
    if pct >= 10:
        return TRAFFIC_LIGHT_RED
    if pct >= 5:
        return TRAFFIC_LIGHT_YELLOW
    return TRAFFIC_LIGHT_GREEN


def update_traffic_light(student, request=None) -> str:
    """
    Berechnet die Ampel, speichert sie und sendet bei Wechsel eine
    Benachrichtigung an die Ausbildungsleitung.
    Gibt den neuen Ampelwert zurück.
    """
    new_light = compute_traffic_light(student)

    state, created = StudentAbsenceState.objects.get_or_create(
        student=student,
        defaults={'traffic_light': new_light},
    )

    if not created and state.traffic_light != new_light:
        old_light = state.traffic_light
        state.traffic_light = new_light
        state.save(update_fields=['traffic_light', 'last_updated'])
        _notify_ausbildungsleitung_traffic_light(student, old_light, new_light, request)
    elif created:
        pass  # Erstanlage – keine Benachrichtigung

    return new_light


def _notify_ausbildungsleitung_traffic_light(student, old_light: str, new_light: str, request=None):
    """Benachrichtigt alle Ausbildungsleitung-Nutzer über einen Ampelwechsel."""
    import logging
    from django.contrib.auth import get_user_model

    logger = logging.getLogger(__name__)
    User = get_user_model()

    director_users = User.objects.filter(
        groups__name='ausbildungsleitung', email__gt='',
    ).distinct()
    if not director_users.exists():
        director_users = User.objects.filter(is_staff=True, email__gt='').distinct()

    labels = dict(TRAFFIC_LIGHT_CHOICES)
    old_label = labels.get(old_light, old_light)
    new_label = labels.get(new_light, new_light)

    base_url = (
        request.build_absolute_uri(f'/student/{student.pk}/')
        if request else f'/student/{student.pk}/'
    )

    try:
        from services.email import send_mail
        subject = (
            f'Abwesenheitsampel: {student.first_name} {student.last_name} '
            f'– {old_label} → {new_label}'
        )
        body = (
            f'Die Abwesenheitsampel für {student.first_name} {student.last_name} '
            f'hat sich geändert:\n\n'
            f'  Vorher: {old_label}\n'
            f'  Jetzt:  {new_label}\n\n'
            f'Detailseite: {base_url}\n'
        )
        for user in director_users:
            try:
                send_mail(subject=subject, body_text=body, recipient_list=[user.email])
            except Exception as exc:
                logger.warning('Ampel-Mail an %s fehlgeschlagen: %s', user.email, exc)
    except Exception as exc:
        logger.error('_notify_ausbildungsleitung_traffic_light fehlgeschlagen: %s', exc)
