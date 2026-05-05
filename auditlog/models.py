# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Datenmodell für das Änderungsprotokoll (Audit-Log) aller relevanten Modelländerungen."""

from django.db import models


class AuditLogEntry(models.Model):
    """Protokolleintrag einer Erstell-, Änderungs- oder Löschaktion mit Änderungsdetails."""

    ACTION_CREATE = 'create'
    ACTION_UPDATE = 'update'
    ACTION_DELETE = 'delete'
    ACTION_SUBMIT = 'submit'
    ACTION_LOGIN = 'login'
    ACTION_LOGOUT = 'logout'
    ACTION_LOGIN_FAILED = 'login_failed'
    ACTION_BACKUP = 'backup'
    ACTION_BACKUP_FAILED = 'backup_failed'
    ACTION_RESTORE = 'restore'
    ACTION_UNLOCK = 'unlock'
    ACTION_CHOICES = [
        (ACTION_CREATE,        'Erstellt'),
        (ACTION_UPDATE,        'Geändert'),
        (ACTION_DELETE,        'Gelöscht'),
        (ACTION_SUBMIT,        'Eingereicht'),
        (ACTION_LOGIN,         'Anmeldung'),
        (ACTION_LOGOUT,        'Abmeldung'),
        (ACTION_LOGIN_FAILED,  'Anmeldung fehlgeschlagen'),
        (ACTION_BACKUP,        'Backup erstellt'),
        (ACTION_BACKUP_FAILED, 'Backup fehlgeschlagen'),
        (ACTION_RESTORE,       'Wiederherstellung'),
        (ACTION_UNLOCK,        'Konto entsperrt'),
    ]

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Zeitpunkt')
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_log_entries',
        verbose_name='Benutzer',
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name='Aktion')
    app_label = models.CharField(max_length=100)
    model_name = models.CharField(max_length=100, db_index=True)
    model_verbose_name = models.CharField(max_length=200, verbose_name='Objekt-Typ')
    object_id = models.CharField(max_length=200, db_index=True, verbose_name='Objekt-ID')
    object_repr = models.TextField(verbose_name='Objekt')
    changes = models.JSONField(default=dict, verbose_name='Änderungen')

    # Optional: Verknüpfung zur Nachwuchskraft für einfache Filterung
    student_id = models.CharField(
        max_length=200, null=True, blank=True, db_index=True,
        verbose_name='Nachwuchskraft-ID',
    )

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Änderungsprotokoll-Eintrag'
        verbose_name_plural = 'Änderungsprotokoll'

    def __str__(self):
        return f"[{self.timestamp:%d.%m.%Y %H:%M}] {self.get_action_display()} {self.model_verbose_name}: {self.object_repr}"

    @property
    def action_color(self):
        return {
            self.ACTION_CREATE:        'success',
            self.ACTION_UPDATE:        'primary',
            self.ACTION_DELETE:        'danger',
            self.ACTION_SUBMIT:        'info',
            self.ACTION_LOGIN:         'success',
            self.ACTION_LOGOUT:        'secondary',
            self.ACTION_LOGIN_FAILED:  'danger',
            self.ACTION_BACKUP:        'success',
            self.ACTION_BACKUP_FAILED: 'danger',
            self.ACTION_RESTORE:       'warning',
            self.ACTION_UNLOCK:        'success',
        }.get(self.action, 'secondary')

    @property
    def action_icon(self):
        return {
            self.ACTION_CREATE:        'bi-plus-circle',
            self.ACTION_UPDATE:        'bi-pencil',
            self.ACTION_DELETE:        'bi-trash',
            self.ACTION_SUBMIT:        'bi-send-check',
            self.ACTION_LOGIN:         'bi-box-arrow-in-right',
            self.ACTION_LOGOUT:        'bi-box-arrow-right',
            self.ACTION_LOGIN_FAILED:  'bi-shield-exclamation',
            self.ACTION_BACKUP:        'bi-hdd-stack',
            self.ACTION_BACKUP_FAILED: 'bi-hdd-stack-fill',
            self.ACTION_RESTORE:       'bi-arrow-counterclockwise',
            self.ACTION_UNLOCK:        'bi-unlock',
        }.get(self.action, 'bi-circle')
