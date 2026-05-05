# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Benachrichtigungen rund um Pflichtschulungen.

Drei Sender:

* T-30-Erinnerung an die Nachwuchskraft (Mail + Portal-Notification)
* T-7-Erinnerung an die Nachwuchskraft (Mail + Portal-Notification, dringender Tonfall)
* Wöchentliche Sammelmail an Office/Director (Tabelle aller überfälligen Pflichten)
"""
from __future__ import annotations

import logging
from datetime import date

logger = logging.getLogger(__name__)


def _portal_url():
    from django.urls import reverse
    try:
        return reverse('mandatorytraining:portal_my_trainings')
    except Exception:
        return '/pflichtschulungen/portal/'


def _student_email(student) -> str | None:
    return getattr(student, 'email_id', None) or getattr(student, 'email_private', None) or None


def notify_student_expiry_reminder_30(completion):
    """30 Tage vor Ablauf: freundliche Erinnerung an die Nachwuchskraft."""
    _send_student_reminder(completion, days=30)


def notify_student_expiry_reminder_7(completion):
    """7 Tage vor Ablauf: dringende Erinnerung an die Nachwuchskraft."""
    _send_student_reminder(completion, days=7)


def _send_student_reminder(completion, days: int):
    from services.email import send_mail
    from services.models import create_notification

    student = completion.student
    email = _student_email(student)
    portal_url = _portal_url()

    subject = (
        f'Pflichtschulung läuft in {days} Tagen ab: {completion.training_type.name}'
        if days > 1 else
        f'Pflichtschulung läuft morgen ab: {completion.training_type.name}'
    )
    body = (
        f'Guten Tag {student.first_name} {student.last_name},\n\n'
        f'die Pflichtschulung „{completion.training_type.name}" läuft am '
        f'{completion.expires_on.strftime("%d.%m.%Y")} ab '
        f'(in {days} Tag{"en" if days != 1 else ""}).\n\n'
        f'Bitte melde dich zur Auffrischung an. Übersicht deiner Schulungen:\n'
        f'  {portal_url}\n'
    )

    if email:
        try:
            send_mail(subject=subject, body_text=body, recipient_list=[email])
            logger.info('T-%d-Reminder an %s gesendet (Completion pk=%s)', days, email, completion.pk)
        except Exception as exc:
            logger.warning('T-%d-Reminder an %s fehlgeschlagen: %s', days, email, exc)
    else:
        logger.info('T-%d-Reminder: NK %s ohne E-Mail (Completion pk=%s)', days, student, completion.pk)

    if getattr(student, 'user', None):
        try:
            create_notification(
                student.user,
                message=f'Pflichtschulung „{completion.training_type.name}" läuft in {days} Tagen ab.',
                link=portal_url,
                icon='bi-shield-exclamation' if days <= 7 else 'bi-shield-check',
                category='Pflichtschulung',
            )
        except Exception:
            pass


def notify_office_overdue_summary(items: list[dict]):
    """Wöchentliche Sammelmail an Ausbildungsleitung + -referat.

    ``items`` ist eine Liste der vom Service gelieferten Dicts mit
    ``student``, ``training_type``, ``latest``, ``status``, ``days_overdue``.
    """
    from django.conf import settings
    from django.contrib.auth.models import User
    from services.email import send_mail
    from services.models import create_notification

    today = date.today()
    recipients = list(
        User.objects.filter(
            groups__name__in=['ausbildungsleitung', 'ausbildungsreferat'],
            is_active=True,
        ).exclude(email='').values_list('email', flat=True).distinct()
    )

    # Tabelle aufbauen — Plain-Text für Mail-Body
    rows = ['Pflicht-Schulungen mit Status „abgelaufen" oder „nie absolviert":', '']
    rows.append(
        f'{"Nachwuchskraft":<35} {"Schulung":<30} {"Status":<22} {"Letzte Teilnahme":<18}'
    )
    rows.append('-' * 110)
    for it in sorted(items, key=lambda x: (x['student'].last_name, x['student'].first_name)):
        s = it['student']
        last = it['latest'].completed_on.strftime('%d.%m.%Y') if it['latest'] else '—'
        status_label = 'Abgelaufen' if it['status'] == 'expired' else 'Nicht absolviert'
        days_info = f' ({it["days_overdue"]} Tg.)' if it.get('days_overdue') else ''
        rows.append(
            f'{(s.first_name + " " + s.last_name)[:33]:<35} '
            f'{it["training_type"].name[:28]:<30} '
            f'{(status_label + days_info)[:20]:<22} '
            f'{last:<18}'
        )

    body = (
        f'Guten Tag,\n\n'
        f'Stand {today.strftime("%d.%m.%Y")} sind {len(items)} Pflicht-Schulungen '
        f'überfällig oder noch nie absolviert worden.\n\n'
        + '\n'.join(rows) + '\n\n'
        f'Detailansicht: /pflichtschulungen/\n'
    )
    subject = f'Wöchentliche Übersicht: {len(items)} überfällige Pflichtschulungen'

    if recipients:
        try:
            send_mail(subject=subject, body_text=body, recipient_list=recipients)
        except Exception as exc:
            logger.warning('Sammelmail an %s fehlgeschlagen: %s', recipients, exc)

    # Interne Notification an alle Empfänger
    try:
        users = User.objects.filter(
            groups__name__in=['ausbildungsleitung', 'ausbildungsreferat'],
            is_active=True,
        ).distinct()
        for u in users:
            create_notification(
                u,
                message=f'{len(items)} überfällige Pflichtschulungen — Wochenübersicht',
                link='/pflichtschulungen/',
                icon='bi-shield-exclamation',
                category='Pflichtschulung',
            )
    except Exception:
        pass
