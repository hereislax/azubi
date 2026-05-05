# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.contrib import admin
from .models import TrainingRecord, TrainingDay, TrainingRecordExportTemplate


class TrainingDayInline(admin.TabularInline):
    model = TrainingDay
    extra = 0
    fields = ['date', 'day_type', 'content']
    readonly_fields = ['date']


@admin.register(TrainingRecord)
class TrainingRecordAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'student', 'week_start', 'status', 'submitted_at', 'reviewed_by', 'reviewed_at']
    list_filter = ['status']
    search_fields = ['student__first_name', 'student__last_name']
    readonly_fields = ['submitted_at', 'reviewed_by', 'reviewed_at', 'created_at', 'updated_at']
    inlines = [TrainingDayInline]


@admin.register(TrainingRecordExportTemplate)
class TrainingRecordExportTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'uploaded_at']
    list_editable = ['is_active']
    fields = ['name', 'template_file', 'is_active']

    def get_readonly_fields(self, request, obj=None):
        return ['uploaded_at'] if obj else []
