# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Django-Admin-Konfiguration für Praxistutoren und Ausbildungskoordinationen."""
from django.contrib import admin
from .models import Instructor, TrainingCoordination, InstructorOrderTemplate


@admin.register(Instructor)
class InstructorAdmin(admin.ModelAdmin):
    list_display = ('last_name', 'first_name', 'salutation', 'email', 'unit')
    list_filter = ('salutation', 'unit')
    search_fields = ('first_name', 'last_name', 'email')
    filter_horizontal = ('job_profiles',)


@admin.register(TrainingCoordination)
class TrainingCoordinationAdmin(admin.ModelAdmin):
    list_display = ('name', 'functional_email')
    search_fields = ('name', 'functional_email')
    filter_horizontal = ('units',)


@admin.register(InstructorOrderTemplate)
class InstructorOrderTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'uploaded_at')
    list_editable = ('is_active',)
    list_filter = ('is_active',)
