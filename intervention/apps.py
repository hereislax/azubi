# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.apps import AppConfig


class InterventionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'intervention'
    verbose_name = 'Maßnahmen'
