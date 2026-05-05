# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Django-Admin-Konfiguration für das Maßnahmen-Modul."""

from django.contrib import admin
from .models import InterventionCategory, Intervention


@admin.register(InterventionCategory)
class InterventionCategoryAdmin(admin.ModelAdmin):
    list_display  = ['name', 'escalation_level', 'color', 'requires_followup', 'is_active']
    list_filter   = ['escalation_level', 'is_active']
    search_fields = ['name']
    ordering      = ['escalation_level', 'name']


@admin.register(Intervention)
class InterventionAdmin(admin.ModelAdmin):
    list_display      = ['student', 'category', 'date', 'trigger_type', 'status', 'created_by']
    list_filter       = ['status', 'trigger_type', 'category']
    search_fields     = ['student__first_name', 'student__last_name', 'description']
    raw_id_fields     = ['student', 'trigger_sick_leave', 'trigger_assessment',
                         'closed_by', 'created_by', 'follow_up']
    filter_horizontal = ['participants']
    date_hierarchy    = 'date'
    ordering          = ['-date']
