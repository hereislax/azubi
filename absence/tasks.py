# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""
Celery-Tasks für das Abwesenheitsmodul.

  absence.send_vacation_batch      – Täglich 08:00: Urlaubsanträge an Urlaubsstelle
  absence.send_sick_leave_report   – Täglich 08:00: Krankmeldungsbericht an Urlaubsstelle
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='absence.send_vacation_batch')
def send_vacation_batch():
    """
    Bündelt alle genehmigten, noch nicht versendeten Urlaubsanträge
    (Urlaub + Stornierungen) in einem Paket und sendet der Urlaubsstelle
    eine E-Mail mit dem einmaligen Bearbeitungslink.
    """
    from .models import AbsenceSettings, VacationBatch, VacationRequest, STATUS_APPROVED

    settings_obj = AbsenceSettings.get()
    if not settings_obj.vacation_office_email:
        logger.info('send_vacation_batch: Keine Urlaubsstelle-E-Mail konfiguriert – übersprungen.')
        return 0

    pending_requests = VacationRequest.objects.filter(
        status=STATUS_APPROVED,
        batch__isnull=True,
    ).select_related('student')

    if not pending_requests.exists():
        logger.info('send_vacation_batch: Keine neuen Anträge – kein Paket erstellt.')
        return 0

    count = pending_requests.count()

    batch = VacationBatch.objects.create()
    pending_requests.update(batch=batch)

    # URL aufbauen (kein request-Objekt verfügbar in Tasks)
    from django.conf import settings as django_settings
    base_url = getattr(django_settings, 'SITE_BASE_URL', 'http://localhost:8080').rstrip('/')
    portal_url = f'{base_url}/abwesenheiten/urlaubsstelle/{batch.token}/'

    subject = f'Urlaubsanträge zur Bearbeitung – {count} Antrag/Anträge'
    body = (
        f'Sehr geehrte Damen und Herren,\n\n'
        f'es liegen {count} genehmigte Urlaubsantrag/Urlaubsanträge zur Bearbeitung vor.\n\n'
        f'Bitte öffnen Sie den folgenden Link, um die Anträge zu bearbeiten:\n\n'
        f'{portal_url}\n\n'
        f'Der Link ist einmalig gültig und wird nach der Bearbeitung ungültig.\n\n'
        f'Mit freundlichen Grüßen\nDas Ausbildungsreferat\n'
    )

    try:
        from services.email import send_mail_sync as send_mail
        send_mail(
            subject=subject,
            body_text=body,
            recipient_list=[settings_obj.vacation_office_email],
        )
        logger.info(
            'send_vacation_batch: Paket %s mit %d Antrag/Anträgen an %s gesendet.',
            batch.token, count, settings_obj.vacation_office_email,
        )
    except Exception as exc:
        logger.error('send_vacation_batch: E-Mail-Versand fehlgeschlagen: %s', exc)

    return count


@shared_task(name='absence.send_sick_leave_report')
def send_sick_leave_report():
    """
    Sendet der Urlaubsstelle einen täglichen Bericht über neu erfasste
    Krankmeldungen (Öffnungen) und Gesundmeldungen (Schließungen).
    """
    from .models import AbsenceSettings, SickLeave

    settings_obj = AbsenceSettings.get()
    if not settings_obj.vacation_office_email:
        logger.info('send_sick_leave_report: Keine Urlaubsstelle-E-Mail konfiguriert – übersprungen.')
        return 0

    new_opens = list(
        SickLeave.objects.filter(opening_reported=False)
        .select_related('student')
        .order_by('student__last_name', 'start_date')
    )
    new_closes = list(
        SickLeave.objects.filter(
            closing_reported=False,
            end_date__isnull=False,
        )
        .select_related('student')
        .order_by('student__last_name', 'end_date')
    )

    if not new_opens and not new_closes:
        logger.info('send_sick_leave_report: Keine neuen Meldungen – kein Bericht gesendet.')
        return 0

    lines = ['Täglicher Bericht: Krank- und Gesundmeldungen\n']

    if new_opens:
        lines.append(f'Neue Krankmeldungen ({len(new_opens)}):')
        for sl in new_opens:
            lines.append(
                f'  – {sl.student.course} | {sl.student.last_name}, {sl.student.first_name} ({sl.student.employment}): '
                f'krank ab {sl.start_date.strftime("%d.%m.%Y")} '
                f'({sl.get_sick_type_display()})'
            )
        lines.append('')

    if new_closes:
        lines.append(f'Gesundmeldungen ({len(new_closes)}):')
        for sl in new_closes:
            lines.append(
                f'  – {sl.student.course} | {sl.student.last_name}, {sl.student.first_name} ({sl.student.employment}): '
                f'gesund ab {sl.end_date.strftime("%d.%m.%Y")} '
                f'(krank seit {sl.start_date.strftime("%d.%m.%Y")})'
            )
        lines.append('')

    body = '\n'.join(lines)
    subject = f'Krank- und Gesundmeldungen – {len(new_opens)} neu / {len(new_closes)} geschlossen'

    try:
        from services.email import send_mail_sync as send_mail
        send_mail(
            subject=subject,
            body_text=body,
            recipient_list=[settings_obj.vacation_office_email],
        )

        # Als gemeldet markieren
        open_pks  = [sl.pk for sl in new_opens]
        close_pks = [sl.pk for sl in new_closes]
        if open_pks:
            SickLeave.objects.filter(pk__in=open_pks).update(opening_reported=True)
        if close_pks:
            SickLeave.objects.filter(pk__in=close_pks).update(closing_reported=True)

        total = len(new_opens) + len(new_closes)
        logger.info(
            'send_sick_leave_report: Bericht mit %d Einträgen an %s gesendet.',
            total, settings_obj.vacation_office_email,
        )
        return total
    except Exception as exc:
        logger.error('send_sick_leave_report: E-Mail-Versand fehlgeschlagen: %s', exc)
        return 0
