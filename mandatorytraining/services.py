# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Service-Funktionen für Pflichtschulungen.

Berechnet Compliance-Status pro Nachwuchskraft, listet überfällige/bald
ablaufende Schulungen und liefert Daten für Heatmaps und Reports.
"""
from __future__ import annotations

from datetime import date, timedelta

from .models import TrainingCompletion, TrainingType


# Status-Konstanten
STATUS_NEVER         = 'never'
STATUS_EXPIRED       = 'expired'
STATUS_SOON_EXPIRING = 'soon_expiring'
STATUS_COMPLETED     = 'completed'

STATUS_LABELS = {
    STATUS_NEVER:         'Noch nicht absolviert',
    STATUS_EXPIRED:       'Abgelaufen',
    STATUS_SOON_EXPIRING: 'Bald ablaufend',
    STATUS_COMPLETED:     'Erfüllt',
}

STATUS_BADGE = {
    STATUS_NEVER:         'secondary',
    STATUS_EXPIRED:       'danger',
    STATUS_SOON_EXPIRING: 'warning',
    STATUS_COMPLETED:     'success',
}


def applicable_training_types(student) -> list[TrainingType]:
    """Liefert alle aktiven Schulungstypen, die für die Nachwuchskraft gelten."""
    qs = TrainingType.objects.filter(active=True).prefetch_related('applies_to_job_profiles')
    job_profile = None
    try:
        job_profile = student.course.job_profile
    except AttributeError:
        pass
    result = []
    for tt in qs:
        if tt.applies_to_all_students:
            result.append(tt)
        elif job_profile and tt.applies_to_job_profiles.filter(pk=job_profile.pk).exists():
            result.append(tt)
    return result


def latest_completions(student) -> dict[int, TrainingCompletion]:
    """Liefert pro Schulungs-Typ die jeweils jüngste Teilnahme der NK."""
    out: dict[int, TrainingCompletion] = {}
    for c in (
        TrainingCompletion.objects
        .filter(student=student)
        .select_related('training_type')
        .order_by('training_type_id', '-completed_on')
    ):
        # Erste pro Typ ist dank Sortierung die jüngste
        out.setdefault(c.training_type_id, c)
    return out


def derive_status(completion: TrainingCompletion | None,
                  training_type: TrainingType,
                  today: date | None = None) -> str:
    """Status-Ableitung pro Schulung — siehe ``STATUS_*``-Konstanten.

    Spezialfall ``one_time``: sobald *irgendeine* Teilnahme existiert ⇒ ``completed``,
    da diese Schulungen lebenslang gelten (``expires_on`` ist NULL).
    """
    today = today or date.today()
    if completion is None:
        return STATUS_NEVER
    if completion.expires_on is None:
        # Einmalige Schulung mit gültiger Teilnahme — immer erfüllt
        return STATUS_COMPLETED
    if completion.expires_on < today:
        return STATUS_EXPIRED
    days = (completion.expires_on - today).days
    if days <= training_type.reminder_days_before:
        return STATUS_SOON_EXPIRING
    return STATUS_COMPLETED


def compliance_status_for_student(student) -> dict:
    """Vollständige Compliance-Übersicht für eine Nachwuchskraft.

    Returns dict mit:
        rows           — Liste pro Schulungs-Typ: {type, latest, status, status_label, ...}
        mandatory_total, mandatory_ok — für Compliance-Quote
        overall_status — 'green' | 'yellow' | 'red' | 'unknown'
    """
    types = applicable_training_types(student)
    latest = latest_completions(student)
    rows = []
    mandatory_total = 0
    mandatory_ok = 0
    has_red = False
    has_yellow = False
    for tt in types:
        c = latest.get(tt.pk)
        st = derive_status(c, tt)
        if tt.is_mandatory:
            mandatory_total += 1
            if st == STATUS_COMPLETED:
                mandatory_ok += 1
            elif st in (STATUS_EXPIRED, STATUS_NEVER):
                has_red = True
            elif st == STATUS_SOON_EXPIRING:
                has_yellow = True
        days_left = None
        if c and c.expires_on is not None:
            days_left = (c.expires_on - date.today()).days
        rows.append({
            'type':         tt,
            'latest':       c,
            'status':       st,
            'status_label': STATUS_LABELS[st],
            'badge':        STATUS_BADGE[st],
            'days_left':    days_left,
            'history_count': TrainingCompletion.objects.filter(student=student, training_type=tt).count(),
        })
    if not types:
        overall = 'unknown'
    elif has_red:
        overall = 'red'
    elif has_yellow:
        overall = 'yellow'
    else:
        overall = 'green'
    quote_pct = round(mandatory_ok / mandatory_total * 100) if mandatory_total else None
    return {
        'rows':              rows,
        'mandatory_total':   mandatory_total,
        'mandatory_ok':      mandatory_ok,
        'overall_status':    overall,
        'compliance_pct':    quote_pct,
    }


def overdue_completions_for_office() -> list[dict]:
    """Liste aller aktuell überfälligen oder fehlenden Pflicht-Schulungen je Azubi.

    Wird vom Wochen-Sammelmail-Task konsumiert.
    """
    from student.models import Student
    today = date.today()
    out = []
    students = Student.objects.filter(anonymized_at__isnull=True).select_related('course__job_profile')
    for s in students:
        types = applicable_training_types(s)
        latest = latest_completions(s)
        for tt in types:
            if not tt.is_mandatory:
                continue
            c = latest.get(tt.pk)
            st = derive_status(c, tt, today)
            if st in (STATUS_EXPIRED, STATUS_NEVER):
                out.append({
                    'student': s, 'training_type': tt, 'latest': c, 'status': st,
                    'days_overdue': (today - c.expires_on).days if c else None,
                })
    return out


def upcoming_reminders(today: date | None = None) -> dict[str, list[TrainingCompletion]]:
    """Findet Completions, deren Erinnerungs-Marker (T-30 / T-7) heute fällig sind.

    Einmalige Schulungen (``expires_on IS NULL``) werden ignoriert — sie laufen nicht ab.
    """
    today = today or date.today()
    qs = (
        TrainingCompletion.objects
        .filter(expires_on__isnull=False, expires_on__gte=today)
        .select_related('student', 'training_type')
    )
    due_30, due_7 = [], []
    for c in qs:
        days = (c.expires_on - today).days
        if not c.reminder_30_sent and days <= c.training_type.reminder_days_before and days > 7:
            due_30.append(c)
        if not c.reminder_7_sent and days <= 7:
            due_7.append(c)
    return {'days_30': due_30, 'days_7': due_7}
