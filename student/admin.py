"""
Django-Admin-Konfiguration für die Student-App.

Registriert nur Stammdaten und Vorlagen. Operative Tabellen (InternalNote,
TrainingResponsibleAccess) werden über die App-Views gepflegt.
"""
# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django import forms
from django.contrib import admin

from services.models import Gender
from student.models import (
    Employment, Status, Student, StudentFieldDefinition, StudentFieldValue,
    StudentDocumentTemplate,
    ChecklistTemplate, ChecklistTemplateItem,
)

WIDGETS = {
    'text':    forms.TextInput(),
    'number':  forms.NumberInput(),
    'date':    forms.DateInput(attrs={'type': 'date'}),
    'boolean': forms.CheckboxInput(),
}


class StudentFieldValueForm(forms.ModelForm):
    class Meta:
        model = StudentFieldValue
        fields = ('field', 'value')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field_def = None

        if self.instance and self.instance.pk:
            field_def = self.instance.field
        elif self.data.get(self.add_prefix('field')):
            try:
                field_def = StudentFieldDefinition.objects.get(
                    pk=self.data[self.add_prefix('field')]
                )
            except StudentFieldDefinition.DoesNotExist:
                pass

        if field_def and field_def.field_type in WIDGETS:
            self.fields['value'].widget = WIDGETS[field_def.field_type]


class StudentFieldValueInline(admin.TabularInline):
    model = StudentFieldValue
    form = StudentFieldValueForm
    extra = 0
    fields = ("field", "value")


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    inlines = [StudentFieldValueInline]


@admin.register(StudentFieldDefinition)
class StudentFieldDefinitionAdmin(admin.ModelAdmin):
    list_display = ("name", "field_type")


admin.site.register(Gender)
admin.site.register(Employment)
admin.site.register(Status)


@admin.register(StudentDocumentTemplate)
class StudentDocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'available_in_portal', 'uploaded_at')
    list_editable = ('is_active', 'available_in_portal')
    fields = ('name', 'description', 'template_file', 'is_active', 'available_in_portal')


class ChecklistTemplateItemInline(admin.TabularInline):
    model = ChecklistTemplateItem
    extra = 1
    fields = ('order', 'text')
    ordering = ('order',)


@admin.register(ChecklistTemplate)
class ChecklistTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    list_editable = ('is_active',)
    inlines = [ChecklistTemplateItemInline]
    filter_horizontal = ('job_profiles',)
