# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.contrib import admin
from .models import TrainingRecordExportTemplate


@admin.register(TrainingRecordExportTemplate)
class TrainingRecordExportTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'uploaded_at']
    list_editable = ['is_active']
    fields = ['name', 'template_file', 'is_active']

    def get_readonly_fields(self, request, obj=None):
        return ['uploaded_at'] if obj else []
