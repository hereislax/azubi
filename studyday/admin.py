# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.contrib import admin
from .models import StudyDayPolicy, StudyDayRequest


@admin.register(StudyDayPolicy)
class StudyDayPolicyAdmin(admin.ModelAdmin):
    list_display = ['job_profile', 'allocation_type', 'amount', 'scope']
    list_filter = ['scope', 'allocation_type']


@admin.register(StudyDayRequest)
class StudyDayRequestAdmin(admin.ModelAdmin):
    list_display = ['student', 'date', 'status', 'created_at', 'approved_by']
    list_filter = ['status']
    search_fields = ['student__first_name', 'student__last_name']
    raw_id_fields = ['student']
