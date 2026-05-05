# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Celery-Tasks für asynchrone Services (E-Mail-Versand, Paperless-Cache-Pflege, Backup)."""
import base64
import datetime as _dt
import logging
import os
import re
import subprocess
import tarfile
from pathlib import Path
from celery import shared_task

logger = logging.getLogger(__name__)


# ───────────────────────────────────────────────────────────────────────────
# Backup-Hilfsfunktionen
# ───────────────────────────────────────────────────────────────────────────

# Dateiname-Format: <prefix>-<YYYYMMDD-HHMMSS>.<ext>
_BACKUP_TS_RE = re.compile(r'-(\d{8}-\d{6})\.[^.]+$')


def _backup_dir() -> Path:
    """Gibt das konfigurierte Backup-Verzeichnis zurück und legt es bei Bedarf an."""
    from django.conf import settings
    path = Path(settings.BACKUP_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _now_stamp() -> str:
    return _dt.datetime.now().strftime('%Y%m%d-%H%M%S')


def _audit_log(action: str, summary: str, details: dict | None = None) -> None:
    """Schreibt einen System-Eintrag ins Audit-Log (kein User, kein Object)."""
    try:
        from auditlog.models import AuditLogEntry
        AuditLogEntry.objects.create(
            user=None,
            action=action,
            app_label='services',
            model_name='backup',
            model_verbose_name='Backup',
            object_id='-',
            object_repr=summary,
            changes=details or {},
        )
    except Exception:
        # Audit-Log-Fehler darf den Backup-Lauf nicht abbrechen
        logger.exception('Audit-Log-Eintrag für Backup fehlgeschlagen')


def _alert_admins(subject: str, body: str) -> None:
    """Sendet eine Fehler-Mail an die in BACKUP_ALERT_EMAILS konfigurierten Adressen."""
    recipients = [
        addr.strip()
        for addr in os.environ.get('BACKUP_ALERT_EMAILS', '').split(',')
        if addr.strip()
    ]
    if not recipients:
        return
    try:
        send_mail_task.delay(subject=subject, body_text=body, recipient_list=recipients)
    except Exception:
        logger.exception('Backup-Alert-Mail konnte nicht eingestellt werden')


@shared_task(name='services.refresh_paperless_unassigned')
def refresh_paperless_unassigned():
    """Aktualisiert den Eingangskorb-Cache, damit Views immer einen warmen Cache lesen."""
    from services.paperless import PaperlessService
    docs = PaperlessService.get_unassigned_documents(force_refresh=True)
    logger.info("Paperless-Eingangskorb-Cache aktualisiert: %d Dokumente", len(docs))
    return len(docs)


@shared_task(name='services.refresh_paperless_for_student')
def refresh_paperless_for_student(student_id):
    """Aktualisiert den Dokumenten-Cache eines Studierenden im Hintergrund."""
    from services.paperless import PaperlessService
    docs = PaperlessService.get_documents_for_student(student_id, force_refresh=True)
    return len(docs)


@shared_task(name='services.refresh_paperless_for_course')
def refresh_paperless_for_course(course_title: str):
    """Aktualisiert den Dokumenten-Cache eines Kurses im Hintergrund."""
    from services.paperless import PaperlessService
    docs = PaperlessService.get_documents_for_course(course_title, force_refresh=True)
    return len(docs)


@shared_task(
    name='services.send_mail',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def send_mail_task(
    self,
    subject: str,
    body_text: str,
    recipient_list: list,
    body_html: str | None = None,
    attachments_b64: list | None = None,
):
    """
    Versendet eine E-Mail via SMTP.

    Anhänge werden als base64-kodierte Strings übergeben, damit
    die JSON-Serialisierung von Celery funktioniert:
        attachments_b64: [[filename, b64_content, mimetype], ...]
    """
    from django.conf import settings
    from django.core.mail import EmailMultiAlternatives

    from_email    = settings.DEFAULT_FROM_EMAIL
    reply_to      = getattr(settings, 'DEFAULT_REPLY_TO_EMAIL', None)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=body_text,
        from_email=from_email,
        to=recipient_list,
        reply_to=[reply_to] if reply_to else None,
    )
    if body_html:
        msg.attach_alternative(body_html, 'text/html')
    for filename, b64_content, mimetype in (attachments_b64 or []):
        msg.attach(filename, base64.b64decode(b64_content), mimetype)

    try:
        msg.send()
    except Exception as exc:
        logger.exception('E-Mail-Versand fehlgeschlagen an %s', recipient_list)
        raise self.retry(exc=exc)


# ───────────────────────────────────────────────────────────────────────────
# Backup-Tasks (Stufe 1: lokale Backups)
# ───────────────────────────────────────────────────────────────────────────

@shared_task(name='services.backup_database')
def backup_database():
    """Erzeugt einen pg_dump der Azubi-Datenbank im lokalen Backup-Verzeichnis."""
    from auditlog.models import AuditLogEntry
    from django.core.management import call_command
    try:
        call_command('dbbackup', '--clean', '--noinput')
        # Ermittle den jüngsten Dump für den Audit-Eintrag
        dumps = sorted(_backup_dir().glob('azubi-*.psql.bin'))
        latest = dumps[-1] if dumps else None
        size_mb = latest.stat().st_size / 1024 / 1024 if latest else 0
        _audit_log(
            AuditLogEntry.ACTION_BACKUP,
            f'Datenbank-Backup erstellt ({size_mb:.1f} MB)',
            {'file': latest.name if latest else None, 'size_mb': round(size_mb, 1)},
        )
        return latest.name if latest else None
    except Exception as exc:
        logger.exception('Datenbank-Backup fehlgeschlagen')
        _audit_log(
            AuditLogEntry.ACTION_BACKUP_FAILED,
            f'Datenbank-Backup fehlgeschlagen: {exc}',
            {'error': str(exc)},
        )
        _alert_admins(
            subject='[Azubi] Datenbank-Backup fehlgeschlagen',
            body=f'Das tägliche Datenbank-Backup ist mit folgendem Fehler abgebrochen:\n\n{exc}',
        )
        raise


@shared_task(name='services.backup_media')
def backup_media():
    """Erzeugt einen Media-Tarball (django-dbbackup mediabackup)."""
    from auditlog.models import AuditLogEntry
    from django.core.management import call_command
    try:
        call_command('mediabackup', '--clean', '--noinput')
        dumps = sorted(_backup_dir().glob('azubi-media-*.tar'))
        latest = dumps[-1] if dumps else None
        size_mb = latest.stat().st_size / 1024 / 1024 if latest else 0
        _audit_log(
            AuditLogEntry.ACTION_BACKUP,
            f'Media-Backup erstellt ({size_mb:.1f} MB)',
            {'file': latest.name if latest else None, 'size_mb': round(size_mb, 1)},
        )
        return latest.name if latest else None
    except Exception as exc:
        logger.exception('Media-Backup fehlgeschlagen')
        _audit_log(
            AuditLogEntry.ACTION_BACKUP_FAILED,
            f'Media-Backup fehlgeschlagen: {exc}',
            {'error': str(exc)},
        )
        _alert_admins(
            subject='[Azubi] Media-Backup fehlgeschlagen',
            body=f'Das tägliche Media-Backup ist abgebrochen:\n\n{exc}',
        )
        raise


@shared_task(name='services.backup_paperless')
def backup_paperless():
    """
    Erzeugt ein Paperless-Backup bestehend aus:
      - pg_dump der Paperless-Datenbank (custom format, komprimiert)
      - tar.gz von /paperless/data und /paperless/media (read-only Mounts)

    Restore-Anleitung in docs/backup.md.
    """
    from auditlog.models import AuditLogEntry

    stamp = _now_stamp()
    backup_dir = _backup_dir()
    db_file = backup_dir / f'paperless-db-{stamp}.dump'
    files_file = backup_dir / f'paperless-files-{stamp}.tar.gz'

    db_host = os.environ.get('DB_HOST', 'db')
    db_port = os.environ.get('DB_PORT', '5432')
    db_user = os.environ.get('DB_USER', 'postgres')
    db_password = os.environ.get('DB_PASSWORD', '')

    data_dir = Path(os.environ.get('PAPERLESS_DATA_DIR', '/paperless/data'))
    media_dir = Path(os.environ.get('PAPERLESS_MEDIA_DIR', '/paperless/media'))

    try:
        env = os.environ.copy()
        env['PGPASSWORD'] = db_password
        subprocess.run(
            [
                'pg_dump',
                '-h', db_host,
                '-p', db_port,
                '-U', db_user,
                '-d', 'paperless',
                '-Fc',  # custom format
                '-f', str(db_file),
            ],
            env=env,
            check=True,
            capture_output=True,
        )

        with tarfile.open(files_file, 'w:gz') as tar:
            if data_dir.exists():
                tar.add(data_dir, arcname='data')
            if media_dir.exists():
                tar.add(media_dir, arcname='media')

        total_mb = (db_file.stat().st_size + files_file.stat().st_size) / 1024 / 1024
        _audit_log(
            AuditLogEntry.ACTION_BACKUP,
            f'Paperless-Backup erstellt ({total_mb:.1f} MB)',
            {
                'db_file': db_file.name,
                'files_file': files_file.name,
                'size_mb': round(total_mb, 1),
            },
        )
        return [db_file.name, files_file.name]
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode('utf-8', errors='replace') if exc.stderr else ''
        logger.exception('Paperless-pg_dump fehlgeschlagen: %s', stderr)
        _audit_log(
            AuditLogEntry.ACTION_BACKUP_FAILED,
            'Paperless-Backup fehlgeschlagen (pg_dump)',
            {'error': stderr or str(exc)},
        )
        _alert_admins(
            subject='[Azubi] Paperless-Backup fehlgeschlagen',
            body=f'pg_dump für Paperless abgebrochen:\n\n{stderr or exc}',
        )
        raise
    except Exception as exc:
        logger.exception('Paperless-Backup fehlgeschlagen')
        _audit_log(
            AuditLogEntry.ACTION_BACKUP_FAILED,
            f'Paperless-Backup fehlgeschlagen: {exc}',
            {'error': str(exc)},
        )
        _alert_admins(
            subject='[Azubi] Paperless-Backup fehlgeschlagen',
            body=f'Paperless-Backup abgebrochen:\n\n{exc}',
        )
        raise


@shared_task(name='services.cleanup_old_backups')
def cleanup_old_backups():
    """
    Wendet eine GFS-Rotation auf das Backup-Verzeichnis an.

    Behalten wird:
      - die letzten N täglichen Backups (aus DBBACKUP_CLEANUP_KEEP)
      - das jeweils älteste Backup pro Kalenderwoche (Mo) für die letzten K Wochen
      - das jeweils älteste Backup pro Kalendermonat für die letzten M Monate

    Alles andere wird gelöscht. Werte aus SiteConfiguration.
    """
    from auditlog.models import AuditLogEntry
    from django.conf import settings
    from services.models import SiteConfiguration

    cfg = SiteConfiguration.get()
    keep_daily = int(settings.DBBACKUP_CLEANUP_KEEP)
    keep_weekly = cfg.backup_keep_weekly
    keep_monthly = cfg.backup_keep_monthly

    backup_dir = _backup_dir()
    deleted = []

    # Pro Prefix gruppieren (azubi, azubi-media, paperless-db, paperless-files)
    prefixes = ['azubi', 'azubi-media', 'paperless-db', 'paperless-files']
    for prefix in prefixes:
        candidates = []
        for path in backup_dir.iterdir():
            if not path.is_file() or not path.name.startswith(prefix + '-'):
                continue
            m = _BACKUP_TS_RE.search(path.name)
            if not m:
                continue
            try:
                ts = _dt.datetime.strptime(m.group(1), '%Y%m%d-%H%M%S')
            except ValueError:
                continue
            candidates.append((ts, path))
        candidates.sort(key=lambda x: x[0], reverse=True)

        keep = set()
        # Tages-Slots
        for ts, path in candidates[:keep_daily]:
            keep.add(path)
        # Wochen-Slots: ältester Eintrag pro ISO-Woche
        weekly_seen = {}
        for ts, path in candidates:
            key = (ts.isocalendar().year, ts.isocalendar().week)
            weekly_seen.setdefault(key, path)
        for path in list(weekly_seen.values())[:keep_weekly]:
            keep.add(path)
        # Monats-Slots: ältester Eintrag pro Monat
        monthly_seen = {}
        for ts, path in candidates:
            key = (ts.year, ts.month)
            monthly_seen.setdefault(key, path)
        for path in list(monthly_seen.values())[:keep_monthly]:
            keep.add(path)

        for ts, path in candidates:
            if path not in keep:
                try:
                    path.unlink()
                    deleted.append(path.name)
                except OSError:
                    logger.exception('Konnte altes Backup nicht löschen: %s', path)

    _audit_log(
        AuditLogEntry.ACTION_BACKUP,
        f'Backup-Rotation: {len(deleted)} alte Dateien gelöscht',
        {'deleted_count': len(deleted), 'deleted': deleted[:50]},
    )
    return deleted


# ───────────────────────────────────────────────────────────────────────────
# Backup-Tasks (Stufe 2: Off-Site via restic)
# ───────────────────────────────────────────────────────────────────────────

def _restic_env() -> dict:
    """Baut die Umgebungsvariablen für restic-Aufrufe."""
    env = os.environ.copy()
    repo = env.get('RESTIC_REPOSITORY')
    if not repo:
        raise RuntimeError(
            'RESTIC_REPOSITORY ist nicht gesetzt – Off-Site-Backup übersprungen.'
        )
    # Eines von beiden muss gesetzt sein. Bevorzugt: PASSWORD_FILE (sicherer).
    if not env.get('RESTIC_PASSWORD') and not env.get('RESTIC_PASSWORD_FILE'):
        raise RuntimeError(
            'Weder RESTIC_PASSWORD noch RESTIC_PASSWORD_FILE gesetzt.'
        )
    return env


def _restic_init_if_needed(env: dict) -> bool:
    """Initialisiert das Repo, falls noch nicht vorhanden. Idempotent."""
    result = subprocess.run(
        ['restic', 'snapshots', '--last', '1'],
        env=env, capture_output=True,
    )
    if result.returncode == 0:
        return False
    # Häufigster Fehlerfall: Repo existiert noch nicht
    stderr = result.stderr.decode('utf-8', errors='replace')
    if 'unable to open config file' in stderr or 'Is there a repository at the' in stderr:
        subprocess.run(['restic', 'init'], env=env, check=True, capture_output=True)
        return True
    raise subprocess.CalledProcessError(result.returncode, result.args, output=result.stdout, stderr=result.stderr)


@shared_task(name='services.backup_offsite')
def backup_offsite():
    """
    Spiegelt das lokale Backup-Verzeichnis via restic auf das konfigurierte
    Off-Site-Repository (NAS). Verschlüsselt und dedupliziert.

    Konfiguration via .env:
      RESTIC_REPOSITORY=sftp:user@nas.local:/volume1/backups/azubi
      RESTIC_PASSWORD_FILE=/secrets/restic.key

    Bei SMB-NAS: NAS auf dem Host mounten (z. B. /mnt/nas), als Bind-Mount in
    den Container hängen (/mnt/nas/azubi → /restic-target) und
      RESTIC_REPOSITORY=/restic-target
    setzen.
    """
    from auditlog.models import AuditLogEntry
    from services.models import SiteConfiguration

    cfg = SiteConfiguration.get()
    backup_dir = _backup_dir()

    try:
        env = _restic_env()
        initialized = _restic_init_if_needed(env)

        # Backup
        proc = subprocess.run(
            ['restic', 'backup', str(backup_dir), '--tag', 'azubi'],
            env=env, capture_output=True, check=True,
        )
        backup_out = proc.stdout.decode('utf-8', errors='replace')

        # GFS-Forget mit Prune – Werte aus SiteConfiguration
        subprocess.run(
            [
                'restic', 'forget',
                '--keep-daily', str(int(os.environ.get('BACKUP_KEEP_DAILY', '7'))),
                '--keep-weekly', str(cfg.backup_keep_weekly),
                '--keep-monthly', str(cfg.backup_keep_monthly),
                '--prune',
                '--tag', 'azubi',
            ],
            env=env, capture_output=True, check=True,
        )

        # Letzte Zeile von restic backup enthält i. d. R. die Zusammenfassung
        summary_line = next(
            (line for line in reversed(backup_out.splitlines())
             if 'processed' in line or 'Added' in line),
            'Off-Site-Backup abgeschlossen',
        )
        _audit_log(
            AuditLogEntry.ACTION_BACKUP,
            f'Off-Site-Sync (restic) erfolgreich: {summary_line.strip()}',
            {'initialized': initialized, 'repository_redacted': '***'},
        )
        return summary_line.strip()
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode('utf-8', errors='replace') if exc.stderr else str(exc)
        logger.exception('restic-Off-Site-Backup fehlgeschlagen: %s', stderr)
        _audit_log(
            AuditLogEntry.ACTION_BACKUP_FAILED,
            'Off-Site-Sync (restic) fehlgeschlagen',
            {'error': stderr[:2000]},
        )
        _alert_admins(
            subject='[Azubi] Off-Site-Backup (restic) fehlgeschlagen',
            body=f'restic ist mit folgendem Fehler abgebrochen:\n\n{stderr}',
        )
        raise
    except Exception as exc:
        logger.exception('restic-Off-Site-Backup fehlgeschlagen')
        _audit_log(
            AuditLogEntry.ACTION_BACKUP_FAILED,
            f'Off-Site-Sync fehlgeschlagen: {exc}',
            {'error': str(exc)},
        )
        _alert_admins(
            subject='[Azubi] Off-Site-Backup fehlgeschlagen',
            body=f'Fehler beim Off-Site-Sync:\n\n{exc}',
        )
        raise


# ───────────────────────────────────────────────────────────────────────────
# Backup-Tasks (Stufe 3: Quartals-Restore-Test)
# ───────────────────────────────────────────────────────────────────────────

# Tabellen, die nach einem Restore mindestens vorhanden sein müssen.
# Treffer-Schwelle: alle aufgelisteten müssen nach Restore existieren.
_REQUIRED_TABLES = (
    'auth_user',
    'student_student',
    'course_course',
    'auditlog_auditlogentry',
)


@shared_task(name='services.test_restore')
def test_restore():
    """
    Quartalsweiser Restore-Test: Spielt den jüngsten Azubi-DB-Dump in eine
    Test-Datenbank ein und prüft, dass Pflicht-Tabellen vorhanden sind.

    Bei Fehler: AuditLog-Eintrag + Mail an Admins. Test-DB wird am Ende immer
    gelöscht (auch bei Fehler), damit der Postgres-Cluster sauber bleibt.
    """
    from auditlog.models import AuditLogEntry
    from django.conf import settings

    backup_dir = _backup_dir()
    dumps = sorted(backup_dir.glob('azubi-*.psql.bin'))
    if not dumps:
        msg = 'Kein DB-Dump für Restore-Test gefunden – Backups laufen nicht?'
        _audit_log(AuditLogEntry.ACTION_BACKUP_FAILED, msg, {})
        _alert_admins(subject='[Azubi] Restore-Test übersprungen', body=msg)
        return msg

    latest = dumps[-1]
    test_db = f'azubi_restore_test_{_now_stamp()}'
    db_host = settings.DATABASES['default']['HOST']
    db_port = str(settings.DATABASES['default']['PORT'])
    db_user = settings.DATABASES['default']['USER']
    env = os.environ.copy()
    env['PGPASSWORD'] = settings.DATABASES['default']['PASSWORD']

    def psql_admin(sql):
        return subprocess.run(
            ['psql', '-h', db_host, '-p', db_port, '-U', db_user,
             '-d', 'postgres', '-c', sql],
            env=env, capture_output=True,
        )

    try:
        # 1. Test-DB anlegen
        result = psql_admin(f'CREATE DATABASE {test_db};')
        if result.returncode != 0:
            raise RuntimeError(
                f'CREATE DATABASE fehlgeschlagen: {result.stderr.decode(errors="replace")}'
            )

        # 2. Restore
        subprocess.run(
            ['pg_restore', '-h', db_host, '-p', db_port, '-U', db_user,
             '-d', test_db, '--no-owner', '--no-acl', str(latest)],
            env=env, capture_output=True,
            # Returncode != 0 ist bei Warnungen normal – wir validieren über Tabellen
        )

        # 3. Tabellen-Validierung
        check = subprocess.run(
            ['psql', '-h', db_host, '-p', db_port, '-U', db_user,
             '-d', test_db, '-tAc',
             "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"],
            env=env, check=True, capture_output=True,
        )
        present = {line.strip() for line in check.stdout.decode().splitlines() if line.strip()}
        missing = [t for t in _REQUIRED_TABLES if t not in present]

        if missing:
            raise RuntimeError(
                f'Restore unvollständig – fehlende Pflichttabellen: {", ".join(missing)}. '
                f'Tabellen gesamt: {len(present)}'
            )

        _audit_log(
            AuditLogEntry.ACTION_RESTORE,
            f'Restore-Test erfolgreich ({latest.name}, {len(present)} Tabellen)',
            {
                'dump_file': latest.name,
                'tables_total': len(present),
                'required_present': True,
            },
        )
        return {'ok': True, 'dump': latest.name, 'tables': len(present)}
    except Exception as exc:
        logger.exception('Restore-Test fehlgeschlagen')
        _audit_log(
            AuditLogEntry.ACTION_BACKUP_FAILED,
            f'Restore-Test fehlgeschlagen: {exc}',
            {'dump_file': latest.name, 'error': str(exc)[:1000]},
        )
        _alert_admins(
            subject='[Azubi] Restore-Test fehlgeschlagen',
            body=(
                f'Der quartalsweise Restore-Test ist fehlgeschlagen.\n\n'
                f'Dump: {latest.name}\nFehler: {exc}\n\n'
                f'Bitte Backup-Integrität prüfen!'
            ),
        )
        raise
    finally:
        # Test-DB immer aufräumen
        psql_admin(f'DROP DATABASE IF EXISTS {test_db};')
