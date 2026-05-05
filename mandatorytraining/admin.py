# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.contrib import admin

from .models import TrainingType, TrainingCompletion


@admin.register(TrainingType)
class TrainingTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'recurrence', 'validity_months', 'reminder_days_before',
                    'is_mandatory', 'applies_to_all_students', 'active')
    list_filter = ('recurrence', 'is_mandatory', 'applies_to_all_students', 'active')
    list_editable = ('active',)
    search_fields = ('name', 'description')
    filter_horizontal = ('applies_to_job_profiles',)


@admin.register(TrainingCompletion)
class TrainingCompletionAdmin(admin.ModelAdmin):
    list_display = ('student', 'training_type', 'completed_on', 'expires_on',
                    'registered_by', 'registered_at')
    list_filter = ('training_type', 'expires_on')
    search_fields = ('student__first_name', 'student__last_name', 'training_type__name')
    date_hierarchy = 'completed_on'
    raw_id_fields = ('student', 'registered_by')
    readonly_fields = ('registered_at', 'reminder_30_sent', 'reminder_7_sent')
