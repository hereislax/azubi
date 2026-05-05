# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Celery-Tasks für automatisierte Anonymisierung inaktiver Nachwuchskräfte."""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='student.anonymize_inactive_students')
def anonymize_inactive_students():
    """
    Anonymisiert alle Nachwuchskräfte, die seit mehr als 12 Monaten inaktiv sind.

    Wird täglich um 03:00 Uhr von Celery Beat ausgeführt.
    Kann auch manuell aufgerufen werden: python manage.py anonymize_inactive_students
    """
    from student.anonymization import anonymize_student, get_students_due_for_anonymization

    students = list(get_students_due_for_anonymization())
    total = len(students)
    if total == 0:
        logger.info('Keine Nachwuchskräfte zur Anonymisierung gefunden.')
        return 0

    success_count = 0
    error_count = 0
    for student in students:
        try:
            anonymize_student(student)
            success_count += 1
            logger.info('Anonymisiert: %s %s (%s)', student.first_name, student.last_name, student.pk)
        except Exception as exc:
            error_count += 1
            logger.error(
                'Anonymisierung fehlgeschlagen für %s %s (%s): %s',
                student.first_name, student.last_name, student.pk, exc,
            )

    logger.info(
        'anonymize_inactive_students abgeschlossen: %d anonymisiert, %d Fehler.',
        success_count, error_count,
    )
    return success_count
