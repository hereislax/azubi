# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Celery-Tasks für automatisierte Erinnerungsmails an Praxistutoren."""
import logging
from datetime import date, timedelta

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='course.send_internship_reminders')
def send_internship_reminders():
    """
    Sendet Erinnerungs-E-Mails an Praxistutoren:
      - Einsatz beginnt in 7 Tagen
      - Einsatz endet in 7 Tagen (mit Hinweis auf Praxisbeurteilung)

    Wird täglich um 07:00 Uhr von Celery Beat ausgeführt.
    Kann auch manuell aufgerufen werden: python manage.py send_internship_reminders
    """
    from course.models import InternshipAssignment
    from services.email import send_mail_sync as send_mail
    from services.models import NotificationTemplate, SiteConfiguration

    config = SiteConfiguration.get()
    today = date.today()

    qs_base = InternshipAssignment.objects.filter(
        instructor__isnull=False,
        instructor__email__gt='',
    ).select_related('instructor', 'student', 'unit', 'schedule_block')

    sent = 0
    for template_key, label, days, assignments in [
        ('reminder_start', 'Start', config.reminder_days_before_start,
         qs_base.filter(start_date=today + timedelta(days=config.reminder_days_before_start))),
        ('reminder_end',   'Ende',  config.reminder_days_before_end,
         qs_base.filter(end_date=today + timedelta(days=config.reminder_days_before_end))),
    ]:
        for assignment in assignments:
            instructor = assignment.instructor
            student = assignment.student
            context = {
                'anrede':           f'Guten Tag {instructor.first_name} {instructor.last_name},',
                'student_vorname':  student.first_name,
                'student_nachname': student.last_name,
                'einheit':          assignment.unit.name,
                'von':              assignment.start_date.strftime('%d.%m.%Y'),
                'bis':              assignment.end_date.strftime('%d.%m.%Y'),
                'block':            assignment.schedule_block.name,
            }
            subject, body = NotificationTemplate.render(template_key, context)
            try:
                send_mail(subject=subject, body_text=body, recipient_list=[instructor.email])
                sent += 1
                logger.info('%s-Erinnerung gesendet → %s', label, instructor.email)
            except Exception as exc:
                logger.warning('Erinnerung (%s) an %s fehlgeschlagen: %s', label, instructor.email, exc)

            # Bei Ende-Erinnerung: Assessment-Token erstellen und mitsenden
            if template_key == 'reminder_end':
                _create_and_send_assessment_token(assignment, instructor)

    logger.info('send_internship_reminders abgeschlossen: %d Erinnerung(en) gesendet.', sent)
    return sent


def _create_and_send_assessment_token(assignment, instructor):
    """
    Erstellt ein Assessment-Record für den Einsatz (falls noch nicht vorhanden)
    und sendet den tokenbasierten Beurteilungslink an den Praxistutoren.
    Wird nur ausgeführt wenn eine aktive Beurteilungsvorlage für das Berufsbild existiert.
    """
    from django.utils import timezone

    try:
        from assessment.models import Assessment, STATUS_PENDING
        from assessment.views import _send_assessment_token_mail
    except ImportError:
        return

    # Berufsbild des Azubis ermitteln
    try:
        job_profile = assignment.student.course.job_profile
    except AttributeError:
        logger.debug('Assessment-Token: kein Berufsbild für %s', assignment)
        return

    # Aktive Vorlage für dieses Berufsbild suchen
    from assessment.models import AssessmentTemplate
    template = AssessmentTemplate.objects.filter(
        job_profile=job_profile,
        active=True,
    ).first()
    if not template:
        logger.debug('Assessment-Token: keine aktive Vorlage für %s', job_profile)
        return

    # Assessment-Record anlegen oder vorhandenen ermitteln
    assessment, created = Assessment.objects.get_or_create(
        assignment=assignment,
        defaults={
            'template': template,
            'assessor_name':  f'{instructor.first_name} {instructor.last_name}',
            'assessor_email': instructor.email,
            'status': STATUS_PENDING,
        },
    )

    if not created and assessment.status != STATUS_PENDING:
        # Bereits eingereicht oder bestätigt – kein erneuter Versand
        return

    _send_assessment_token_mail(assessment)
    assessment.token_sent_at = timezone.now()
    assessment.save(update_fields=['token_sent_at'])
    logger.info('Assessment-Token gesendet → %s (Assignment: %s)', instructor.email, assignment.pk)
