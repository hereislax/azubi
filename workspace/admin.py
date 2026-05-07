# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.contrib import admin

from .models import Workspace, WorkspaceType, WorkspaceClosure


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
