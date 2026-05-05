# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""
Management Command: send_sick_leave_report

Ruft den gleichnamigen Celery-Task synchron auf (kein Broker erforderlich).
Nützlich für manuelle Ausführung und Tests.

  python manage.py send_sick_leave_report [--dry-run]
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Sendet Krank- und Gesundmeldungen an die Urlaubsstelle'

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

        from absence.tasks import send_sick_leave_report
        count = send_sick_leave_report()
        self.stdout.write(self.style.SUCCESS(f'{count} Meldung(en) versendet.'))

    def _dry_run(self):
        from absence.models import AbsenceSettings, SickLeave

        settings_obj = AbsenceSettings.get()
        self.stdout.write(f'Urlaubsstelle-E-Mail: {settings_obj.vacation_office_email or "(nicht konfiguriert)"}')

        new_opens = SickLeave.objects.filter(opening_reported=False).select_related('student')
        new_closes = SickLeave.objects.filter(
            closing_reported=False, end_date__isnull=False
        ).select_related('student')

        if not new_opens and not new_closes:
            self.stdout.write('[DRY RUN] Keine neuen Meldungen vorhanden.')
            return

        if new_opens:
            self.stdout.write(f'[DRY RUN] {new_opens.count()} neue Krankmeldung(en):')
            for sl in new_opens:
                self.stdout.write(
                    f'  – {sl.student} | krank ab {sl.start_date.strftime("%d.%m.%Y")} '
                    f'({sl.get_sick_type_display()})'
                )

        if new_closes:
            self.stdout.write(f'[DRY RUN] {new_closes.count()} Gesundmeldung(en):')
            for sl in new_closes:
                self.stdout.write(
                    f'  – {sl.student} | gesund ab {sl.end_date.strftime("%d.%m.%Y")} '
                    f'(krank seit {sl.start_date.strftime("%d.%m.%Y")})'
                )

        self.stdout.write('[DRY RUN] Keine E-Mail gesendet.')
