# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Celery-Tasks für automatisierte Erinnerungsmails an Nachwuchskräfte."""
import logging
from datetime import date, timedelta

from celery import shared_task

logger = logging.getLogger(__name__)


def _last_monday(today: date) -> date:
    """Gibt den Montag der Vorwoche zurück."""
    # today.weekday(): 0=Mo, 6=So
    # Montag dieser Woche = today - today.weekday() Tage
    # Montag letzter Woche = Montag dieser Woche - 7 Tage
    return today - timedelta(days=today.weekday() + 7)


@shared_task(name='proofoftraining.send_proof_of_training_reminders')
def send_proof_of_training_reminders():
    """
    Sendet Erinnerungs-E-Mails an Nachwuchskräfte, deren Ausbildungsnachweis
    für die Vorwoche fehlt oder noch im Status Entwurf bzw. Korrekturbedarf ist.

    Wird täglich um 07:00 Uhr von Celery Beat ausgeführt.
    Kann auch manuell aufgerufen werden:
        python manage.py send_proof_of_training_reminders
    """
    from proofoftraining.models import TrainingRecord, STATUS_DRAFT, STATUS_REJECTED
    from services.email import send_mail_sync as send_mail
    from services.models import NotificationTemplate
    from student.models import Student

    today = date.today()
    week_start = _last_monday(today)
    week_end = week_start + timedelta(days=4)
    kw = week_start.isocalendar()[1]
    jahr = week_start.year

    # Nur Nachwuchskräfte mit Portal-Benutzerkonto und E-Mail-Adresse berücksichtigen
    students = (
        Student.objects
        .filter(user__isnull=False, user__email__gt='', user__is_active=True)
        .select_related('user')
    )

    portal_url = '/ausbildungsnachweise/'

    sent = 0
    for student in students:
        record = TrainingRecord.objects.filter(
            student=student,
            week_start=week_start,
        ).first()

        if record is None:
            status_label = 'fehlt'
        elif record.status in (STATUS_DRAFT, STATUS_REJECTED):
            status_label = record.get_status_display()
        else:
            # Eingereicht oder angenommen – keine Erinnerung nötig
            continue

        from services.notifications import is_email_enabled
        if not is_email_enabled(student.user, 'proof_of_training_reminder'):
            logger.info('Erinnerung übersprungen (deaktiviert): %s', student.user.email)
            continue

        context = {
            'vorname':    student.first_name,
            'nachname':   student.last_name,
            'kw':         kw,
            'jahr':       jahr,
            'von':        week_start.strftime('%d.%m.%Y'),
            'bis':        week_end.strftime('%d.%m.%Y'),
            'status':     status_label,
            'portal_url': portal_url,
        }
        subject, body = NotificationTemplate.render('proof_of_training_reminder', context)
        try:
            send_mail(subject=subject, body_text=body, recipient_list=[student.user.email])
            sent += 1
            logger.info(
                'Nachweis-Erinnerung gesendet → %s (KW %d/%d, Status: %s)',
                student.user.email, kw, jahr, status_label,
            )
        except Exception as exc:
            logger.warning(
                'Nachweis-Erinnerung an %s fehlgeschlagen: %s',
                student.user.email, exc,
            )

    logger.info(
        'send_proof_of_training_reminders abgeschlossen: %d Erinnerung(en) gesendet.', sent,
    )
    return sent
