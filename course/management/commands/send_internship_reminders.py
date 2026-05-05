# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""
Management Command: send_internship_reminders

Ruft den gleichnamigen Celery-Task synchron auf (kein Broker erforderlich).
Nützlich für manuelle Ausführung und Tests.

  python manage.py send_internship_reminders [--dry-run]
"""
import logging
from datetime import date, timedelta

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sendet Erinnerungen an Praxistutoren (Beginn/Ende in 7 Tagen)'

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

        from course.tasks import send_internship_reminders
        sent = send_internship_reminders()
        self.stdout.write(self.style.SUCCESS(f'{sent} Erinnerung(en) gesendet.'))

    def _dry_run(self):
        from course.models import InternshipAssignment
        from services.models import SiteConfiguration

        config = SiteConfiguration.get()
        today = date.today()

        qs_base = InternshipAssignment.objects.filter(
            instructor__isnull=False,
            instructor__email__gt='',
        ).select_related('instructor', 'student', 'unit', 'schedule_block')

        for label, days, assignments in [
            ('Start', config.reminder_days_before_start,
             qs_base.filter(start_date=today + timedelta(days=config.reminder_days_before_start))),
            ('Ende',  config.reminder_days_before_end,
             qs_base.filter(end_date=today + timedelta(days=config.reminder_days_before_end))),
        ]:
            for assignment in assignments:
                instructor = assignment.instructor
                self.stdout.write(
                    f'[DRY RUN] {label}-Erinnerung ({days}d Vorlauf) → {instructor.email} '
                    f'({assignment.student} @ {assignment.unit})'
                )

        self.stdout.write('[DRY RUN] Keine E-Mails wurden gesendet.')
