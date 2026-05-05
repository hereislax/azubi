# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.contrib import admin
from .models import ReceiptTemplate, InventoryCategory, InventoryItem, InventoryIssuance


@admin.register(ReceiptTemplate)
class ReceiptTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "uploaded_at")
    list_filter = ("is_active",)


@admin.register(InventoryCategory)
class InventoryCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "icon", "receipt_template")
    list_select_related = ("receipt_template",)


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "serial_number", "status", "location")
    list_filter = ("category", "status")
    search_fields = ("name", "serial_number")
    list_select_related = ("category",)


@admin.register(InventoryIssuance)
class InventoryIssuanceAdmin(admin.ModelAdmin):
    list_display = ("item", "student", "issued_by", "issued_at", "returned_at")
    list_filter = ("item__category",)
    search_fields = ("item__name", "student__first_name", "student__last_name")
    list_select_related = ("item", "student", "issued_by")
    readonly_fields = ("created_at",)
