# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.contrib import admin

from .models import TrainingType


@admin.register(TrainingType)
class TrainingTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'recurrence', 'validity_months', 'reminder_days_before',
                    'is_mandatory', 'applies_to_all_students', 'active')
    list_filter = ('recurrence', 'is_mandatory', 'applies_to_all_students', 'active')
    list_editable = ('active',)
    search_fields = ('name', 'description')
    filter_horizontal = ('applies_to_job_profiles',)
