# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Celery-Tasks für Pflichtschulungs-Erinnerungen.

Zwei Tasks (täglich + wöchentlich), eingerichtet via Migration als
``PeriodicTask`` im django-celery-beat-DatabaseScheduler.

* ``send_expiry_reminders`` — täglich. Versendet T-30 und T-7-Reminders an
  die Nachwuchskraft pro betroffener Completion (Marker pro Stufe).
* ``send_overdue_summary`` — wöchentlich. Sammelmail an Ausbildungsleitung
  und -referat über alle aktuell überfälligen Pflicht-Schulungen.
"""
from __future__ import annotations

import logging
from datetime import date

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='mandatorytraining.send_expiry_reminders')
def send_expiry_reminders():
    """Verschickt T-30- und T-7-Erinnerungen an die jeweilige Nachwuchskraft."""
    from .services import upcoming_reminders
    from .notifications import (
        notify_student_expiry_reminder_30,
        notify_student_expiry_reminder_7,
    )

    today = date.today()
    due = upcoming_reminders(today)
    sent = {'30': 0, '7': 0}
    for c in due['days_30']:
        try:
            notify_student_expiry_reminder_30(c)
            c.reminder_30_sent = True
            c.save(update_fields=['reminder_30_sent'])
            sent['30'] += 1
        except Exception as exc:
            logger.warning('T-30-Reminder pk=%s fehlgeschlagen: %s', c.pk, exc)
    for c in due['days_7']:
        try:
            notify_student_expiry_reminder_7(c)
            c.reminder_7_sent = True
            c.save(update_fields=['reminder_7_sent'])
            sent['7'] += 1
        except Exception as exc:
            logger.warning('T-7-Reminder pk=%s fehlgeschlagen: %s', c.pk, exc)
    logger.info('Pflichtschulungs-Reminder versendet: T-30=%d, T-7=%d', sent['30'], sent['7'])
    return sent


@shared_task(name='mandatorytraining.send_overdue_summary')
def send_overdue_summary():
    """Wöchentliche Sammelübersicht aller überfälligen/fehlenden Pflicht-Schulungen.

    Geht per Mail + interner Notification an alle aktiven Mitglieder der
    Gruppen ``ausbildungsleitung`` und ``ausbildungsreferat``.
    """
    from .services import overdue_completions_for_office
    from .notifications import notify_office_overdue_summary

    items = overdue_completions_for_office()
    if not items:
        logger.info('Keine überfälligen Pflichtschulungen — keine Sammelmail nötig.')
        return 0
    try:
        notify_office_overdue_summary(items)
    except Exception as exc:
        logger.error('Sammelmail überfällige Schulungen fehlgeschlagen: %s', exc)
        return 0
    logger.info('Sammelmail versendet (%d überfällige Einträge).', len(items))
    return len(items)
