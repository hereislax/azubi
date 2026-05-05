# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.contrib import admin

from .models import Workspace, WorkspaceType, WorkspaceBooking, WorkspaceClosure


class WorkspaceClosureInline(admin.TabularInline):
    model = WorkspaceClosure
    extra = 0


@admin.register(WorkspaceType)
class WorkspaceTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon', 'is_active')
    list_editable = ('is_active',)
    search_fields = ('name',)


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'workspace_type', 'location', 'capacity', 'is_active')
    list_filter = ('workspace_type', 'location', 'is_active')
    search_fields = ('name', 'description', 'equipment')
    inlines = [WorkspaceClosureInline]


@admin.register(WorkspaceClosure)
class WorkspaceClosureAdmin(admin.ModelAdmin):
    list_display = ('workspace', 'start_date', 'end_date', 'reason')
    list_filter = ('workspace__location', 'workspace')
    date_hierarchy = 'start_date'


@admin.register(WorkspaceBooking)
class WorkspaceBookingAdmin(admin.ModelAdmin):
    list_display = ('workspace', 'student', 'date', 'status', 'booked_by', 'created_at')
    list_filter = ('status', 'workspace__location', 'workspace__workspace_type', 'workspace')
    search_fields = (
        'student__first_name', 'student__last_name',
        'workspace__name', 'purpose',
    )
    date_hierarchy = 'date'
    readonly_fields = ('created_at', 'cancelled_at', 'notification_sequence')
    raw_id_fields = ('workspace', 'student', 'booked_by', 'cancelled_by')