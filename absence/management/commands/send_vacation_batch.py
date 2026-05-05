# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""
Management Command: send_vacation_batch

Ruft den gleichnamigen Celery-Task synchron auf (kein Broker erforderlich).
Nützlich für manuelle Ausführung und Tests.

  python manage.py send_vacation_batch [--dry-run]
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Bündelt genehmigte Urlaubsanträge und sendet sie an die Urlaubsstelle'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Kein Paket erstellen und keine E-Mails senden, nur anzeigen was versendet würde.',
        )

    def handle(self, *args, **options):
        if options['dry_run']:
            self._dry_run()
            return

        from absence.tasks import send_vacation_batch
        count = send_vacation_batch()
        self.stdout.write(self.style.SUCCESS(f'{count} Antrag/Anträge versendet.'))

    def _dry_run(self):
        from absence.models import VacationRequest, STATUS_APPROVED, AbsenceSettings

        settings_obj = AbsenceSettings.get()
        self.stdout.write(f'Urlaubsstelle-E-Mail: {settings_obj.vacation_office_email or "(nicht konfiguriert)"}')

        qs = VacationRequest.objects.filter(
            status=STATUS_APPROVED,
            batch__isnull=True,
        ).select_related('student')

        if not qs.exists():
            self.stdout.write('[DRY RUN] Keine genehmigten, unversendeten Anträge vorhanden.')
            return

        self.stdout.write(f'[DRY RUN] {qs.count()} Antrag/Anträge würden versendet:')
        for vr in qs:
            kind = 'Stornierung' if vr.is_cancellation else 'Urlaub'
            self.stdout.write(
                f'  – {vr.student} | {kind} | '
                f'{vr.start_date.strftime("%d.%m.%Y")}–{vr.end_date.strftime("%d.%m.%Y")}'
            )
        self.stdout.write('[DRY RUN] Kein Paket erstellt, keine E-Mail gesendet.')
