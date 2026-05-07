# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Django-Admin-Konfiguration für das Maßnahmen-Modul."""

from django.contrib import admin
from .models import InterventionCategory


@admin.register(InterventionCategory)
class InterventionCategoryAdmin(admin.ModelAdmin):
    list_display  = ['name', 'escalation_level', 'color', 'requires_followup', 'is_active']
    list_filter   = ['escalation_level', 'is_active']
    search_fields = ['name']
    ordering      = ['escalation_level', 'name']
