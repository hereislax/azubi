# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Manueller Trigger für ein vollständiges Backup (DB + Media + Paperless)."""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        'Erzeugt sofort ein vollständiges Backup (Datenbank, Media, Paperless) im '
        'lokalen Backup-Verzeichnis. Nutzt dieselben Tasks wie der nächtliche Lauf, '
        'aber synchron ausgeführt – damit Fehler direkt sichtbar sind.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-paperless',
            action='store_true',
            help='Paperless-Backup überspringen (z. B. wenn Paperless nicht läuft).',
        )
        parser.add_argument(
            '--skip-cleanup',
            action='store_true',
            help='GFS-Rotation am Ende überspringen.',
        )

    def handle(self, *args, **options):
        from services.tasks import (
            backup_database,
            backup_media,
            backup_paperless,
            cleanup_old_backups,
        )

        steps = [
            ('Datenbank', backup_database),
            ('Media',     backup_media),
        ]
        if not options['skip_paperless']:
            steps.append(('Paperless', backup_paperless))

        for name, fn in steps:
            self.stdout.write(f'→ {name}-Backup …')
            try:
                result = fn()
                self.stdout.write(self.style.SUCCESS(f'  ✓ {result}'))
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f'  ✗ {exc}'))
                raise

        if not options['skip_cleanup']:
            self.stdout.write('→ Rotation alter Backups …')
            deleted = cleanup_old_backups()
            self.stdout.write(self.style.SUCCESS(f'  ✓ {len(deleted)} Dateien gelöscht'))

        self.stdout.write(self.style.SUCCESS('Backup abgeschlossen.'))
