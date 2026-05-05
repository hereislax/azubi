# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.apps import AppConfig


class AuditlogConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'auditlog'
    verbose_name = 'Änderungsprotokoll'

    def ready(self):
        from .signals import register_signals
        register_signals()
