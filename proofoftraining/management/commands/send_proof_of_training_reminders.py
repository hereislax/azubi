# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""
Management Command: send_proof_of_training_reminders

Ruft den gleichnamigen Celery-Task synchron auf (kein Broker erforderlich).
Nützlich für manuelle Ausführung und Tests.

  python manage.py send_proof_of_training_reminders [--dry-run]
"""
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sendet Erinnerungen an Nachwuchskräfte für fehlende oder nicht eingereichte Ausbildungsnachweise der Vorwoche'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Keine E-Mails senden, nur anzeigen was gesendet würde.',
        )

    def handle(self, *args, **options):
        if options['dry_run']:
            self._dry_run()
            return

        from proofoftraining.tasks import send_proof_of_training_reminders
        sent = send_proof_of_training_reminders()
        self.stdout.write(self.style.SUCCESS(f'{sent} Erinnerung(en) gesendet.'))

    def _dry_run(self):
        from datetime import date

        from proofoftraining.models import TrainingRecord, STATUS_DRAFT, STATUS_REJECTED
        from proofoftraining.tasks import _last_monday
        from student.models import Student

        today = date.today()
        week_start = _last_monday(today)
        week_end = week_start + timedelta(days=4)
        kw = week_start.isocalendar()[1]
        jahr = week_start.year

        self.stdout.write(f'Prüfe KW {kw}/{jahr} ({week_start.strftime("%d.%m.%Y")} – {week_end.strftime("%d.%m.%Y")})')

        students = (
            Student.objects
            .filter(user__isnull=False, user__email__gt='', user__is_active=True)
            .select_related('user')
        )

        found = 0
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
                continue

            self.stdout.write(
                f'[DRY RUN] Erinnerung → {student.user.email} '
                f'({student.first_name} {student.last_name}, KW {kw}/{jahr}, Status: {status_label})'
            )
            found += 1

        if found == 0:
            self.stdout.write('Keine ausstehenden Nachweise gefunden.')
        self.stdout.write('[DRY RUN] Keine E-Mails wurden gesendet.')
