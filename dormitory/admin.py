# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.contrib import admin
from .models import Dormitory, Room, RoomAssignment, RoomBlock, ReservationTemplate, DormitoryManagementProfile


class RoomInline(admin.TabularInline):
    model = Room
    extra = 1


class RoomAssignmentInline(admin.TabularInline):
    model = RoomAssignment
    extra = 0
    readonly_fields = ("created_at", "updated_at")


class RoomBlockInline(admin.TabularInline):
    model = RoomBlock
    extra = 0


@admin.register(Dormitory)
class DormitoryAdmin(admin.ModelAdmin):
    list_display = ("name", "address")
    inlines = [RoomInline]


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("dormitory", "number", "capacity")
    list_filter = ("dormitory",)
    inlines = [RoomAssignmentInline, RoomBlockInline]


@admin.register(ReservationTemplate)
class ReservationTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "dormitory", "is_active", "uploaded_at")
    list_editable = ("is_active",)
    list_filter = ("dormitory", "is_active")


@admin.register(DormitoryManagementProfile)
class DormitoryManagementProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "dormitory")
    list_filter = ("dormitory",)
    raw_id_fields = ("user",)
