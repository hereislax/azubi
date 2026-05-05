# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django.contrib import admin
from django.utils.html import format_html
from .models import Location, OrganisationalUnit, Competence


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("name", "address")
    search_fields = ("name", "address__street", "address__city")
    autocomplete_fields = ("address",)


@admin.register(OrganisationalUnit)
class OrganisationalUnitAdmin(admin.ModelAdmin):

    list_display = ("indented_name", "label", "unit_type_display", "parent", "is_active")
    list_filter = ("unit_type", "is_active")
    search_fields = ("name", "label")
    list_editable = ("is_active",)
    readonly_fields = ("created_at", "updated_at", "full_path")

    fieldsets = (
        (None, {
            "fields": ("name", "label", "unit_type", "parent", "max_capacity", "is_active"),
        }),
        ("Standorte & Kompetenzen", {
            "fields": ("locations", "competences"),
        }),
        ("Details", {
            "fields": ("notes", "full_path"),
            "classes": ("collapse",),
        }),
        ("Metadata", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    # ── Custom display columns ────────────────────────────────────────────

    @admin.display(description="Name")
    def indented_name(self, obj: OrganisationalUnit) -> str:
        icon = {
            "authority":      "🏛",
            "department":     "🏢",
            "division_group": "📂",
            "division":       "📄",
        }.get(obj.unit_type, "•")
        return format_html("{} {}", icon, obj.name)

    @admin.display(description="Type")
    def unit_type_display(self, obj: OrganisationalUnit) -> str:
        return obj.get_unit_type_display()

    filter_horizontal = ("competences",)

    @admin.display(description="Full Path")
    def full_path(self, obj: OrganisationalUnit) -> str:
        return obj.get_full_path()


@admin.register(Competence)
class CompetenceAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
