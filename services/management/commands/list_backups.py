# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Listet alle vorhandenen Backups gruppiert nach Typ mit Größe und Datum."""
import datetime as _dt
from collections import defaultdict
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


PREFIXES = {
    'azubi-media-':     'Azubi-Media',
    'azubi-':           'Azubi-DB',
    'paperless-db-':    'Paperless-DB',
    'paperless-files-': 'Paperless-Files',
}


def _classify(name: str) -> str | None:
    for prefix, label in PREFIXES.items():
        if name.startswith(prefix):
            return label
    return None


def _human(size_bytes: int) -> str:
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if size_bytes < 1024 or unit == 'TB':
            return f'{size_bytes:.1f} {unit}'
        size_bytes /= 1024


class Command(BaseCommand):
    help = 'Listet alle Backups im lokalen Backup-Verzeichnis gruppiert nach Typ.'

    def handle(self, *args, **options):
        backup_dir = Path(settings.BACKUP_DIR)
        if not backup_dir.exists():
            self.stdout.write(self.style.WARNING(f'Backup-Verzeichnis fehlt: {backup_dir}'))
            return

        groups: dict[str, list] = defaultdict(list)
        total_size = 0
        for path in backup_dir.iterdir():
            if not path.is_file():
                continue
            label = _classify(path.name)
            if not label:
                continue
            stat = path.stat()
            groups[label].append((path.name, stat.st_size, _dt.datetime.fromtimestamp(stat.st_mtime)))
            total_size += stat.st_size

        if not groups:
            self.stdout.write(self.style.WARNING(f'Keine Backups in {backup_dir} gefunden.'))
            return

        for label in sorted(groups):
            entries = sorted(groups[label], key=lambda e: e[2], reverse=True)
            self.stdout.write(self.style.HTTP_INFO(f'\n{label} ({len(entries)})'))
            for name, size, mtime in entries:
                self.stdout.write(f'  {mtime:%Y-%m-%d %H:%M:%S}  {_human(size):>10}  {name}')

        self.stdout.write(self.style.SUCCESS(f'\nGesamt: {_human(total_size)} in {backup_dir}'))
