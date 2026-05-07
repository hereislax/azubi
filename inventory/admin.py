# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.contrib import admin
from .models import ReceiptTemplate, InventoryCategory


@admin.register(ReceiptTemplate)
class ReceiptTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "uploaded_at")
    list_filter = ("is_active",)


@admin.register(InventoryCategory)
class InventoryCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "icon", "receipt_template")
    list_select_related = ("receipt_template",)
