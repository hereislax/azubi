# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Synchronisiert SiteConfiguration mit django-celery-beat-PeriodicTasks.

Die Konfiguration der Hintergrundaufgaben (Uhrzeiten, Intervalle) wird im
Portal über SiteConfiguration gepflegt. Damit der Celery-Beat-Worker diese
Werte ohne Neustart übernimmt, betreiben wir einen DatabaseScheduler
(django_celery_beat). Diese Funktion bildet SiteConfiguration auf die
PeriodicTask-Tabelle ab.
"""
from django_celery_beat.models import CrontabSchedule, IntervalSchedule, PeriodicTask


def _crontab(hour, minute, day_of_month='*', month_of_year='*', day_of_week='*'):
    schedule, _ = CrontabSchedule.objects.get_or_create(
        minute=str(minute),
        hour=str(hour),
        day_of_month=str(day_of_month),
        month_of_year=str(month_of_year),
        day_of_week=str(day_of_week),
    )
    return schedule


def _interval(seconds):
    schedule, _ = IntervalSchedule.objects.get_or_create(
        every=int(seconds),
        period=IntervalSchedule.SECONDS,
    )
    return schedule


def _upsert_crontab_task(name, task, hour, minute,
                         day_of_month='*', month_of_year='*', day_of_week='*'):
    PeriodicTask.objects.update_or_create(
        name=name,
        defaults={
            'task': task,
            'crontab': _crontab(hour, minute, day_of_month, month_of_year, day_of_week),
            'interval': None,
            'enabled': True,
        },
    )


def _upsert_interval_task(name, task, seconds):
    PeriodicTask.objects.update_or_create(
        name=name,
        defaults={
            'task': task,
            'interval': _interval(seconds),
            'crontab': None,
            'enabled': True,
        },
    )


def sync_periodic_tasks(config):
    """Bildet die sieben Hintergrundaufgaben auf PeriodicTask ab."""
    _upsert_crontab_task(
        'erinnerungen-praxiseinsatz',
        'course.send_internship_reminders',
        config.reminder_hour, config.reminder_minute,
    )
    _upsert_crontab_task(
        'erinnerungen-ausbildungsnachweis',
        'proofoftraining.send_proof_of_training_reminders',
        config.reminder_hour, config.reminder_minute,
    )
    _upsert_crontab_task(
        'anonymisierung-nachwuchskraefte',
        'student.anonymize_inactive_students',
        config.anonymization_hour, config.anonymization_minute,
    )
    _upsert_crontab_task(
        'urlaubsantraege-an-urlaubsstelle',
        'absence.send_vacation_batch',
        config.vacation_batch_hour, config.vacation_batch_minute,
    )
    _upsert_crontab_task(
        'krankmeldungen-an-urlaubsstelle',
        'absence.send_sick_leave_report',
        config.sick_leave_report_hour, config.sick_leave_report_minute,
    )
    _upsert_crontab_task(
        'eskalation-stationsbeurteilungen',
        'assessment.escalate_pending_assessments',
        config.assessment_escalation_hour, config.assessment_escalation_minute,
    )
    _upsert_interval_task(
        'paperless-eingangskorb-cache',
        'services.refresh_paperless_unassigned',
        config.paperless_cache_interval_seconds,
    )

    # Tägliche Backups (Stufe 1)
    # Versatz: DB → Media (+15min) → Paperless (+30min) → Cleanup (+45min),
    # damit pg_dump nicht mit großem Tar um IO/RAM konkurriert.
    _upsert_crontab_task(
        'backup-database',
        'services.backup_database',
        config.backup_hour, config.backup_minute,
    )
    _upsert_crontab_task(
        'backup-media',
        'services.backup_media',
        config.backup_hour, (config.backup_minute + 15) % 60,
    )
    _upsert_crontab_task(
        'backup-paperless',
        'services.backup_paperless',
        config.backup_hour, (config.backup_minute + 30) % 60,
    )
    _upsert_crontab_task(
        'backup-cleanup',
        'services.cleanup_old_backups',
        config.backup_hour, (config.backup_minute + 45) % 60,
    )

    # Off-Site-Sync via restic (Stufe 2)
    _upsert_crontab_task(
        'backup-offsite',
        'services.backup_offsite',
        config.backup_offsite_hour, config.backup_offsite_minute,
    )

    # Quartalsweiser Restore-Test (Stufe 3): jeweils am 1. von Jan/Apr/Jul/Okt
    _upsert_crontab_task(
        'backup-restore-test',
        'services.test_restore',
        config.backup_offsite_hour, (config.backup_offsite_minute + 30) % 60,
        day_of_month='1',
        month_of_year='1,4,7,10',
    )