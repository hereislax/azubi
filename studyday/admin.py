# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.contrib import admin
from .models import StudyDayPolicy


@admin.register(StudyDayPolicy)
class StudyDayPolicyAdmin(admin.ModelAdmin):
    list_display = ['job_profile', 'allocation_type', 'amount', 'scope']
    list_filter = ['scope', 'allocation_type']
