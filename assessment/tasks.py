# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Celery-Tasks für die 3-stufige Eskalation ausstehender Stationsbeurteilungen."""
import logging
from datetime import timedelta

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='assessment.escalate_pending_assessments')
def escalate_pending_assessments():
    """
    Prüft täglich alle ausstehenden Stationsbeurteilungen und fährt die
    3-stufige Eskalation hoch:

      Stufe 1: token_sent_at + stage1_days     → freundliche Erinnerung an Praxistutor
      Stufe 2: last_reminder_at + stage2_days  → schärfere Erinnerung an Praxistutor
      Stufe 3: token_sent_at + final_days      → Information an Ausbildungskoordination

    Pro Beurteilung wird je Lauf höchstens eine Stufe ausgeführt.
    """
    from django.utils import timezone

    from assessment.models import Assessment, STATUS_PENDING
    from services.models import SiteConfiguration

    config = SiteConfiguration.get()
    now = timezone.now()

    pending = (
        Assessment.objects
        .filter(status=STATUS_PENDING, token_sent_at__isnull=False)
        .select_related('assignment__student', 'assignment__unit', 'assignment__schedule_block', 'assignment__instructor')
    )

    counts = {'stage1': 0, 'stage2': 0, 'stage3': 0}

    for assessment in pending:
        days_since_token = (now - assessment.token_sent_at).days

        if assessment.escalated_at:
            continue

        # Stufe 3: Eskalation an Koordination
        if days_since_token >= config.escalation_final_days:
            if _send_escalation(assessment):
                counts['stage3'] += 1
            continue

        # Stufe 2: Schärfere Erinnerung
        if assessment.reminder_count >= 1 and assessment.last_reminder_at:
            days_since_reminder = (now - assessment.last_reminder_at).days
            if days_since_reminder >= config.escalation_stage2_days:
                if _send_reminder(assessment, urgent=True, config=config):
                    counts['stage2'] += 1
                continue

        # Stufe 1: Erste Erinnerung
        if assessment.reminder_count == 0 and days_since_token >= config.escalation_stage1_days:
            if _send_reminder(assessment, urgent=False, config=config):
                counts['stage1'] += 1

    logger.info(
        'escalate_pending_assessments: Stufe 1: %d, Stufe 2: %d, Stufe 3: %d',
        counts['stage1'], counts['stage2'], counts['stage3'],
    )
    return counts


def _send_reminder(assessment, urgent: bool, config) -> bool:
    """Sendet eine Erinnerung (Stufe 1 oder 2) an den Praxistutor."""
    from django.conf import settings
    from django.utils import timezone

    from services.email import send_mail_sync as send_mail
    from services.models import NotificationTemplate

    if not assessment.assessor_email:
        logger.warning('Erinnerung übersprungen: keine E-Mail (Assessment %s)', assessment.pk)
        return False

    assignment = assessment.assignment
    instructor = assignment.instructor
    student = assignment.student
    days_since_token = (timezone.now() - assessment.token_sent_at).days
    template_key = 'assessment_reminder_urgent' if urgent else 'assessment_reminder'

    token_url = f'{settings.SITE_BASE_URL}/beurteilungen/praxistutor/{assessment.token}/'
    context = {
        'anrede':              f'Guten Tag {instructor.first_name} {instructor.last_name},' if instructor else 'Guten Tag,',
        'student_vorname':     student.first_name,
        'student_nachname':    student.last_name,
        'einheit':             assignment.unit.name,
        'von':                 assignment.start_date.strftime('%d.%m.%Y'),
        'bis':                 assignment.end_date.strftime('%d.%m.%Y'),
        'block':               assignment.schedule_block.name,
        'beurteilungs_url':    token_url,
        'tage_offen':          days_since_token,
        'eskalation_in_tagen': max(0, config.escalation_final_days - days_since_token),
    }
    subject, body = NotificationTemplate.render(template_key, context)
    try:
        send_mail(subject=subject, body_text=body, recipient_list=[assessment.assessor_email])
    except Exception as exc:
        logger.warning('Erinnerung (%s) an %s fehlgeschlagen: %s', template_key, assessment.assessor_email, exc)
        return False

    assessment.reminder_count += 1
    assessment.last_reminder_at = timezone.now()
    assessment.save(update_fields=['reminder_count', 'last_reminder_at'])
    logger.info(
        '%s gesendet → %s (Assessment %s, Stufe %d)',
        template_key, assessment.assessor_email, assessment.pk, assessment.reminder_count,
    )
    return True


def _send_escalation(assessment) -> bool:
    """Stufe 3: Sendet Eskalations-Mail an alle zuständigen Ausbildungskoordinationen."""
    from django.conf import settings
    from django.utils import timezone

    from services.email import send_mail_sync as send_mail
    from services.models import NotificationTemplate
    from services.notifications import _get_coordinations_for_unit

    assignment = assessment.assignment
    student = assignment.student
    coordinations = list(_get_coordinations_for_unit(assignment.unit))
    if not coordinations:
        logger.warning(
            'Eskalation übersprungen: keine Koordination für Einheit %s gefunden (Assessment %s)',
            assignment.unit, assessment.pk,
        )
        return False

    days_since_token = (timezone.now() - assessment.token_sent_at).days
    detail_url = f'{settings.SITE_BASE_URL}/beurteilungen/{assessment.public_id}/'

    sent_to_any = False
    primary_coordination = None
    for coord in coordinations:
        if not coord.functional_email:
            continue
        context = {
            'koordination_name':    coord.name,
            'praxistutor_name':     assessment.assessor_name or '–',
            'praxistutor_email':    assessment.assessor_email or '–',
            'student_vorname':      student.first_name,
            'student_nachname':     student.last_name,
            'einheit':              assignment.unit.name,
            'von':                  assignment.start_date.strftime('%d.%m.%Y'),
            'bis':                  assignment.end_date.strftime('%d.%m.%Y'),
            'block':                assignment.schedule_block.name,
            'tage_offen':           days_since_token,
            'anzahl_erinnerungen':  assessment.reminder_count,
            'detail_url':           detail_url,
        }
        subject, body = NotificationTemplate.render('assessment_escalation', context)
        try:
            send_mail(subject=subject, body_text=body, recipient_list=[coord.functional_email])
            sent_to_any = True
            if primary_coordination is None:
                primary_coordination = coord
            logger.info(
                'Eskalation gesendet → %s (Koordination %s, Assessment %s)',
                coord.functional_email, coord.name, assessment.pk,
            )
        except Exception as exc:
            logger.warning(
                'Eskalations-Mail an %s fehlgeschlagen: %s', coord.functional_email, exc,
            )

    if not sent_to_any:
        logger.warning(
            'Eskalation gescheitert: keine Koordination mit functional_email (Assessment %s)',
            assessment.pk,
        )
        return False

    assessment.escalated_at = timezone.now()
    assessment.escalated_to = primary_coordination
    assessment.save(update_fields=['escalated_at', 'escalated_to'])
    return True