# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Spielt ein Datenbank-Backup zurück. Kritische Operation – nur mit --confirm."""
import os
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        'Spielt einen pg_dump (custom format) in eine PostgreSQL-Datenbank zurück. '
        'Standardmäßig in eine Test-DB (azubi_restore_test) – mit --target=production '
        'in die laufende Datenbank (DESTRUKTIV).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'dump_file',
            help='Pfad zum .psql.bin / .dump – Datei innerhalb des Containers.',
        )
        parser.add_argument(
            '--target',
            choices=['test', 'production'],
            default='test',
            help=(
                '"test" (Default): Restore in eine temporäre DB azubi_restore_test. '
                '"production": Restore in die laufende Azubi-DB. '
                'Erfordert zusätzlich --confirm.'
            ),
        )
        parser.add_argument(
            '--target-db',
            default=None,
            help='Optional: Name der Ziel-DB (überschreibt --target).',
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Sicherheits-Flag – ohne wird nichts geschrieben (Dry-Run-Verhalten).',
        )

    def handle(self, *args, **options):
        from auditlog.models import AuditLogEntry

        dump_path = Path(options['dump_file'])
        if not dump_path.is_file():
            raise CommandError(f'Dump-Datei nicht gefunden: {dump_path}')

        if options['target_db']:
            target_db = options['target_db']
        elif options['target'] == 'production':
            target_db = settings.DATABASES['default']['NAME']
        else:
            target_db = 'azubi_restore_test'

        is_production = target_db == settings.DATABASES['default']['NAME']

        if is_production and not options['confirm']:
            raise CommandError(
                'Restore in die Produktiv-DB erfordert --confirm. '
                'Stoppe vorher app/celery_worker/celery_beat!'
            )
        if not options['confirm']:
            self.stdout.write(self.style.WARNING(
                f'Dry-Run: Würde {dump_path.name} nach DB "{target_db}" zurückspielen. '
                'Mit --confirm erneut aufrufen, um den Restore wirklich auszuführen.'
            ))
            return

        db_host = settings.DATABASES['default']['HOST']
        db_port = settings.DATABASES['default']['PORT']
        db_user = settings.DATABASES['default']['USER']
        env = os.environ.copy()
        env['PGPASSWORD'] = settings.DATABASES['default']['PASSWORD']

        # Test-DB ggf. neu anlegen (für "test" Target)
        if not is_production:
            self.stdout.write(f'→ Lege Test-DB "{target_db}" neu an …')
            for sql in (f'DROP DATABASE IF EXISTS {target_db};',
                        f'CREATE DATABASE {target_db};'):
                subprocess.run(
                    ['psql', '-h', db_host, '-p', str(db_port), '-U', db_user,
                     '-d', 'postgres', '-c', sql],
                    env=env, check=True, capture_output=True,
                )
        else:
            self.stdout.write(self.style.WARNING(
                f'→ Restore IN PRODUKTIV-DB "{target_db}" – stelle sicher, dass '
                'app/celery_worker/celery_beat gestoppt sind!'
            ))
            subprocess.run(
                ['psql', '-h', db_host, '-p', str(db_port), '-U', db_user,
                 '-d', target_db, '-c',
                 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'],
                env=env, check=True, capture_output=True,
            )

        self.stdout.write(f'→ Spiele {dump_path.name} ein …')
        result = subprocess.run(
            ['pg_restore', '-h', db_host, '-p', str(db_port), '-U', db_user,
             '-d', target_db, '--no-owner', '--no-acl', str(dump_path)],
            env=env, capture_output=True,
        )
        # pg_restore meldet Warnungen mit returncode != 0, oft trotzdem erfolgreich.
        # Wir prüfen anhand der Tabellenanzahl, ob etwas Brauchbares drin ist.
        check = subprocess.run(
            ['psql', '-h', db_host, '-p', str(db_port), '-U', db_user,
             '-d', target_db, '-tAc',
             "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';"],
            env=env, check=True, capture_output=True,
        )
        table_count = int(check.stdout.decode().strip() or 0)

        AuditLogEntry.objects.create(
            user=None,
            action=AuditLogEntry.ACTION_RESTORE,
            app_label='services',
            model_name='backup',
            model_verbose_name='Backup',
            object_id='-',
            object_repr=f'Restore {dump_path.name} → {target_db}',
            changes={
                'target_db': target_db,
                'is_production': is_production,
                'tables_after_restore': table_count,
                'pg_restore_returncode': result.returncode,
            },
        )

        if table_count == 0:
            raise CommandError(
                f'Restore lieferte 0 Tabellen in {target_db} – Dump beschädigt?'
            )
        self.stdout.write(self.style.SUCCESS(
            f'✓ Restore abgeschlossen: {table_count} Tabellen in "{target_db}".'
        ))
        if result.returncode != 0:
            stderr = result.stderr.decode('utf-8', errors='replace')
            self.stdout.write(self.style.WARNING(
                f'pg_restore hat Warnungen ausgegeben (Returncode {result.returncode}):\n{stderr[:500]}'
            ))
