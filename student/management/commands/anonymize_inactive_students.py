# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""
Management Command: anonymize_inactive_students

Ruft den gleichnamigen Celery-Task synchron auf (kein Broker erforderlich).
Nützlich für manuelle Ausführung und Tests.

  python manage.py anonymize_inactive_students
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Anonymisiert alle Nachwuchskräfte, die seit mehr als 12 Monaten inaktiv sind.'

    def handle(self, *args, **options):
        from student.tasks import anonymize_inactive_students
        count = anonymize_inactive_students()
        self.stdout.write(self.style.SUCCESS(f'{count} Nachwuchskraft/-kräfte anonymisiert.'))
